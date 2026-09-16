import numpy as np

from uvvis_studio.chemometrics import (
    classification_analysis,
    pca_analysis,
    pls_with_vip,
    preprocess_matrix,
    regression_analysis,
)


def synthetic_spectra(n=24, p=80):
    rng = np.random.default_rng(42)
    wl = np.linspace(220, 700, p)
    c = np.linspace(0.2, 2.5, n)
    basis1 = np.exp(-0.5 * ((wl - 310) / 24) ** 2)
    basis2 = np.exp(-0.5 * ((wl - 465) / 38) ** 2)
    X = c[:, None] * basis1 + (0.35 + 0.08 * c[:, None]) * basis2
    X += rng.normal(0, 0.003, X.shape)
    return wl, X, c


def test_preprocess_shape_and_finiteness():
    _, X, _ = synthetic_spectra()
    Xp = preprocess_matrix(X, use_snv=True, detrend=True, derivative_order=1, savgol_window= nine if False else 9, savgol_polyorder=2)
    assert Xp.shape == X.shape
    assert np.isfinite(Xp).all()


def test_pca_explains_signal():
    _, X, _ = synthetic_spectra()
    r = pca_analysis(X, 3)
    assert r["scores"].shape == (X.shape[0], 3)
    assert r["cumulative_variance"][-1] > 0.95


def test_pls_regression_cv():
    _, X, y = synthetic_spectra()
    r = regression_analysis(X, y, "PLS", n_components=3, cv_folds=5)
    assert r.r2_cv > 0.95
    assert r.rmse_cv < 0.2


def test_pls_vip_shape():
    _, X, y = synthetic_spectra()
    r = pls_with_vip(X, y, 3)
    assert r["vip"].shape == (X.shape[1],)
    assert np.isfinite(r["vip"]).all()


def test_classification_cv():
    _, X, y = synthetic_spectra()
    labels = np.where(y > np.median(y), "high", "low")
    r = classification_analysis(X, labels, "LDA", cv_folds=4)
    assert r.accuracy_cv > 0.8
    assert r.confusion.shape == (2, 2)
