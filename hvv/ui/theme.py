"""Colours, type and spacing shared by every screen.

Every colour is a (light, dark) pair, which customtkinter switches
automatically. Canvas drawings (charts, the gauge) call ``pick`` instead.
"""
from __future__ import annotations

import sys
import tkinter as tk
import tkinter.font as tkfont

import customtkinter as ctk

from .. import paths

# -- colour ------------------------------------------------------------------
BG = ("#EDF1F5", "#0E1620")            # window background
SURFACE = ("#FFFFFF", "#172230")       # cards
SURFACE_ALT = ("#F4F7FA", "#1D2A3A")   # inputs, quiet panels
BORDER = ("#D3DBE4", "#2C3B4D")
TEXT = ("#14202E", "#E6ECF2")
MUTED = ("#566373", "#9AA8B8")
SIDEBAR = ("#12263F", "#0A121C")       # survey-ink navy
SIDEBAR_TEXT = ("#DCE6F2", "#DCE6F2")
SIDEBAR_MUTED = ("#8FA3BC", "#8FA3BC")
SIDEBAR_ACTIVE = ("#21405F", "#1B2B3F")
PRIMARY = ("#0F6E6E", "#2FA39B")       # teal: every action
PRIMARY_HOVER = ("#0B5757", "#3DB6AE")
ON_PRIMARY = ("#FFFFFF", "#04201F")
ACCENT = ("#E39E12", "#F2B63C")        # marigold: the estimate, nothing else
ERROR = ("#B93232", "#F28B8B")
SELECTED = ("#BFE3DF", "#1F5F5C")      # chosen segment: tinted, keeps normal text
SELECTED_HOVER = ("#A9D8D3", "#277571")
TRACK = ("#DCE3EB", "#2A394B")         # gauge and bar backgrounds
BAR_QUIET = ("#9FB0C3", "#56687D")     # non-highlighted bars

PAD = 24
RADIUS = 12


def pick(pair: tuple[str, str]) -> str:
    """The light or dark member of a colour pair, for plain tkinter widgets."""
    return pair[1] if ctk.get_appearance_mode() == "Dark" else pair[0]


# -- type ----------------------------------------------------------------------
_family = None          # body family
_semibold = None        # (family, weight) used for headings and numbers


def load_fonts() -> None:
    """Register the bundled Poppins files. Call once, after the window exists."""
    global _family, _semibold
    for name in ("Poppins-Regular.ttf", "Poppins-Medium.ttf", "Poppins-SemiBold.ttf"):
        try:
            ctk.FontManager.load_font(str(paths.FONTS_DIR / name))
        except Exception:
            pass
    families = set(tkfont.families())
    if "Poppins" in families:
        _family = "Poppins"
        # Windows lists the semi-bold cut as its own family; Linux folds it
        # into "Poppins" and picks it when bold is requested.
        _semibold = ("Poppins SemiBold", "normal") if "Poppins SemiBold" in families \
            else ("Poppins", "bold")
    else:  # macOS cannot load private fonts this way: use the system face
        _family = {"win32": "Segoe UI", "darwin": "Helvetica Neue"}.get(sys.platform, "DejaVu Sans")
        _semibold = (_family, "bold")


def font(size: int = 13, strong: bool = False) -> ctk.CTkFont:
    if _family is None:
        load_fonts()
    if strong:
        return ctk.CTkFont(family=_semibold[0], size=size, weight=_semibold[1])
    return ctk.CTkFont(family=_family, size=size)


def canvas_font(size: int, strong: bool = False, scale: float = 1.0) -> tuple:
    """Font tuple for canvas text; negative size means pixels."""
    if _family is None:
        load_fonts()
    px = -max(1, round(size * scale))
    return (_semibold[0], px, _semibold[1]) if strong else (_family, px)


# -- small factories ---------------------------------------------------------------
def card(master, **kwargs) -> ctk.CTkFrame:
    options = dict(fg_color=SURFACE, corner_radius=RADIUS, border_width=1, border_color=BORDER)
    options.update(kwargs)
    return ctk.CTkFrame(master, **options)


def label(master, text="", size=13, strong=False, color=TEXT, wrap=False, **kwargs) -> ctk.CTkLabel:
    """A text label. With wrap=True (and packed with fill="x") the text re-wraps
    to whatever width the label is given, so nothing is cut off in a small window."""
    options = dict(text=text, font=font(size, strong), text_color=color, anchor="w", justify="left")
    options.update(kwargs)
    widget = ctk.CTkLabel(master, **options)
    if wrap:
        state = {"width": 0}

        def rewrap(event):
            if event.widget is not widget:
                return
            width = int(event.width / ctk.ScalingTracker.get_widget_scaling(widget)) - 2
            if width > 40 and abs(width - state["width"]) > 3:
                state["width"] = width
                widget.configure(wraplength=width)

        tk.Frame.bind(widget, "<Configure>", rewrap, add="+")
    return widget


def primary_button(master, text, command, **kwargs) -> ctk.CTkButton:
    options = dict(text=text, command=command, height=40, corner_radius=8,
                   font=font(14, True), fg_color=PRIMARY, hover_color=PRIMARY_HOVER,
                   text_color=ON_PRIMARY, text_color_disabled=MUTED)
    options.update(kwargs)
    return ctk.CTkButton(master, **options)


def quiet_button(master, text, command, **kwargs) -> ctk.CTkButton:
    options = dict(text=text, command=command, height=40, corner_radius=8,
                   font=font(14), fg_color=SURFACE_ALT, hover_color=BORDER,
                   text_color=TEXT, border_width=1, border_color=BORDER)
    options.update(kwargs)
    return ctk.CTkButton(master, **options)


def entry(master, placeholder="", **kwargs) -> ctk.CTkEntry:
    options = dict(placeholder_text=placeholder, height=38, corner_radius=8,
                   font=font(14), fg_color=SURFACE_ALT, border_color=BORDER,
                   border_width=1, text_color=TEXT, placeholder_text_color=MUTED)
    options.update(kwargs)
    return ctk.CTkEntry(master, **options)


def segmented(master, values, **kwargs) -> ctk.CTkSegmentedButton:
    options = dict(values=values, height=36, corner_radius=8, font=font(13),
                   fg_color=SURFACE_ALT, selected_color=SELECTED,
                   selected_hover_color=SELECTED_HOVER, unselected_color=SURFACE_ALT,
                   unselected_hover_color=BORDER, text_color=TEXT,
                   dynamic_resizing=False)
    options.update(kwargs)
    return ctk.CTkSegmentedButton(master, **options)
