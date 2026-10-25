from gerald.config import load_settings


def test_ocr_budget_defaults_to_two_and_a_half_seconds(monkeypatch):
    monkeypatch.delenv("GERALD_OCR_BUDGET", raising=False)

    assert load_settings().ocr_budget == 2.5


def test_ocr_budget_can_be_configured(monkeypatch):
    monkeypatch.setenv("GERALD_OCR_BUDGET", "1.75")

    assert load_settings().ocr_budget == 1.75


def test_computer_action_confirmation_is_enabled_by_default(monkeypatch):
    monkeypatch.delenv("GERALD_REQUIRE_CONFIRMATION", raising=False)

    assert load_settings().require_confirmation is True


def test_computer_action_confirmation_can_be_disabled(monkeypatch):
    monkeypatch.setenv("GERALD_REQUIRE_CONFIRMATION", "0")

    assert load_settings().require_confirmation is False
