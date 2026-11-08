#!/usr/bin/env python3
"""Multi-finger touchpad gestures for XFCE/X11 (3 and 4 fingers).

3 fingers: down = show/hide desktop
           up = open and hold the Alt+Tab switcher; lift to commit,
                place the fingers again within the grace window to keep choosing
           right = next app, left = previous app
4 fingers: down = show/hide desktop | up = hold the Alt+Tab switcher
           right = next workspace, left = previous workspace

Five fingers are handled by TouchTamer (moving the window), so they are not
handled here.
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
START_PX = 35          # movement needed to pick a direction
H_STEP_PX = 60         # horizontal movement per app step while switcher is held
COOLDOWN = 0.3         # ignore a new gesture right after an action
COMMIT_DELAY = 0.6     # keep the switcher open this long after lifting the fingers
SWIPE_LEFT_IS_NEXT = True   # one-shot app switch: swipe left = next app
# --------------------------------------------------------------------------

LINE_RE = re.compile(
    r"GESTURE_SWIPE_(BEGIN|UPDATE|END)\s+(?:\d+\s+)?\+?[\d.]+s\s+(\d+)"
    r"(?:\s+(-?[\d.]+)\s*/\s*(-?[\d.]+))?"
)

alt_held = False
commit_timer = None
last_action = 0.0
state_lock = threading.Lock()


def log(msg):
    print(msg, file=sys.stderr, flush=True)


def run(*cmd):
    try:
        subprocess.run(cmd, check=False, timeout=2,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as exc:  # noqa: BLE001
        log(f"cmd failed {cmd}: {exc}")


def alt_down():
    global alt_held
    with state_lock:
        alt_held = True
    run("xdotool", "keydown", "alt")


def alt_up():
    global alt_held
    with state_lock:
        if not alt_held:
            return
        alt_held = False
    run("xdotool", "keyup", "alt")


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
    run("xdotool", "key", "shift+Tab" if shift else "Tab")


def switch_app(next_app):
    combo = "alt+Tab" if next_app else "alt+shift+Tab"
    run("xdotool", "key", "--clearmodifiers", combo)


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
    run("xdotool", "key", "ctrl+alt+" + ("Right" if next_ws else "Left"))


def cleanup(*_):
    cancel_commit()
    alt_up()
    sys.exit(0)


class Swipe:
    def __init__(self, fingers):
        self.fingers = fingers
        self.action = None
        self.dx = 0.0
        self.dy = 0.0
        self.h_acc = 0.0

    def update(self, dx, dy):
        global last_action
        now = time.monotonic()

        if self.action == "pending_switcher":
            self.dx += dx
            self.dy += dy
            if abs(self.dx) < START_PX and abs(self.dy) < START_PX:
                return
            if abs(self.dx) > abs(self.dy):
                self.action = "switcher"
                self.h_acc = self.dx
                self._step_switcher()
            else:
                alt_up()
                ax, ay = self.dx, self.dy
                self.action = None
                self.dx = self.dy = 0.0
                self.update(ax, ay)
            return

        if self.action is None:
            self.dx += dx
            self.dy += dy
            if abs(self.dx) < START_PX and abs(self.dy) < START_PX:
                return
            if abs(self.dy) >= abs(self.dx):
                if self.dy > 0:
                    self.action = "desktop"
                    last_action = now
                    log(f"{self.fingers}-finger swipe down -> show desktop")
                    toggle_desktop()
                else:
                    self.action = "switcher"
                    log(f"{self.fingers}-finger swipe up -> app switcher")
                    alt_down()
                    time.sleep(0.05)
                    tab()
            else:
                self.action = "horizontal"
                last_action = now
                right = self.dx > 0
                next_dir = (not right) if SWIPE_LEFT_IS_NEXT else right
                if self.fingers >= 4:
                    log(f"{self.fingers}-finger swipe "
                        f"{'right' if right else 'left'} -> workspace")
                    switch_workspace(next_dir)
                else:
                    log(f"{self.fingers}-finger swipe "
                        f"{'right' if right else 'left'} -> "
                        f"{'next' if next_dir else 'previous'} app")
                    switch_app(next_dir)
            return

        if self.action == "switcher" and is_alt_held():
            self.h_acc += dx
            self._step_switcher()

    def _step_switcher(self):
        while abs(self.h_acc) >= H_STEP_PX:
            if self.h_acc >= H_STEP_PX:
                tab(shift=False)
                self.h_acc -= H_STEP_PX
            else:
                tab(shift=True)
                self.h_acc += H_STEP_PX

    def end(self):
        alt_up()
        self.action = None


def main():
    global last_action
    signal.signal(signal.SIGTERM, cleanup)
    signal.signal(signal.SIGINT, cleanup)
    cancel_commit()
    alt_up()

    proc = subprocess.Popen(
        ["libinput", "debug-events"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        bufsize=1,
    )
    debug = bool(os.environ.get("GESTURE_DEBUG"))
    log(f"touchpad-gestures started (debug={debug})")
    swipe = None
    for line in proc.stdout:
        m = LINE_RE.search(line)
        if not m:
            if debug and "GESTURE" in line:
                log(f"RAW: {line.strip()}")
            continue
        phase, fingers, dx, dy = m.groups()
        fingers = int(fingers)
        if debug:
            log(f"EV: {phase} fingers={fingers} dx={dx} dy={dy}")
        if fingers not in FINGERS:
            continue
        now = time.monotonic()
        if phase == "BEGIN":
            cancel_commit()
            if is_alt_held():
                swipe = Swipe(fingers)
                swipe.action = "pending_switcher"
                log("switcher continues")
            elif now - last_action < COOLDOWN:
                swipe = Swipe(fingers)
                swipe.action = "ignored"
            else:
                alt_up()
                swipe = Swipe(fingers)
        elif phase == "UPDATE" and swipe is not None:
            if swipe.action == "ignored":
                continue
            swipe.update(float(dx or 0), float(dy or 0))
        elif phase == "END":
            if swipe is not None:
                if swipe.action in ("switcher", "pending_switcher"):
                    schedule_commit()
                elif swipe.action != "ignored":
                    swipe.end()
            swipe = None

    log("libinput stopped, exiting")
    sys.exit(1)


if __name__ == "__main__":
    main()
