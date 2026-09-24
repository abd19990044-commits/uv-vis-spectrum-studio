"""Generate extended test datasets for Section 2-8 scientific workflows."""
import numpy as np
import pandas as pd
from pathlib import Path

OUT_DIR = Path("audit_artifacts/functional")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# 1. Independent Reference Dataset for AUC (User Request Section 3)
# Wavelength (nm): 250, 255, 260, 265, 270, 275, 280, 285, 290
# Absorbance:      0.120, 0.180, 0.280, 0.410, 0.520, 0.470, 0.350, 0.230, 0.150
# Expected AUC (255-285 nm) = 11.175 Abs*nm
auc_ref = pd.DataFrame({
    "Wavelength_nm": [250.0, 255.0, 260.0, 265.0, 270.0, 275.0, 280.0, 285.0, 290.0],
    "Absorbance": [0.120, 0.180, 0.280, 0.410, 0.520, 0.470, 0.350, 0.230, 0.150],
})
auc_ref.to_csv(OUT_DIR / "auc_reference_spectrum.csv", index=False)
print("Created auc_reference_spectrum.csv")

# 2. Sinusoidal Spectrum for Fourier Transform Validation (Section 4)
# Known period = 50.0 nm (frequency = 0.02 cycles/nm)
x_fft = np.linspace(200.0, 800.0, 1201)  # dx = 0.5 nm
y_fft = 0.50 + 0.35 * np.sin(2.0 * np.pi * (x_fft - 200.0) / 50.0) + 0.10 * np.sin(2.0 * np.pi * (x_fft - 200.0) / 20.0)
sin_df = pd.DataFrame({"Wavelength_nm": x_fft, "Absorbance": y_fft})
sin_df.to_csv(OUT_DIR / "sinusoidal_spectrum.csv", index=False)
print("Created sinusoidal_spectrum.csv")

# 3. Noisy Spectrum for Wavelet Denoising & CWT (Section 5)
np.random.seed(42)
x_wave = np.linspace(200.0, 500.0, 601)  # dx = 0.5 nm
clean_peak = 0.85 * np.exp(-0.5 * ((x_wave - 273.0) / 15.0)**2) + 0.40 * np.exp(-0.5 * ((x_wave - 350.0) / 25.0)**2)
noise = np.random.normal(0, 0.035, size=len(x_wave))
noisy_df = pd.DataFrame({"Wavelength_nm": x_wave, "Absorbance": clean_peak + noise, "Clean_Signal": clean_peak})
noisy_df.to_csv(OUT_DIR / "noisy_caffeine_spectrum.csv", index=False)
print("Created noisy_caffeine_spectrum.csv")

# 4. Chemometrics Multivariate Dataset (Section 6)
# 10 synthetic calibration samples with known analyte concentrations
concentrations = np.array([1.0, 2.5, 5.0, 7.5, 10.0, 12.5, 15.0, 17.5, 20.0, 25.0])
x_chem = np.linspace(220.0, 400.0, 361)
spectra_matrix = {}
spectra_matrix["Wavelength_nm"] = x_chem
for idx, conc in enumerate(concentrations):
    # Pure analyte peak at 280 nm + matrix baseline background
    peak = (conc * 0.04) * np.exp(-0.5 * ((x_chem - 280.0) / 12.0)**2)
    bkg = 0.05 + 0.001 * (x_chem - 220.0)
    spec_noise = np.random.normal(0, 0.003, size=len(x_chem))
    spectra_matrix[f"Sample_{idx+1}_C{conc:.1f}"] = peak + bkg + spec_noise

chemo_df = pd.DataFrame(spectra_matrix)
chemo_df.to_csv(OUT_DIR / "chemometrics_multivariate_dataset.csv", index=False)
print("Created chemometrics_multivariate_dataset.csv")
