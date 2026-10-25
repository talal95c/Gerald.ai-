import json

from PyQt6.QtCore import QRect
from PyQt6.QtGui import QImage, QPainter

from gerald.home.agents import agents_path, load_mascot, save_mascot
from gerald.home.mascots import (
    DEFAULT_MASCOT,
    MASCOTS,
    MascotWidget,
    paint_mascot,
)


def test_mascot_persistence_round_trip(monkeypatch, tmp_path):
    monkeypatch.setenv("GERALD_HOME", str(tmp_path))

    assert load_mascot() == DEFAULT_MASCOT
    save_mascot("zoe")

    assert json.loads(agents_path().read_text(encoding="utf-8")) == {
        "mascot": "zoe"
    }
    assert load_mascot() == "zoe"


def test_corrupt_or_invalid_mascot_data_defaults_to_gerald(monkeypatch, tmp_path):
    monkeypatch.setenv("GERALD_HOME", str(tmp_path))
    path = agents_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    path.write_text("{", encoding="utf-8")
    assert load_mascot() == DEFAULT_MASCOT

    path.write_text('{"mascot": []}', encoding="utf-8")
    assert load_mascot() == DEFAULT_MASCOT


def test_each_fixed_mascot_paints_non_empty_pixels():
    for mascot in MASCOTS:
        image = QImage(128, 128, QImage.Format.Format_ARGB32)
        image.fill(0)
        painter = QPainter(image)
        paint_mascot(painter, mascot.id, QRect(0, 0, 128, 128))
        painter.end()

        assert any(
            image.pixelColor(x, y).alpha() > 0
            for y in range(image.height())
            for x in range(image.width())
        ), mascot.id


def test_mascot_idle_animation_respects_reduced_motion(monkeypatch):
    monkeypatch.setenv("GERALD_REDUCE_MOTION", "1")
    widget = MascotWidget("alba", animate=True)

    assert widget._lift_animation is None
    widget.close()
