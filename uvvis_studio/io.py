from __future__ import annotations

from io import BytesIO, StringIO
from pathlib import Path
from typing import BinaryIO
import csv

import numpy as np
import pandas as pd


_TEXT_ENCODINGS = ("utf-8-sig", "utf-8", "cp1252", "windows-1256", "latin-1")


def _decode_text(raw: bytes) -> tuple[str, str]:
    errors: list[str] = []
    for encoding in _TEXT_ENCODINGS:
        try:
            return raw.decode(encoding), encoding
        except UnicodeDecodeError as exc:
            errors.append(f"{encoding}: {exc}")
    raise ValueError("Could not decode text file using supported encodings: " + "; ".join(errors))


def _read_text(raw: bytes, name: str) -> pd.DataFrame:
    text, _encoding = _decode_text(raw)
    sample = text[:8192]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t ")
        sep = dialect.delimiter
    except csv.Error:
        sep = None

    if sep == " ":
        frame = pd.read_csv(StringIO(text), sep=r"\s+", engine="python")
    elif sep:
        frame = pd.read_csv(StringIO(text), sep=sep, engine="python")
    else:
        frame = pd.read_csv(StringIO(text), sep=None, engine="python")

    if frame.empty or frame.shape[1] < 2:
        raise ValueError(f"{name}: no usable two-column-or-more table was detected.")
    return frame


def read_table(file_obj: BinaryIO, filename: str, sheet_name: str | int | None = 0) -> pd.DataFrame:
    ext = Path(filename).suffix.lower()
    raw = file_obj.read()
    if not raw:
        raise ValueError("Input file is empty.")
    if ext in {".xlsx", ".xlsm", ".xltx", ".xltm", ".xls"}:
        frame = pd.read_excel(BytesIO(raw), sheet_name=sheet_name)
    elif ext in {".csv", ".txt", ".dat", ".asc", ".tsv"}:
        frame = _read_text(raw, filename)
    else:
        raise ValueError(f"Unsupported file type: {ext or 'unknown'}")
    if frame is None or frame.empty:
        raise ValueError("The selected table contains no data rows.")
    return frame


def excel_sheets(file_obj: BinaryIO, filename: str) -> list[str]:
    ext = Path(filename).suffix.lower()
    if ext not in {".xlsx", ".xlsm", ".xltx", ".xltm", ".xls"}:
        return []
    raw = file_obj.read()
    if not raw:
        return []
    return pd.ExcelFile(BytesIO(raw)).sheet_names


def _numeric_series(series: pd.Series) -> pd.Series:
    if series.dtype == object:
        # Support decimal comma when a column has already been split correctly.
        cleaned = series.astype(str).str.strip().str.replace(",", ".", regex=False)
        return pd.to_numeric(cleaned, errors="coerce")
    return pd.to_numeric(series, errors="coerce")


def detect_wavelength_column(df: pd.DataFrame, threshold: float = 200.0) -> str:
    """Detect the most plausible wavelength column.

    The user rule that the wavelength column begins at >=200 nm is preserved,
    while monotonicity, plausible UV-Vis range, uniqueness and column naming are
    used to rank candidates.
    """
    candidates: list[tuple[float, str]] = []
    for col in df.columns:
        s = _numeric_series(df[col]).dropna()
        if len(s) < 2:
            continue
        first = float(s.iloc[0])
        if first < threshold:
            continue
        vals = s.to_numpy(float)
        diffs = np.diff(vals)
        monotonic = bool(np.all(diffs >= 0) or np.all(diffs <= 0))
        in_range = float(np.mean((vals >= 180) & (vals <= 2500)))
        unique_ratio = float(pd.Series(vals).nunique() / max(len(vals), 1))
        score = 0.0
        score += 5.0 if monotonic else 0.0
        score += 3.0 * in_range
        score += 2.0 * unique_ratio
        score += min(len(vals) / 1000.0, 1.0)
        low_name = str(col).lower()
        if "wave" in low_name or "lambda" in low_name or "nm" in low_name or "wavelength" in low_name:
            score += 5.0
        candidates.append((score, str(col)))
    if not candidates:
        raise ValueError("No wavelength column found with a first numeric value >= 200 nm.")
    candidates.sort(reverse=True)
    return candidates[0][1]


def numeric_signal_columns(df: pd.DataFrame, wavelength_col: str) -> list[str]:
    out: list[str] = []
    for col in df.columns:
        if str(col) == str(wavelength_col):
            continue
        s = _numeric_series(df[col])
        if s.notna().sum() >= 2:
            out.append(str(col))
    return out


def clean_xy(
    df: pd.DataFrame,
    x_col: str,
    y_col: str,
    *,
    duplicate_policy: str = "mean",
) -> tuple[np.ndarray, np.ndarray]:
    """Clean, sort and de-duplicate one spectral X/Y pair.

    Duplicate wavelengths default to the mean signal rather than silently
    keeping the first observation.  This is safer for repeated exports while
    remaining deterministic.  ``duplicate_policy='first'`` is retained for
    compatibility when explicitly required.
    """
    x = _numeric_series(df[x_col])
    y = _numeric_series(df[y_col])
    valid = x.notna() & y.notna() & np.isfinite(x) & np.isfinite(y)
    work = pd.DataFrame({"x": x[valid].astype(float), "y": y[valid].astype(float)})
    if len(work) < 2:
        raise ValueError("Fewer than two finite wavelength/signal pairs remain after cleaning.")

    if duplicate_policy == "mean":
        work = work.groupby("x", as_index=False, sort=True)["y"].mean()
    elif duplicate_policy == "first":
        work = work.sort_values("x").drop_duplicates("x", keep="first")
    else:
        raise ValueError("duplicate_policy must be 'mean' or 'first'.")

    x_arr = work["x"].to_numpy(float)
    y_arr = work["y"].to_numpy(float)
    if len(x_arr) < 2 or np.any(np.diff(x_arr) <= 0):
        raise ValueError("Wavelength values must contain at least two unique sortable points.")
    return x_arr, y_arr
