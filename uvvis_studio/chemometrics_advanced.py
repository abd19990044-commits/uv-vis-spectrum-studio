from __future__ import annotations

import numpy as np
from scipy.spatial.distance import pdist, squareform
from sklearn.cross_decomposition import PLSRegression
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.model_selection import KFold, cross_val_predict


def _as_xy(X, y) -> tuple[np.ndarray, np.ndarray]:
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=float).reshape(-1)
    if X.ndim != 2:
        raise ValueError("X must be a two-dimensional sample-by-variable matrix.")
    if len(X) != len(y):
        raise ValueError("X and y must contain the same number of samples.")
    if len(X) < 3:
        raise ValueError("At least three samples are required.")
    if not np.all(np.isfinite(X)) or not np.all(np.isfinite(y)):
        raise ValueError("X and y must contain only finite values.")
    return X, y


def _folds(n_samples: int, requested: int) -> int:
    return max(2, min(int(requested), n_samples))


def _safe_pls_components(n_samples: int, n_variables: int, folds: int, requested: int) -> int:
    """Largest feasible component count in every CV training fold."""
    smallest_train = n_samples - int(np.ceil(n_samples / folds))
    if smallest_train < 2:
        raise ValueError("PLS cross-validation needs at least two training samples in every fold.")
    return max(1, min(int(requested), n_variables, smallest_train - 1))


def kennard_stone(X, n_train: int):
    X = np.asarray(X, dtype=float)
    if X.ndim != 2 or len(X) < 3 or X.shape[1] == 0 or not np.all(np.isfinite(X)):
        raise ValueError("Kennard-Stone requires at least three samples.")
    if len(X) > 5000:
        raise ValueError("Distance-based splitting is limited to 5,000 samples.")
    n_train = max(2, min(int(n_train), len(X) - 1))
    centered = X - X.mean(axis=0)
    scale = X.std(axis=0, ddof=1)
    scale[scale == 0] = 1.0
    Z = centered / scale
    distance = squareform(pdist(Z))
    np.fill_diagonal(distance, -np.inf)
    i, j = np.unravel_index(np.argmax(distance), distance.shape)
    selected = [int(i), int(j)]
    while len(selected) < n_train:
        remaining = [k for k in range(len(X)) if k not in selected]
        k = max(remaining, key=lambda r: min(distance[r, s] for s in selected))
        selected.append(int(k))
    test = [k for k in range(len(X)) if k not in selected]
    return np.array(selected, dtype=int), np.array(test, dtype=int)


def spxy(X, y, n_train: int, alpha: float = 0.5):
    X, y = _as_xy(X, y)
    if not 0 <= float(alpha) <= 1:
        raise ValueError("alpha must be between 0 and 1.")
    if len(X) > 5000:
        raise ValueError("Distance-based splitting is limited to 5,000 samples.")
    dx = squareform(pdist(X))
    dy = np.abs(y[:, None] - y[None, :])
    # SPXY normalizes each distance matrix by its maximum. Autoscaling
    # individual X variables is a separate analyst preprocessing choice.
    if dx.max() > 0:
        dx /= dx.max()
    if dy.max() > 0:
        dy /= dy.max()
    distance = (1 - float(alpha)) * dx + float(alpha) * dy
    np.fill_diagonal(distance, -np.inf)
    n_train = max(2, min(int(n_train), len(X) - 1))
    i, j = np.unravel_index(np.argmax(distance), distance.shape)
    selected = [int(i), int(j)]
    while len(selected) < n_train:
        remaining = [k for k in range(len(X)) if k not in selected]
        k = max(remaining, key=lambda r: min(distance[r, s] for s in selected))
        selected.append(int(k))
    test = [k for k in range(len(X)) if k not in selected]
    return np.array(selected, dtype=int), np.array(test, dtype=int)


def optimize_pls_components(X, y, max_components=15, cv_folds=5):
    """Exploratory inner-CV component selection.

    The returned best-CV score is useful for tuning but is optimistic if it is
    reported as final model performance.  Use ``nested_pls_evaluation`` for an
    approximately unbiased performance estimate after component selection.
    """
    X, y = _as_xy(X, y)
    cv = KFold(n_splits=_folds(len(X), cv_folds), shuffle=True, random_state=42)
    max_components = _safe_pls_components(len(X), X.shape[1], cv.n_splits, max_components)
    rows = []
    for n_components in range(1, max_components + 1):
        model = PLSRegression(n_components=n_components, scale=True)
        prediction = np.asarray(cross_val_predict(model, X, y, cv=cv)).reshape(-1)
        rows.append(
            {
                "components": n_components,
                "r2_cv": float(r2_score(y, prediction)),
                "rmsecv": float(np.sqrt(mean_squared_error(y, prediction))),
            }
        )
    best = min(rows, key=lambda row: row["rmsecv"])
    return {
        "results": rows,
        "best_components": best["components"],
        "best_rmsecv": best["rmsecv"],
        "best_r2_cv": best["r2_cv"],
        "selection_warning": (
            "Best-component CV statistics are tuning statistics. For final predictive performance, "
            "use nested cross-validation or a truly external test set."
        ),
    }


def nested_pls_evaluation(
    X,
    y,
    *,
    max_components: int = 15,
    outer_folds: int = 5,
    inner_folds: int = 5,
    random_state: int = 42,
) -> dict:
    """Nested cross-validation for PLS component selection and performance.

    Component count is selected using only each outer-training fold.  The held
    out outer fold is never used for model selection, reducing selection bias.
    """
    X, y = _as_xy(X, y)
    outer_n = _folds(len(X), outer_folds)
    if outer_n >= len(X):
        outer_n = max(2, len(X) - 1)
    outer = KFold(n_splits=outer_n, shuffle=True, random_state=random_state)
    prediction = np.full(len(y), np.nan, dtype=float)
    chosen: list[int] = []
    fold_rows: list[dict] = []

    for fold, (train_idx, test_idx) in enumerate(outer.split(X), start=1):
        X_train, y_train = X[train_idx], y[train_idx]
        inner_n = _folds(len(X_train), inner_folds)
        if inner_n >= len(X_train):
            inner_n = max(2, len(X_train) - 1)
        inner = KFold(n_splits=inner_n, shuffle=True, random_state=random_state + fold)
        maxc = _safe_pls_components(len(X_train), X_train.shape[1], inner_n, max_components)

        tuning = []
        for n_components in range(1, maxc + 1):
            pred_inner = np.asarray(
                cross_val_predict(
                    PLSRegression(n_components=n_components, scale=True),
                    X_train,
                    y_train,
                    cv=inner,
                )
            ).reshape(-1)
            rmse = float(np.sqrt(mean_squared_error(y_train, pred_inner)))
            tuning.append((rmse, n_components))
        best_rmse, best_components = min(tuning, key=lambda item: item[0])
        chosen.append(int(best_components))

        model = PLSRegression(n_components=best_components, scale=True)
        model.fit(X_train, y_train)
        fold_prediction = np.asarray(model.predict(X[test_idx])).reshape(-1)
        prediction[test_idx] = fold_prediction
        fold_rows.append(
            {
                "fold": fold,
                "train_n": int(len(train_idx)),
                "test_n": int(len(test_idx)),
                "selected_components": int(best_components),
                "inner_rmsecv": float(best_rmse),
                "outer_rmsep": float(np.sqrt(mean_squared_error(y[test_idx], fold_prediction))),
            }
        )

    valid = np.isfinite(prediction)
    if not np.all(valid):
        raise RuntimeError("Nested PLS did not produce predictions for every sample.")
    residuals = y - prediction
    return {
        "predicted": prediction,
        "residuals": residuals,
        "q2_nested": float(r2_score(y, prediction)),
        "rmsep_nested": float(np.sqrt(mean_squared_error(y, prediction))),
        "maep_nested": float(np.mean(np.abs(residuals))),
        "selected_components": np.asarray(chosen, dtype=int),
        "median_selected_components": int(np.median(chosen)),
        "folds": fold_rows,
        "n_outer_folds": int(outer_n),
    }


def y_randomization_test(
    X,
    y,
    n_components=2,
    permutations=100,
    cv_folds=5,
    random_state=42,
):
    X, y = _as_xy(X, y)
    rng = np.random.default_rng(random_state)
    cv = KFold(n_splits=_folds(len(X), cv_folds), shuffle=True, random_state=42)
    n_components = _safe_pls_components(len(X), X.shape[1], cv.n_splits, n_components)
    prediction = np.asarray(
        cross_val_predict(PLSRegression(n_components=n_components, scale=True), X, y, cv=cv)
    ).reshape(-1)
    observed = float(r2_score(y, prediction))
    null = []
    for _ in range(max(10, int(permutations))):
        permuted_y = rng.permutation(y)
        permuted_prediction = np.asarray(
            cross_val_predict(
                PLSRegression(n_components=n_components, scale=True),
                X,
                permuted_y,
                cv=cv,
            )
        ).reshape(-1)
        null.append(float(r2_score(permuted_y, permuted_prediction)))
    null_array = np.asarray(null)
    p_value = float((1 + np.sum(null_array >= observed)) / (len(null_array) + 1))
    return {
        "observed_q2": observed,
        "permuted_q2": null_array,
        "p_value": p_value,
        "null_mean": float(np.mean(null_array)),
        "null_sd": float(np.std(null_array, ddof=1)),
    }


def vip_threshold_select(vip, wavelengths, threshold=1.0):
    vip = np.asarray(vip, dtype=float)
    wavelengths = np.asarray(wavelengths, dtype=float)
    if vip.shape != wavelengths.shape:
        raise ValueError("VIP and wavelength arrays must have identical shape.")
    mask = np.isfinite(vip) & np.isfinite(wavelengths) & (vip >= float(threshold))
    return {
        "indices": np.flatnonzero(mask),
        "wavelengths": wavelengths[mask],
        "vip": vip[mask],
    }


def interval_pls(X, y, wavelengths, n_intervals=10, n_components=2, cv_folds=5):
    """Exploratory iPLS interval ranking.

    Because the best interval is selected using the same CV results that rank
    intervals, its minimum RMSECV should not be presented as an unbiased final
    predictive error. Use nested interval selection or an external test set for
    confirmatory performance reporting.
    """
    X, y = _as_xy(X, y)
    wavelengths = np.asarray(wavelengths, dtype=float)
    if wavelengths.ndim != 1 or len(wavelengths) != X.shape[1]:
        raise ValueError("wavelengths must contain one value per X variable.")
    chunks = np.array_split(
        np.arange(X.shape[1]), max(2, min(int(n_intervals), X.shape[1]))
    )
    rows = []
    cv = KFold(n_splits=_folds(len(X), cv_folds), shuffle=True, random_state=42)
    for index, variables in enumerate(chunks):
        if len(variables) < 1:
            continue
        ncomp = _safe_pls_components(len(X), len(variables), cv.n_splits, n_components)
        prediction = np.asarray(
            cross_val_predict(
                PLSRegression(n_components=ncomp, scale=True),
                X[:, variables],
                y,
                cv=cv,
            )
        ).reshape(-1)
        rows.append(
            {
                "interval": index + 1,
                "start_nm": float(wavelengths[variables[0]]),
                "end_nm": float(wavelengths[variables[-1]]),
                "variables": len(variables),
                "q2": float(r2_score(y, prediction)),
                "rmsecv": float(np.sqrt(mean_squared_error(y, prediction))),
                "indices": variables,
            }
        )
    return {
        "results": rows,
        "best": min(rows, key=lambda row: row["rmsecv"]) if rows else None,
        "selection_warning": (
            "The best interval is selected on these CV results; validate it with nested CV or an external set."
        ),
    }
