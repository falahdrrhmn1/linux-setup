#!/usr/bin/env python3
"""TouchTamer for Linux: touchpad gestures for brightness, volume and moving windows.

Gestures:
  Ctrl+Shift + two-finger vertical swipe
      left half of the touchpad  -> brightness
      right half of the touchpad -> volume
  Five-finger swipe              -> move the window under the cursor

This program reads the touchpad directly through evdev, so it does not depend on
the desktop's gesture handling, and its gestures work in every application.
"""

import configparser
import fcntl
import glob
import math
import os
import re
import signal
import subprocess
import sys
import time
import threading

import evdev
from evdev import ecodes

from Xlib import X, XK, display, protocol
from Xlib.ext import xtest  # noqa: F401  (kept for extensions used by some setups)

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, GLib, Gtk  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gesture import Contact, MoveGesture, PadGesture  # noqa: E402

APP = "touchtamer"
CONFIG_PATH = os.path.expanduser("~/.config/touchtamer/TouchTamer.ini")
CACHE_DIR = os.path.expanduser("~/.cache/touchtamer")
LOG_PATH = os.path.join(CACHE_DIR, "TouchTamer.log")
LOCK_PATH = os.path.join(CACHE_DIR, "touchtamer.lock")
SCROLL_STATE = os.path.join(CACHE_DIR, "scroll-original")

DEFAULTS = {
    "level_gesture": 1,
    "gesture_mod": "ctrl+shift",
    "full_height_pct": 60,
    "move_gesture": 1,
    "move_speed_pct": 150,
    "size_hotkeys": 1,
    "width_hotkeys": 1,
    "hide_after_ms": 850,
    "alpha": 245,
    "suppress_scroll": 1,
    "debug": 0,
}


def log(cfg, message):
    if not cfg.get("debug"):
        return
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write("%s %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), message))
    except OSError:
        pass


def load_config():
    cfg = dict(DEFAULTS)
    parser = configparser.ConfigParser()
    if os.path.exists(CONFIG_PATH):
        parser.read(CONFIG_PATH)
        if parser.has_section("touchtamer"):
            for key in DEFAULTS:
                if parser.has_option("touchtamer", key):
                    raw = parser.get("touchtamer", key)
                    if key == "gesture_mod":
                        cfg[key] = raw.strip().lower()
                    else:
                        try:
                            cfg[key] = int(raw)
                        except ValueError:
                            pass
    cfg["alpha"] = max(40, min(255, cfg["alpha"]))
    cfg["move_speed_pct"] = max(10, cfg["move_speed_pct"])
    cfg["hide_after_ms"] = max(100, cfg["hide_after_ms"])
    return cfg


def mods_from_name(name):
    mods = set()
    for part in re.split(r"[+, ]+", name.lower()):
        if part in ("ctrl", "control"):
            mods.add("ctrl")
        elif part == "alt":
            mods.add("alt")
        elif part == "shift":
            mods.add("shift")
    return mods or {"ctrl", "shift"}


class Hud:
    """Small dark panel at the bottom of the screen showing a percentage."""

    def __init__(self, cfg):
        self.cfg = cfg
        self.timeout = None
        self.window = Gtk.Window(type=Gtk.WindowType.POPUP)
        self.window.set_decorated(False)
        self.window.set_resizable(False)
        self.window.set_skip_taskbar_hint(True)
        self.window.set_skip_pager_hint(True)
        self.window.set_accept_focus(False)
        self.window.set_focus_on_map(False)
        self.window.set_keep_above(True)
        self.window.set_type_hint(Gdk.WindowTypeHint.NOTIFICATION)
        self.window.set_opacity(cfg["alpha"] / 255.0)

        screen = self.window.get_screen()
        visual = screen.get_rgba_visual()
        if visual is not None:
            self.window.set_visual(visual)
            self.window.set_app_paintable(True)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.set_name("ttbox")
        box.set_border_width(16)
        self.label = Gtk.Label()
        self.label.set_xalign(0.0)
        self.bar = Gtk.ProgressBar()
        box.pack_start(self.label, False, False, 0)
        box.pack_start(self.bar, False, False, 0)
        self.window.add(box)

        css = b"""
        window { background: transparent; }
        #ttbox { background-color: rgba(18,18,18,0.94); border-radius: 12px; }
        #ttbox label { color: #ffffff; font-size: 15px; font-weight: bold; }
        #ttbox progressbar trough { min-height: 8px; border-radius: 4px; background-color: rgba(255,255,255,0.18); }
        #ttbox progressbar progress { min-height: 8px; border-radius: 4px; background-color: #4ea1ff; }
        """
        provider = Gtk.CssProvider()
        provider.load_from_data(css)
        Gtk.StyleContext.add_provider_for_screen(
            screen, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        self.width = 320
        self.height = 86

    def show(self, title, pct):
        GLib.idle_add(self._show, title, int(pct))

    def _monitor_geometry(self):
        display_ = Gdk.Display.get_default()
        if display_ is None:
            return 0, 0, 1920, 1080
        monitor = display_.get_primary_monitor() or display_.get_monitor(0)
        if monitor is None:
            return 0, 0, 1920, 1080
        geo = monitor.get_geometry()
        return geo.x, geo.y, geo.width, geo.height

    def _show(self, title, pct):
        self.label.set_text("%s   %d%%" % (title, pct))
        self.bar.set_fraction(max(0.0, min(1.0, pct / 100.0)))
        mx, my, mw, mh = self._monitor_geometry()
        x = mx + (mw - self.width) // 2
        y = my + mh - self.height - 120
        self.window.resize(self.width, self.height)
        self.window.move(x, y)
        self.window.show_all()
        self.window.get_window().raise_()
        if self.timeout is not None:
            GLib.source_remove(self.timeout)
        self.timeout = GLib.timeout_add(self.cfg["hide_after_ms"], self._hide)
        return False

    def _hide(self):
        self.window.hide()
        self.timeout = None
        return False


class ScrollGuard:
    """Temporarily disable touchpad scrolling while one of our gestures runs.

    This keeps the application underneath from scrolling or zooming during a
    brightness/volume swipe or a five-finger window move. The original setting
    is stored on disk so a crash cannot leave scrolling off forever.
    """

    def __init__(self, device_name, enabled):
        self.name = device_name
        self.enabled = bool(enabled)
        self.saved = None
        self.disabled = False
        self._cleanup_from_crash()
        self.original = self._read() or (1, 0, 0)
        if self.original == (0, 0, 0):
            self.original = (1, 0, 0)

    def _read(self):
        try:
            out = subprocess.check_output(
                ["xinput", "list-props", self.name],
                stderr=subprocess.DEVNULL,
                timeout=2,
            ).decode("utf-8", "ignore")
        except (OSError, subprocess.SubprocessError):
            return None
        m = re.search(
            r"libinput Scroll Method Enabled[^:]*:\s*(\d),\s*(\d),\s*(\d)", out
        )
        if not m:
            return None
        return tuple(int(v) for v in m.groups())

    def _set(self, values):
        try:
            subprocess.run(
                [
                    "xinput",
                    "set-prop",
                    self.name,
                    "libinput Scroll Method Enabled",
                    *[str(v) for v in values],
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=2,
            )
        except (OSError, subprocess.SubprocessError):
            pass

    def _cleanup_from_crash(self):
        try:
            if os.path.exists(SCROLL_STATE):
                with open(SCROLL_STATE, encoding="utf-8") as fh:
                    values = tuple(int(v) for v in fh.read().split())
                if len(values) == 3:
                    self._set(values)
                os.remove(SCROLL_STATE)
        except (OSError, ValueError):
            pass

    def disable(self):
        if not self.enabled or self.disabled:
            return
        try:
            os.makedirs(CACHE_DIR, exist_ok=True)
            with open(SCROLL_STATE, "w", encoding="utf-8") as fh:
                fh.write(" ".join(str(v) for v in self.original))
        except OSError:
            return
        self._set((0, 0, 0))
        self.disabled = True

    def restore(self):
        if not self.disabled:
            return
        self._set(self.original)
        self.disabled = False
        try:
            os.remove(SCROLL_STATE)
        except OSError:
            pass


class LevelController:
    """Turns finger deltas into brightness and volume changes."""

    def __init__(self, cfg, hud, callback_target):
        self.cfg = cfg
        self.hud = hud
        self.acc = [0.0, 0.0]
        self.level = [None, None]
        self.last_apply = 0.0
        self.last_pct = [-1, -1]
        self.callback_target = callback_target
        self.backlight_dir = self._find_backlight()
        self.max_brightness = 0
        self.backlight_name = None
        if self.backlight_dir:
            self.backlight_name = os.path.basename(self.backlight_dir)
            try:
                with open(os.path.join(self.backlight_dir, "max_brightness")) as fh:
                    self.max_brightness = int(fh.read().strip())
            except (OSError, ValueError):
                self.max_brightness = 0

    @staticmethod
    def _find_backlight():
        entries = sorted(glob.glob("/sys/class/backlight/*"))
        for path in entries:
            if os.path.basename(path) == "intel_backlight":
                return path
        return entries[0] if entries else None

    def _read_brightness(self):
        if not self.backlight_dir:
            return 50
        try:
            with open(os.path.join(self.backlight_dir, "brightness")) as fh:
                current = int(fh.read().strip())
            if self.max_brightness:
                return int(round(current * 100.0 / self.max_brightness))
        except (OSError, ValueError):
            pass
        return 50

    def _set_brightness(self, pct):
        if not self.backlight_dir or not self.max_brightness:
            return False
        value = int(round(max(5, min(100, pct)) * self.max_brightness / 100.0))
        try:
            subprocess.run(
                [
                    "busctl",
                    "call",
                    "org.freedesktop.login1",
                    "/org/freedesktop/login1/session/auto",
                    "org.freedesktop.login1.Session",
                    "SetBrightness",
                    "ssu",
                    "backlight",
                    self.backlight_name,
                    str(value),
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=2,
            )
            return True
        except (OSError, subprocess.SubprocessError):
            return False

    def _read_volume(self):
        try:
            out = subprocess.check_output(
                ["pactl", "get-sink-volume", "@DEFAULT_SINK@"],
                stderr=subprocess.DEVNULL,
                timeout=2,
            ).decode("utf-8", "ignore")
            m = re.search(r"(\d+)%", out)
            if m:
                return int(m.group(1))
        except (OSError, subprocess.SubprocessError):
            pass
        return 50

    def _set_volume(self, pct):
        try:
            subprocess.run(
                ["pactl", "set-sink-volume", "@DEFAULT_SINK@", "%d%%" % int(pct)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=2,
            )
            return True
        except (OSError, subprocess.SubprocessError):
            return False

    def _read_level(self, target):
        if target == 1:
            return self._read_brightness()
        return self._read_volume()

    def begin(self, target):
        self.level[target - 1] = self._read_level(target)
        self.last_pct[target - 1] = -1

    def add(self, target, pct):
        self.acc[target - 1] += pct

    def flush(self, force=False):
        now = time.monotonic()
        if not force and now - self.last_apply < 0.03:
            return
        self.last_apply = now
        for index in (0, 1):
            change = self.acc[index]
            if change == 0:
                continue
            self.acc[index] = 0.0
            if self.level[index] is None:
                self.level[index] = self._read_level(index + 1)
            level = max(0.0, min(100.0, self.level[index] + change))
            self.level[index] = level
            pct = int(level + 0.5)
            if pct == self.last_pct[index]:
                continue
            self.last_pct[index] = pct
            if index == 0:
                if self._set_brightness(pct):
                    log(self.cfg, "apply brightness -> %d%%" % pct)
                    self.hud.show("Brightness", pct)
                    self.callback_target(1, pct)
            else:
                if self._set_volume(pct):
                    log(self.cfg, "apply volume -> %d%%" % pct)
                    self.hud.show("Volume", pct)
                    self.callback_target(2, pct)


class WindowMover:
    """Moves the window under the cursor using EWMH window messages."""

    def __init__(self, dpy):
        self.dpy = dpy
        self.root = dpy.screen().root
        geo = self.root.get_geometry()
        self.screen_w = geo.width
        self.screen_h = geo.height
        self.win = None
        self.wid = None
        self.want_x = self.want_y = 0.0
        self.want_cx = self.want_cy = 0.0
        self.frame_w = self.frame_h = 0
        self.px_per_count = 1.0
        self.atom_moveresize = dpy.intern_atom("_NET_MOVERESIZE_WINDOW")
        self.atom_state = dpy.intern_atom("_NET_WM_STATE")
        self.atom_max_h = dpy.intern_atom("_NET_WM_STATE_MAXIMIZED_HORZ")
        self.atom_max_v = dpy.intern_atom("_NET_WM_STATE_MAXIMIZED_VERT")

    def _pointer(self):
        p = self.root.query_pointer()
        return p.root_x, p.root_y

    def _window_under_pointer(self):
        try:
            out = subprocess.check_output(
                ["xdotool", "getmouselocation", "--shell"],
                stderr=subprocess.DEVNULL,
                timeout=2,
            ).decode("utf-8", "ignore")
        except (OSError, subprocess.SubprocessError):
            return None
        for line in out.splitlines():
            if line.startswith("WINDOW="):
                try:
                    return int(line.split("=", 1)[1])
                except ValueError:
                    return None
        return None

    def _prop(self, window, name):
        try:
            prop = window.get_full_property(
                self.dpy.intern_atom(name), X.AnyPropertyType
            )
            return prop.value if prop is not None else None
        except Exception:
            return None

    def _frame_extents(self, window):
        value = self._prop(window, "_NET_FRAME_EXTENTS")
        if value and len(value) >= 4:
            return tuple(int(v) for v in value[:4])
        return (0, 0, 0, 0)

    def _work_area(self):
        value = self._prop(self.root, "_NET_WORKAREA")
        if value and len(value) >= 4:
            return tuple(int(v) for v in value[:4])
        return (0, 0, self.screen_w, self.screen_h)

    def _send_client_message(self, window, atom, data):
        event = protocol.event.ClientMessage(
            window=window,
            client_type=atom,
            data=(32, [int(v) & 0xFFFFFFFF for v in data]),
        )
        self.root.send_event(
            event,
            event_mask=X.SubstructureRedirectMask | X.SubstructureNotifyMask,
        )

    def _move_resize(self, window, x, y, w=None, h=None):
        gravity = 1  # NorthWest
        present = 0x03 if w is None or h is None else 0x0F
        flags = gravity | (present << 8) | (2 << 12)  # source = pager
        self._send_client_message(
            window,
            self.atom_moveresize,
            [flags, round(x), round(y), round(w or 0), round(h or 0)],
        )
        self.dpy.flush()

    def _set_maximized(self, window, enabled):
        action = 1 if enabled else 0
        self._send_client_message(
            window, self.atom_state, [action, self.atom_max_v, self.atom_max_h, 2, 0]
        )
        self.dpy.flush()

    def begin(self, px_per_count):
        cx, cy = self._pointer()
        wid = self._window_under_pointer()
        if not wid or wid == self.root.id:
            return False
        try:
            window = self.dpy.create_resource_object("window", wid)
            if window.get_attributes().map_state != X.IsViewable:
                return False

            window_type = self._prop(window, "_NET_WM_WINDOW_TYPE") or []
            if (
                self.dpy.intern_atom("_NET_WM_WINDOW_TYPE_DOCK") in window_type
                or self.dpy.intern_atom("_NET_WM_WINDOW_TYPE_DESKTOP") in window_type
            ):
                return False

            state = self._prop(window, "_NET_WM_STATE") or []
            if self.dpy.intern_atom("_NET_WM_STATE_FULLSCREEN") in state:
                return False
            maximized = self.atom_max_h in state or self.atom_max_v in state

            geom = window.get_geometry()
            left, right, top, bottom = self._frame_extents(window)
            abs_x, abs_y = self._absolute_position(window)
            frame_w = geom.width + left + right
            frame_h = geom.height + top + bottom

            if maximized:
                wx, wy, ww, wh = self._work_area()
                frame_w = int(ww * 0.75)
                frame_h = int(wh * 0.75)
                frame_x = cx - int((cx - wx) * frame_w / max(1, ww))
                frame_y = cy - int((cy - wy) * frame_h / max(1, wh))
                self._set_maximized(window, False)
                time.sleep(0.02)
                self._move_resize(window, frame_x, frame_y, frame_w, frame_h)
            else:
                frame_x = abs_x - left
                frame_y = abs_y - top

            self.win = window
            self.wid = wid
            self.want_x = float(frame_x)
            self.want_y = float(frame_y)
            self.want_cx = float(cx)
            self.want_cy = float(cy)
            self.frame_w = frame_w
            self.frame_h = frame_h
            self.px_per_count = max(0.1, px_per_count)

            try:
                subprocess.run(
                    ["xdotool", "windowraise", str(wid)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=1,
                )
            except (OSError, subprocess.SubprocessError):
                pass
            return True
        except Exception:
            self.win = None
            return False

    def _absolute_position(self, window):
        coords = self.root.translate_coords(window, 0, 0)
        return coords.x, coords.y

    def move(self, dx, dy):
        if self.win is None:
            return
        self.want_x += dx
        self.want_y += dy
        self.want_cx += dx
        self.want_cy += dy

        wx, wy, ww, wh = self._work_area()
        keep = 120
        max_x = wx + ww - keep
        max_y = wy + wh - 40
        fx = max(wx, min(self.want_x, max_x))
        fy = max(wy, min(self.want_y, max_y))

        self._move_resize(self.win, fx, fy)

        cx = max(0, min(self.screen_w - 1, int(round(self.want_cx))))
        cy = max(0, min(self.screen_h - 1, int(round(self.want_cy))))
        try:
            self.root.warp_pointer(cx, cy)
            self.dpy.flush()
        except Exception:
            pass

    def end(self):
        self.win = None
        self.wid = None


class WindowSizer:
    """Alt+Up/Down change the size, Alt+Left/Right change the width."""

    LEVELS = (0.0, 0.95, 0.90, 0.75, 0.40)
    LAST = 4
    MIN_WIDTH = 300

    def __init__(self, dpy):
        self.dpy = dpy
        self.root = dpy.screen().root
        self.atom_moveresize = dpy.intern_atom("_NET_MOVERESIZE_WINDOW")
        self.atom_state = dpy.intern_atom("_NET_WM_STATE")
        self.atom_max_h = dpy.intern_atom("_NET_WM_STATE_MAXIMIZED_HORZ")
        self.atom_max_v = dpy.intern_atom("_NET_WM_STATE_MAXIMIZED_VERT")

    def _prop(self, window, name):
        try:
            prop = window.get_full_property(
                self.dpy.intern_atom(name), X.AnyPropertyType
            )
            return prop.value if prop is not None else None
        except Exception:
            return None

    def _frame_extents(self, window):
        value = self._prop(window, "_NET_FRAME_EXTENTS")
        if value and len(value) >= 4:
            return tuple(int(v) for v in value[:4])
        return (0, 0, 0, 0)

    def _work_area(self):
        value = self._prop(self.root, "_NET_WORKAREA")
        if value and len(value) >= 4:
            return tuple(int(v) for v in value[:4])
        geo = self.root.get_geometry()
        return (0, 0, geo.width, geo.height)

    def _send(self, window, atom, data):
        event = protocol.event.ClientMessage(
            window=window,
            client_type=atom,
            data=(32, [int(v) & 0xFFFFFFFF for v in data]),
        )
        self.root.send_event(
            event,
            event_mask=X.SubstructureRedirectMask | X.SubstructureNotifyMask,
        )
        self.dpy.flush()

    def _move_resize(self, window, x, y, w, h):
        flags = 1 | (0x0F << 8) | (2 << 12)
        self._send(window, self.atom_moveresize, [flags, x, y, w, h])

    def _maximize(self, window, enabled):
        action = 1 if enabled else 0
        self._send(
            window, self.atom_state, [action, self.atom_max_v, self.atom_max_h, 2, 0]
        )

    def _active_window(self):
        value = self._prop(self.root, "_NET_ACTIVE_WINDOW")
        if not value or not value[0]:
            return None
        try:
            return self.dpy.create_resource_object("window", int(value[0]))
        except Exception:
            return None

    def _valid(self, window):
        if window is None:
            return False
        try:
            if window.get_attributes().map_state != X.IsViewable:
                return False
        except Exception:
            return False
        window_type = self._prop(window, "_NET_WM_WINDOW_TYPE") or []
        if (
            self.dpy.intern_atom("_NET_WM_WINDOW_TYPE_DOCK") in window_type
            or self.dpy.intern_atom("_NET_WM_WINDOW_TYPE_DESKTOP") in window_type
        ):
            return False
        return True

    def _is_maximized(self, window):
        state = self._prop(window, "_NET_WM_STATE") or []
        return self.atom_max_h in state or self.atom_max_v in state

    def _frame_rect(self, window):
        geom = window.get_geometry()
        left, right, top, bottom = self._frame_extents(window)
        coords = self.root.translate_coords(window, 0, 0)
        return (
            coords.x - left,
            coords.y - top,
            geom.width + left + right,
            geom.height + top + bottom,
        )

    def step_size(self, step):
        window = self._active_window()
        if not self._valid(window):
            return
        wx, wy, ww, wh = self._work_area()
        maximized = self._is_maximized(window)

        current = 0
        if not maximized:
            fx, fy, fw, fh = self._frame_rect(window)
            best = 1e18
            for index in range(1, self.LAST + 1):
                diff = abs(fw - ww * self.LEVELS[index])
                if diff < best:
                    best = diff
                    current = index

        target = current + step
        if target < 0:
            target = self.LAST
        if target > self.LAST:
            target = self.LAST
        if target == 0:
            self._maximize(window, True)
            return

        fw = int(ww * self.LEVELS[target] + 0.5)
        fh = int(wh * self.LEVELS[target] + 0.5)
        fx = wx + (ww - fw) // 2
        fy = wy + (wh - fh) // 2
        if maximized:
            self._maximize(window, False)
            time.sleep(0.02)
        self._move_resize(window, fx, fy, fw, fh)

    def adjust_width(self, delta):
        window = self._active_window()
        if not self._valid(window):
            return
        wx, wy, ww, wh = self._work_area()
        if self._is_maximized(window):
            if delta > 0:
                return
            self._maximize(window, False)
            time.sleep(0.02)
            self._move_resize(window, wx, wy, ww + delta, wh)
            return

        fx, fy, fw, fh = self._frame_rect(window)
        new_w = fw + delta
        if delta > 0:
            room = wx + ww - fx
            if new_w > room:
                new_w = room if room > fw else fw
        elif new_w < self.MIN_WIDTH:
            new_w = fw if fw < self.MIN_WIDTH else self.MIN_WIDTH
        self._move_resize(window, fx, fy, new_w, fh)


class HotkeyListener(threading.Thread):
    """Global Alt+arrow hotkeys through XGrabKey."""

    def __init__(self, cfg, stop):
        super().__init__(daemon=True)
        self.cfg = cfg
        self.stop_event = stop
        self.ready = threading.Event()

    def run(self):
        try:
            dpy = display.Display()
        except Exception as exc:
            log(self.cfg, "hotkeys: cannot open display: %s" % exc)
            return

        def error_handler(error, request):
            log(self.cfg, "hotkeys: %s" % error)
            return 0

        try:
            dpy.set_error_handler(error_handler)
        except Exception:
            pass

        sizer = WindowSizer(dpy)
        root = dpy.screen().root
        keys = {}
        if self.cfg["size_hotkeys"]:
            keys[dpy.keysym_to_keycode(XK.string_to_keysym("Up"))] = "up"
            keys[dpy.keysym_to_keycode(XK.string_to_keysym("Down"))] = "down"
        if self.cfg["width_hotkeys"]:
            keys[dpy.keysym_to_keycode(XK.string_to_keysym("Left"))] = "left"
            keys[dpy.keysym_to_keycode(XK.string_to_keysym("Right"))] = "right"

        if not keys:
            dpy.close()
            return

        try:
            root.change_attributes(event_mask=X.KeyPressMask)
        except Exception:
            pass

        modifiers = [
            X.Mod1Mask,
            X.Mod1Mask | X.Mod2Mask,
            X.Mod1Mask | X.LockMask,
            X.Mod1Mask | X.Mod2Mask | X.LockMask,
        ]
        grabbed = []
        for keycode in keys:
            for mods in modifiers:
                try:
                    root.grab_key(
                        keycode, mods, False, X.GrabModeAsync, X.GrabModeAsync
                    )
                    grabbed.append((keycode, mods))
                except Exception:
                    pass
        try:
            dpy.sync()
        except Exception:
            pass
        self.ready.set()
        log(self.cfg, "hotkeys ready: %d grabs" % len(grabbed))

        last_action = 0.0
        while not self.stop_event.is_set():
            try:
                import select

                ready, _, _ = select.select([dpy.fileno()], [], [], 0.5)
                if not ready:
                    continue
                while dpy.pending_events():
                    event = dpy.next_event()
                    if event.type != X.KeyPress:
                        continue
                    name = keys.get(event.detail)
                    if name is None:
                        continue
                    now = time.monotonic()
                    if now - last_action < 0.25:
                        continue
                    last_action = now
                    log(self.cfg, "hotkey %s" % name)
                    if name == "up":
                        sizer.step_size(-1)
                    elif name == "down":
                        sizer.step_size(1)
                    elif name == "right":
                        sizer.adjust_width(40)
                    elif name == "left":
                        sizer.adjust_width(-40)
            except Exception as exc:
                log(self.cfg, "hotkeys loop: %s" % exc)
                time.sleep(0.2)

        for keycode, mods in grabbed:
            try:
                root.ungrab_key(keycode, mods)
            except Exception:
                pass
        try:
            dpy.close()
        except Exception:
            pass


class ModifierState:
    def __init__(self, dpy, names):
        self.dpy = dpy
        self.wanted = mods_from_name(names)
        self.codes = {
            "ctrl": {
                dpy.keysym_to_keycode(XK.string_to_keysym("Control_L")),
                dpy.keysym_to_keycode(XK.string_to_keysym("Control_R")),
            },
            "alt": {
                dpy.keysym_to_keycode(XK.string_to_keysym("Alt_L")),
                dpy.keysym_to_keycode(XK.string_to_keysym("Alt_R")),
            },
            "shift": {
                dpy.keysym_to_keycode(XK.string_to_keysym("Shift_L")),
                dpy.keysym_to_keycode(XK.string_to_keysym("Shift_R")),
            },
        }

    def down(self):
        keymap = self.dpy.query_keymap()

        def pressed(codes):
            for code in codes:
                if code and keymap[code // 8] & (1 << (code % 8)):
                    return True
            return False

        for name in self.wanted:
            if not pressed(self.codes[name]):
                return False
        return True


class TouchpadReader:
    def __init__(self, name_hint="Touchpad"):
        self.device = None
        for path in evdev.list_devices():
            try:
                dev = evdev.InputDevice(path)
            except (OSError, PermissionError):
                continue
            if name_hint in dev.name:
                self.device = dev
                break
        if self.device is None:
            raise RuntimeError("touchpad tidak ditemukan")

        caps = self.device.capabilities(absinfo=True)
        abs_caps = dict(caps.get(ecodes.EV_ABS, []))
        self.x_max = abs_caps[ecodes.ABS_MT_POSITION_X].max
        self.y_max = abs_caps[ecodes.ABS_MT_POSITION_Y].max
        self.slots = {}
        self.current_slot = 0

    def read_loop(self, on_frame, stop):
        import select

        while not stop.is_set():
            ready, _, _ = select.select([self.device.fd], [], [], 0.5)
            if not ready:
                continue
            for event in self.device.read():
                if event.type == ecodes.EV_ABS:
                    if event.code == ecodes.ABS_MT_SLOT:
                        self.current_slot = event.value
                    elif event.code == ecodes.ABS_MT_TRACKING_ID:
                        if event.value == -1:
                            self.slots.pop(self.current_slot, None)
                        else:
                            self.slots.setdefault(self.current_slot, {})[
                                "id"
                            ] = event.value
                    elif event.code == ecodes.ABS_MT_POSITION_X:
                        self.slots.setdefault(self.current_slot, {})["x"] = event.value
                    elif event.code == ecodes.ABS_MT_POSITION_Y:
                        self.slots.setdefault(self.current_slot, {})["y"] = event.value
                elif event.type == ecodes.EV_SYN and event.code == ecodes.SYN_REPORT:
                    contacts = [
                        Contact(slot["id"], slot["x"], slot["y"])
                        for slot in self.slots.values()
                        if "id" in slot and "x" in slot and "y" in slot
                    ]
                    on_frame(contacts, time.monotonic())


def worker(cfg, hud, stop):
    try:
        _worker(cfg, hud, stop)
    except Exception:
        import traceback

        traceback.print_exc()
        log(cfg, "worker crashed")


def _worker(cfg, hud, stop):
    dpy = display.Display()
    modifiers = ModifierState(dpy, cfg["gesture_mod"])
    reader = TouchpadReader()

    pad = PadGesture(reader.x_max, reader.y_max)
    mover_gesture = MoveGesture()
    level = LevelController(cfg, hud, lambda target, pct: None)
    mover = WindowMover(dpy)
    guard = ScrollGuard(reader.device.name, cfg["suppress_scroll"])

    state = {"suppress": False}
    log(
        cfg,
        "started device=%s x_max=%d y_max=%d"
        % (reader.device.name, reader.x_max, reader.y_max),
    )

    def update_suppress():
        want = pad.active or mover_gesture.state != "idle"
        if want and not state["suppress"]:
            guard.disable()
            state["suppress"] = True
            log(cfg, "gesture start (%s)" % ("level" if pad.active else "move"))
        elif not want and state["suppress"]:
            guard.restore()
            state["suppress"] = False
            log(cfg, "gesture end")

    def on_frame(contacts, now):
        if stop.is_set():
            return
        try:
            _handle_frame(contacts, now)
        except Exception as exc:
            print("frame error: %s" % exc, file=sys.stderr, flush=True)
            log(cfg, "frame error: %s" % exc)
            try:
                level.flush(force=True)
            except Exception:
                pass
            try:
                guard.restore()
            except Exception:
                pass
            state["suppress"] = False
            pad.active = False
            mover_gesture.state = "idle"
            mover.end()

    def _handle_frame(contacts, now):
        # Brightness / volume: Ctrl+Shift and two fingers.
        if cfg["level_gesture"]:
            was_active = pad.active
            mods = modifiers.down() if len(contacts) == 2 else False
            result = pad.on_frame(contacts, mods)
            if result is not None:
                target, dy, started = result
                if started:
                    level.begin(target)
                if dy:
                    level.add(target, dy * cfg["full_height_pct"] / reader.y_max)
                level.flush()
            if was_active and not pad.active:
                level.flush(force=True)
        else:
            pad.active = False

        # Five-finger window move.
        if cfg["move_gesture"]:
            kind, mx, my = mover_gesture.on_frame(contacts, now)
            if kind == "started":
                px_per_count = (
                    mover.screen_w * cfg["move_speed_pct"] / 100.0 / reader.x_max
                )
                if not mover.begin(px_per_count):
                    mover_gesture.state = "idle"
            elif kind == "moved":
                mover.move(mx * mover.px_per_count, my * mover.px_per_count)
            elif kind == "ended":
                mover.end()

        update_suppress()

    try:
        reader.read_loop(on_frame, stop)
    finally:
        try:
            level.flush(force=True)
        except Exception:
            pass
        guard.restore()
        mover.end()


def main():
    os.makedirs(CACHE_DIR, exist_ok=True)
    lock_file = open(LOCK_PATH, "w")
    try:
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print("TouchTamer sudah berjalan.")
        return 1

    cfg = load_config()
    hud = Hud(cfg)
    stop = threading.Event()
    thread = threading.Thread(target=worker, args=(cfg, hud, stop), daemon=True)
    thread.start()
    hotkeys = HotkeyListener(cfg, stop)
    hotkeys.start()

    def quit_handler(*_args):
        stop.set()
        Gtk.main_quit()

    signal.signal(signal.SIGINT, quit_handler)
    signal.signal(signal.SIGTERM, quit_handler)

    try:
        Gtk.main()
    finally:
        stop.set()
    return 0


if __name__ == "__main__":
    sys.exit(main())
