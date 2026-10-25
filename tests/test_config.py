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


def test_cursor_and_proactive_settings_default_on_and_can_be_disabled(monkeypatch):
    monkeypatch.delenv("GERALD_CURSOR", raising=False)
    monkeypatch.delenv("GERALD_PROACTIVE", raising=False)
    settings = load_settings()
    assert settings.cursor_enabled is True
    assert settings.proactive_enabled is True

    monkeypatch.setenv("GERALD_CURSOR", "0")
    monkeypatch.setenv("GERALD_PROACTIVE", "false")
    settings = load_settings()
    assert settings.cursor_enabled is False
    assert settings.proactive_enabled is False
