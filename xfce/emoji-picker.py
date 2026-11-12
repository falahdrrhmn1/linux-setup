#!/usr/bin/env python3
"""Pemilih emoji ala Windows (Win+;): muncul di dekat mouse, pilih, lalu otomatis
ditempel ke jendela yang tadi aktif. Memakai pemilih emoji bawaan GTK3."""
import os
import subprocess
import sys

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk  # noqa: E402

DRY = bool(os.environ.get("EMOJI_DRY"))


def sh(*cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw).stdout.strip()


prev = sh("xdotool", "getactivewindow")
loc = dict(p.split("=") for p in sh("xdotool", "getmouselocation", "--shell").split())
mx, my = int(loc["X"]), int(loc["Y"])

win = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
win.set_decorated(False)
win.set_keep_above(True)
win.set_skip_taskbar_hint(True)
win.set_default_size(340, 420)
entry = Gtk.Entry()
entry.set_placeholder_text("Emoji…")
box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
box.pack_start(entry, False, False, 0)
win.add(box)

screen = win.get_screen()
sw, sh_ = screen.get_width(), screen.get_height()
win.move(max(0, min(mx, sw - 340)), max(0, min(my, sh_ - 440)))
done = {"v": False}


def finish(text):
    if done["v"]:
        return
    done["v"] = True
    win.hide()
    p = subprocess.Popen(["xclip", "-selection", "clipboard"], stdin=subprocess.PIPE)
    p.stdin.write(text.encode())
    p.stdin.close()
    if DRY:
        print("PICKED", text, "prev", prev)
    elif prev:
        sh("xdotool", "windowactivate", "--sync", prev)
        GLib.timeout_add(120, lambda: (subprocess.run(
            ["xdotool", "key", "--clearmodifiers", "ctrl+v"]), Gtk.main_quit())[1])
        return
    GLib.idle_add(Gtk.main_quit)


def on_changed(e):
    t = e.get_text().strip()
    if t and any(ord(c) > 0x2000 for c in t):
        finish(t)


def on_focus_out(*_):
    GLib.timeout_add(250, lambda: (None if done["v"] else Gtk.main_quit()) or False)


entry.connect("changed", on_changed)
win.connect("focus-out-event", on_focus_out)
win.connect("key-press-event", lambda w, e: Gtk.main_quit() if e.keyval == 0xFF1B and not done["v"] and not entry.get_text() else None)
win.connect("destroy", Gtk.main_quit)
win.show_all()
win.present()
GLib.timeout_add(150, lambda: (entry.emit("insert-emoji"), False)[1])
if os.environ.get("EMOJI_AUTOTEST"):
    GLib.timeout_add(1200, lambda: (entry.set_text("😀"), False)[1])
GLib.timeout_add_seconds(60, lambda: (Gtk.main_quit(), False)[1])
Gtk.main()
