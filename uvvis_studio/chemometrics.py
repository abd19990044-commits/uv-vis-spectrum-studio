from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.signal import detrend as scipy_detrend
from scipy.signal import savgol_filter
from sklearn.base import BaseEstimator, TransformerMixin, clone
from sklearn.cluster import AgglomerativeClustering, KMeans
from sklearn.cross_decomposition import PLSRegression
from sklearn.decomposition import FastICA, NMF, PCA
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis, QuadraticDiscriminantAnalysis
from sklearn.ensemble import (
    ExtraTreesClassifier,
    ExtraTreesRegressor,
    GradientBoostingClassifier,
    GradientBoostingRegressor,
    RandomForestClassifier,
    RandomForestRegressor,
)
from sklearn.linear_model import ElasticNet, Lasso, LinearRegression, LogisticRegression, Ridge
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    confusion_matrix,
    mean_absolute_error,
    mean_squared_error,
    r2_score,
)
from sklearn.model_selection import KFold, StratifiedKFold, cross_val_predict
from sklearn.naive_bayes import GaussianNB
from sklearn.neighbors import KNeighborsClassifier, KNeighborsRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.svm import SVC, SVR


@dataclass
class RegressionResult:
    model_name: str
    observed: np.ndarray
    predicted_cv: np.ndarray
    r2_cv: float
    rmse_cv: float
    mae_cv: float
    model: object


@dataclass
class ClassificationResult:
    model_name: str
    observed: np.ndarray
    predicted_cv: np.ndarray
    accuracy_cv: float
    balanced_accuracy_cv: float
    confusion: np.ndarray
    classes: np.ndarray
    model: object


def _as_matrix(X: np.ndarray) -> np.ndarray:
    X = np.asarray(X, dtype=float)
    if X.ndim != 2 or X.shape[0] < 2 or X.shape[1] < 2:
        raise ValueError("Chemometric X must be a 2D matrix with at least 2 samples and 2 variables.")
    if not np.all(np.isfinite(X)):
        raise ValueError("Chemometric X contains missing or non-finite values.")
    return X


def _snv_rows(X: np.ndarray) -> np.ndarray:
    mean = X.mean(axis=1, keepdims=True)
    sd = X.std(axis=1, ddof=1, keepdims=True)
    sd[~np.isfinite(sd) | (sd == 0)] = 1.0
    return (X - mean) / sd


def snv(X: np.ndarray) -> np.ndarray:
    return _snv_rows(_as_matrix(X))


def _msc_rows(X: np.ndarray, reference: np.ndarray) -> np.ndarray:
    reference = np.asarray(reference, dtype=float).reshape(-1)
    if reference.size != X.shape[1] or not np.all(np.isfinite(reference)):
        raise ValueError("MSC reference must contain one finite value per variable.")
    out = np.empty_like(X)
    for i, row in enumerate(X):
        slope, intercept = np.polyfit(reference, row, 1)
        out[i] = (row - intercept) / slope if abs(slope) > 1e-15 else row
    return out


def msc(X: np.ndarray, reference: np.ndarray | None = None) -> np.ndarray:
    X = _as_matrix(X)
    ref = np.asarray(reference, dtype=float) if reference is not None else X.mean(axis=0)
    return _msc_rows(X, ref)


def _safe_savgol_parameters(n_variables: int, window: int, polyorder: int, derivative_order: int) -> tuple[int, int]:
    order = int(derivative_order)
    poly = max(int(polyorder), order)
    win = max(int(window), poly + 2)
    if win % 2 == 0:
        win += 1
    maximum = n_variables if n_variables % 2 else n_variables - 1
    win = min(win, maximum)
    if win <= poly or win < 3:
        raise ValueError(
            "Savitzky-Golay window is too short for the requested polynomial/derivative order and variable count."
        )
    return win, poly


class SpectralPreprocessor(BaseEstimator, TransformerMixin):
    """Fold-safe spectral preprocessing for supervised chemometrics.

    Sample-local operations (SNV, detrending, SG derivatives) are applied
    independently.  Operations that learn population statistics (MSC reference,
    mean centering and autoscaling) are fitted on the training fold only, which
    prevents validation/test leakage during scikit-learn cross-validation.
    """

    def __init__(
        self,
        *,
        mean_center: bool = False,
        autoscale: bool = False,
        use_snv: bool = False,
        use_msc: bool = False,
        detrend: bool = False,
        derivative_order: int = 0,
        savgol_window: int = 11,
        savgol_polyorder: int = 2,
    ):
        self.mean_center = mean_center
        self.autoscale = autoscale
        self.use_snv = use_snv
        self.use_msc = use_msc
        self.detrend = detrend
        self.derivative_order = derivative_order
        self.savgol_window = savgol_window
        self.savgol_polyorder = savgol_polyorder

    def _sample_local(self, X: np.ndarray) -> np.ndarray:
        out = np.asarray(X, dtype=float).copy()
        if self.use_snv:
            out = _snv_rows(out)
        if self.detrend:
            out = scipy_detrend(out, axis=1, type="linear")
        order = int(self.derivative_order)
        if order:
            window, poly = _safe_savgol_parameters(
                out.shape[1], self.savgol_window, self.savgol_polyorder, order
            )
            out = savgol_filter(out, window, poly, deriv=order, axis=1, mode="interp")
        return out

    def fit(self, X, y=None):
        X = _as_matrix(X)
        local = self._sample_local(X)
        self.n_features_in_ = local.shape[1]
        self.msc_reference_ = local.mean(axis=0) if self.use_msc else None
        population = _msc_rows(local, self.msc_reference_) if self.use_msc else local
        self.center_ = population.mean(axis=0) if (self.mean_center or self.autoscale) else None
        if self.autoscale:
            scale = population.std(axis=0, ddof=1)
            scale[~np.isfinite(scale) | (scale == 0)] = 1.0
            self.scale_ = scale
        else:
            self.scale_ = None
        return self

    def transform(self, X):
        X = np.asarray(X, dtype=float)
        if X.ndim != 2 or X.shape[1] != self.n_features_in_ or not np.all(np.isfinite(X)):
            raise ValueError("SpectralPreprocessor received incompatible/non-finite data.")
        out = self._sample_local(X)
        if self.use_msc:
            out = _msc_rows(out, self.msc_reference_)
        if self.mean_center or self.autoscale:
            out = out - self.center_
        if self.autoscale:
            out = out / self.scale_
        return out


def preprocessing_transformer(**kwargs) -> SpectralPreprocessor:
    allowed = {
        "mean_center",
        "autoscale",
        "use_snv",
        "use_msc",
        "detrend",
        "derivative_order",
        "savgol_window",
        "savgol_polyorder",
    }
    unknown = set(kwargs) - allowed
    if unknown:
        raise ValueError(f"Unknown preprocessing options: {sorted(unknown)}")
    return SpectralPreprocessor(**kwargs)


def preprocess_matrix(
    X: np.ndarray,
    *,
    mean_center: bool = False,
    autoscale: bool = False,
    use_snv: bool = False,
    use_msc: bool = False,
    detrend: bool = False,
    derivative_order: int = 0,
    savgol_window: int = 11,
    savgol_polyorder: int = 2,
) -> np.ndarray:
    """Fit-transform preprocessing for exploratory/unsupervised use.

    For supervised cross-validation use ``regression_analysis`` or
    ``classification_analysis`` with the ``preprocessing`` argument so learned
    statistics are fitted independently inside each training fold.
    """
    X = _as_matrix(X)
    transformer = SpectralPreprocessor(
        mean_center=mean_center,
        autoscale=autoscale,
        use_snv=use_snv,
        use_msc=use_msc,
        detrend=detrend,
        derivative_order=derivative_order,
        savgol_window=savgol_window,
        savgol_polyorder=savgol_polyorder,
    )
    return transformer.fit_transform(X)


def pca_analysis(X: np.ndarray, n_components: int = 2) -> dict:
    X = _as_matrix(X)
    n = max(1, min(int(n_components), X.shape[0], X.shape[1]))
    model = PCA(n_components=n)
    scores = model.fit_transform(X)
    loadings = model.components_.T
    reconstructed = model.inverse_transform(scores)
    residual = X - reconstructed
    q_residual = np.sum(residual**2, axis=1)
    eig = model.explained_variance_
    with np.errstate(divide="ignore", invalid="ignore"):
        t2 = np.sum((scores**2) / np.where(eig > 0, eig, np.nan), axis=1)
    return {
        "model": model,
        "scores": scores,
        "loadings": loadings,
        "explained_variance_ratio": model.explained_variance_ratio_,
        "cumulative_variance": np.cumsum(model.explained_variance_ratio_),
        "q_residual": q_residual,
        "hotelling_t2": t2,
    }


def _regressor(name: str, n_components: int = 2):
    models = {
        "Linear regression": LinearRegression(),
        "PCR": Pipeline(
            [
                ("scale", StandardScaler()),
                ("pca", PCA(n_components=max(1, int(n_components)))),
                ("reg", LinearRegression()),
            ]
        ),
        "PLS": PLSRegression(n_components=max(1, int(n_components)), scale=True),
        "Ridge": Pipeline([("scale", StandardScaler()), ("reg", Ridge(alpha=1.0))]),
        "Lasso": Pipeline([("scale", StandardScaler()), ("reg", Lasso(alpha=0.001, max_iter=20000))]),
        "Elastic Net": Pipeline(
            [("scale", StandardScaler()), ("reg", ElasticNet(alpha=0.001, l1_ratio=0.5, max_iter=20000))]
        ),
        "SVR (RBF)": Pipeline([("scale", StandardScaler()), ("reg", SVR(kernel="rbf", C=10.0, epsilon=0.01))]),
        "KNN": Pipeline([("scale", StandardScaler()), ("reg", KNeighborsRegressor(n_neighbors=3))]),
        "Random Forest": RandomForestRegressor(n_estimators=300, random_state=42),
        "Extra Trees": ExtraTreesRegressor(n_estimators=300, random_state=42),
        "Gradient Boosting": GradientBoostingRegressor(random_state=42),
    }
    if name not in models:
        raise ValueError(f"Unsupported regression model: {name}")
    return models[name]


def _with_preprocessing(model, preprocessing: dict | None):
    if not preprocessing:
        return model
    return Pipeline([("spectral_preprocess", preprocessing_transformer(**preprocessing)), ("model", model)])


def regression_analysis(
    X: np.ndarray,
    y: np.ndarray,
    model_name: str = "PLS",
    *,
    n_components: int = 2,
    cv_folds: int = 5,
    preprocessing: dict | None = None,
) -> RegressionResult:
    X = _as_matrix(X)
    y = np.asarray(y, dtype=float).reshape(-1)
    if len(y) != X.shape[0] or not np.all(np.isfinite(y)):
        raise ValueError("Regression y must contain one finite value per sample.")
    folds = max(2, min(int(cv_folds), X.shape[0]))
    smallest_train = X.shape[0] - int(np.ceil(X.shape[0] / folds))
    if smallest_train < 2:
        raise ValueError("Regression CV requires at least two training samples per fold.")
    if model_name == "KNN" and smallest_train < 3:
        raise ValueError("KNN requires at least three training samples per fold.")
    if model_name in {"PCR", "PLS"}:
        n_components = max(1, min(int(n_components), X.shape[1], smallest_train - 1))
    model = _with_preprocessing(_regressor(model_name, n_components), preprocessing)
    cv = KFold(n_splits=folds, shuffle=True, random_state=42)
    predicted = np.asarray(cross_val_predict(model, X, y, cv=cv)).reshape(-1)
    fitted = clone(model).fit(X, y)
    return RegressionResult(
        model_name,
        y,
        predicted,
        float(r2_score(y, predicted)),
        float(np.sqrt(mean_squared_error(y, predicted))),
        float(mean_absolute_error(y, predicted)),
        fitted,
    )


def _classifier(name: str):
    models = {
        "LDA": LinearDiscriminantAnalysis(),
        "QDA": QuadraticDiscriminantAnalysis(),
        "Logistic regression": Pipeline(
            [("scale", StandardScaler()), ("clf", LogisticRegression(max_iter=10000))]
        ),
        "SVM (RBF)": Pipeline([("scale", StandardScaler()), ("clf", SVC(kernel="rbf", C=10.0))]),
        "KNN": Pipeline([("scale", StandardScaler()), ("clf", KNeighborsClassifier(n_neighbors=3))]),
        "Gaussian Naive Bayes": GaussianNB(),
        "Random Forest": RandomForestClassifier(n_estimators=300, random_state=42),
        "Extra Trees": ExtraTreesClassifier(n_estimators=300, random_state=42),
        "Gradient Boosting": GradientBoostingClassifier(random_state=42),
    }
    if name not in models:
        raise ValueError(f"Unsupported classification model: {name}")
    return models[name]


def classification_analysis(
    X: np.ndarray,
    labels: np.ndarray,
    model_name: str = "LDA",
    *,
    cv_folds: int = 5,
    preprocessing: dict | None = None,
) -> ClassificationResult:
    X = _as_matrix(X)
    labels = np.asarray(labels).astype(str).reshape(-1)
    if len(labels) != X.shape[0]:
        raise ValueError("Classification labels must contain one class per sample.")
    encoder = LabelEncoder()
    y = encoder.fit_transform(labels)
    counts = np.bincount(y)
    if len(counts) < 2:
        raise ValueError("At least two classes are required.")
    if int(counts.min()) < 2:
        raise ValueError("Each class needs at least two samples for stratified cross-validation.")
    folds = max(2, min(int(cv_folds), int(counts.min())))
    model = _with_preprocessing(_classifier(model_name), preprocessing)
    cv = StratifiedKFold(n_splits=folds, shuffle=True, random_state=42)
    predicted = np.asarray(cross_val_predict(model, X, y, cv=cv)).reshape(-1)
    fitted = clone(model).fit(X, y)
    return ClassificationResult(
        model_name,
        labels,
        encoder.inverse_transform(predicted),
        float(accuracy_score(y, predicted)),
        float(balanced_accuracy_score(y, predicted)),
        confusion_matrix(y, predicted),
        encoder.classes_,
        fitted,
    )


def pls_vip(pls_model: PLSRegression) -> np.ndarray:
    t = np.asarray(pls_model.x_scores_)
    w = np.asarray(pls_model.x_weights_)
    q = np.asarray(pls_model.y_loadings_)
    p, h = w.shape
    s = np.diag(t.T @ t @ q.T @ q).reshape(h, -1)
    total = float(np.sum(s))
    if total <= 0:
        return np.zeros(p)
    return np.sqrt(p * (w**2 @ s).reshape(-1) / total)


def pls_with_vip(X: np.ndarray, y: np.ndarray, n_components: int = 2) -> dict:
    X = _as_matrix(X)
    y = np.asarray(y, dtype=float).reshape(-1)
    if len(y) != X.shape[0] or not np.all(np.isfinite(y)):
        raise ValueError("PLS y must contain one finite value per sample.")
    n = max(1, min(int(n_components), X.shape[1], X.shape[0] - 1))
    model = PLSRegression(n_components=n, scale=True).fit(X, y)
    return {
        "model": model,
        "vip": pls_vip(model),
        "x_weights": model.x_weights_,
        "x_loadings": model.x_loadings_,
        "x_scores": model.x_scores_,
    }


def unsupervised_decomposition(X: np.ndarray, method: str = "PCA", n_components: int = 2) -> dict:
    X = _as_matrix(X)
    n = max(1, min(int(n_components), X.shape[0], X.shape[1]))
    if method == "PCA":
        result = pca_analysis(X, n)
        return {"scores": result["scores"], "components": result["loadings"].T, "model": result["model"]}
    if method == "ICA":
        model = FastICA(n_components=n, random_state=42, max_iter=3000, whiten="unit-variance")
        scores = model.fit_transform(X)
        return {"scores": scores, "components": model.components_, "model": model}
    if method == "NMF / MCR-like":
        shifted = X - np.min(X)
        model = NMF(n_components=n, init="nndsvda", random_state=42, max_iter=3000)
        scores = model.fit_transform(shifted)
        return {"scores": scores, "components": model.components_, "model": model}
    raise ValueError(f"Unsupported decomposition method: {method}")


def cluster_samples(X: np.ndarray, method: str = "K-means", n_clusters: int = 2) -> np.ndarray:
    X = _as_matrix(X)
    n_clusters = max(2, min(int(n_clusters), X.shape[0]))
    if method == "K-means":
        return KMeans(n_clusters=n_clusters, n_init=20, random_state=42).fit_predict(X)
    if method == "Hierarchical (Ward)":
        return AgglomerativeClustering(n_clusters=n_clusters, linkage="ward").fit_predict(X)
    raise ValueError(f"Unsupported clustering method: {method}")
