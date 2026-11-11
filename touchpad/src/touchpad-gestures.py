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


keys = Keys()


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
        slots, slot = set(), 0
        for event in dev.read_loop():
            if event.type == ecodes.EV_ABS:
                if event.code == ecodes.ABS_MT_SLOT:
                    slot = event.value
                elif event.code == ecodes.ABS_MT_TRACKING_ID:
                    if event.value == -1:
                        slots.discard(slot)
                    else:
                        slots.add(slot)
            elif event.type == ecodes.EV_KEY and event.code == ecodes.BTN_TOOL_QUINTTAP:
                if event.value:
                    self.last_five = time.monotonic()
            elif event.type == ecodes.EV_SYN and event.code == ecodes.SYN_REPORT:
                self.count = len(slots)
                if self.count >= 5:
                    self.last_five = time.monotonic()

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


def handle_line(line, now=None):
    """Process one `libinput debug-events` line."""
    global swipe
    now = time.monotonic() if now is None else now
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
