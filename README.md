# UV-Vis Spectrum Studio

[![CI](https://github.com/abd19990044-commits/uv-vis-spectrum-studio/actions/workflows/ci.yml/badge.svg)](https://github.com/abd19990044-commits/uv-vis-spectrum-studio/actions/workflows/ci.yml)
[![Windows build](https://github.com/abd19990044-commits/uv-vis-spectrum-studio/actions/workflows/windows-installer.yml/badge.svg)](https://github.com/abd19990044-commits/uv-vis-spectrum-studio/actions/workflows/windows-installer.yml)
[![Cross-platform builds](https://github.com/abd19990044-commits/uv-vis-spectrum-studio/actions/workflows/cross-platform-desktop.yml/badge.svg)](https://github.com/abd19990044-commits/uv-vis-spectrum-studio/actions/workflows/cross-platform-desktop.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**UV-Vis Spectrum Studio** is an open-source analytical spectroscopy environment for UV-Vis data processing, publication-quality visualization, quantitative analysis, analytical-method validation, multicomponent spectrophotometry, peak fitting and deconvolution, Fourier/wavelet analysis, chemometrics, and reproducible scientific project files.

The project is designed for analytical chemists, spectroscopy researchers, students, method-development laboratories, and scientists who would otherwise combine spreadsheets, Origin-like plotting tools, custom scripts, and separate chemometric software.

**Current software version: v3.1.0**

> UV-Vis Spectrum Studio is research and analytical-support software. It is not represented as a validated GMP/GLP/21 CFR Part 11/ISO 17025 system by default. Laboratories using it in regulated workflows remain responsible for software and method validation within their quality system.

---

## Why this project exists

A UV-Vis workflow commonly moves through several disconnected programs: instrument export, spreadsheet cleaning, plotting, derivative calculation, calibration, statistical validation, multicomponent equations, chemometrics, and figure preparation. UV-Vis Spectrum Studio brings these operations into one reproducible workspace while keeping the raw spectrum separate from user-selected processing steps.

Processing is **not silently enabled**. Smoothing, baseline correction, normalization, derivatives, variable selection, and other transformations are explicitly selected by the analyst.

---

## v3.1 scientific hardening

Version 3.1 focuses on numerical defensibility, reproducibility, and production packaging.

### Analytical validation

- Linear calibration with slope, intercept, R² and Sy/x.
- Slope/intercept standard errors and 95% confidence intervals.
- LOD = 3.3σ/|S| and LOQ = 10σ/|S|.
- Manual or regression-derived σ.
- Residual plots and tabulated residuals.
- Lack-of-fit ANOVA when replicated calibration levels are available.
- **Mandel fitting test** for linear-versus-quadratic model comparison.
- Approximate confidence intervals for inverse prediction of an unknown.
- Precision, SD, RSD, recovery and bias summaries.

### Spectroscopy quality control

- High-absorbance diagnostics with caution flags above configurable analytical ranges.
- Negative-absorbance diagnostics for blank/reference problems.
- Wavelength-spacing diagnostics.
- High-order derivative quality diagnostics.
- Explicit fourth-derivative safeguards for Savitzky-Golay polynomial/window compatibility.
- Optional FWHM-aware reporting of points per band and smoothing-window/FWHM ratio.

High-order derivative warnings are diagnostic rather than universal rejection rules because acceptable wavelength interval, bandwidth, stray light, S/N and smoothing depend on the instrument and validated analytical procedure.

### Multicomponent safeguards

- Two-component simultaneous-equation analysis.
- Matrix **condition number** reporting.
- Warning/rejection of severely ill-conditioned absorptivity systems.
- Q-analysis with physically implausible fraction diagnostics.
- Dual-wavelength calculations.
- Ratio, mean-centered ratio and derivative-ratio workflows.

### Peak fitting

- Gaussian.
- Lorentzian.
- Voigt using the Faddeeva function.
- Pseudo-Voigt with a common-FWHM parameterization.
- Multiple overlapping components.
- Polynomial baseline orders 0–3.
- Peak center, amplitude, FWHM and area.
- RMSE and R².
- Parameter covariance diagnostics and uncertainty warnings where available.

### Chemometric validation

- PCA, ICA and NMF/MCR-like decomposition.
- PLS, PCR and classical/machine-learning regressors.
- Classification and clustering.
- Kennard-Stone and SPXY splitting.
- PLS latent-variable screening.
- **Nested PLS cross-validation** for less biased model-selection assessment.
- Y-randomization/permutation testing.
- VIP wavelength screening.
- Interval PLS (iPLS).
- Fold-safe supervised preprocessing so MSC references, centering and scaling are fitted from each training fold rather than from the entire dataset.

Variable selection performed on all samples can still bias performance. For confirmatory work, selection and hyperparameter tuning should occur inside nested validation or be finalized before evaluation on a locked independent test set.

---

## Core UV-Vis processing

- Excel, CSV, TXT, DAT, ASC and TSV import.
- UTF-8, CP1252, Windows-1256 and Latin-1 text handling.
- Automatic wavelength-column detection.
- Duplicate wavelength handling by deterministic averaging.
- Multiple overlaid spectra.
- Per-curve names, colors and line styles.
- Solid lines by default.
- Publication black-and-white mode.
- Manual X/Y axis titles and ranges.
- Absorbance ↔ %Transmittance conversion.
- Spectral difference, ratio, addition and reference subtraction.
- Savitzky-Golay, moving-average and Gaussian smoothing.
- ALS, endpoint-linear and polynomial-edge baselines.
- Max, min-max and area normalization.
- Derivative spectroscopy from 0D through 4D.
- Zero crossings.
- λmax / λmin.
- FWHM.
- Spectral centroid.
- Peak detection.
- Signal extraction at a selected wavelength.
- S/N estimation from a user-defined region.

---

## Area under the curve

Manual wavelength limits are supported. Boundary values are interpolated when the requested limits fall between measured wavelengths.

Outputs include:

- signed AUC,
- absolute AUC,
- exact integration limits,
- optional shaded integration region,
- CSV export.

---

## Fourier and wavelet analysis

- FFT amplitude and power spectra.
- Hann, Hamming and Blackman windows.
- Optional detrending.
- Dominant-period estimation.
- DWT denoising preview.
- Universal-threshold wavelet denoising.
- Soft/hard thresholding.
- Continuous Wavelet Transform (CWT).
- CWT scalograms.

Wavelet denoising is not silently substituted for raw data.

---

## Quantitative and stoichiometric tools

### Beer-Lambert calibration

- Manual concentration/response entry.
- Linear regression.
- LOD/LOQ.
- Residuals.
- Molar absorptivity ε when molecular weight, concentration unit and path length are supplied.

Supported concentration units include µg/mL, mg/L, mmol/L and mol/L.

### Direct-entry analytical methods

- Job's method of continuous variations.
- Mole-ratio method.
- Standard addition.
- Interpolated isosbestic-point detection.
- Simultaneous equations.
- Absorbance-ratio/Q-analysis.
- Dual-wavelength spectrophotometry.

---

## Chemometrics

### Pretreatment

- Mean centering.
- Autoscaling.
- SNV.
- MSC.
- Linear detrending.
- Savitzky-Golay derivatives.

### Regression

- PLS.
- PCR.
- Ordinary linear regression.
- Ridge.
- Lasso.
- Elastic Net.
- SVR-RBF.
- KNN regression.
- Random Forest.
- Extra Trees.
- Gradient Boosting.

### Classification

- LDA.
- QDA.
- Logistic regression.
- SVM-RBF.
- KNN.
- Gaussian Naive Bayes.
- Random Forest.
- Extra Trees.
- Gradient Boosting.

### Exploratory analysis

- PCA scores/loadings.
- Explained and cumulative variance.
- Hotelling T².
- Q residuals.
- ICA.
- NMF/MCR-like decomposition.
- K-means.
- Hierarchical Ward clustering.

---

## Reproducible `.uvvisproj` projects

The project format stores raw spectra separately from processing settings so re-opening a project does not accidentally process already processed data a second time.

Project metadata can include:

- raw spectral arrays,
- curve names/colors/styles,
- source file information,
- source hashes,
- user notes,
- analyst and instrument fields,
- processing settings,
- processing audit trail,
- application version,
- Python version,
- operating system/platform,
- key package versions,
- build/Git commit when embedded during packaging.

The current project format includes SHA-256 integrity information so modified archive members can be detected when the project is reopened. This is a **tamper-evident integrity mechanism**, not a replacement for an authenticated regulatory audit-trail system.

---

## Publication export

- PNG: 300, 600, 720, 900 and 1200 DPI.
- SVG.
- PDF.
- Processed CSV.
- AUC CSV.
- Peak tables.
- User-defined figure dimensions.
- Publication fonts.
- Color or black-and-white figures.
- Direct save to a user-selected folder in desktop builds.

Kaleido/Chrome is bundled by the release workflows where supported so vector and high-resolution export can operate without a separate browser installation.

---

## Desktop builds

The same scientific core is packaged for the major desktop operating systems.

| Platform | Distribution | Notes |
|---|---|---|
| Windows x64 | Inno Setup `.exe` installer | PyInstaller + pywebview; Authenticode signing supported. A self-signed fallback certificate may still trigger SmartScreen warnings. |
| macOS | `.app` packaged as `.zip` | Built and self-tested on GitHub-hosted macOS. Unsigned/notarization-free development builds may require Gatekeeper approval. |
| Linux x86_64 | `.tar.gz` desktop bundle | Uses pywebview when a supported WebKit/GTK runtime is present; otherwise the launcher falls back to the local system browser. |
| Source | Python 3.11+ | Works anywhere the Python dependencies are available. |

Every packaged desktop workflow runs scientific tests before packaging and then executes a **packaged self-test** against the frozen application/server.

Release workflows also generate SHA-256 checksum files and environment lock snapshots.

---

## Installation from source

Python 3.11 or newer is recommended.

```bash
python -m venv .venv
```

Windows:

```powershell
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

Linux/macOS:

```bash
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

For desktop packaging dependencies:

```bash
pip install -r requirements-desktop.txt
```

---

## Testing

```bash
pytest -q
python -m compileall app.py desktop_launcher.py uvvis_studio
```

The test suite covers spectral calculations, integration, transformations, calibration, method validation, Mandel testing, LOD/LOQ, multicomponent conditioning, fourth-derivative safeguards, project round-trips and integrity checks, chemometric preprocessing, PLS validation, sample splitting, variable screening, peak fitting and Streamlit smoke tests.

---

## Scientific validation strategy

Software unit tests establish numerical regression protection; they do not constitute analytical-method validation.

Before using results in validated QC or formal regulatory work, a laboratory should independently verify at minimum:

1. instrument-file import with its actual instrument/software exports,
2. reference calculations against trusted software or hand calculations,
3. calibration and uncertainty behavior on representative data,
4. method-specific accuracy, precision, selectivity, robustness and range,
5. chemometric train/test separation and preprocessing strategy,
6. installation qualification and the organization's data-integrity requirements.

---

## Repository structure

```text
app.py                                  Streamlit entry point
desktop_launcher.py                     Cross-platform desktop launcher
uvvis_studio/analysis.py                Spectral processing and metrics
uvvis_studio/io.py                      File import and wavelength detection
uvvis_studio/export.py                  High-resolution/vector export
uvvis_studio/transforms.py              FFT and wavelet analysis
uvvis_studio/quantitation.py            Calibration and direct-entry methods
uvvis_studio/validation.py              Analytical-method validation
uvvis_studio/quality.py                 Spectroscopy/derivative quality diagnostics
uvvis_studio/multicomponent.py          Multicomponent spectrophotometry
uvvis_studio/peakfit.py                 Peak fitting and deconvolution
uvvis_studio/project.py                 Reproducible .uvvisproj format
uvvis_studio/chemometrics.py            Core chemometric models and preprocessing
uvvis_studio/chemometrics_advanced.py   Advanced validation/variable selection
uvvis_studio/*_ui.py                    Streamlit presentation layer
installer/                              Windows Inno Setup configuration
.github/workflows/ci.yml                Python CI
.github/workflows/windows-installer.yml Windows production build
.github/workflows/cross-platform-desktop.yml macOS/Linux builds
tests/                                  Scientific regression tests
CITATION.cff                            Citation metadata
.zenodo.json                            Zenodo GitHub-release metadata
LICENSE                                 MIT License
LICENSE-NOTICE.md                       Licensing/scientific-use explanation
```

---

## Citation

If UV-Vis Spectrum Studio contributes materially to your work, cite the exact release used. GitHub can read `CITATION.cff` through **Cite this repository**.

After the repository is enabled in Zenodo and a GitHub release is archived, use the Zenodo DOI for the corresponding software version. The DOI is intentionally **not hard-coded before Zenodo assigns it**.

Citation metadata are provided in:

- `CITATION.cff`
- `.zenodo.json`

---

## Zenodo publication readiness

The repository is prepared for future GitHub → Zenodo archiving.

Recommended release procedure:

1. Connect the GitHub account to Zenodo.
2. Enable `abd19990044-commits/uv-vis-spectrum-studio` in Zenodo's GitHub integration.
3. Ensure CI and platform builds pass.
4. Create a versioned GitHub Release/tag, e.g. `v3.1.0`.
5. Allow Zenodo to ingest the release.
6. Verify title, creator, license, version and files in the Zenodo record.
7. Add the assigned Zenodo DOI badge/citation back to this README in the next commit/release.

Because `.zenodo.json` is present, it is the Zenodo-specific metadata source for GitHub-release archiving; `CITATION.cff` remains useful to GitHub and citation tools.

---

## License

UV-Vis Spectrum Studio is licensed under the **MIT License**. See [`LICENSE`](LICENSE).

The standard MIT text is intentionally left unchanged for unambiguous machine and human recognition. Additional explanation of third-party software and scientific-use responsibilities is available in [`LICENSE-NOTICE.md`](LICENSE-NOTICE.md); that notice does **not** add restrictions to the MIT License.

---

## Author

**Abdulsalam S. Hasan**

Repository: https://github.com/abd19990044-commits/uv-vis-spectrum-studio
