#!/usr/bin/env python3
"""Multi-finger touchpad gestures for XFCE/X11 (3 and 4 fingers).

3 fingers: down = show/hide desktop
           up = open and hold the Alt+Tab switcher; lift to commit,
                place the fingers again within the grace window to keep choosing
           left/right = switch app right away; keep dragging to go further
4 fingers: down = show/hide desktop | up = hold the Alt+Tab switcher
           right = next workspace, left = previous workspace

Five fingers are handled by TouchTamer (moving the window). This daemon also
watches the raw touchpad finger count, so the 3/4-finger gestures that libinput
reports while a 5th finger is landing or lifting are ignored.
"""

import os
import re
import signal
import subprocess
import sys
import threading
import time

# --- tuning ---------------------------------------------------------------
FINGERS = (3, 4)
START_PX = 25          # movement needed to pick a direction
V_BIAS = 1.25          # vertical only wins if |dy| > V_BIAS * |dx|
SETTLE = 0.06          # a swipe must exist this long before it may act (s)
FIVE_HOLD = 0.5        # ignore 3/4-finger events this long after 5 fingers (s)
H_STEP_PX = 70         # horizontal movement per extra app step in the switcher
COOLDOWN = 0.25        # ignore a new gesture right after a one-shot action
COMMIT_DELAY = 0.6     # switcher opened by swipe-up stays open this long
H_COMMIT_DELAY = 0.12  # switcher opened by a sideways swipe commits this fast
SWIPE_LEFT_IS_NEXT = True   # sideways app switch: swipe left = next app

# Pinch to zoom (sent as Ctrl+scroll, like the Windows precision touchpad).
PINCH_ZOOM = True
PINCH_STEP = 0.10      # scale change per zoom step (10% ~ one browser zoom step)

# Two-finger flick sideways = browser Back/Forward (only in browser windows).
NAV_SWIPE = True
NAV_DIST = 0.22        # horizontal travel needed, as a fraction of pad width
NAV_TIME = 0.60        # ...and it must happen within this many seconds
NAV_STRAIGHT = 0.55    # |dy| must stay below this fraction of |dx|
NAV_FINGER_RIGHT_IS_BACK = True   # fingers move left->right = Back
# While the page is pinch-zoomed, sideways two-finger movement is panning, so
# Back/Forward is disabled until you pinch back to normal size (or navigate).
ZOOM_LOCK = True
ZOOM_MIN = 1.08        # net zoom above this counts as "zoomed in"
ZOOM_MAX = 10.0
BROWSER_CLASSES = (
    "firefox", "navigator", "librewolf", "zen", "waterfox",
    "google-chrome", "chromium", "brave", "microsoft-edge", "vivaldi", "opera",
)
# --------------------------------------------------------------------------

DRY = bool(os.environ.get("GESTURE_DRY"))

LINE_RE = re.compile(
    r"GESTURE_SWIPE_(BEGIN|UPDATE|END)\s+(?:\d+\s+)?\+?[\d.]+s\s+(\d+)"
    r"(?:\s+(-?[\d.]+)\s*/\s*(-?[\d.]+))?"
)

alt_held = False
commit_timer = None
last_action = 0.0
switcher_sign = 1      # +1: moving right = next entry, -1: moving left = next
state_lock = threading.Lock()


def log(msg):
    print(msg, file=sys.stderr, flush=True)


# --- keyboard output through XTest (no process spawn, so no added delay) ----
class Keys:
    def __init__(self):
        self.lock = threading.Lock()
        self.dpy = None
        self.xk = None

    def _open(self):
        from Xlib import X, XK, display
        from Xlib.ext import xtest

        self.X, self.XK, self.xtest = X, XK, xtest
        self.dpy = display.Display()

    def send(self, *events):
        """events: (keysym name, is_down) pairs, sent in order."""
        if DRY:
            log("KEYS " + " ".join(f"{n}{'v' if d else '^'}" for n, d in events))
            return
        with self.lock:
            for attempt in (1, 2):
                try:
                    if self.dpy is None:
                        self._open()
                    for name, down in events:
                        keysym = self.XK.string_to_keysym(name)
                        keycode = self.dpy.keysym_to_keycode(keysym)
                        self.xtest.fake_input(
                            self.dpy,
                            self.X.KeyPress if down else self.X.KeyRelease,
                            keycode,
                        )
                    self.dpy.sync()
                    return
                except Exception as exc:  # noqa: BLE001
                    log(f"xtest failed ({attempt}): {exc}")
                    self.dpy = None


    def wheel(self, up, ctrl=True):
        """One scroll-wheel click (button 4 = up, 5 = down), optionally with Ctrl."""
        if DRY:
            log(f"WHEEL {'up' if up else 'down'} ctrl={ctrl}")
            return
        with self.lock:
            for attempt in (1, 2):
                try:
                    if self.dpy is None:
                        self._open()
                    kc = self.dpy.keysym_to_keycode(self.XK.string_to_keysym("Control_L"))
                    btn = 4 if up else 5
                    if ctrl:
                        self.xtest.fake_input(self.dpy, self.X.KeyPress, kc)
                    self.xtest.fake_input(self.dpy, self.X.ButtonPress, btn)
                    self.xtest.fake_input(self.dpy, self.X.ButtonRelease, btn)
                    if ctrl:
                        self.xtest.fake_input(self.dpy, self.X.KeyRelease, kc)
                    self.dpy.sync()
                    return
                except Exception as exc:  # noqa: BLE001
                    log(f"xtest wheel failed ({attempt}): {exc}")
                    self.dpy = None

    def click(self, button):
        if DRY:
            log(f"CLICK button {button}")
            return
        with self.lock:
            for attempt in (1, 2):
                try:
                    if self.dpy is None:
                        self._open()
                    self.xtest.fake_input(self.dpy, self.X.ButtonPress, button)
                    self.xtest.fake_input(self.dpy, self.X.ButtonRelease, button)
                    self.dpy.sync()
                    return
                except Exception as exc:  # noqa: BLE001
                    log(f"xtest click failed ({attempt}): {exc}")
                    self.dpy = None

    def modifiers_down(self):
        """True if the user physically holds Ctrl/Shift/Alt."""
        if DRY:
            return False
        with self.lock:
            try:
                if self.dpy is None:
                    self._open()
                mask = self.dpy.screen().root.query_pointer().mask
                return bool(mask & (self.X.ControlMask | self.X.ShiftMask
                                    | self.X.Mod1Mask))
            except Exception:  # noqa: BLE001
                self.dpy = None
                return False

    def active_title(self):
        """Title of the focused window (changes when the page navigates)."""
        if DRY:
            return "dry-title"
        with self.lock:
            try:
                if self.dpy is None:
                    self._open()
                root = self.dpy.screen().root
                prop = root.get_full_property(
                    self.dpy.intern_atom("_NET_ACTIVE_WINDOW"), self.X.AnyPropertyType)
                if prop is None or not len(prop.value):
                    return None
                win = self.dpy.create_resource_object("window", int(prop.value[0]))
                name = win.get_full_property(
                    self.dpy.intern_atom("_NET_WM_NAME"), self.X.AnyPropertyType)
                return bytes(name.value) if name is not None else None
            except Exception:  # noqa: BLE001
                self.dpy = None
                return None

    def active_class(self):
        """Lower-case WM_CLASS strings of the focused window."""
        if DRY:
            return ("firefox",)
        with self.lock:
            try:
                if self.dpy is None:
                    self._open()
                root = self.dpy.screen().root
                prop = root.get_full_property(
                    self.dpy.intern_atom("_NET_ACTIVE_WINDOW"), self.X.AnyPropertyType)
                if prop is None or not len(prop.value):
                    return ()
                win = self.dpy.create_resource_object("window", int(prop.value[0]))
                cls = win.get_wm_class()
                return tuple(c.lower() for c in cls) if cls else ()
            except Exception:  # noqa: BLE001
                self.dpy = None
                return ()


keys = Keys()


zoom = {"net": 1.0, "title": None}


def zoom_commit(scale):
    """Remember the net visual zoom after a pinch in a browser (1.0 .. ZOOM_MAX)."""
    zoom["net"] = min(ZOOM_MAX, max(1.0, zoom["net"] * scale))
    zoom["title"] = keys.active_title()
    log("pinch zoom net=%.2f" % zoom["net"])


def is_zoomed():
    if zoom["net"] < ZOOM_MIN:
        return False
    if keys.active_title() != zoom["title"]:   # navigated / other window
        zoom["net"], zoom["title"] = 1.0, None
        return False
    return True


def in_browser():
    return any(c in BROWSER_CLASSES for c in keys.active_class())


def browser_nav(back):
    # Mouse side buttons (8 = Back, 9 = Forward) are understood by every
    # browser and do not clash with TouchTamer's global Alt+Left/Right grabs.
    keys.click(8 if back else 9)


def run(*cmd):
    if DRY:
        log("RUN " + " ".join(cmd))
        return
    try:
        subprocess.run(cmd, check=False, timeout=2,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as exc:  # noqa: BLE001
        log(f"cmd failed {cmd}: {exc}")


def alt_down():
    global alt_held
    with state_lock:
        alt_held = True
    keys.send(("Alt_L", True))


def alt_up():
    global alt_held
    with state_lock:
        if not alt_held:
            return
        alt_held = False
    keys.send(("Alt_L", False))


def is_alt_held():
    with state_lock:
        return alt_held


def cancel_commit():
    global commit_timer
    with state_lock:
        timer = commit_timer
        commit_timer = None
    if timer is not None:
        timer.cancel()


def _commit_now():
    global commit_timer
    with state_lock:
        commit_timer = None
    alt_up()


def schedule_commit(delay=COMMIT_DELAY):
    global commit_timer
    cancel_commit()
    timer = threading.Timer(delay, _commit_now)
    timer.daemon = True
    with state_lock:
        commit_timer = timer
    timer.start()


def tab(shift=False):
    if shift:
        keys.send(("Shift_L", True), ("Tab", True), ("Tab", False),
                  ("Shift_L", False))
    else:
        keys.send(("Tab", True), ("Tab", False))


def toggle_desktop():
    try:
        out = subprocess.run(
            ["xprop", "-root", "_NET_SHOWING_DESKTOP"],
            capture_output=True, text=True, timeout=2,
        ).stdout
        showing = out.strip().endswith("1")
    except Exception:  # noqa: BLE001
        showing = False
    run("wmctrl", "-k", "off" if showing else "on")


def switch_workspace(next_ws):
    arrow = "Right" if next_ws else "Left"
    keys.send(("Control_L", True), ("Alt_L", True), (arrow, True),
              (arrow, False), ("Alt_L", False), ("Control_L", False))


def cleanup(*_):
    cancel_commit()
    alt_up()
    sys.exit(0)


class NavFlick:
    """Two fingers flicked sideways = browser Back/Forward.

    Fires once per touch, only for a fast, long, straight sideways movement
    that starts with exactly two fingers, so normal scrolling is not affected.
    """

    def __init__(self, x_max):
        self.x_max = x_max
        self.state = "idle"   # idle | tracking | done | blocked
        self.start = None
        self.t0 = 0.0
        self.spread0 = 0.0
        self.maxdx = self.maxdy = self.maxspread = 0.0
        self.reason = "-"

    def _summary(self, now):
        if self.maxdx >= 0.08 * self.x_max and self.reason != "blocked":
            log("2-finger touch: dx=%.0f%% dy=%.0f%% spread=%.0f%% t=%.2fs -> %s" % (
                100 * self.maxdx / self.x_max, 100 * self.maxdy / self.x_max,
                100 * self.maxspread, now - self.t0, self.reason))

    @staticmethod
    def _center(pts):
        return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))

    @staticmethod
    def _spread(pts):
        return ((pts[0][0] - pts[1][0]) ** 2 + (pts[0][1] - pts[1][1]) ** 2) ** 0.5

    def on_frame(self, pts, now):
        n = len(pts)
        if n == 0:
            if self.state in ("tracking", "done"):
                self._summary(now)
            self.state = "idle"
            return
        if n > 2:
            self.state = "blocked"        # 3+ fingers: not ours until all lift
            self.reason = "blocked"
            return
        if self.state == "blocked":
            return
        if n == 1:
            if self.state == "tracking":
                self.state = "done"
            return
        if self.state == "idle":
            self.state = "tracking"
            self.start = self._center(pts)
            self.t0 = now
            self.spread0 = max(1.0, self._spread(pts))
            self.maxdx = self.maxdy = self.maxspread = 0.0
            self.reason = "no-fire"
            return
        if self.state != "tracking":
            return
        cx, cy = self._center(pts)
        dx, dy = cx - self.start[0], cy - self.start[1]
        self.maxdx = max(self.maxdx, abs(dx))
        self.maxdy = max(self.maxdy, abs(dy))
        self.maxspread = max(self.maxspread, abs(self._spread(pts) - self.spread0) / self.spread0)
        if now - self.t0 > NAV_TIME:
            self.state = "done"           # too slow: this is scrolling
            self.reason = "too-slow"
            return
        if abs(dy) > NAV_STRAIGHT * max(abs(dx), 0.05 * self.x_max) and abs(dy) > 0.12 * self.x_max:
            self.state = "done"           # not straight enough
            self.reason = "not-straight"
            return
        if abs(dx) >= NAV_DIST * self.x_max and abs(dy) <= NAV_STRAIGHT * abs(dx):
            self.state = "done"
            self.reason = "fired"
            self.fire(dx > 0)

    @staticmethod
    def fire(finger_right):
        if not in_browser():
            log("flick ignored: window is not a browser: %s" % (keys.active_class(),))
            return
        if keys.modifiers_down():
            log("flick ignored: a modifier key is held")
            return
        if ZOOM_LOCK and is_zoomed():
            log("flick ignored: page is zoomed (net %.2fx), this is panning" % zoom["net"])
            return
        back = finger_right == NAV_FINGER_RIGHT_IS_BACK
        log(f"2-finger flick {'right' if finger_right else 'left'} -> "
            f"browser {'back' if back else 'forward'}")
        browser_nav(back)


# --- raw finger count, so 5-finger activity can be recognised ---------------
class FingerTracker(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.count = 0
        self.last_five = 0.0

    def five_recent(self, now):
        return self.count >= 5 or (now - self.last_five) < FIVE_HOLD

    def _find(self):
        import evdev

        for path in evdev.list_devices():
            try:
                dev = evdev.InputDevice(path)
            except (OSError, PermissionError):
                continue
            if "Touchpad" in dev.name:
                return dev
        return None

    def _loop(self):
        from evdev import ecodes

        dev = self._find()
        if dev is None:
            raise RuntimeError("touchpad not found")
        log(f"finger tracker on {dev.name}")
        caps = dict(dev.capabilities(absinfo=True).get(ecodes.EV_ABS, []))
        nav = NavFlick(caps[ecodes.ABS_MT_POSITION_X].max)
        slots, slot, pos = set(), 0, {}
        for event in dev.read_loop():
            if event.type == ecodes.EV_ABS:
                if event.code == ecodes.ABS_MT_SLOT:
                    slot = event.value
                elif event.code == ecodes.ABS_MT_TRACKING_ID:
                    if event.value == -1:
                        slots.discard(slot)
                        pos.pop(slot, None)
                    else:
                        slots.add(slot)
                elif event.code == ecodes.ABS_MT_POSITION_X:
                    pos.setdefault(slot, [None, None])[0] = event.value
                elif event.code == ecodes.ABS_MT_POSITION_Y:
                    pos.setdefault(slot, [None, None])[1] = event.value
            elif event.type == ecodes.EV_KEY and event.code == ecodes.BTN_TOOL_QUINTTAP:
                if event.value:
                    self.last_five = time.monotonic()
            elif event.type == ecodes.EV_SYN and event.code == ecodes.SYN_REPORT:
                self.count = len(slots)
                if self.count >= 5:
                    self.last_five = time.monotonic()
                if NAV_SWIPE:
                    nav.on_frame([tuple(pos[s]) for s in slots
                                  if s in pos and None not in pos[s]],
                                 time.monotonic())

    def run(self):
        while True:
            try:
                self._loop()
            except Exception as exc:  # noqa: BLE001
                log(f"finger tracker: {exc}")
                self.count = 0
                time.sleep(2)


tracker = FingerTracker()


class Swipe:
    def __init__(self, fingers, now):
        self.fingers = fingers
        self.action = None
        self.t0 = now
        self.dx = 0.0
        self.dy = 0.0
        self.h_acc = 0.0

    def update(self, dx, dy, now):
        global last_action, switcher_sign

        if self.action == "ignored":
            return

        # A 5th finger is landing or lifting: this is TouchTamer's gesture.
        if tracker.five_recent(now):
            if self.action in (None, "pending_switcher"):
                self.action = "ignored"
            return

        if self.action == "pending_switcher":
            self.dx += dx
            self.dy += dy
            if abs(self.dx) < START_PX and abs(self.dy) < START_PX:
                return
            if abs(self.dy) <= abs(self.dx) * V_BIAS:
                self.action = "switcher"
                self.h_acc = self.dx
                self._step_switcher()
            else:
                alt_up()
                ax, ay = self.dx, self.dy
                self.action = None
                self.dx = self.dy = 0.0
                self.update(ax, ay, now)
            return

        if self.action is None:
            self.dx += dx
            self.dy += dy
            if abs(self.dx) < START_PX and abs(self.dy) < START_PX:
                return
            if now - self.t0 < SETTLE:
                return          # fingers still landing; keep accumulating
            if abs(self.dy) > abs(self.dx) * V_BIAS:
                if self.dy > 0:
                    self.action = "desktop"
                    last_action = now
                    log(f"{self.fingers}-finger swipe down -> show desktop")
                    toggle_desktop()
                else:
                    self.action = "switcher"
                    switcher_sign = 1
                    log(f"{self.fingers}-finger swipe up -> app switcher")
                    alt_down()
                    tab()
            elif self.fingers >= 4:
                self.action = "horizontal"
                last_action = now
                right = self.dx > 0
                next_dir = (not right) if SWIPE_LEFT_IS_NEXT else right
                log(f"4-finger swipe {'right' if right else 'left'} -> workspace")
                switch_workspace(next_dir)
            else:
                self.action = "switcher_h"
                right = self.dx > 0
                switcher_sign = -1 if SWIPE_LEFT_IS_NEXT else 1
                next_dir = (not right) if SWIPE_LEFT_IS_NEXT else right
                log(f"3-finger swipe {'right' if right else 'left'} -> "
                    f"{'next' if next_dir else 'previous'} app")
                alt_down()
                tab(shift=not next_dir)
                self.h_acc = 0.0
            return

        if self.action in ("switcher", "switcher_h") and is_alt_held():
            self.h_acc += dx
            self._step_switcher()

    def _step_switcher(self):
        while abs(self.h_acc) >= H_STEP_PX:
            forward = (self.h_acc * switcher_sign) > 0
            tab(shift=not forward)
            self.h_acc -= H_STEP_PX if self.h_acc > 0 else -H_STEP_PX

    def end(self):
        alt_up()
        self.action = None


swipe = None

PINCH_RE = re.compile(
    r"GESTURE_PINCH_(BEGIN|UPDATE|END)\s+(?:\d+\s+)?\+?[\d.]+s\s+(\d+)"
    r"(?:.*\)\s+(-?[\d.]+)\s*@)?"
)
pinch = {"active": False, "last": 1.0, "skip": False, "scale": 1.0, "browser": False}


def handle_pinch(line):
    """libinput pinch -> Ctrl+scroll (non-browsers); track net zoom in browsers."""
    m = PINCH_RE.search(line)
    if not m:
        return
    phase, _fingers, scale = m.groups()
    if phase == "BEGIN":
        mods, br = keys.modifiers_down(), in_browser()
        pinch.update(active=True, last=1.0, scale=1.0, skip=mods or br,
                     browser=br and not mods)
        return
    if phase == "END":
        if pinch["active"] and pinch["browser"]:
            zoom_commit(pinch["scale"])
        pinch["active"] = False
        return
    if not pinch["active"] or scale is None:
        return
    scale = float(scale)
    if scale <= 0:
        return
    pinch["scale"] = scale
    if pinch["skip"]:
        return
    while scale / pinch["last"] >= 1 + PINCH_STEP:
        keys.wheel(up=True)
        pinch["last"] *= 1 + PINCH_STEP
    while scale / pinch["last"] <= 1 / (1 + PINCH_STEP):
        keys.wheel(up=False)
        pinch["last"] /= 1 + PINCH_STEP


def handle_line(line, now=None):
    """Process one `libinput debug-events` line."""
    global swipe
    now = time.monotonic() if now is None else now
    if PINCH_ZOOM and "GESTURE_PINCH" in line:
        handle_pinch(line)
        return
    m = LINE_RE.search(line)
    if not m:
        return
    phase, fingers, dx, dy = m.groups()
    fingers = int(fingers)
    if fingers not in FINGERS:
        return
    if phase == "BEGIN":
        cancel_commit()
        swipe = Swipe(fingers, now)
        if tracker.five_recent(now):
            swipe.action = "ignored"
        elif is_alt_held():
            swipe.action = "pending_switcher"
            log("switcher continues")
        elif now - last_action < COOLDOWN:
            swipe.action = "ignored"
        else:
            alt_up()
    elif phase == "UPDATE" and swipe is not None:
        swipe.update(float(dx or 0), float(dy or 0), now)
    elif phase == "END":
        if swipe is not None:
            if swipe.action == "switcher_h":
                schedule_commit(H_COMMIT_DELAY)
            elif swipe.action in ("switcher", "pending_switcher"):
                schedule_commit(COMMIT_DELAY)
            elif swipe.action != "ignored":
                swipe.end()
        swipe = None


def main():
    signal.signal(signal.SIGTERM, cleanup)
    signal.signal(signal.SIGINT, cleanup)
    cancel_commit()
    alt_up()
    tracker.start()

    proc = subprocess.Popen(
        ["libinput", "debug-events"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        bufsize=1,
    )
    debug = bool(os.environ.get("GESTURE_DEBUG"))
    log(f"touchpad-gestures started (debug={debug})")
    for line in proc.stdout:
        if debug and "GESTURE" in line:
            log(f"RAW: {line.strip()}")
        handle_line(line)

    log("libinput stopped, exiting")
    sys.exit(1)


if __name__ == "__main__":
    main()
