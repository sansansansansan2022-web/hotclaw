"""Startup safety guard tests."""

from app import main


def test_single_worker_startup_features_are_off_by_default_in_production(monkeypatch):
    monkeypatch.setattr(main.settings, "app_env", "production")

    assert main._single_worker_startup_default_enabled() is False


def test_single_worker_startup_features_are_on_by_default_for_development(monkeypatch):
    monkeypatch.setattr(main.settings, "app_env", "development")

    assert main._single_worker_startup_default_enabled() is True
