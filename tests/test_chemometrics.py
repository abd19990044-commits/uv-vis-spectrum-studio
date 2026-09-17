import numpy as np
from sklearn.pipeline import Pipeline

from uvvis_studio.chemometrics import (
    SpectralPreprocessor,
    classification_analysis,
    pca_analysis,
    pls_with_vip,
    preprocess_matrix,
    regression_analysis,
)
from uvvis_studio.chemometrics_advanced import nested_pls_evaluation


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
    Xp = preprocess_matrix(
        X,
        use_snv=True,
        detrend=True,
        derivative_order=1,
        savgol_window=9,
        savgol_polyorder=2,
    )
    assert Xp.shape == X.shape
    assert np.isfinite(Xp).all()


def test_fold_safe_preprocessor_uses_training_reference():
    _, X, _ = synthetic_spectra()
    train = X[:16]
    test = X[16:]
    pre = SpectralPreprocessor(use_msc=True, mean_center=True, autoscale=True)
    pre.fit(train)
    assert np.allclose(pre.msc_reference_, train.mean(axis=0))
    transformed = pre.transform(test)
    assert transformed.shape == test.shape
    assert np.isfinite(transformed).all()


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


def test_pls_regression_cv_with_preprocessing_pipeline():
    _, X, y = synthetic_spectra()
    r = regression_analysis(
        X,
        y,
        "PLS",
        n_components=3,
        cv_folds=5,
        preprocessing={"use_msc": True, "mean_center": True},
    )
    assert isinstance(r.model, Pipeline)
    assert "spectral_preprocess" in r.model.named_steps
    assert r.r2_cv > 0.9


def test_nested_pls_selection_is_outer_fold_safe():
    _, X, y = synthetic_spectra(n=30, p=60)
    result = nested_pls_evaluation(
        X,
        y,
        max_components=6,
        outer_folds=5,
        inner_folds=4,
        random_state=7,
    )
    assert result["predicted"].shape == y.shape
    assert np.isfinite(result["predicted"]).all()
    assert np.isfinite(result["rmsep_nested"])
    assert result["q2_nested"] > 0.9
    assert len(result["selected_components"]) == 5
    assert all(1 <= value <= 6 for value in result["selected_components"])


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


def test_classification_cv_with_fold_safe_preprocessing():
    _, X, y = synthetic_spectra()
    labels = np.where(y > np.median(y), "high", "low")
    r = classification_analysis(
        X,
        labels,
        "Logistic regression",
        cv_folds=4,
        preprocessing={"autoscale": True, "use_snv": True},
    )
    assert isinstance(r.model, Pipeline)
    assert "spectral_preprocess" in r.model.named_steps
    assert r.accuracy_cv > 0.7
