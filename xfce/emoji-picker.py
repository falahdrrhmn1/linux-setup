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
import time

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("GdkX11", "3.0")
from gi.repository import GLib, Gtk  # noqa: E402

DRY = bool(os.environ.get("EMOJI_DRY"))
W, H = 460, 480
LOCK = f"/tmp/emoji-picker-{os.getuid()}.lock"


def sh(*cmd):
    return subprocess.run(cmd, capture_output=True, text=True).stdout.strip()


LOGF = os.path.expanduser("~/.cache/emoji-picker.log")


def log(msg):
    try:
        os.makedirs(os.path.dirname(LOGF), exist_ok=True)
        if os.path.exists(LOGF) and os.path.getsize(LOGF) > 50000:
            os.remove(LOGF)
        with open(LOGF, "a") as f:
            f.write(f"{time.monotonic() % 1000:.3f} {msg}\n")
    except OSError:
        pass


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
log(f"start prev={prev} name={sh('xdotool', 'getwindowname', prev) if prev else ''}")
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
    log("quit")
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
    log("open_chooser")
    entry.set_text("")
    entry.grab_focus()
    entry.emit("insert-emoji")
    return False


def paste_done():
    # Kembalikan fokus ke pemilih untuk emoji berikutnya.
    win.present()
    sh("xdotool", "windowactivate", str(win.get_window().get_xid()))
    GLib.timeout_add(40, lambda: (st.update(busy=False), open_when_active(), False)[2])
    return False


def pick(text):
    st["busy"] = True
    log(f"pick {text!r}")
    p = subprocess.Popen(["xclip", "-selection", "clipboard"], stdin=subprocess.PIPE)
    p.stdin.write(text.encode())
    p.stdin.close()
    if DRY:
        print("PICKED", text, "prev", prev, flush=True)
        GLib.timeout_add(100, lambda: (st.update(busy=False), False)[1])
        return
    if not prev:
        st["busy"] = False
        return
    sh("xdotool", "windowactivate", "--sync", prev)
    tries = {"n": 0}

    def do_paste():
        now = sh("xdotool", "getactivewindow")
        if now != prev and tries["n"] < 40:
            tries["n"] += 1
            if tries["n"] == 12:
                sh("xdotool", "windowfocus", prev)
            return True            # belum pindah fokus; coba lagi (tiap 25 ms)
        if now != prev:
            log(f"paste skipped: active={now} prev={prev}")
            GLib.timeout_add(50, paste_done)
            return False
        subprocess.run(["xdotool", "key", "--clearmodifiers", "ctrl+v"])
        log("pasted")
        GLib.timeout_add(70, paste_done)
        return False

    GLib.timeout_add(25, do_paste)


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
def open_when_active(n=[0]):
    """Buka popover begitu jendela pemilih benar-benar punya fokus (tanpa jeda tetap)."""
    if win.is_active() or n[0] > 30:
        n[0] = 0
        open_chooser()
        return False
    n[0] += 1
    GLib.timeout_add(20, open_when_active)
    return False


GLib.timeout_add(60, lambda: (sh("xdotool", "windowactivate", "--sync", str(win.get_window().get_xid())), open_when_active(), False)[2])
GLib.timeout_add(100, watch_chooser)
if os.environ.get("EMOJI_AUTOTEST"):
    GLib.timeout_add(1500, lambda: (entry.set_text(os.environ.get("E1","😀")), False)[1])
    GLib.timeout_add(2500, lambda: (entry.set_text(os.environ.get("E2","🎉")), False)[1])
GLib.timeout_add_seconds(1800, quit_now)  # pengaman
Gtk.main()
