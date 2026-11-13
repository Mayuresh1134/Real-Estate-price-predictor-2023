"""The application window: sign-in first, then a sidebar and four pages."""
from __future__ import annotations

import json
import threading

import customtkinter as ctk

from .. import paths
from ..auth import UserStore
from ..service import Estimate, PriceService
from . import theme
from .auth_view import AuthView
from .pages import EstimatePage, ForecastPage, HomePage, InsightsPage

NAV = [("home", "Home"), ("estimate", "Estimate a price"),
       ("forecast", "Forecast a value"), ("insights", "Market insights")]


def _read_settings() -> dict:
    try:
        return json.loads(paths.SETTINGS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _write_settings(settings: dict) -> None:
    try:
        paths.APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
        paths.SETTINGS_FILE.write_text(json.dumps(settings, indent=2), encoding="utf-8")
    except OSError:
        pass


class App(ctk.CTk):
    def __init__(self):
        self.settings = _read_settings()
        ctk.set_appearance_mode(self.settings.get("appearance", "Light"))
        super().__init__(fg_color=theme.BG)
        self.title("HomeValueVision")
        width, height = 1180, 720
        # On a small or heavily zoomed screen, shrink the whole interface to fit.
        dpi = ctk.ScalingTracker.get_window_scaling(self)
        fit = min(1.0, (self.winfo_screenwidth() / dpi - 40) / width,
                  (self.winfo_screenheight() / dpi - 110) / height)
        if fit < 1.0:
            fit = max(0.7, round(fit, 2))
            ctk.set_widget_scaling(fit)
            ctk.set_window_scaling(fit)
        shown = dpi * min(fit, 1.0)
        x = max(0, int((self.winfo_screenwidth() - width * shown) / 2))
        y = max(0, int((self.winfo_screenheight() - height * shown) / 3))
        self.geometry(f"{width}x{height}+{x}+{y}")
        self.minsize(1040, 680)
        theme.load_fonts()

        self.store = UserStore(paths.USERS_FILE)
        self.service = PriceService()
        self.model_error: str | None = None
        self.user: str | None = None
        self.history: list[Estimate] = []
        self.pages: dict[str, ctk.CTkFrame] = {}
        self.nav_buttons: dict[str, ctk.CTkButton] = {}
        self.shell: ctk.CTkFrame | None = None
        self.auth: AuthView | None = None

        # scikit-learn takes a moment to import; do it while the person signs in.
        threading.Thread(target=self._load_model, daemon=True).start()
        self._show_auth()

    def _load_model(self) -> None:
        try:
            self.service.load_model()
        except Exception as problem:
            self.model_error = str(problem) or problem.__class__.__name__

    # -- sign in / out --------------------------------------------------------
    def _show_auth(self) -> None:
        catalog = self.service.catalog
        self.auth = AuthView(self, self.store, self._signed_in,
                             listings=catalog["total_listings"], cities=len(catalog["cities"]))
        self.auth.pack(fill="both", expand=True)

    def _signed_in(self, name: str) -> None:
        self.user = name
        self.history = []
        self.auth.destroy()
        self.auth = None
        self._build_shell()
        self.show("home")

    def sign_out(self) -> None:
        self.shell.destroy()
        self.shell, self.pages, self.nav_buttons, self.user = None, {}, {}, None
        self._show_auth()

    # -- main layout -------------------------------------------------------------
    def _build_shell(self) -> None:
        self.shell = ctk.CTkFrame(self, fg_color=theme.BG, corner_radius=0)
        self.shell.pack(fill="both", expand=True)

        side = ctk.CTkFrame(self.shell, fg_color=theme.SIDEBAR, corner_radius=0, width=232)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        theme.label(side, "HomeValueVision", 18, True, theme.SIDEBAR_TEXT).pack(
            anchor="w", padx=22, pady=(26, 22))
        for key, text in NAV:
            button = ctk.CTkButton(
                side, text=text, anchor="w", height=42, corner_radius=8, font=theme.font(14),
                fg_color="transparent", hover_color=theme.SIDEBAR_ACTIVE,
                text_color=theme.SIDEBAR_TEXT, command=lambda k=key: self.show(k))
            button.pack(fill="x", padx=12, pady=2)
            self.nav_buttons[key] = button

        ctk.CTkButton(
            side, text="Sign out", height=38, corner_radius=8, font=theme.font(13),
            fg_color="transparent", hover_color=theme.SIDEBAR_ACTIVE, border_width=1,
            border_color=theme.SIDEBAR_ACTIVE, text_color=theme.SIDEBAR_TEXT,
            command=self.sign_out).pack(side="bottom", fill="x", padx=16, pady=(8, 20))
        theme.label(side, f"Signed in as {self.user}", 12, False, theme.SIDEBAR_MUTED).pack(
            side="bottom", anchor="w", padx=20)
        mode = ctk.CTkSegmentedButton(
            side, values=["Light", "Dark"], command=self._set_appearance, height=32,
            corner_radius=8, font=theme.font(12), fg_color=theme.SIDEBAR_ACTIVE,
            selected_color=("#3A5D85", "#34506F"), selected_hover_color=("#44699A", "#3D5C80"),
            unselected_color=theme.SIDEBAR_ACTIVE, unselected_hover_color=("#2A4C70", "#243A53"),
            text_color=theme.SIDEBAR_TEXT, dynamic_resizing=False)
        mode.set(ctk.get_appearance_mode())
        mode.pack(side="bottom", fill="x", padx=16, pady=(0, 16))
        theme.label(side, "Appearance", 12, False, theme.SIDEBAR_MUTED).pack(
            side="bottom", anchor="w", padx=20, pady=(0, 4))

        content = ctk.CTkFrame(self.shell, fg_color="transparent")
        content.pack(side="left", fill="both", expand=True)
        content.grid_rowconfigure(0, weight=1)
        content.grid_columnconfigure(0, weight=1)
        for key, page_class in (("home", HomePage), ("estimate", EstimatePage),
                                ("forecast", ForecastPage), ("insights", InsightsPage)):
            page = page_class(content, self)
            page.grid(row=0, column=0, sticky="nsew")
            self.pages[key] = page

    def show(self, key: str) -> None:
        page = self.pages[key]
        if hasattr(page, "on_show"):
            page.on_show()
        page.tkraise()
        for name, button in self.nav_buttons.items():
            active = name == key
            button.configure(fg_color=theme.SIDEBAR_ACTIVE if active else "transparent",
                             font=theme.font(14, active))

    def add_estimate(self, estimate: Estimate) -> None:
        self.history.append(estimate)
        del self.history[:-20]

    def _set_appearance(self, mode: str) -> None:
        ctk.set_appearance_mode(mode)
        self.settings["appearance"] = mode
        _write_settings(self.settings)


def run() -> None:
    App().mainloop()
