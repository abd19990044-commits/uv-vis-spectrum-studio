from __future__ import annotations

from dataclasses import dataclass
import numpy as np
from scipy.signal import savgol_filter, detrend as scipy_detrend
from sklearn.base import clone
from sklearn.cluster import KMeans, AgglomerativeClustering
from sklearn.cross_decomposition import PLSRegression
from sklearn.decomposition import PCA, FastICA, NMF
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis, QuadraticDiscriminantAnalysis
from sklearn.ensemble import RandomForestRegressor, ExtraTreesRegressor, GradientBoostingRegressor, RandomForestClassifier, ExtraTreesClassifier, GradientBoostingClassifier
from sklearn.linear_model import LinearRegression, Ridge, Lasso, ElasticNet, LogisticRegression
from sklearn.metrics import r2_score, mean_squared_error, mean_absolute_error, accuracy_score, balanced_accuracy_score, confusion_matrix
from sklearn.model_selection import KFold, StratifiedKFold, cross_val_predict
from sklearn.neighbors import KNeighborsRegressor, KNeighborsClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.svm import SVR, SVC
from sklearn.naive_bayes import GaussianNB


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


def snv(X: np.ndarray) -> np.ndarray:
    X = _as_matrix(X)
    mean = X.mean(axis=1, keepdims=True)
    sd = X.std(axis=1, ddof=1, keepdims=True)
    sd[sd == 0] = 1.0
    return (X - mean) / sd


def msc(X: np.ndarray, reference: np.ndarray | None = None) -> np.ndarray:
    X = _as_matrix(X)
    ref = np.asarray(reference, dtype=float) if reference is not None else X.mean(axis=0)
    out = np.empty_like(X)
    for i, row in enumerate(X):
        slope, intercept = np.polyfit(ref, row, 1)
        out[i] = (row - intercept) / slope if abs(slope) > 1e-15 else row
    return out


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
    Xp = _as_matrix(X).copy()
    if use_snv:
        Xp = snv(Xp)
    if use_msc:
        Xp = msc(Xp)
    if detrend:
        Xp = scipy_detrend(Xp, axis=1, type="linear")
    order = int(derivative_order)
    if order:
        window = int(savgol_window)
        if window % 2 == 0:
            window += 1
        window = min(window, Xp.shape[1] if Xp.shape[1] % 2 else Xp.shape[1] - 1)
        if window <= int(savgol_polyorder) or window < 3:
            raise ValueError("Savitzky–Golay window must be odd and larger than polynomial order.")
        Xp = savgol_filter(Xp, window, int(savgol_polyorder), deriv=order, axis=1, mode="interp")
    if mean_center:
        Xp = Xp - Xp.mean(axis=0, keepdims=True)
    if autoscale:
        mu = Xp.mean(axis=0, keepdims=True)
        sd = Xp.std(axis=0, ddof=1, keepdims=True)
        sd[sd == 0] = 1.0
        Xp = (Xp - mu) / sd
    return Xp


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
        "PCR": Pipeline([("scale", StandardScaler()), ("pca", PCA(n_components=max(1, int(n_components)))), ("reg", LinearRegression())]),
        "PLS": PLSRegression(n_components=max(1, int(n_components)), scale=True),
        "Ridge": Pipeline([("scale", StandardScaler()), ("reg", Ridge(alpha=1.0))]),
        "Lasso": Pipeline([("scale", StandardScaler()), ("reg", Lasso(alpha=0.001, max_iter=20000))]),
        "Elastic Net": Pipeline([("scale", StandardScaler()), ("reg", ElasticNet(alpha=0.001, l1_ratio=0.5, max_iter=20000))]),
        "SVR (RBF)": Pipeline([("scale", StandardScaler()), ("reg", SVR(kernel="rbf", C=10.0, epsilon=0.01))]),
        "KNN": Pipeline([("scale", StandardScaler()), ("reg", KNeighborsRegressor(n_neighbors=3))]),
        "Random Forest": RandomForestRegressor(n_estimators=300, random_state=42),
        "Extra Trees": ExtraTreesRegressor(n_estimators=300, random_state=42),
        "Gradient Boosting": GradientBoostingRegressor(random_state=42),
    }
    if name not in models:
        raise ValueError(f"Unsupported regression model: {name}")
    return models[name]


def regression_analysis(X: np.ndarray, y: np.ndarray, model_name: str = "PLS", *, n_components: int = 2, cv_folds: int = 5) -> RegressionResult:
    X = _as_matrix(X)
    y = np.asarray(y, dtype=float).reshape(-1)
    if len(y) != X.shape[0] or not np.all(np.isfinite(y)):
        raise ValueError("Regression y must contain one finite value per sample.")
    folds = max(2, min(int(cv_folds), X.shape[0]))
    if model_name in {"PCR", "PLS"}:
        n_components = max(1, min(int(n_components), X.shape[1], X.shape[0] - 1))
    model = _regressor(model_name, n_components)
    cv = KFold(n_splits=folds, shuffle=True, random_state=42)
    pred = np.asarray(cross_val_predict(model, X, y, cv=cv)).reshape(-1)
    fitted = clone(model).fit(X, y)
    return RegressionResult(model_name, y, pred, float(r2_score(y, pred)), float(np.sqrt(mean_squared_error(y, pred))), float(mean_absolute_error(y, pred)), fitted)


def _classifier(name: str):
    models = {
        "LDA": LinearDiscriminantAnalysis(),
        "QDA": QuadraticDiscriminantAnalysis(),
        "Logistic regression": Pipeline([("scale", StandardScaler()), ("clf", LogisticRegression(max_iter=10000))]),
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


def classification_analysis(X: np.ndarray, labels: np.ndarray, model_name: str = "LDA", *, cv_folds: int = 5) -> ClassificationResult:
    X = _as_matrix(X)
    labels = np.asarray(labels).astype(str).reshape(-1)
    if len(labels) != X.shape[0]:
        raise ValueError("Classification labels must contain one class per sample.")
    enc = LabelEncoder()
    y = enc.fit_transform(labels)
    counts = np.bincount(y)
    if len(counts) < 2:
        raise ValueError("At least two classes are required.")
    folds = max(2, min(int(cv_folds), int(counts.min())))
    model = _classifier(model_name)
    cv = StratifiedKFold(n_splits=folds, shuffle=True, random_state=42)
    pred = np.asarray(cross_val_predict(model, X, y, cv=cv)).reshape(-1)
    fitted = clone(model).fit(X, y)
    return ClassificationResult(model_name, labels, enc.inverse_transform(pred), float(accuracy_score(y, pred)), float(balanced_accuracy_score(y, pred)), confusion_matrix(y, pred), enc.classes_, fitted)


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
    n = max(1, min(int(n_components), X.shape[1], X.shape[0] - 1))
    model = PLSRegression(n_components=n, scale=True).fit(X, y)
    return {"model": model, "vip": pls_vip(model), "x_weights": model.x_weights_, "x_loadings": model.x_loadings_, "x_scores": model.x_scores_}


def unsupervised_decomposition(X: np.ndarray, method: str = "PCA", n_components: int = 2) -> dict:
    X = _as_matrix(X)
    n = max(1, min(int(n_components), X.shape[0], X.shape[1]))
    if method == "PCA":
        r = pca_analysis(X, n)
        return {"scores": r["scores"], "components": r["loadings"].T, "model": r["model"]}
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
