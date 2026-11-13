"""The four screens shown after signing in."""
from __future__ import annotations

import customtkinter as ctk

from .. import forecast
from ..formatting import axis_rupees, compact_rupees, group_indian, parse_amount, rupees
from ..service import MAX_AREA, MIN_AREA, OTHER_LABEL, Estimate, InputError
from . import theme
from .widgets import BarChart, LineChart, RangeGauge, SearchSelect

P = theme.PAD


def _page_header(master, title: str, subtitle: str) -> None:
    theme.label(master, title, 26, True).pack(anchor="w", padx=P, pady=(P, 0))
    theme.label(master, subtitle, 14, False, theme.MUTED).pack(anchor="w", padx=P, pady=(0, 16))


def _field(master, text: str, pady=(9, 2)) -> None:
    theme.label(master, text, 13, False, theme.MUTED).pack(anchor="w", padx=P, pady=pady)


# ---------------------------------------------------------------------------
# Home
# ---------------------------------------------------------------------------
class HomePage(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        _page_header(self, f"Hello, {app.user}",
                     "Three tools for thinking about the price of a home.")

        tools = ctk.CTkFrame(self, fg_color="transparent")
        tools.pack(fill="x", padx=P - 8)
        for column, (title, body, button, page) in enumerate([
            ("Estimate a price",
             "Pick a city and locality, enter the size, and get a price with its likely range.",
             "Estimate a price", "estimate"),
            ("Forecast a future value",
             "See what a property could be worth in a few years at a growth rate you choose.",
             "Forecast a value", "forecast"),
            ("Check the model",
             "See how accurate the estimates are and how prices compare across cities.",
             "Open market insights", "insights"),
        ]):
            tools.grid_columnconfigure(column, weight=1, uniform="tools")
            card = theme.card(tools)
            card.grid(row=0, column=column, sticky="nsew", padx=8)
            theme.label(card, title, 17, True).pack(anchor="w", padx=20, pady=(20, 6))
            maker = theme.primary_button if column == 0 else theme.quiet_button
            maker(card, button, lambda p=page: app.show(p), height=38).pack(
                side="bottom", anchor="w", padx=20, pady=(16, 20))
            theme.label(card, body, 13, False, theme.MUTED, wrap=True).pack(
                anchor="w", padx=20, fill="x")

        self.recent = theme.card(self)
        self.recent.pack(fill="both", expand=True, padx=P, pady=(20, P))
        theme.label(self.recent, "Recent estimates", 17, True).pack(anchor="w", padx=20, pady=(18, 2))
        self.rows = ctk.CTkScrollableFrame(self.recent, fg_color="transparent")
        self.rows.pack(fill="both", expand=True, padx=8, pady=(0, 10))
        for column, weight in enumerate((5, 3, 3, 5)):
            self.rows.grid_columnconfigure(column, weight=weight, uniform="recent")

    def on_show(self) -> None:
        for child in self.rows.winfo_children():
            child.destroy()
        history = self.app.history
        if not history:
            theme.label(
                self.rows,
                "No estimates yet. Estimates you make in this session are listed here.",
                14, False, theme.MUTED).grid(row=0, column=0, columnspan=4, sticky="w",
                                             padx=12, pady=14)
            return
        for column, text in enumerate(("Place", "Home", "Estimate", "Likely range")):
            theme.label(self.rows, text, 12, False, theme.MUTED).grid(
                row=0, column=column, sticky="w", padx=12, pady=(6, 2))
        for row, e in enumerate(reversed(history), start=1):
            cells = (e.place, f"{e.bhk} BHK, {group_indian(e.area_sqft)} sq ft",
                     compact_rupees(e.price),
                     f"{compact_rupees(e.low)} to {compact_rupees(e.high)}")
            for column, text in enumerate(cells):
                theme.label(self.rows, text, 14, column == 2).grid(
                    row=row, column=column, sticky="w", padx=12, pady=5)


# ---------------------------------------------------------------------------
# Estimate a price
# ---------------------------------------------------------------------------
class EstimatePage(ctk.CTkFrame):
    BEDROOMS = ["1", "2", "3", "4", "5", "6"]
    STATUS = ["Ready to move", "Under construction"]
    SALE = ["Resale", "New"]
    YES_NO = ["No", "Yes"]

    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.service = app.service
        self.current: Estimate | None = None
        _page_header(self, "Estimate a price",
                     "Describe the home. The estimate comes from listings of similar homes nearby.")

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=P - 8, pady=(0, P))
        body.grid_columnconfigure(0, weight=5, uniform="estimate")
        body.grid_columnconfigure(1, weight=6, uniform="estimate")
        body.grid_rowconfigure(0, weight=1)

        # -- form -------------------------------------------------------------
        form = theme.card(body)
        form.grid(row=0, column=0, sticky="nsew", padx=8)

        _field(form, "City", pady=(16, 2))
        self.city = SearchSelect(form, f"Type to search {len(self.service.cities())} cities",
                                 on_change=self._city_changed)
        self.city.pack(fill="x", padx=P)
        self.city.set_values(self.service.cities())

        _field(form, "Locality")
        self.locality = SearchSelect(form, "Choose a city first")
        self.locality.pack(fill="x", padx=P)
        self.locality.configure_state(False)

        _field(form, "Built-up area, in sq ft")
        self.area = theme.entry(form, f"{MIN_AREA:,} to {MAX_AREA:,}")
        self.area.pack(fill="x", padx=P)
        self.area.bind("<Return>", lambda e: self.submit())

        _field(form, "Bedrooms (BHK)")
        self.bhk = theme.segmented(form, self.BEDROOMS)
        self.bhk.pack(fill="x", padx=P)
        self.bhk.set("2")

        _field(form, "Construction status")
        self.status = theme.segmented(form, self.STATUS)
        self.status.pack(fill="x", padx=P)
        self.status.set(self.STATUS[0])

        pair = ctk.CTkFrame(form, fg_color="transparent")
        pair.pack(fill="x", padx=P, pady=(9, 0))
        for column, (text, values) in enumerate((("Sale type", self.SALE),
                                                 ("RERA registered", self.YES_NO))):
            pair.grid_columnconfigure(column, weight=1, uniform="pair")
            theme.label(pair, text, 13, False, theme.MUTED).grid(
                row=0, column=column, sticky="w", padx=(0 if column == 0 else 8, 0), pady=(0, 2))
            control = theme.segmented(pair, values)
            control.grid(row=1, column=column, sticky="ew",
                         padx=(0, 8) if column == 0 else (8, 0))
            control.set(values[0])
            if column == 0:
                self.sale = control
            else:
                self.rera = control

        actions = ctk.CTkFrame(form, fg_color="transparent")
        actions.pack(fill="x", padx=P, pady=(4, 16), side="bottom")
        self.error = theme.label(form, "", 13, False, theme.ERROR, wrap=True)
        self.error.pack(anchor="w", padx=P, pady=(0, 2), fill="x", side="bottom")

        self.button = theme.primary_button(actions, "Estimate price", self.submit)
        self.button.pack(side="left", fill="x", expand=True)
        theme.quiet_button(actions, "Clear", self.clear, width=84).pack(side="left", padx=(10, 0))

        # -- result -------------------------------------------------------------
        self.result = theme.card(body)
        self.result.grid(row=0, column=1, sticky="nsew", padx=8)

        self.empty = ctk.CTkFrame(self.result, fg_color="transparent")
        theme.label(self.empty, "Your estimate will appear here", 18, True,
                    anchor="center", justify="center").pack(pady=(0, 6))
        theme.label(self.empty,
                    "Choose a city and locality, enter the size,\nthen select Estimate price.",
                    14, False, theme.MUTED, anchor="center", justify="center").pack()

        self.filled = ctk.CTkFrame(self.result, fg_color="transparent")
        theme.label(self.filled, "Estimated price", 14, False, theme.MUTED).pack(
            anchor="w", padx=P - 6, pady=(16, 0))
        self.price = theme.label(self.filled, "", 46, True)
        self.price.pack(anchor="w", padx=P - 6)
        self.price_full = theme.label(self.filled, "", 14, False, theme.MUTED, wrap=True)
        self.price_full.pack(anchor="w", padx=P - 6, fill="x")

        self.gauge = RangeGauge(self.filled)
        self.gauge.pack(fill="x", padx=P - 16, pady=(18, 0))
        self.range_text = theme.label(self.filled, "", 13, False, theme.TEXT, wrap=True)
        self.range_text.pack(anchor="w", padx=P - 6, fill="x")

        theme.label(self.filled, "Price per sq ft", 13, True).pack(
            anchor="w", padx=P - 6, pady=(18, 4))
        stats = ctk.CTkFrame(self.filled, fg_color=theme.SURFACE_ALT, corner_radius=10)
        stats.pack(fill="x", padx=P - 6)
        self.stat_labels = []
        for column in range(3):
            stats.grid_columnconfigure(column, weight=1, uniform="stats")
            cell = ctk.CTkFrame(stats, fg_color="transparent")
            cell.grid(row=0, column=column, sticky="nsew", padx=(14, 4), pady=10)
            caption = theme.label(cell, "", 12, False, theme.MUTED)
            caption.pack(anchor="w")
            value = theme.label(cell, "", 17, True)
            value.pack(anchor="w")
            note = theme.label(cell, "", 12, False, theme.MUTED)
            note.pack(anchor="w")
            self.stat_labels.append((caption, value, note))

        self.note = theme.label(self.filled, "", 13, False, theme.MUTED, wrap=True)
        self.note.pack(anchor="w", padx=P - 6, pady=(12, 0), fill="x")

        theme.quiet_button(self.filled, "Forecast this price", self._to_forecast).pack(
            anchor="w", padx=P - 6, pady=(10, 14), side="bottom")

        self._show_result(None)

    # -- behaviour --------------------------------------------------------------
    def _city_changed(self, city) -> None:
        self.error.configure(text="")
        if city:
            self.locality.configure_state(True)
            self.locality.set_values(self.service.localities(city))
            named = len(self.service.localities(city)) - 1
            self.locality.entry.configure(
                placeholder_text=f"Type to search {named} localities" if named
                else f"Choose “{OTHER_LABEL}”")
        else:
            self.locality.set_values([])
            self.locality.entry.configure(placeholder_text="Choose a city first")
            self.locality.configure_state(False)

    def _mark(self, field: str | None) -> None:
        self.city.set_error(field == "city")
        self.locality.set_error(field == "locality")
        self.area.configure(border_color=theme.ERROR if field == "area" else theme.BORDER)

    def submit(self) -> None:
        self.error.configure(text="")
        self._mark(None)
        args = (self.city.get(), self.locality.get(), self.area.get(), self.bhk.get())
        try:
            self.service.validate(*args)
        except InputError as problem:
            self._fail(problem)
            return
        if not self.service.model_ready:
            self.button.configure(text="Loading the model…", state="disabled")
            self.after(150, self._wait_for_model)
            return
        self._estimate()

    def _wait_for_model(self) -> None:
        if self.app.model_error:
            self.button.configure(text="Estimate price", state="normal")
            self.error.configure(text=f"The model could not be loaded: {self.app.model_error}")
        elif self.service.model_ready:
            self.button.configure(text="Estimate price", state="normal")
            self._estimate()
        else:
            self.after(150, self._wait_for_model)

    def _estimate(self) -> None:
        try:
            estimate = self.service.estimate(
                self.city.get(), self.locality.get(), self.area.get(), self.bhk.get(),
                under_construction=self.status.get() == self.STATUS[1],
                rera=self.rera.get() == "Yes",
                resale=self.sale.get() == self.SALE[0])
        except InputError as problem:
            self._fail(problem)
            return
        except Exception as problem:            # model trouble: say so, do not crash
            self.error.configure(text=f"The estimate could not be made: {problem}")
            return
        self.app.add_estimate(estimate)
        self._show_result(estimate)

    def _fail(self, problem: InputError) -> None:
        self.error.configure(text=str(problem))
        self._mark(problem.field)
        target = {"city": self.city.focus_entry, "locality": self.locality.focus_entry,
                  "area": self.area.focus_set}.get(problem.field)
        if target:
            target()

    def clear(self) -> None:
        self.city.clear()
        self._city_changed(None)
        self.area.delete(0, "end")
        self.bhk.set("2")
        self.status.set(self.STATUS[0])
        self.sale.set(self.SALE[0])
        self.rera.set("No")
        self.error.configure(text="")
        self._mark(None)
        self._show_result(None)
        self.focus_set()

    def _show_result(self, e: Estimate | None) -> None:
        self.current = e
        if e is None:
            self.filled.pack_forget()
            self.empty.pack(expand=True)
            return
        self.empty.pack_forget()
        self.filled.pack(fill="both", expand=True, padx=6, pady=6)

        self.price.configure(text=compact_rupees(e.price))
        self.price_full.configure(
            text=f"{rupees(e.price)} for a {e.bhk} BHK, {group_indian(e.area_sqft)} sq ft home "
                 f"in {e.place}")
        self.gauge.show(e.low, e.price, e.high, compact_rupees(e.low), compact_rupees(e.high))
        share = round(e.coverage * 10)
        self.range_text.configure(
            text=f"Likely range {compact_rupees(e.low)} to {compact_rupees(e.high)}. "
                 f"About {share} in 10 comparable listings were priced inside this range.")

        stats = [("This estimate", f"{rupees(e.ppsf)}", "for this home")]
        if e.locality_median_ppsf:
            stats.append((f"{e.locality} median", rupees(e.locality_median_ppsf),
                          f"{e.locality_listings:,} listings"))
        else:
            stats.append(("Locality median", "No data", "not in the data"))
        stats.append((f"{e.city} median", rupees(e.city_median_ppsf),
                      f"{e.city_listings:,} listings"))
        for (caption, value, note), (c, v, n) in zip(self.stat_labels, stats):
            caption.configure(text=c if len(c) <= 18 else c[:17] + "…")
            value.configure(text=v)
            note.configure(text=n)

        if e.known_locality:
            self.note.configure(
                text="An estimate from asking prices in past listings, not a formal valuation.")
        else:
            self.note.configure(
                text=f"This locality is not in the data, so the estimate is based on the rest "
                     f"of {e.city} and its range is wider.")

    def _to_forecast(self) -> None:
        if self.current:
            self.app.pages["forecast"].prefill(self.current.price, self.current.city)
            self.app.show("forecast")


# ---------------------------------------------------------------------------
# Forecast a future value
# ---------------------------------------------------------------------------
class ForecastPage(ctk.CTkFrame):
    PRESET_PROMPT = "Fill in a past average"

    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        _page_header(self, "Forecast a future value",
                     "What a property would be worth if its price grew by the same rate every year.")

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=P - 8, pady=(0, P))
        body.grid_columnconfigure(0, weight=4, uniform="forecast")
        body.grid_columnconfigure(1, weight=7, uniform="forecast")
        body.grid_rowconfigure(0, weight=1)

        form = theme.card(body)
        form.grid(row=0, column=0, sticky="nsew", padx=8)

        _field(form, "Property value today, in rupees", pady=(20, 4))
        self.value = theme.entry(form, "78,50,000 or 78.5 lakh or 1.2 cr")
        self.value.pack(fill="x", padx=P)

        _field(form, "Growth per year, in percent")
        self.rate = theme.entry(form, "For example 8")
        self.rate.pack(fill="x", padx=P)

        self.preset = ctk.CTkOptionMenu(
            form, values=[f"{place}: {rate:g}%" for place, rate in forecast.HISTORICAL_GROWTH.items()],
            command=self._use_preset, font=theme.font(13), dropdown_font=theme.font(13),
            fg_color=theme.SURFACE_ALT, button_color=theme.SURFACE_ALT,
            button_hover_color=theme.BORDER, text_color=theme.TEXT, height=34, corner_radius=8,
            dropdown_fg_color=theme.SURFACE, dropdown_text_color=theme.TEXT,
            dropdown_hover_color=theme.SELECTED)
        self.preset.set(self.PRESET_PROMPT)
        self.preset.pack(fill="x", padx=P, pady=(8, 0))
        theme.label(form, "Past averages are for home prices from 2011 to 2021.",
                    12, False, theme.MUTED, wrap=True).pack(anchor="w", padx=P, pady=(4, 0), fill="x")

        self.years_label = theme.label(form, "", 13, False, theme.MUTED)
        self.years_label.pack(anchor="w", padx=P, pady=(16, 4))
        self.years = ctk.CTkSlider(
            form, from_=1, to=forecast.MAX_YEARS, number_of_steps=forecast.MAX_YEARS - 1,
            command=self._years_changed, progress_color=theme.PRIMARY, fg_color=theme.TRACK,
            button_color=theme.PRIMARY, button_hover_color=theme.PRIMARY_HOVER)
        self.years.set(10)
        self.years.pack(fill="x", padx=P - 4)
        self._years_changed(10)

        self.error = theme.label(form, "", 13, False, theme.ERROR, wrap=True)
        self.error.pack(anchor="w", padx=P, pady=(12, 0), fill="x")

        theme.primary_button(form, "Forecast value", self.submit).pack(
            fill="x", padx=P, pady=(6, 20), side="bottom")
        for widget in (self.value, self.rate):
            widget.bind("<Return>", lambda e: self.submit())

        # -- result -------------------------------------------------------------
        self.result = theme.card(body)
        self.result.grid(row=0, column=1, sticky="nsew", padx=8)
        self.empty = theme.label(
            self.result, "Enter a value and a growth rate\nto see the forecast.",
            15, False, theme.MUTED, anchor="center", justify="center")

        self.filled = ctk.CTkFrame(self.result, fg_color="transparent")
        self.caption = theme.label(self.filled, "", 14, False, theme.MUTED)
        self.caption.pack(anchor="w", padx=P - 6, pady=(16, 0))
        self.future = theme.label(self.filled, "", 40, True)
        self.future.pack(anchor="w", padx=P - 6)
        self.summary = theme.label(self.filled, "", 14, False, theme.MUTED, wrap=True)
        self.summary.pack(anchor="w", padx=P - 6, fill="x")
        self.chart = LineChart(self.filled, height=230, value_format=compact_rupees,
                               axis_format=axis_rupees)
        self.chart.pack(fill="x", padx=P - 14, pady=(10, 0))
        theme.label(self.filled, "Year by year", 13, True).pack(anchor="w", padx=P - 6, pady=(6, 0))
        self.table = ctk.CTkScrollableFrame(self.filled, fg_color="transparent", height=90)
        self.table.pack(fill="both", expand=True, padx=P - 18, pady=(0, 4))
        for column in range(3):
            self.table.grid_columnconfigure(column, weight=1, uniform="table")
        theme.label(self.filled,
                    "A fixed rate is a simplification: real prices rise and fall unevenly.",
                    12, False, theme.MUTED).pack(anchor="w", padx=P - 6, pady=(0, 10), side="bottom")

        self._show(None)

    def prefill(self, value: float, city: str | None = None) -> None:
        self.value.delete(0, "end")
        self.value.insert(0, group_indian(round(value)))
        self.error.configure(text="")
        if self.rate.get().strip():
            self.submit()
        else:
            self._show(None)
            self.rate.focus_set()

    def _use_preset(self, choice: str) -> None:
        rate = choice.split(":")[1].strip().rstrip("%")
        self.rate.delete(0, "end")
        self.rate.insert(0, rate)
        self.preset.set(self.PRESET_PROMPT)

    def _years_changed(self, value) -> None:
        years = int(round(float(value)))
        self.years_label.configure(text=f"Years ahead: {years}")

    def submit(self) -> None:
        self.error.configure(text="")
        self.value.configure(border_color=theme.BORDER)
        self.rate.configure(border_color=theme.BORDER)
        try:
            present = parse_amount(self.value.get())
        except ValueError:
            self.value.configure(border_color=theme.ERROR)
            self.error.configure(text="Enter today's value as a number, for example 78,50,000 or 78.5 lakh.")
            self.value.focus_set()
            self._show(None)
            return
        try:
            rate = float(self.rate.get().replace("%", "").strip())
        except ValueError:
            self.rate.configure(border_color=theme.ERROR)
            self.error.configure(text="Enter the yearly growth as a number, for example 8.")
            self.rate.focus_set()
            self._show(None)
            return
        try:
            result = forecast.project(present, rate, int(round(self.years.get())))
        except ValueError as problem:
            self.error.configure(text=str(problem))
            self._show(None)
            return
        self._show(result)

    def _show(self, f: forecast.Forecast | None) -> None:
        if f is None:
            self.filled.pack_forget()
            self.empty.pack(expand=True)
            return
        self.empty.pack_forget()
        self.filled.pack(fill="both", expand=True, padx=6, pady=6)
        plural = "s" if f.years != 1 else ""
        self.caption.configure(text=f"Value after {f.years} year{plural} at {f.rate_pct:g}% a year")
        self.future.configure(text=compact_rupees(f.future_value))
        direction = "more" if f.gain >= 0 else "less"
        self.summary.configure(
            text=f"{rupees(f.future_value)}. That is {compact_rupees(abs(f.gain))} {direction} than "
                 f"today's {compact_rupees(f.present_value)}, or {f.multiple:.2f} times the value.")
        self.chart.show(f.values)
        for child in self.table.winfo_children():
            child.destroy()
        per_column = -(-f.years // 3)
        for i in range(1, f.years + 1):
            column, row = (i - 1) // per_column, (i - 1) % per_column
            cell = ctk.CTkFrame(self.table, fg_color="transparent")
            cell.grid(row=row, column=column, sticky="ew", padx=10, pady=1)
            theme.label(cell, f"Year {i}", 12, False, theme.MUTED, width=52).pack(side="left")
            theme.label(cell, compact_rupees(f.values[i]), 13).pack(side="left")


# ---------------------------------------------------------------------------
# Market insights
# ---------------------------------------------------------------------------
class InsightsPage(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        service = app.service
        metrics, catalog = service.metrics, service.catalog
        _page_header(self, "Market insights",
                     "How good the estimates are, and how prices compare across cities.")
        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=P - 14, pady=(0, 8))

        if not metrics:
            theme.label(scroll, "No model report found. Run  python -m ml.train  to create it.",
                        14, False, theme.MUTED).pack(anchor="w", padx=14, pady=14)
            return

        models = metrics["models"]
        chosen, baseline = models[metrics["chosen"]], models[metrics["baseline"]]
        groups = metrics["by_locality_type"]

        # -- accuracy ---------------------------------------------------------
        card = theme.card(scroll)
        card.pack(fill="x", padx=8, pady=(0, 16))
        theme.label(card, "How accurate are the estimates?", 17, True).pack(
            anchor="w", padx=20, pady=(18, 0))
        theme.label(
            card,
            f"Each of the {metrics['dataset']['rows']:,} listings was estimated by a model that "
            "had not seen it, and the estimate was compared with the listed price.",
            13, False, theme.MUTED, wrap=True).pack(anchor="w", padx=20, fill="x")
        tiles = ctk.CTkFrame(card, fg_color="transparent")
        tiles.pack(fill="x", padx=12, pady=(12, 6))
        for column, (value, caption) in enumerate([
            (f"{chosen['median_error_pct']:.0f}%", "typical gap between estimate and listed price"),
            (f"{chosen['within_20_pct']:.0f}%", "of estimates land within 20% of the listed price"),
            (f"{chosen['r2']:.2f}", "R² score, where 1.00 would be perfect"),
            (f"{metrics['dataset']['cities']}",
             f"cities in the data, {len(catalog['cities'])} with enough listings to offer"),
        ]):
            tiles.grid_columnconfigure(column, weight=1, uniform="tiles")
            tile = ctk.CTkFrame(tiles, fg_color=theme.SURFACE_ALT, corner_radius=10)
            tile.grid(row=0, column=column, sticky="nsew", padx=8)
            theme.label(tile, value, 30, True).pack(anchor="w", padx=16, pady=(12, 0))
            theme.label(tile, caption, 12, False, theme.MUTED, wrap=True).pack(
                anchor="w", padx=16, pady=(0, 12), fill="x")
        theme.label(
            card,
            f"In the {metrics['dataset']['named_localities']:,} localities the model knows by name, "
            f"the typical gap is {groups['listed']['median_error_pct']:.0f}%. For homes elsewhere in "
            f"a city it is {groups['other']['median_error_pct']:.0f}%, which is why those estimates "
            "come with a wider range.",
            13, False, theme.TEXT, wrap=True).pack(anchor="w", padx=20, pady=(8, 18), fill="x")

        # -- model comparison ---------------------------------------------------
        card = theme.card(scroll)
        card.pack(fill="x", padx=8, pady=(0, 16))
        theme.label(card, "Typical error of each model tried", 17, True).pack(
            anchor="w", padx=20, pady=(18, 0))
        theme.label(card, "Median gap between estimate and listed price. Shorter is better.",
                    13, False, theme.MUTED).pack(anchor="w", padx=20)
        rows = [{
            "label": name.replace(" (chosen)", ""),
            "value": m["median_error_pct"],
            "text": f"{m['median_error_pct']:.1f}%",
            "highlight": name == metrics["chosen"],
            "detail": f"R² {m['r2']:.2f}, {m['within_20_pct']:.0f}% of estimates within 20%",
        } for name, m in models.items()]
        BarChart(card, rows, label_width=270).pack(fill="x", padx=20, pady=(10, 4))
        forest = models.get("Random forest")
        extra = ""
        if forest:
            extra = (" A random forest scores about the same; gradient boosting was kept because "
                     "it can guarantee that a larger home never gets a lower estimate, and it "
                     "trains faster.")
        theme.label(
            card,
            f"The first version of this project used linear regression on a 506-row dataset. On "
            f"this data a linear model is off by {baseline['median_error_pct']:.0f}% on a typical "
            f"home; gradient boosting is off by {chosen['median_error_pct']:.0f}%." + extra,
            13, False, theme.TEXT, wrap=True).pack(anchor="w", padx=20, pady=(4, 18), fill="x")

        # -- cities ---------------------------------------------------------------
        card = theme.card(scroll)
        card.pack(fill="x", padx=8, pady=(0, 16))
        theme.label(card, "Median price per sq ft in the 12 cities with most listings", 17, True).pack(
            anchor="w", padx=20, pady=(18, 0))
        theme.label(card, "Point at a bar for the number of listings and the median home price.",
                    13, False, theme.MUTED).pack(anchor="w", padx=20)
        biggest = sorted(catalog["cities"].items(), key=lambda kv: -kv[1]["listings"])[:12]
        rows = [{
            "label": city,
            "value": info["median_ppsf"],
            "text": rupees(info["median_ppsf"]),
            "detail": f"{info['listings']:,} listings, median home {compact_rupees(info['median_price'])}",
        } for city, info in sorted(biggest, key=lambda kv: -kv[1]["median_ppsf"])]
        BarChart(card, rows, label_width=130).pack(fill="x", padx=20, pady=(10, 18))

        # -- data -------------------------------------------------------------------
        card = theme.card(scroll)
        card.pack(fill="x", padx=8, pady=(0, 16))
        theme.label(card, "About the data", 17, True).pack(anchor="w", padx=20, pady=(18, 4))
        theme.label(
            card,
            f"{catalog['total_listings']:,} property listings from across India (the MachineHack "
            "House Price Prediction Challenge data), after removing duplicates and impossible "
            "rows. Prices are asking prices from one period, so they can differ from sale prices "
            "and from prices today. Delhi and Hyderabad are not listed as cities; nearby Noida, "
            "Gurgaon, Ghaziabad, Faridabad and Secunderabad are.",
            13, False, theme.TEXT, wrap=True).pack(anchor="w", padx=20, pady=(0, 18), fill="x")

    def on_show(self) -> None:
        pass
