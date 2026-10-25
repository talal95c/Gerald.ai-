import json
import math
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFontMetricsF, QImage, QPainter
from PyQt6.QtWidgets import QApplication

from gerald.board import BoardWindow, PLOT_PALETTE
from gerald.tools.plot import PLOT_INSETS, build_plot, parse_expression
from gerald.tools.plot_render import _font_at_local_size, _text_flags, draw_plot
from gerald.tools.registry import BOARD_TOOL_NAMES, TOOL_SCHEMAS


def _base_args(expr="x**2-5*x+6"):
    return {
        "functions": [{"expr": expr, "label": "f(x)"}],
        "x_min": -1,
        "x_max": 6,
    }


@pytest.mark.parametrize(
    ("local_size", "image_to_local_scale", "expected_size"),
    [(13, 0.5, 26), (14, 0.5, 28), (13, 1.0, 13)],
)
def test_plot_fonts_compensate_for_image_to_local_scale(
    local_size, image_to_local_scale, expected_size
):
    font = _font_at_local_size("Google Sans Flex", local_size, image_to_local_scale)

    assert font.pixelSize() == expected_size


def test_scaled_y_tick_labels_do_not_clip_in_the_left_gutter(monkeypatch):
    app = QApplication.instance() or QApplication([])
    assert app is not None
    args = {
        **_base_args(),
        "y_min": -100,
        "y_max": 100,
        "x": 100,
        "y": 100,
        "w": 420,
        "h": 300,
    }
    plot, _result = build_plot(args, (800, 600))
    image = QImage(800, 600, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor("#FFFFFF"))
    observed_flags = []
    original_text_flags = _text_flags

    def record_text_flags(alignment):
        flags = original_text_flags(alignment)
        observed_flags.append(flags)
        return flags

    monkeypatch.setattr("gerald.tools.plot_render._text_flags", record_text_flags)
    painter = QPainter(image)
    painter.scale(0.5, 0.5)
    painter.translate(plot.box[0], plot.box[1])
    draw_plot(painter, plot, 1.0, "Google Sans Flex", PLOT_PALETTE, 0.5)
    painter.end()

    tick_font = _font_at_local_size("Google Sans Flex", 13, 0.5)
    assert QFontMetricsF(tick_font).horizontalAdvance("-100") > PLOT_INSETS[0] - 12
    assert any(
        flags & int(Qt.AlignmentFlag.AlignRight)
        and flags & int(Qt.TextFlag.TextDontClip)
        for flags in observed_flags
    )
    assert not image.isNull()


def test_expression_parser_accepts_allowed_math_forms():
    assert parse_expression("x**2 - 5*x + 6")(2) == 0
    assert parse_expression("x^2 - 5x + 6")(2) == 0
    assert math.isclose(parse_expression("sqrt(x**2) + sin(pi / 2)")(3), 4)
    assert math.isclose(parse_expression("abs(-x) + log(e)")(3), 4)


@pytest.mark.parametrize(
    "expression",
    ["__import__('os')", "x.real", "x**1000", "other + 1"],
)
def test_expression_parser_rejects_unsafe_or_unknown_syntax(expression):
    with pytest.raises(ValueError):
        parse_expression(expression)


def test_sampling_finds_quadratic_minimum_and_automatic_y_range():
    plot, _result = build_plot(_base_args(), (800, 600))

    samples = [sample for sample in plot.curves[0].samples if sample is not None]
    minimum = min(samples, key=lambda sample: sample[1])

    assert len(plot.curves[0].samples) == 400
    assert math.isclose(minimum[0], 2.5, abs_tol=0.02)
    assert math.isclose(minimum[1], -0.25, abs_tol=0.01)
    assert plot.y_min < minimum[1]
    assert plot.y_max > 12


def test_sampling_breaks_asymptote_jumps():
    plot, _result = build_plot(
        {"functions": [{"expr": "1/x"}], "x_min": -1, "x_max": 1},
        (800, 600),
    )

    assert None in plot.curves[0].samples


def test_plot_schema_and_validation_errors():
    assert "plot" in BOARD_TOOL_NAMES
    schema = next(tool for tool in TOOL_SCHEMAS if tool["name"] == "plot")
    assert schema["parameters"]["required"] == ["functions", "x_min", "x_max"]
    with pytest.raises(ValueError, match="between 1 and 3"):
        build_plot({**_base_args(), "functions": []}, (800, 600))
    with pytest.raises(ValueError, match="span must be at most 200"):
        build_plot({**_base_args(), "x_min": 0, "x_max": 201}, (800, 600))
    with pytest.raises(ValueError, match="plot box must fit"):
        build_plot({**_base_args(), "x": 700, "y": 400}, (800, 600))


def test_board_plot_renders_and_returns_point_image_coordinates():
    app = QApplication.instance() or QApplication([])
    board = BoardWindow()
    board.resize(800, 600)
    args = _base_args()
    args["points"] = [
        {"x": 2, "y": 0, "label": "Racine 2"},
        {"x": 3, "y": 0, "label": "Racine 3"},
        {"x": 2.5, "y": -0.25, "label": "Sommet"},
    ]

    result = json.loads(board.execute_tool("plot", args))

    assert result["ok"] is True
    x, y, width, height = result["box"]
    assert (width, height) == (420, 300)
    assert len(result["points"]) == 3
    for point in result["points"]:
        assert x <= point["x_img"] <= x + width
        assert y <= point["y_img"] <= y + height
    assert result["points"][0]["label"] == "Racine 2"
    assert result["points"][1]["label"] == "Racine 3"
    assert board._gerald[0]["kind"] == "plot"
    board._gerald[0]["created"] -= 1
    board.show()
    app.processEvents()
    image = board.grab().toImage()
    assert not image.isNull()
    assert image.pixelColor(x + 20, y + 20) == QColor("#F7F6F3")
    plot = board._gerald[0]["plot"]
    left, top, right, bottom = PLOT_INSETS
    graph_left, graph_top = left, top
    graph_width = width - left - right
    graph_height = height - top - bottom
    axis_x = round(x + graph_left + (0 - plot.x_min) / (plot.x_max - plot.x_min) * graph_width)
    curve_y = graph_top + (plot.y_max - 6) / (plot.y_max - plot.y_min) * graph_height
    probe_y = round(y + (graph_top + curve_y) / 2)
    assert image.pixelColor(axis_x, probe_y).red() < 100
    board.close()
    app.processEvents()
