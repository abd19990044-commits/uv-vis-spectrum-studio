# UV-Vis Spectrum Studio

[![CI](https://github.com/abd19990044-commits/uv-vis-spectrum-studio/actions/workflows/ci.yml/badge.svg)](https://github.com/abd19990044-commits/uv-vis-spectrum-studio/actions/workflows/ci.yml)
[![Windows](https://github.com/abd19990044-commits/uv-vis-spectrum-studio/actions/workflows/windows-installer.yml/badge.svg)](https://github.com/abd19990044-commits/uv-vis-spectrum-studio/actions/workflows/windows-installer.yml)
[![macOS / Linux](https://github.com/abd19990044-commits/uv-vis-spectrum-studio/actions/workflows/cross-platform-desktop.yml/badge.svg)](https://github.com/abd19990044-commits/uv-vis-spectrum-studio/actions/workflows/cross-platform-desktop.yml)
[![Python distribution](https://github.com/abd19990044-commits/uv-vis-spectrum-studio/actions/workflows/python-distribution.yml/badge.svg)](https://github.com/abd19990044-commits/uv-vis-spectrum-studio/actions/workflows/python-distribution.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-3.1.0-blue.svg)](CHANGELOG.md)

**UV-Vis Spectrum Studio** is an open-source scientific environment for UV-Vis spectroscopy, analytical chemistry, chemometrics, publication-quality visualization, quantitative analysis, analytical-method validation, multicomponent spectrophotometry, peak fitting/deconvolution, Fourier/wavelet analysis, and reproducible project archives.

It is designed for analytical chemists, spectroscopy researchers, method-development laboratories, students, and scientists who otherwise need to combine spreadsheets, plotting software, custom scripts, and separate chemometric tools.

**Current release line: v3.1.0**

> **Scientific-use statement:** UV-Vis Spectrum Studio is research and analytical-support software. It is not represented by default as a validated GMP, GLP, 21 CFR Part 11, or ISO 17025 system. Laboratories remain responsible for software qualification, analytical-method validation, access controls, data-integrity controls, and regulatory compliance required by their quality system.

---

## Highlights

### Spectral processing

- Excel, CSV, TXT, DAT, ASC, and TSV import.
- UTF-8, CP1252, Windows-1256, and Latin-1 text handling.
- Automatic wavelength-column detection.
- Deterministic duplicate-wavelength averaging.
- Multiple spectra and publication overlays.
- Absorbance ↔ %Transmittance conversion.
- Savitzky-Golay, moving-average, and Gaussian smoothing.
- ALS, endpoint-linear, and polynomial-edge baseline correction.
- Max, min-max, and area normalization.
- Derivative spectroscopy from 0D through 4D.
- λmax, λmin, FWHM, centroid, peaks, zero crossings, AUC, selected-wavelength response, and S/N tools.

Processing is **not silently enabled**. Smoothing, baseline correction, normalization, derivatives, and other transformations require explicit analyst selection.

### High-order derivative safeguards

Fourth-derivative spectroscopy is supported with numerical safeguards rather than a simple `deriv=4` switch.

The software checks or reports:

- effective Savitzky-Golay polynomial order,
- valid odd window length,
- wavelength spacing and grid nonuniformity,
- median Δλ,
- optional points-per-FWHM,
- smoothing-window/FWHM ratio,
- high-order noise-amplification cautions.

These diagnostics are **not universal acceptance limits**. Appropriate scan interval, bandwidth, smoothing, and S/N depend on the instrument, spectral band shape, and validated method.

### Analytical validation

- Linear calibration with slope, intercept, R², and Sy/x.
- Slope/intercept standard errors and 95% confidence intervals.
- LOD = 3.3σ/|S| and LOQ = 10σ/|S|.
- Manual or regression-derived σ.
- Residual plots and residual tables.
- Lack-of-fit ANOVA with replicated calibration levels.
- Mandel fitting test for linear-versus-quadratic model comparison.
- Approximate inverse-prediction confidence intervals.
- Precision, SD, RSD, recovery, and bias summaries.

A high R² is not treated as sufficient evidence of analytical validity.

### Spectroscopy quality diagnostics

- High-absorbance caution flags.
- Negative-absorbance diagnostics.
- Wavelength-spacing diagnostics.
- Derivative-risk diagnostics.
- Instrument/method caveats for Beer-Lambert linearity and stray light.

### Multicomponent spectrophotometry

- Simultaneous equations.
- Absorptivity-matrix condition number.
- Warning/rejection of severely ill-conditioned systems.
- Absorbance-ratio / Q-analysis.
- Dual-wavelength analysis.
- Ratio spectra.
- Mean-centered ratio spectra.
- Derivative-ratio spectra.
- Job's method.
- Mole-ratio method.
- Standard addition.
- Interpolated isosbestic-point detection.

### Peak fitting and deconvolution

- Gaussian.
- Lorentzian.
- Voigt using the Faddeeva function.
- Pseudo-Voigt with common-FWHM parameterization.
- Multiple overlapping components.
- Polynomial baselines of order 0–3.
- Peak center, amplitude, FWHM, area, RMSE, and R².
- Covariance and parameter-identifiability diagnostics where available.

### Fourier and wavelet analysis

- FFT amplitude/power analysis.
- Hann, Hamming, and Blackman windows.
- Optional detrending.
- Dominant-period estimation.
- DWT denoising.
- Universal-threshold wavelet denoising.
- CWT and scalograms.

### Chemometrics

Pretreatment:

- mean centering,
- autoscaling,
- SNV,
- MSC,
- linear detrending,
- Savitzky-Golay derivatives.

Regression:

- PLS,
- PCR,
- ordinary linear regression,
- Ridge,
- Lasso,
- Elastic Net,
- SVR-RBF,
- KNN,
- Random Forest,
- Extra Trees,
- Gradient Boosting.

Classification:

- LDA,
- QDA,
- logistic regression,
- SVM-RBF,
- KNN,
- Gaussian Naive Bayes,
- Random Forest,
- Extra Trees,
- Gradient Boosting.

Exploratory / validation tools:

- PCA scores/loadings,
- explained and cumulative variance,
- Hotelling T²,
- Q residuals,
- ICA,
- NMF/MCR-like decomposition,
- K-means,
- Ward hierarchical clustering,
- Kennard-Stone,
- SPXY,
- PLS latent-variable screening,
- nested PLS cross-validation,
- Y-randomization,
- VIP wavelength screening,
- interval PLS (iPLS).

Supervised preprocessing is fold-safe for operations that learn population statistics: MSC references, centering, and scaling are fitted from training folds rather than the entire dataset.

> Variable selection performed on all samples can still bias performance. Confirmatory studies should perform selection/tuning inside nested validation or evaluate the locked final model on an untouched independent test set.

---

## Reproducible `.uvvisproj` projects

Project files preserve raw spectral arrays separately from processing settings so reopening a project does not process already processed data a second time.

A project can store:

- raw spectra,
- curve names, colors, and styles,
- source filenames and source hashes,
- user notes,
- analyst and instrument fields,
- processing settings,
- processing audit trail,
- application version,
- Python version,
- operating-system/platform information,
- major dependency versions,
- build/Git commit when embedded by release CI.

Current project archives include SHA-256 integrity information for project members. Modified members are detected when the project is reopened. This is a **tamper-evident integrity mechanism**, not an authenticated regulatory audit-trail/electronic-signature system.

---

## Publication export

- PNG at 300, 600, 720, 900, and 1200 DPI.
- SVG.
- PDF.
- Processed CSV.
- AUC CSV.
- Peak tables.
- User-defined figure dimensions.
- Publication fonts.
- Color or black-and-white figures.
- Direct save to a selected local folder in desktop builds.

---

## Downloads and supported distributions

The same scientific core is tested before packaging.

| Platform | Release asset | Architecture / status |
|---|---|---|
| Windows | Inno Setup `.exe` installer | Windows x64-compatible build; Authenticode supported. A self-signed fallback may trigger SmartScreen warnings. |
| Linux | portable `.tar.gz` | Built on Ubuntu x86_64; pywebview is used when the required GTK/WebKit runtime is available, otherwise the launcher can fall back to the system browser. |
| macOS | `.app` in `.zip` and `.dmg` | Built on GitHub-hosted Apple Silicon macOS. Without Apple Developer signing/notarization, Gatekeeper may require explicit user approval. |
| Python | `.whl` + source `.tar.gz` | Cross-platform source-based installation for Python ≥3.11 where dependencies are available. |
| Source | GitHub source archive | Suitable for development and unsupported CPU architectures when dependencies can be installed. |

Each packaged desktop release is expected to pass:

1. scientific tests,
2. Python compilation checks,
3. PyInstaller packaging,
4. packaged application/server self-test,
5. release checksum generation.

Release workflows also produce environment lock snapshots and build provenance files where applicable.

### Architecture note

“Cross-platform” does not mean that one binary runs on every CPU architecture. Platform binaries are architecture-specific. The Python source distribution is the portable fallback for systems for which a prebuilt desktop binary is not provided.

---

## Installation from source

Python **3.11+** is required.

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

Desktop-development dependencies:

```bash
pip install -r requirements-desktop.txt
```

---

## Testing

```bash
pytest -q
python -m compileall app.py desktop_launcher.py uvvis_studio
```

The automated suite covers spectral calculations, integration, transformations, calibration, LOD/LOQ, Mandel testing, inverse prediction, multicomponent conditioning, fourth-derivative safeguards, project round-trip/integrity, chemometric preprocessing and validation, sample splitting, variable screening, peak fitting, and Streamlit smoke behavior.

Automated numerical tests protect software behavior; they are not a substitute for analytical-method validation on real instrument data.

---

## Scientific validation strategy

Before relying on the software in formal QC or regulated work, independently verify at minimum:

1. import of actual instrument/software export files,
2. reference calculations against trusted independent software or hand calculations,
3. calibration behavior and uncertainty on representative data,
4. method-specific accuracy, precision, selectivity, robustness, stability, matrix effects, and range,
5. chemometric train/test separation and preprocessing/variable-selection strategy,
6. installation and operational qualification appropriate to the laboratory,
7. data-integrity, access-control, audit-trail, backup, and electronic-signature requirements applicable to the workflow.

---

## Repository structure

```text
app.py                                   Streamlit entry point
desktop_launcher.py                      Cross-platform desktop launcher
uvvis_studio/analysis.py                 Spectral processing and metrics
uvvis_studio/io.py                       File import and wavelength detection
uvvis_studio/export.py                   High-resolution/vector export
uvvis_studio/transforms.py               FFT and wavelet analysis
uvvis_studio/quantitation.py             Calibration and direct-entry methods
uvvis_studio/validation.py               Analytical-method validation
uvvis_studio/quality.py                  Spectroscopy/derivative QC diagnostics
uvvis_studio/multicomponent.py           Multicomponent spectrophotometry
uvvis_studio/peakfit.py                  Peak fitting/deconvolution
uvvis_studio/project.py                  Reproducible `.uvvisproj` format
uvvis_studio/chemometrics.py             Core chemometric models/preprocessing
uvvis_studio/chemometrics_advanced.py    Advanced validation/variable selection
uvvis_studio/*_ui.py                     Streamlit presentation layer
installer/                               Windows Inno Setup configuration
.github/workflows/ci.yml                 Python CI
.github/workflows/windows-installer.yml  Windows production build
.github/workflows/cross-platform-desktop.yml Linux/macOS desktop builds
.github/workflows/python-distribution.yml Wheel/sdist build
CITATION.cff                             Citation metadata
.zenodo.json                             Zenodo metadata
ZENODO.md                                DOI/archive release procedure
CHANGELOG.md                             Release history
LICENSE                                  MIT License
LICENSE-NOTICE.md                        Scientific/licensing explanation
```

---

## Citation

If UV-Vis Spectrum Studio contributes materially to a publication, cite the **exact software release** used.

GitHub reads [`CITATION.cff`](CITATION.cff) through **Cite this repository**.

After Zenodo archives a release, prefer the DOI assigned to that version. No DOI is hard-coded before Zenodo actually assigns one.

---

## Zenodo readiness

The repository contains:

- `CITATION.cff`,
- `.zenodo.json`,
- semantic version metadata,
- MIT licensing,
- release changelog,
- platform build workflows,
- release checksums,
- dependency snapshots,
- build provenance metadata.

For the exact GitHub → Zenodo release procedure, see [`ZENODO.md`](ZENODO.md).

A software DOI identifies an archived software release. It does **not** certify analytical-method validation or regulatory compliance.

---

## License

UV-Vis Spectrum Studio is released under the **MIT License**. See [`LICENSE`](LICENSE).

The canonical MIT text is intentionally left unmodified. This keeps the license easy for GitHub, Zenodo, institutions, scanners, and downstream users to identify. [`LICENSE-NOTICE.md`](LICENSE-NOTICE.md) explains third-party dependencies and scientific-use responsibilities without adding restrictions to the MIT License.

---

## Release history

See [`CHANGELOG.md`](CHANGELOG.md).

---

## Author

**Abdulsalam S. Hasan**

Repository: https://github.com/abd19990044-commits/uv-vis-spectrum-studio
