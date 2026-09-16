import numpy as np
from uvvis_studio.analysis import calculate_metrics, derivative, crop_xy


def test_auc_and_lambda_max():
    x = np.linspace(200, 300, 101)
    y = np.ones_like(x) * 2
    m = calculate_metrics(x, y)
    assert abs(m.area - 200.0) < 1e-9
    assert m.lambda_max == 200.0


def test_first_derivative_linear_signal():
    x = np.linspace(200, 300, 101)
    y = 3 * x + 2
    dy = derivative(x, y, order=1, window=11, polyorder=3)
    assert np.allclose(dy[5:-5], 3.0, atol=1e-8)


def test_crop():
    x = np.array([200, 250, 300], dtype=float)
    y = np.array([1, 2, 3], dtype=float)
    xx, yy = crop_xy(x, y, 225, 275)
    assert xx.tolist() == [250.0]
    assert yy.tolist() == [2.0]
