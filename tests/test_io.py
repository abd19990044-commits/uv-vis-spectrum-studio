import pandas as pd
from uvvis_studio.io import detect_wavelength_column, clean_xy


def test_detect_wavelength_column_by_200_rule():
    df = pd.DataFrame({"Abs": [0.1, 0.2, 0.3], "nm": [200, 201, 202]})
    assert detect_wavelength_column(df) == "nm"


def test_clean_xy_sorts_and_drops_nan():
    df = pd.DataFrame({"x": [202, 200, 201, None], "y": [3, 1, 2, 5]})
    x, y = clean_xy(df, "x", "y")
    assert x.tolist() == [200.0, 201.0, 202.0]
    assert y.tolist() == [1.0, 2.0, 3.0]
