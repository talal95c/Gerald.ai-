from gerald.perception.eval_metrics import prediction_hit, scale_box


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
