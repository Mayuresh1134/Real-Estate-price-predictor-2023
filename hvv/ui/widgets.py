"""Custom widgets: a searchable picker and the canvas drawings (gauge, charts)."""
from __future__ import annotations

import math
import tkinter as tk
import tkinter.font as tkfont
import weakref

import customtkinter as ctk

from . import theme


def _scale(widget) -> float:
    try:
        return float(ctk.ScalingTracker.get_widget_scaling(widget))
    except Exception:
        return 1.0


# ---------------------------------------------------------------------------
# Searchable picker
# ---------------------------------------------------------------------------
class SearchSelect(ctk.CTkFrame):
    """A text box that filters a long list as you type.

    Arrow keys move through the matches, Enter picks one, Escape closes the
    list. ``get()`` returns the picked value, or None if nothing is picked.
    """

    MAX_ROWS = 8
    _instances: "weakref.WeakSet[SearchSelect]" = weakref.WeakSet()
    _bound_windows: set = set()

    def __init__(self, master, placeholder: str = "", on_change=None):
        super().__init__(master, fg_color="transparent")
        self._values: list[str] = []
        self._shown: list[str] = []
        self._value: str | None = None
        self._popup: tk.Frame | None = None
        self._listbox: tk.Listbox | None = None
        self._on_change = on_change

        self.entry = theme.entry(self, placeholder)
        self.entry.pack(fill="x")
        self.entry.bind("<KeyRelease>", self._on_key)
        self.entry.bind("<Button-1>", lambda e: self.after(1, self.open))
        self.entry.bind("<Down>", lambda e: self._move(1))
        self.entry.bind("<Up>", lambda e: self._move(-1))
        self.entry.bind("<Return>", self._on_return)
        self.entry.bind("<Escape>", lambda e: self._finish())
        self.entry.bind("<FocusOut>", lambda e: self.after(160, self._on_focus_out))
        # One click handler per window closes whichever list is open.
        SearchSelect._instances.add(self)
        top = self.winfo_toplevel()
        if str(top) not in SearchSelect._bound_windows:
            SearchSelect._bound_windows.add(str(top))
            top.bind("<Button-1>", SearchSelect._dispatch_click, add="+")
        ctk.AppearanceModeTracker.add(self._on_mode, self)

    @staticmethod
    def _dispatch_click(event) -> None:
        for picker in list(SearchSelect._instances):
            try:
                if picker.winfo_exists():
                    picker._on_any_click(event)
            except tk.TclError:
                pass

    # -- public -------------------------------------------------------------
    def set_values(self, values: list[str]) -> None:
        self._values = list(values)
        self.clear()

    def get(self) -> str | None:
        return self._value

    def set(self, value: str | None) -> None:
        self._value = value if value in self._values else None
        self._show_text(self._value or "")

    def clear(self) -> None:
        self.close()
        self._value = None
        self._show_text("")

    def set_error(self, on: bool) -> None:
        self.entry.configure(border_color=theme.ERROR if on else theme.BORDER)

    def focus_entry(self) -> None:
        self.entry.focus_set()

    def configure_state(self, enabled: bool) -> None:
        self.entry.configure(state="normal" if enabled else "disabled")

    # -- internals ----------------------------------------------------------
    def _show_text(self, text: str) -> None:
        self.entry.delete(0, "end")
        if text:
            self.entry.insert(0, text)

    def _matches(self, query: str) -> list[str]:
        q = query.strip().lower()
        if not q or (self._value and q == self._value.lower()):
            return self._values
        starts = [v for v in self._values if v.lower().startswith(q)]
        inside = [v for v in self._values if q in v.lower() and not v.lower().startswith(q)]
        return starts + inside

    def open(self) -> None:
        if not self._values or str(self.entry.cget("state")) == "disabled":
            return
        self._shown = self._matches(self.entry.get())
        top = self.winfo_toplevel()
        scale = _scale(self)
        if self._popup is None:
            self._popup = tk.Frame(top, bd=0, highlightthickness=1)
            self._listbox = tk.Listbox(
                self._popup, activestyle="none", exportselection=False, bd=0,
                highlightthickness=0, relief="flat", selectmode="browse")
            scrollbar = ctk.CTkScrollbar(self._popup, command=self._listbox.yview, width=14)
            self._listbox.configure(yscrollcommand=scrollbar.set)
            scrollbar.pack(side="right", fill="y")
            self._listbox.pack(side="left", fill="both", expand=True, padx=(6, 0), pady=4)
            self._listbox.bind("<ButtonRelease-1>", self._on_list_click)
            self._listbox.bind("<Return>", self._on_return)
            self._listbox.bind("<Escape>", lambda e: self._finish())
        self._style_popup(scale)

        self._listbox.delete(0, "end")
        if self._shown:
            self._listbox.insert("end", *self._shown)
            self._listbox.configure(state="normal")
            self._select_row(self._shown.index(self._value) if self._value in self._shown else 0)
        else:
            self._listbox.insert("end", "No match. Try fewer letters.")
            self._listbox.configure(state="disabled")

        row = tkfont.Font(font=self._listbox.cget("font")).metrics("linespace") + 1
        height = row * max(1, min(self.MAX_ROWS, len(self._shown))) + 10
        inner = self.entry
        x = inner.winfo_rootx() - top.winfo_rootx()
        y = inner.winfo_rooty() - top.winfo_rooty() + inner.winfo_height() + 2
        if y + height > top.winfo_height() - 8:           # no room below: open upward
            y = inner.winfo_rooty() - top.winfo_rooty() - height - 2
        self._popup.place(x=x, y=max(4, y), width=inner.winfo_width(), height=height)
        self._popup.lift()

    def _style_popup(self, scale: float) -> None:
        self._popup.configure(bg=theme.pick(theme.SURFACE),
                              highlightbackground=theme.pick(theme.BORDER),
                              highlightcolor=theme.pick(theme.BORDER))
        self._listbox.configure(
            font=theme.canvas_font(13, scale=scale),
            bg=theme.pick(theme.SURFACE), fg=theme.pick(theme.TEXT),
            disabledforeground=theme.pick(theme.MUTED),
            selectbackground=theme.pick(theme.SELECTED),
            selectforeground=theme.pick(theme.TEXT))

    def close(self) -> None:
        if self._popup is not None:
            self._popup.place_forget()

    def _is_open(self) -> bool:
        return self._popup is not None and bool(self._popup.winfo_ismapped())

    def _select_row(self, index: int) -> None:
        self._listbox.selection_clear(0, "end")
        self._listbox.selection_set(index)
        self._listbox.see(index)

    def _move(self, step: int):
        if not self._is_open():
            self.open()
            return "break"
        if self._shown:
            current = self._listbox.curselection()
            index = (current[0] + step) if current else 0
            self._select_row(max(0, min(len(self._shown) - 1, index)))
        return "break"

    def _commit(self, value: str) -> None:
        changed = value != self._value
        self._value = value
        self._show_text(value)
        self.close()
        self.set_error(False)
        if changed and self._on_change:
            self._on_change(value)

    def _finish(self) -> None:
        """Close the list and put the box back in a consistent state."""
        self.close()
        typed = self.entry.get().strip().lower()
        exact = next((v for v in self._values if v.lower() == typed), None)
        if exact and exact != self._value:
            self._commit(exact)
        elif not typed and self._value is not None:
            self._value = None
            if self._on_change:
                self._on_change(None)
        else:
            self._show_text(self._value or "")

    def _on_key(self, event) -> None:
        if event.keysym in ("Up", "Down", "Return", "Escape", "Tab", "Shift_L", "Shift_R",
                            "Control_L", "Control_R", "Alt_L", "Alt_R"):
            return
        self.set_error(False)
        self.open()

    def _on_return(self, event=None):
        if self._is_open() and self._shown:
            current = self._listbox.curselection()
            self._commit(self._shown[current[0] if current else 0])
        else:
            self._finish()
        return "break"

    def _on_list_click(self, event) -> None:
        if self._shown:
            index = self._listbox.nearest(event.y)
            if 0 <= index < len(self._shown):
                self._commit(self._shown[index])
                self.entry.focus_set()

    def _on_focus_out(self) -> None:
        try:
            focused = self.focus_get()
        except KeyError:
            focused = None
        if focused is not None and self._popup is not None and \
                str(focused).startswith(str(self._popup)):
            return
        if self._is_open() or self.entry.get().strip() != (self._value or ""):
            self._finish()

    def _on_any_click(self, event) -> None:
        if not self._is_open():
            return
        widget = str(event.widget)
        if widget.startswith(str(self._popup)) or widget.startswith(str(self.entry)):
            return
        self._finish()

    def _on_mode(self, _mode=None) -> None:
        if self._popup is not None and self.winfo_exists():
            self._style_popup(_scale(self))

    def destroy(self):
        ctk.AppearanceModeTracker.remove(self._on_mode)
        SearchSelect._instances.discard(self)
        if self._popup is not None:
            self._popup.destroy()
        super().destroy()


# ---------------------------------------------------------------------------
# Canvas base: redraws on resize and on light/dark switch
# ---------------------------------------------------------------------------
class Drawing(tk.Canvas):
    surface = theme.SURFACE

    def __init__(self, master, height: int):
        self.s = _scale(master)
        super().__init__(master, height=round(height * self.s), highlightthickness=0,
                         bd=0, bg=theme.pick(self.surface))
        self._pending = None
        self.bind("<Configure>", self._schedule)
        ctk.AppearanceModeTracker.add(self._on_mode, self)

    def _on_mode(self, _mode=None) -> None:
        if self.winfo_exists():
            self._schedule()

    def _schedule(self, _event=None) -> None:
        if self._pending is None:
            self._pending = self.after(15, self._redraw)

    def _redraw(self) -> None:
        self._pending = None
        if not self.winfo_exists():
            return
        self.s = _scale(self)
        self.configure(bg=theme.pick(self.surface))
        self.delete("all")
        if self.winfo_width() > 20:
            self.draw(self.winfo_width(), self.winfo_height())

    def draw(self, width: int, height: int) -> None:   # overridden
        raise NotImplementedError

    def px(self, value: float) -> int:
        return round(value * self.s)

    def round_rect(self, x1, y1, x2, y2, r, **kwargs):
        r = max(0, min(r, (x2 - x1) / 2, (y2 - y1) / 2))
        points = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
                  x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
        return self.create_polygon(points, smooth=True, **kwargs)

    def tooltip(self, x: float, y: float, text: str) -> None:
        """A small label near (x, y), kept inside the canvas."""
        self.delete("tip")
        pad = self.px(7)
        item = self.create_text(0, 0, text=text, anchor="nw", tags="tip",
                                font=theme.canvas_font(12, scale=self.s),
                                fill=theme.pick(theme.SURFACE))
        x1, y1, x2, y2 = self.bbox(item)
        w, h = x2 - x1 + 2 * pad, y2 - y1 + 2 * pad
        left = min(max(4, x - w / 2), self.winfo_width() - w - 4)
        top = y - h - self.px(10)
        if top < 2:
            top = y + self.px(14)
        self.round_rect(left, top, left + w, top + h, self.px(6),
                        fill=theme.pick(theme.TEXT), outline="", tags="tip")
        self.coords(item, left + pad, top + pad)
        self.tag_raise(item)

    def destroy(self):
        ctk.AppearanceModeTracker.remove(self._on_mode)
        super().destroy()


# ---------------------------------------------------------------------------
# The estimate's likely range
# ---------------------------------------------------------------------------
class RangeGauge(Drawing):
    """A band from the low to the high end of the range, with the estimate marked."""

    def __init__(self, master):
        super().__init__(master, height=64)
        self._data = None

    def show(self, low: float, estimate: float, high: float, low_text: str, high_text: str):
        self._data = (low, estimate, high, low_text, high_text)
        self._schedule()

    def clear(self):
        self._data = None
        self._schedule()

    def draw(self, width, height):
        if not self._data:
            return
        low, estimate, high, low_text, high_text = self._data
        pad = self.px(10)
        y = self.px(16)
        bar = self.px(10)
        # The track runs a little past both ends so the band reads as a range.
        t_low, t_high = math.log(low) - 0.18, math.log(high) + 0.18
        pos = lambda v: pad + (math.log(v) - t_low) / (t_high - t_low) * (width - 2 * pad)
        self.round_rect(pad, y - bar / 2, width - pad, y + bar / 2, bar / 2,
                        fill=theme.pick(theme.TRACK), outline="")
        self.round_rect(pos(low), y - bar / 2, pos(high), y + bar / 2, bar / 2,
                        fill=theme.pick(theme.PRIMARY), outline="")
        r = self.px(9)
        x = pos(estimate)
        self.create_oval(x - r, y - r, x + r, y + r, fill=theme.pick(theme.ACCENT),
                         outline=theme.pick(self.surface), width=self.px(3))
        text_y = y + self.px(18)
        font = theme.canvas_font(12, scale=self.s)
        self.create_text(pos(low), text_y, text=low_text, anchor="n", font=font,
                         fill=theme.pick(theme.MUTED))
        self.create_text(pos(high), text_y, text=high_text, anchor="n", font=font,
                         fill=theme.pick(theme.MUTED))


# ---------------------------------------------------------------------------
# Line chart (one series over years)
# ---------------------------------------------------------------------------
def _nice_ticks(top: float, count: int = 4) -> list[float]:
    """Round axis values from 0 up to at least ``top``."""
    raw = top / count
    magnitude = 10 ** math.floor(math.log10(raw))
    step = next(m * magnitude for m in (1, 2, 2.5, 5, 10) if m * magnitude >= raw)
    ticks = [step * i for i in range(count + 2)]
    return [t for t in ticks if t <= top + step * 0.999]


class LineChart(Drawing):
    """Value by year. Hover to read any year."""

    def __init__(self, master, height: int = 260, value_format=str, axis_format=str):
        super().__init__(master, height=height)
        self._values: tuple[float, ...] = ()
        self._fmt, self._axis_fmt = value_format, axis_format
        self._geometry = None
        self.bind("<Motion>", self._on_motion)
        self.bind("<Leave>", lambda e: self.delete("hover", "tip"))

    def show(self, values):
        self._values = tuple(values)
        self._schedule()

    def draw(self, width, height):
        values = self._values
        if len(values) < 2:
            return
        font = theme.canvas_font(11, scale=self.s)
        muted, grid = theme.pick(theme.MUTED), theme.pick(theme.BORDER)
        ticks = _nice_ticks(max(values) * 1.02)
        labels = [self._axis_fmt(t) for t in ticks]
        left = self.px(14) + max(len(l) for l in labels) * self.px(7)
        right, top, bottom = width - self.px(22), self.px(26), height - self.px(30)
        y_max = ticks[-1]
        n = len(values) - 1
        fx = lambda i: left + (right - left) * i / n
        fy = lambda v: bottom - (bottom - top) * v / y_max
        self._geometry = (left, right, n, fx, fy)

        for tick, text in zip(ticks, labels):
            y = fy(tick)
            self.create_line(left, y, right, y, fill=grid, width=1)
            self.create_text(left - self.px(8), y, text=text, anchor="e", font=font, fill=muted)
        step = max(1, math.ceil(n / 8))
        for i in range(0, n + 1, step):
            self.create_text(fx(i), bottom + self.px(8), anchor="n", font=font, fill=muted,
                             text="Today" if i == 0 else f"Year {i}")

        points = [c for i, v in enumerate(values) for c in (fx(i), fy(v))]
        self.create_line(points, fill=theme.pick(theme.PRIMARY), width=self.px(2),
                         capstyle="round", joinstyle="round")
        r = self.px(5)
        x, y = fx(n), fy(values[-1])
        self.create_oval(x - r, y - r, x + r, y + r, fill=theme.pick(theme.PRIMARY),
                         outline=theme.pick(self.surface), width=self.px(2))
        self.create_text(x - self.px(10), y - self.px(6), text=self._fmt(values[-1]), anchor="se",
                         font=theme.canvas_font(12, True, self.s), fill=theme.pick(theme.TEXT))

    def _on_motion(self, event):
        self.delete("hover", "tip")
        if not self._geometry or len(self._values) < 2:
            return
        left, right, n, fx, fy = self._geometry
        if not left - 10 <= event.x <= right + 10:
            return
        i = max(0, min(n, round((event.x - left) / (right - left) * n)))
        x, y = fx(i), fy(self._values[i])
        self.create_line(x, fy(0), x, y, fill=theme.pick(theme.MUTED), dash=(3, 3), tags="hover")
        r = self.px(5)
        self.create_oval(x - r, y - r, x + r, y + r, fill=theme.pick(theme.PRIMARY),
                         outline=theme.pick(self.surface), width=self.px(2), tags="hover")
        when = "Today" if i == 0 else f"After {i} year{'s' if i != 1 else ''}"
        self.tooltip(x, y, f"{when}: {self._fmt(self._values[i])}")


# ---------------------------------------------------------------------------
# Horizontal bar chart (one series; one bar may be highlighted)
# ---------------------------------------------------------------------------
class BarChart(Drawing):
    ROW = 34

    def __init__(self, master, rows, label_width: int = 150):
        """rows: dicts with label, value, text (shown at the bar end) and
        optional highlight (bool) and detail (hover text)."""
        self._rows = list(rows)
        self._label_width = label_width
        self._hit = []
        super().__init__(master, height=self.ROW * len(self._rows) + 8)
        self.bind("<Motion>", self._on_motion)
        self.bind("<Leave>", lambda e: self.delete("hover", "tip"))

    def draw(self, width, height):
        rows = self._rows
        if not rows:
            return
        font = theme.canvas_font(12, scale=self.s)
        strong = theme.canvas_font(12, True, self.s)
        text, muted = theme.pick(theme.TEXT), theme.pick(theme.MUTED)
        left = self.px(self._label_width)
        value_room = self.px(16) + max(len(r["text"]) for r in rows) * self.px(8)
        right = width - value_room
        top_value = max(r["value"] for r in rows)
        row_h, bar_h = self.px(self.ROW), self.px(14)
        self._hit = []
        for i, r in enumerate(rows):
            cy = self.px(4) + row_h * i + row_h / 2
            highlight = r.get("highlight", False)
            self.create_text(0, cy, text=r["label"], anchor="w",
                             font=strong if highlight else font, fill=text if highlight else muted)
            x2 = left + max(self.px(3), (right - left) * r["value"] / top_value)
            self.round_rect(left, cy - bar_h / 2, x2, cy + bar_h / 2, self.px(4), outline="",
                            fill=theme.pick(theme.PRIMARY if highlight else theme.BAR_QUIET))
            self.create_text(x2 + self.px(8), cy, text=r["text"], anchor="w",
                             font=strong if highlight else font, fill=text)
            self._hit.append((cy - row_h / 2, cy + row_h / 2, x2, cy, r.get("detail")))

    def _on_motion(self, event):
        self.delete("hover", "tip")
        for y1, y2, x2, cy, detail in self._hit:
            if y1 <= event.y < y2 and detail:
                self.tooltip(min(event.x, self.winfo_width() - 20), cy - self.px(6), detail)
                break


# ---------------------------------------------------------------------------
# Sign-in artwork: a street of homes, a few windows lit
# ---------------------------------------------------------------------------
class Skyline(Drawing):
    surface = theme.SIDEBAR

    # (x, width, height) as fractions of the canvas; kind decides the roof.
    BUILDINGS = [
        (0.00, 0.13, 0.46, "flat"), (0.13, 0.11, 0.30, "gable"), (0.24, 0.15, 0.78, "flat"),
        (0.39, 0.12, 0.38, "gable"), (0.51, 0.16, 0.60, "step"), (0.67, 0.10, 0.28, "gable"),
        (0.77, 0.13, 0.90, "flat"), (0.90, 0.10, 0.42, "gable"),
    ]
    LIT = {(0, 1, 0), (0, 2, 1), (2, 0, 1), (2, 3, 0), (2, 5, 2), (4, 1, 1), (4, 3, 2),
           (6, 1, 0), (6, 4, 1), (6, 6, 0), (6, 7, 1), (1, 0, 0), (3, 0, 1), (7, 1, 0)}

    def __init__(self, master, height: int = 230):
        super().__init__(master, height=height)

    def draw(self, width, height):
        line = theme.pick(theme.SIDEBAR_MUTED)
        lit = theme.pick(theme.ACCENT)
        base = height - self.px(2)
        w = max(1, self.px(1.4))
        for b, (fx, fw, fh, kind) in enumerate(self.BUILDINGS):
            x1, x2 = fx * width + 3, (fx + fw) * width - 3
            top = base - fh * (height - self.px(24))
            body_top = top
            if kind == "gable":
                body_top = top + (x2 - x1) * 0.32
                self.create_line(x1 - 4, body_top, (x1 + x2) / 2, top, x2 + 4, body_top,
                                 fill=line, width=w, joinstyle="round")
            elif kind == "step":
                mid = x1 + (x2 - x1) * 0.55
                step_top = top + (base - top) * 0.22
                self.create_line(x1, base, x1, top, mid, top, mid, step_top, x2, step_top,
                                 x2, base, fill=line, width=w, joinstyle="round")
            if kind != "step":
                self.create_line(x1, base, x1, body_top, x2, body_top, x2, base,
                                 fill=line, width=w, joinstyle="round")
            # windows
            cols = 2 if (x2 - x1) < self.px(70) else 3
            win_w = (x2 - x1) / (cols * 2 + 1)
            win_h = self.px(9)
            gap = self.px(22)
            start = (body_top if kind != "step" else top + (base - top) * 0.22) + self.px(14)
            row = 0
            y = start
            while y + win_h < base - self.px(22):
                for c in range(cols):
                    wx = x1 + win_w * (1 + 2 * c)
                    on = (b, row, c) in self.LIT
                    self.create_rectangle(wx, y, wx + win_w, y + win_h, outline=lit if on else line,
                                          fill=lit if on else "", width=1)
                row += 1
                y += gap
            # door
            dw = min(self.px(12), (x2 - x1) / 4)
            dx = (x1 + x2) / 2 - dw / 2
            self.create_line(dx, base, dx, base - self.px(16), dx + dw, base - self.px(16),
                             dx + dw, base, fill=line, width=w)
        self.create_line(0, base, width, base, fill=line, width=w)
