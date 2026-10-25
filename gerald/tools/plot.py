from __future__ import annotations

import ast
import math
import operator
import re
from dataclasses import dataclass
from typing import Callable

PLOT_INSETS = (56.0, 36.0, 18.0, 44.0)
SAMPLE_COUNT = 400

_BINARY_OPERATORS: dict[type[ast.operator], Callable[[float, float], float]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
}
_FUNCTIONS: dict[str, Callable[[float], float]] = {
    "sqrt": math.sqrt,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "exp": math.exp,
    "log": math.log,
    "abs": abs,
}


@dataclass(frozen=True)
class PlotCurve:
    expr: str
    label: str
    samples: tuple[tuple[float, float] | None, ...]


@dataclass(frozen=True)
class PlotPoint:
    label: str
    x: float
    y: float
    x_img: int
    y_img: int


@dataclass(frozen=True)
class PlotCommand:
    box: tuple[float, float, float, float]
    x_min: float
    x_max: float
    y_min: float
    y_max: float
    curves: tuple[PlotCurve, ...]
    points: tuple[PlotPoint, ...]


def _constant_number(node: ast.AST) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        if isinstance(node.value, bool) or not math.isfinite(node.value):
            raise ValueError("numeric constants must be finite")
        return float(node.value)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -_constant_number(node.operand)
    if isinstance(node, ast.BinOp):
        left = _constant_number(node.left)
        right = _constant_number(node.right)
        if isinstance(node.op, ast.Pow):
            if abs(right) > 10:
                raise ValueError("exponents must have an absolute value at most 10")
            return math.pow(left, right)
        operation = _BINARY_OPERATORS.get(type(node.op))
        if operation is not None:
            return operation(left, right)
    raise ValueError("exponents must be numeric constants")


def _validate_expression(node: ast.AST) -> None:
    if isinstance(node, ast.Constant):
        if not isinstance(node.value, (int, float)) or isinstance(node.value, bool):
            raise ValueError("only real numeric constants are allowed")
        if not math.isfinite(node.value):
            raise ValueError("numeric constants must be finite")
        return
    if isinstance(node, ast.Name):
        if node.id not in {"x", "pi", "e"}:
            raise ValueError(f"unsupported name: {node.id}")
        return
    if isinstance(node, ast.UnaryOp):
        if not isinstance(node.op, ast.USub):
            raise ValueError("only unary minus is allowed")
        _validate_expression(node.operand)
        return
    if isinstance(node, ast.BinOp):
        if isinstance(node.op, ast.Pow):
            exponent = _constant_number(node.right)
            if abs(exponent) > 10:
                raise ValueError("exponents must have an absolute value at most 10")
        elif type(node.op) not in _BINARY_OPERATORS:
            raise ValueError("unsupported arithmetic operator")
        _validate_expression(node.left)
        _validate_expression(node.right)
        return
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id not in _FUNCTIONS:
            raise ValueError("only sqrt, sin, cos, tan, exp, log, and abs calls are allowed")
        if len(node.args) != 1 or node.keywords:
            raise ValueError(f"{node.func.id} requires exactly one positional argument")
        _validate_expression(node.args[0])
        return
    raise ValueError(f"unsupported expression element: {type(node).__name__}")


def _evaluate(node: ast.AST, x: float) -> float:
    if isinstance(node, ast.Constant):
        return float(node.value)
    if isinstance(node, ast.Name):
        if node.id == "x":
            return x
        if node.id == "pi":
            return math.pi
        if node.id == "e":
            return math.e
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -_evaluate(node.operand, x)
    if isinstance(node, ast.BinOp):
        left = _evaluate(node.left, x)
        right = _evaluate(node.right, x)
        if isinstance(node.op, ast.Pow):
            return math.pow(left, right)
        operation = _BINARY_OPERATORS.get(type(node.op))
        if operation is not None:
            return operation(left, right)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        return _FUNCTIONS[node.func.id](_evaluate(node.args[0], x))
    raise ValueError("unsupported expression")


def parse_expression(expression: str) -> Callable[[float], float]:
    if not isinstance(expression, str) or not expression.strip():
        raise ValueError("expr must be a non-empty string")
    try:
        normalized = re.sub(r"(?<=\d)\s*(?=x\b)", "*", expression.replace("^", "**"))
        tree = ast.parse(normalized, mode="eval")
    except (SyntaxError, ValueError) as error:
        raise ValueError("expr is not a valid mathematical expression") from error
    try:
        _validate_expression(tree.body)
    except (ArithmeticError, OverflowError) as error:
        raise ValueError("invalid constant arithmetic in expr") from error

    def evaluate(x: float) -> float:
        try:
            value = _evaluate(tree.body, x)
            return float(value) if math.isfinite(value) else math.nan
        except (ArithmeticError, OverflowError, TypeError, ValueError):
            return math.nan

    return evaluate


def _number(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    return float(value)


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def _place_box(
    image_size: tuple[int, int],
    box_size: tuple[float, float],
    occupied: list[tuple[float, float, float, float]],
) -> tuple[float, float]:
    image_width, image_height = image_size
    width, height = box_size
    margin = 24.0
    bottom = max((y + h for _x, y, _w, h in occupied), default=margin)
    positions = [
        (margin, bottom + margin),
        (image_width - width - margin, margin * 2),
        (image_width - width - margin, image_height - height - margin),
        (margin, margin),
    ]
    for x, y in positions:
        x = min(max(0.0, x), max(0.0, image_width - width))
        y = min(max(0.0, y), max(0.0, image_height - height))
        if not any(
            x < other_x + other_w + 16
            and x + width + 16 > other_x
            and y < other_y + other_h + 16
            and y + height + 16 > other_y
            for other_x, other_y, other_w, other_h in occupied
        ):
            return x, y
    return max(0.0, image_width - width - margin), max(0.0, image_height - height - margin)


def build_plot(
    args: dict,
    image_size: tuple[int, int],
    occupied_boxes: list[tuple[float, float, float, float]] | None = None,
) -> tuple[PlotCommand, dict]:
    allowed = {"functions", "x_min", "x_max", "y_min", "y_max", "points", "x", "y", "w", "h"}
    if not isinstance(args, dict):
        raise ValueError("arguments must be an object")
    extra = set(args) - allowed
    if extra:
        raise ValueError(f"unexpected argument: {sorted(extra)[0]}")
    if not {"functions", "x_min", "x_max"} <= args.keys():
        raise ValueError("functions, x_min, and x_max are required")
    image_width, image_height = image_size
    if image_width <= 0 or image_height <= 0:
        raise ValueError("board image size must be positive")

    x_min = _number(args["x_min"], "x_min")
    x_max = _number(args["x_max"], "x_max")
    if x_max <= x_min:
        raise ValueError("x_max must be greater than x_min")
    if x_max - x_min > 200:
        raise ValueError("x range span must be at most 200")

    functions = args["functions"]
    if not isinstance(functions, list) or not 1 <= len(functions) <= 3:
        raise ValueError("functions must contain between 1 and 3 items")
    parsed: list[tuple[str, str, Callable[[float], float]]] = []
    for index, function in enumerate(functions):
        if not isinstance(function, dict) or set(function) - {"expr", "label"}:
            raise ValueError("each function must contain expr and optional label")
        expression = function.get("expr")
        if not isinstance(expression, str) or not expression.strip():
            raise ValueError(f"function {index + 1} expr must be a non-empty string")
        label = function.get("label", expression)
        if not isinstance(label, str) or len(label) > 24:
            raise ValueError(f"function {index + 1} label must be at most 24 characters")
        parsed.append((expression, label, parse_expression(expression)))

    raw_curves: list[tuple[str, str, list[tuple[float, float] | None]]] = []
    all_values: list[float] = []
    for expression, label, function in parsed:
        samples: list[tuple[float, float] | None] = []
        for index in range(SAMPLE_COUNT):
            x_value = x_min + (x_max - x_min) * index / (SAMPLE_COUNT - 1)
            y_value = function(x_value)
            if math.isfinite(y_value):
                samples.append((x_value, y_value))
                all_values.append(y_value)
            else:
                samples.append(None)
        raw_curves.append((expression, label, samples))

    points_arg = args.get("points", [])
    if not isinstance(points_arg, list) or len(points_arg) > 8:
        raise ValueError("points must contain at most 8 items")
    data_points: list[tuple[str, float, float]] = []
    for index, point in enumerate(points_arg):
        if not isinstance(point, dict) or set(point) - {"x", "y", "label"}:
            raise ValueError("each point must contain x, y, and optional label")
        if not {"x", "y"} <= point.keys():
            raise ValueError(f"point {index + 1} requires x and y")
        point_x = _number(point["x"], f"point {index + 1} x")
        point_y = _number(point["y"], f"point {index + 1} y")
        label = point.get("label", "")
        if not isinstance(label, str) or len(label) > 24:
            raise ValueError(f"point {index + 1} label must be at most 24 characters")
        data_points.append((label, point_x, point_y))

    if not all_values and not data_points:
        raise ValueError("functions produced no finite samples")
    if data_points:
        all_values.extend(point_y for _label, _point_x, point_y in data_points)
    low = _percentile(all_values, 0.01)
    high = _percentile(all_values, 0.99)
    margin = (high - low) * 0.1 if high > low else max(abs(low) * 0.1, 1.0)
    auto_min, auto_max = low - margin, high + margin
    y_min = _number(args["y_min"], "y_min") if "y_min" in args else auto_min
    y_max = _number(args["y_max"], "y_max") if "y_max" in args else auto_max
    if y_max <= y_min:
        raise ValueError("y_max must be greater than y_min")
    y_range = y_max - y_min

    curves = []
    for expression, label, samples in raw_curves:
        broken_samples: list[tuple[float, float] | None] = []
        previous: tuple[float, float] | None = None
        for sample in samples:
            if sample is None:
                broken_samples.append(None)
                previous = None
                continue
            if previous is not None and abs(sample[1] - previous[1]) > 3 * y_range:
                broken_samples.append(None)
            broken_samples.append(sample)
            previous = sample
        curves.append(PlotCurve(expression, label, tuple(broken_samples)))

    box_x, box_y = args.get("x"), args.get("y")
    if (box_x is None) != (box_y is None):
        raise ValueError("x and y must be provided together")
    width = _number(args.get("w", 420), "w")
    height = _number(args.get("h", 300), "h")
    if width <= 0 or height <= 0:
        raise ValueError("w and h must be positive numbers")
    if box_x is None:
        width = min(width, float(image_width))
        height = min(height, float(image_height))
        box_x, box_y = _place_box(
            image_size,
            (width, height),
            occupied_boxes or [],
        )
    else:
        box_x = _number(box_x, "x")
        box_y = _number(box_y, "y")
        if box_x < 0 or box_y < 0 or box_x + width > image_width or box_y + height > image_height:
            raise ValueError("plot box must fit within the board image")

    left, top, right, bottom = PLOT_INSETS
    graph_width = max(1.0, width - left - right)
    graph_height = max(1.0, height - top - bottom)
    plotted_points = []
    for label, point_x, point_y in data_points:
        horizontal = min(1.0, max(0.0, (point_x - x_min) / (x_max - x_min)))
        vertical = min(1.0, max(0.0, (y_max - point_y) / y_range))
        plotted_points.append(
            PlotPoint(
                label,
                point_x,
                point_y,
                round(box_x + left + horizontal * graph_width),
                round(box_y + top + vertical * graph_height),
            )
        )
    command = PlotCommand(
        (box_x, box_y, width, height),
        x_min,
        x_max,
        y_min,
        y_max,
        tuple(curves),
        tuple(plotted_points),
    )
    result = {
        "ok": True,
        "box": [round(box_x), round(box_y), round(width), round(height)],
        "points": [
            {"label": point.label, "x_img": point.x_img, "y_img": point.y_img}
            for point in plotted_points
        ],
    }
    return command, result
