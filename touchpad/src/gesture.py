"""Gesture logic for TouchTamer for Linux, kept free of X11/evdev so it can be tested."""

from dataclasses import dataclass


@dataclass
class Contact:
    id: int
    x: int
    y: int


class PadGesture:
    """Modifier keys + exactly two fingers.

    The left half of the touchpad changes brightness, the right half changes volume.
    A finger delta of ``dy > 0`` means the fingers moved up.
    """

    def __init__(self, x_max, y_max):
        self.x_max = x_max
        self.y_max = y_max
        self.deadzone = max(1, int(y_max * 0.015))
        self.active = False
        self.moving = False
        self.ids = frozenset()
        self.target = 0
        self.last_y = 0.0

    def on_frame(self, contacts, mods_down):
        """Return (target, dy, started) where target 1=brightness, 2=volume.

        Returns None when nothing changed. ``started`` is True on the first frame
        with two fingers, so the caller can read the current level.
        """
        if len(contacts) != 2 or not mods_down:
            self.active = False
            return None

        avg_x = (contacts[0].x + contacts[1].x) / 2.0
        avg_y = (contacts[0].y + contacts[1].y) / 2.0
        ids = frozenset(c.id for c in contacts)

        if not self.active or ids != self.ids:
            self.active = True
            self.moving = False
            self.ids = ids
            self.target = 1 if avg_x * 2 < self.x_max else 2
            self.last_y = avg_y
            return (self.target, 0.0, True)

        dy = self.last_y - avg_y
        if not self.moving:
            if abs(dy) < self.deadzone:
                return None
            self.moving = True
        self.last_y = avg_y
        if dy == 0:
            return None
        return (self.target, dy, False)


class MoveGesture:
    """Exactly five fingers move the window under the cursor.

    A finger that slips off for a moment does not end the gesture.
    """

    FINGERS = 5
    KEEP_FINGERS = 4
    GRACE = 0.2  # seconds
    DEADZONE_SQ = 40 * 40

    def __init__(self):
        self.state = "idle"
        self.prev = {}
        self.last_full = 0.0
        self.armed_x = 0.0
        self.armed_y = 0.0

    def on_frame(self, contacts, now):
        """Return (kind, mx, my) with kind None/'started'/'moved'/'ended'."""
        prev = self.prev
        sum_x = sum_y = 0
        matched = 0
        for c in contacts:
            p = prev.get(c.id)
            if p is not None:
                sum_x += c.x - p[0]
                sum_y += c.y - p[1]
                matched += 1
        self.prev = {c.id: (c.x, c.y) for c in contacts}

        mx = sum_x / matched if matched else 0.0
        my = sum_y / matched if matched else 0.0
        tips = len(contacts)
        if tips == self.FINGERS:
            self.last_full = now

        if self.state == "idle":
            if tips == self.FINGERS:
                self.state = "armed"
                self.armed_x = self.armed_y = 0.0
            return (None, 0.0, 0.0)

        if self.state == "armed":
            if tips != self.FINGERS:
                self.state = "idle"
                return (None, 0.0, 0.0)
            self.armed_x += mx
            self.armed_y += my
            if self.armed_x * self.armed_x + self.armed_y * self.armed_y < self.DEADZONE_SQ:
                return (None, 0.0, 0.0)
            self.state = "moving"
            return ("started", self.armed_x, self.armed_y)

        if self.state == "moving":
            if tips == 0 or (tips < self.FINGERS and now - self.last_full > self.GRACE):
                self.state = "idle"
                return ("ended", 0.0, 0.0)
            if tips < self.KEEP_FINGERS or (mx == 0 and my == 0):
                return (None, 0.0, 0.0)
            return ("moved", mx, my)

        return (None, 0.0, 0.0)
