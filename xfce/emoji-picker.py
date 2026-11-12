#!/usr/bin/env python3
"""Pemilih emoji ala Windows (Win+;).

Muncul di dekat mouse. Setiap emoji yang dipilih langsung ditempel ke jendela
yang tadi aktif, lalu pemilih muncul lagi supaya bisa memilih lagi.
Esc, atau klik di luar pemilih, menutupnya. Menekan pintasannya lagi = tutup.
Memakai pemilih emoji bawaan GTK3.
"""
import fcntl
import os
import signal
import subprocess
import sys

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("GdkX11", "3.0")
from gi.repository import GLib, Gtk  # noqa: E402

DRY = bool(os.environ.get("EMOJI_DRY"))
W, H = 460, 480
LOCK = f"/tmp/emoji-picker-{os.getuid()}.lock"


def sh(*cmd):
    return subprocess.run(cmd, capture_output=True, text=True).stdout.strip()


# Satu instance saja: panggilan kedua menutup yang pertama (toggle).
lockf = open(LOCK, "a+")
try:
    fcntl.flock(lockf, fcntl.LOCK_EX | fcntl.LOCK_NB)
except OSError:
    try:
        lockf.seek(0)
        os.kill(int(lockf.read().strip()), signal.SIGTERM)
    except Exception:  # noqa: BLE001
        pass
    sys.exit(0)
lockf.seek(0)
lockf.truncate()
lockf.write(str(os.getpid()))
lockf.flush()

prev = sh("xdotool", "getactivewindow")
loc = dict(p.split("=") for p in sh("xdotool", "getmouselocation", "--shell").split())
mx, my = int(loc["X"]), int(loc["Y"])

win = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
win.set_decorated(False)
win.set_keep_above(True)
win.set_skip_taskbar_hint(True)
win.set_default_size(W, H)
box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
entry = Gtk.Entry()
entry.set_placeholder_text("Emoji…  (Esc = tutup)")
box.pack_start(entry, False, False, 0)
win.add(box)

geo = win.get_screen().get_display().get_monitor_at_point(mx, my).get_geometry()
win.move(max(geo.x, min(mx, geo.x + geo.width - W - 10)),
         max(geo.y, min(my, geo.y + geo.height - H - 10)))

st = {"focused": False, "busy": False, "seen": False}


def quit_now(*_):
    Gtk.main_quit()


def watch_chooser():
    """Esc menutup popover pemilih; kalau sudah pernah terbuka lalu tertutup = selesai."""
    gw = win.get_window()
    if gw is None:
        return True
    vis = any(c.is_visible() and c.get_height() > 100 for c in gw.get_children())
    if vis:
        st["seen"] = True
    elif st["seen"] and not st["busy"]:
        quit_now()
        return False
    return True


def open_chooser():
    st["seen"] = False
    entry.set_text("")
    entry.grab_focus()
    entry.emit("insert-emoji")
    return False


def paste_done():
    # Kembalikan fokus ke pemilih untuk emoji berikutnya.
    win.present()
    sh("xdotool", "windowactivate", str(win.get_window().get_xid()))
    GLib.timeout_add(200, lambda: (st.update(busy=False), open_chooser(), False)[2])
    return False


def pick(text):
    st["busy"] = True
    p = subprocess.Popen(["xclip", "-selection", "clipboard"], stdin=subprocess.PIPE)
    p.stdin.write(text.encode())
    p.stdin.close()
    if DRY:
        print("PICKED", text, "prev", prev, flush=True)
        GLib.timeout_add(100, lambda: (st.update(busy=False), False)[1])
        return
    if prev:
        sh("xdotool", "windowactivate", "--sync", prev)

        def do_paste():
            subprocess.run(["xdotool", "key", "--clearmodifiers", "ctrl+v"])
            GLib.timeout_add(180, paste_done)
            return False

        GLib.timeout_add(150, do_paste)


def on_changed(e):
    t = e.get_text().strip()
    if t and not st["busy"] and any(ord(c) > 0x2000 for c in t):
        pick(t)


def on_focus_in(*_):
    st["focused"] = True


def on_focus_out(*_):
    if not st["focused"] or st["busy"]:
        return
    GLib.timeout_add(300, lambda: (None if (st["busy"] or win.is_active()) else quit_now()) or False)


def on_key(_w, ev):
    if ev.keyval == 0xFF1B:  # Escape
        quit_now()
        return True
    return False


entry.connect("changed", on_changed)
win.connect("focus-in-event", on_focus_in)
win.connect("focus-out-event", on_focus_out)
win.connect("key-press-event", on_key)
win.connect("destroy", quit_now)
GLib.unix_signal_add(GLib.PRIORITY_HIGH, signal.SIGTERM, lambda *_: (quit_now(), False)[1])
win.show_all()
win.present()
GLib.timeout_add(120, lambda: (sh("xdotool", "windowactivate", str(win.get_window().get_xid())), False)[1])
GLib.timeout_add(350, open_chooser)
GLib.timeout_add(100, watch_chooser)
if os.environ.get("EMOJI_AUTOTEST"):
    GLib.timeout_add(1500, lambda: (entry.set_text("😀"), False)[1])
    GLib.timeout_add(2500, lambda: (entry.set_text("🎉"), False)[1])
GLib.timeout_add_seconds(1800, quit_now)  # pengaman
Gtk.main()
