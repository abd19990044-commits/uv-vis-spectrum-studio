from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd

out_dir = Path("audit_artifacts/functional")
out_dir.mkdir(parents=True, exist_ok=True)

# 1. Single UV-Vis Spectrum (e.g., Caffeine in water, peak at ~272 nm)
wl = np.linspace(200.0, 450.0, 501)
# Main peak at 272 nm, secondary shoulder at 205 nm
abs_signal = (
    0.85 * np.exp(-0.5 * ((wl - 272.5) / 14.0) ** 2)
    + 0.40 * np.exp(-0.5 * ((wl - 208.0) / 8.0) ** 2)
    + 0.005 * np.random.RandomState(42).normal(0, 1, size=len(wl))
)
abs_signal = np.clip(abs_signal, 0.0, None)
df_single = pd.DataFrame({"Wavelength_nm": wl, "Absorbance": abs_signal})
df_single.to_csv(out_dir / "caffeine_spectrum.csv", index=False)
print("Saved caffeine_spectrum.csv")

# 2. Multi-standard series for overlay & calibration
standards = [2.0, 5.0, 10.0, 20.0]
df_multi = pd.DataFrame({"Wavelength_nm": wl})
for conc in standards:
    sig = (
        (conc / 20.0) * 0.85 * np.exp(-0.5 * ((wl - 272.5) / 14.0) ** 2)
        + (conc / 20.0) * 0.40 * np.exp(-0.5 * ((wl - 208.0) / 8.0) ** 2)
        + 0.003 * np.random.RandomState(int(conc)).normal(0, 1, size=len(wl))
    )
    df_multi[f"Std_{conc}ug_mL"] = np.clip(sig, 0.0, None)
df_multi.to_csv(out_dir / "standards_series.csv", index=False)
print("Saved standards_series.csv")

# 3. Calibration table dataset
cal_df = pd.DataFrame({
    "Concentration": [0.0, 1.0, 2.0, 4.0, 6.0, 8.0, 10.0],
    "Response": [0.003, 0.081, 0.161, 0.319, 0.481, 0.636, 0.798]
})
cal_df.to_csv(out_dir / "calibration_table.csv", index=False)
print("Saved calibration_table.csv")

# 4. Malformed/Corrupt dataset for testing graceful error handling
with open(out_dir / "corrupted_spectrum.txt", "w", encoding="utf-8") as f:
    f.write("Corrupted header line without delimiter\n1.0\n2.0\n3.0\n")
print("Saved corrupted_spectrum.txt")
