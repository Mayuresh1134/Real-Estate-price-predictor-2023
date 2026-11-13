"""The first screen: sign in or create an account."""
from __future__ import annotations

import customtkinter as ctk

from ..auth import MIN_PASSWORD_LENGTH, AuthError, UserStore
from . import theme
from .widgets import Skyline


class AuthView(ctk.CTkFrame):
    def __init__(self, master, store: UserStore, on_signed_in, listings: int, cities: int):
        super().__init__(master, fg_color=theme.BG, corner_radius=0)
        self.store = store
        self.on_signed_in = on_signed_in
        self.mode = "sign_in"

        self.grid_columnconfigure(0, weight=5, uniform="auth")
        self.grid_columnconfigure(1, weight=6, uniform="auth")
        self.grid_rowconfigure(0, weight=1)

        # -- left: what this is -------------------------------------------------
        left = ctk.CTkFrame(self, fg_color=theme.SIDEBAR, corner_radius=0)
        left.grid(row=0, column=0, sticky="nsew")
        theme.label(left, "HomeValueVision", 18, True, theme.SIDEBAR_TEXT).pack(
            anchor="w", padx=44, pady=(40, 0))
        theme.label(left, "What is this\nhome worth?", 38, True, theme.SIDEBAR_TEXT).pack(
            anchor="w", padx=44, pady=(70, 14))
        theme.label(
            left,
            f"Price estimates for homes in {cities} Indian cities,\n"
            f"learned from {listings:,} property listings.",
            15, False, theme.SIDEBAR_MUTED).pack(anchor="w", padx=44)
        Skyline(left).pack(side="bottom", fill="x", padx=0, pady=(0, 0))

        # -- right: the form ----------------------------------------------------
        right = ctk.CTkFrame(self, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew")
        form = ctk.CTkFrame(right, fg_color="transparent")
        form.place(relx=0.5, rely=0.5, anchor="center")
        ctk.CTkFrame(form, fg_color="transparent", width=380, height=1).pack()   # sets the width

        self.title = theme.label(form, "", 28, True)
        self.title.pack(anchor="w")
        self.subtitle = theme.label(form, "", 14, False, theme.MUTED, wraplength=380)
        self.subtitle.pack(anchor="w", pady=(2, 22))

        theme.label(form, "Username", 13, False, theme.MUTED).pack(anchor="w")
        self.username = theme.entry(form, height=42)
        self.username.pack(fill="x", pady=(4, 14))

        theme.label(form, "Password", 13, False, theme.MUTED).pack(anchor="w")
        self.password = theme.entry(form, height=42, show="•")
        self.password.pack(fill="x", pady=(4, 0))

        self.confirm_label = theme.label(form, "Type the password again", 13, False, theme.MUTED)
        self.confirm = theme.entry(form, height=42, show="•")

        self.show_password = ctk.CTkCheckBox(
            form, text="Show password", font=theme.font(13), text_color=theme.MUTED,
            fg_color=theme.PRIMARY, hover_color=theme.PRIMARY_HOVER, border_color=theme.BORDER,
            checkbox_width=18, checkbox_height=18, border_width=2, corner_radius=4,
            command=self._toggle_show)

        self.message = theme.label(form, "", 13, False, theme.ERROR, wraplength=380)

        self.submit = theme.primary_button(form, "", self._submit, height=44)
        self.switch_row = ctk.CTkFrame(form, fg_color="transparent")
        self.switch_text = theme.label(self.switch_row, "", 13, False, theme.MUTED)
        self.switch_text.pack(side="left")
        self.switch = ctk.CTkButton(
            self.switch_row, text="", command=self._switch_mode, font=theme.font(13, True),
            fg_color="transparent", hover_color=theme.SURFACE_ALT, text_color=theme.PRIMARY,
            width=10, height=28, corner_radius=6)
        self.switch.pack(side="left", padx=(4, 0))

        for widget in (self.username, self.password, self.confirm):
            widget.bind("<Return>", lambda e: self._submit())

        # First run: nobody has an account yet, so start on "create account".
        try:
            if not self.store.has_accounts():
                self.mode = "sign_up"
        except AuthError:
            pass
        self._layout()
        self.after(100, self.username.focus_set)

    # -- layout for the two modes ---------------------------------------------
    def _layout(self) -> None:
        signing_up = self.mode == "sign_up"
        for widget in (self.confirm_label, self.confirm, self.show_password, self.message,
                       self.submit, self.switch_row):
            widget.pack_forget()
        if signing_up:
            self.title.configure(text="Create your account")
            self.subtitle.configure(
                text=f"Accounts stay on this computer. Use {MIN_PASSWORD_LENGTH}+ characters "
                     "for the password.")
            self.confirm_label.pack(anchor="w", pady=(14, 0))
            self.confirm.pack(fill="x", pady=(4, 0))
            self.submit.configure(text="Create account")
            self.switch_text.configure(text="Already have an account?")
            self.switch.configure(text="Sign in")
        else:
            self.title.configure(text="Sign in")
            self.subtitle.configure(text="Welcome back.")
            self.submit.configure(text="Sign in")
            self.switch_text.configure(text="New here?")
            self.switch.configure(text="Create an account")
        self.show_password.pack(anchor="w", pady=(12, 0))
        self.message.pack(anchor="w", pady=(10, 0))
        self.submit.pack(fill="x", pady=(8, 14))
        self.switch_row.pack(anchor="w")
        self._set_message("")

    def _switch_mode(self) -> None:
        self.mode = "sign_in" if self.mode == "sign_up" else "sign_up"
        self.password.delete(0, "end")
        self.confirm.delete(0, "end")
        self._layout()
        self.username.focus_set()

    def _toggle_show(self) -> None:
        show = "" if self.show_password.get() else "•"
        self.password.configure(show=show)
        self.confirm.configure(show=show)

    def _set_message(self, text: str) -> None:
        self.message.configure(text=text)

    def _submit(self) -> None:
        username, password = self.username.get(), self.password.get()
        if not username.strip() or not password:
            self._set_message("Enter a username and a password.")
            return
        try:
            if self.mode == "sign_up":
                self.store.register(username, password, self.confirm.get())
            name = self.store.sign_in(username, password)
        except AuthError as problem:
            self._set_message(str(problem))
            return
        self.on_signed_in(name)
