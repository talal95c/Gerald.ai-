from PIL import Image

from gerald.perception.eval_metrics import annotate_screenshot, prediction_hit, scale_box


def test_ground_truth_box_scales_css_pixels_by_dpr():
    assert scale_box({"x": 10, "y": 20, "width": 30, "height": 40}, 2) == (
        20,
        40,
        60,
        80,
    )


def test_hit_uses_prediction_center_and_expanded_ground_truth():
    gt = (100, 200, 40, 20)

    assert prediction_hit((145, 205, 0, 0), gt, 8)
    assert not prediction_hit((150, 205, 0, 0), gt, 8)


def test_annotated_screenshot_marks_ground_truth_and_prediction():
    image = Image.new("RGB", (100, 100), "white")
    annotated = annotate_screenshot(image, (10, 10, 20, 20), (40, 40, 10, 10))

    assert annotated.getpixel((10, 10)) == (34, 197, 94)
    assert annotated.getpixel((40, 40)) == (255, 159, 10)
