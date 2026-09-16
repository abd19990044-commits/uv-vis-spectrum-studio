from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import BinaryIO
import csv

import numpy as np
import pandas as pd


def _read_text(raw: bytes, name: str) -> pd.DataFrame:
    text = raw.decode("utf-8-sig", errors="replace")
    sample = text[:8192]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t ")
        sep = dialect.delimiter
    except csv.Error:
        sep = None
    bio = BytesIO(raw)
    if sep == " ":
        return pd.read_csv(bio, sep=r"\s+", engine="python")
    if sep:
        return pd.read_csv(bio, sep=sep, engine="python")
    return pd.read_csv(bio, sep=None, engine="python")


def read_table(file_obj: BinaryIO, filename: str, sheet_name: str | int | None = 0) -> pd.DataFrame:
    ext = Path(filename).suffix.lower()
    raw = file_obj.read()
    if ext in {".xlsx", ".xlsm", ".xltx", ".xltm", ".xls"}:
        return pd.read_excel(BytesIO(raw), sheet_name=sheet_name)
    if ext in {".csv", ".txt", ".dat", ".asc", ".tsv"}:
        return _read_text(raw, filename)
    raise ValueError(f"Unsupported file type: {ext or 'unknown'}")


def excel_sheets(file_obj: BinaryIO, filename: str) -> list[str]:
    ext = Path(filename).suffix.lower()
    if ext not in {".xlsx", ".xlsm", ".xltx", ".xltm", ".xls"}:
        return []
    raw = file_obj.read()
    return pd.ExcelFile(BytesIO(raw)).sheet_names


def _numeric_series(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def detect_wavelength_column(df: pd.DataFrame, threshold: float = 200.0) -> str:
    """Detect wavelength column.

    Primary rule: first finite numeric value is >= threshold. Among candidates,
    prefer monotonic columns with plausible UV-Vis ranges and many numeric rows.
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
        if "wave" in str(col).lower() or "lambda" in str(col).lower() or "nm" in str(col).lower():
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


def clean_xy(df: pd.DataFrame, x_col: str, y_col: str) -> tuple[np.ndarray, np.ndarray]:
    x = pd.to_numeric(df[x_col], errors="coerce")
    y = pd.to_numeric(df[y_col], errors="coerce")
    valid = x.notna() & y.notna()
    x_arr = x[valid].to_numpy(float)
    y_arr = y[valid].to_numpy(float)
    order = np.argsort(x_arr)
    x_arr, y_arr = x_arr[order], y_arr[order]
    unique_x, idx = np.unique(x_arr, return_index=True)
    return unique_x, y_arr[idx]
