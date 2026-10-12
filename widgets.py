"""Small, theme-aware Tk controls without runtime dependencies."""
import tkinter as tk


class RoundedScrollbar(tk.Canvas):
    """A quiet rounded thumb; click, drag, wheel and keyboard scrolling."""

    def __init__(self, master, orient="vertical", command=None, **kwargs):
        self.vertical = orient == "vertical"
        super().__init__(master, width=12 if self.vertical else 1,
                         height=1 if self.vertical else 12,
                         highlightthickness=0, borderwidth=0, takefocus=True, **kwargs)
        self.command = command
        self.first, self.last = 0.0, 1.0
        self.hover = False
        self.drag_offset = None
        self.thumb_color, self.active_color = "#bdc8df", "#4a59b2"
        self.bind("<Configure>", lambda _: self.draw())
        self.bind("<Enter>", lambda _: self.set_hover(True))
        self.bind("<Leave>", lambda _: self.set_hover(False))
        self.bind("<Button-1>", self.press)
        self.bind("<B1-Motion>", self.drag)
        self.bind("<ButtonRelease-1>", self.release)
        self.bind("<MouseWheel>", self.wheel)
        self.bind("<Shift-MouseWheel>", self.wheel)
        for key, count in (("Up", -1), ("Left", -1), ("Down", 1), ("Right", 1)):
            self.bind(f"<{key}>", lambda _, n=count: self.scroll(n, "units"))
        for key, count in (("Prior", -1), ("Next", 1)):
            self.bind(f"<{key}>", lambda _, n=count: self.scroll(n, "pages"))
        self.bind("<Home>", lambda _: self.move(0))
        self.bind("<End>", lambda _: self.move(1))
        self.bind("<FocusIn>", lambda _: self.draw())
        self.bind("<FocusOut>", lambda _: self.draw())

    def set(self, first, last):
        self.first = max(0.0, min(1.0, float(first)))
        self.last = max(self.first, min(1.0, float(last)))
        self.draw()

    def set_colors(self, background, thumb, active):
        self.configure(background=background)
        self.thumb_color, self.active_color = thumb, active
        self.draw()

    def geometry_values(self):
        length = self.winfo_height() if self.vertical else self.winfo_width()
        track = max(0, length - 4)
        span = self.last - self.first
        thumb = min(track, max(28, track * span))
        travel = track - thumb
        start = 2 + (travel * self.first / (1 - span) if span < 1 else 0)
        return start, thumb, travel, span

    def draw(self):
        self.delete("all")
        if self.last - self.first >= 0.999999:
            return
        start, thumb, _, _ = self.geometry_values()
        color = self.active_color if self.hover or self.drag_offset is not None or self.focus_get() is self else self.thumb_color
        cross = self.winfo_width() if self.vertical else self.winfo_height()
        lo, hi = 3, max(3, cross - 3)
        radius = max(0, (hi - lo) / 2)
        if self.vertical:
            self.create_rectangle(lo, start + radius, hi, start + thumb - radius, fill=color, outline="")
            for y in (start, start + thumb - 2 * radius):
                self.create_oval(lo, y, hi, y + 2 * radius, fill=color, outline="")
        else:
            self.create_rectangle(start + radius, lo, start + thumb - radius, hi, fill=color, outline="")
            for x in (start, start + thumb - 2 * radius):
                self.create_oval(x, lo, x + 2 * radius, hi, fill=color, outline="")

    def set_hover(self, value):
        self.hover = value
        self.draw()

    def coordinate(self, event):
        return event.y if self.vertical else event.x

    def press(self, event):
        if self.last - self.first >= 0.999999:
            return "break"
        self.focus_set()
        start, thumb, _, _ = self.geometry_values()
        position = self.coordinate(event)
        self.drag_offset = position - start if start <= position <= start + thumb else thumb / 2
        self.drag(event)
        return "break"

    def drag(self, event):
        if self.drag_offset is None:
            return "break"
        _, _, travel, span = self.geometry_values()
        if travel > 0:
            value = (self.coordinate(event) - 2 - self.drag_offset) / travel * (1 - span)
            self.move(value)
        self.draw()
        return "break"

    def release(self, _):
        self.drag_offset = None
        self.draw()

    def move(self, value):
        if self.command:
            self.command("moveto", max(0, min(1 - (self.last - self.first), value)))
        return "break"

    def scroll(self, count, mode):
        if self.command:
            self.command("scroll", count, mode)
        return "break"

    def wheel(self, event):
        if event.delta:
            self.scroll(-max(1, abs(event.delta) // 120) * (1 if event.delta > 0 else -1), "units")
        return "break"
