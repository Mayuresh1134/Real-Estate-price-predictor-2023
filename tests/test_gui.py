"""Opens the real window and clicks through it. Skipped where there is no display."""
import tkinter as tk

import pytest


@pytest.fixture
def app(tmp_path, monkeypatch):
    try:
        probe = tk.Tk()
        probe.destroy()
    except tk.TclError:
        pytest.skip("no display available")
    from hvv import paths
    monkeypatch.setattr(paths, "APP_DATA_DIR", tmp_path)
    monkeypatch.setattr(paths, "USERS_FILE", tmp_path / "users.json")
    monkeypatch.setattr(paths, "SETTINGS_FILE", tmp_path / "settings.json")
    from hvv.ui.app import App
    window = App()
    window.update()
    yield window
    try:
        window.destroy()
    except tk.TclError:
        pass


def test_sign_up_estimate_and_forecast(app):
    auth = app.auth
    assert auth.mode == "sign_up"                  # first run: no accounts yet
    auth.username.insert(0, "Tester")
    auth.password.insert(0, "password1")
    auth.confirm.insert(0, "password1")
    auth._submit()
    app.update()
    assert app.user == "Tester"

    app.service.load_model()
    app.show("estimate")
    page = app.pages["estimate"]
    page.submit()                                  # nothing filled in yet
    assert "city" in page.error.cget("text").lower()

    page.city._commit("Pune")
    assert page.locality.get() is None and len(page.locality._values) > 10
    page.locality._commit(page.locality._values[0])
    page.area.insert(0, "1000")
    page.submit()
    app.update()
    assert page.current is not None and page.current.low < page.current.price < page.current.high
    assert app.history == [page.current]

    page._to_forecast()
    forecast_page = app.pages["forecast"]
    forecast_page.rate.insert(0, "8")
    forecast_page.submit()
    app.update()
    assert forecast_page.future.cget("text").startswith("₹")

    for name in ("home", "insights", "forecast", "estimate"):
        app.show(name)
        app.update()
    app._set_appearance("Dark")
    app.update()
    app.sign_out()
    app.update()
    assert app.user is None and app.auth.mode == "sign_in"
