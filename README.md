# UV-Vis Spectrum Studio

[![CI](https://github.com/abd19990044-commits/uv-vis-spectrum-studio/actions/workflows/ci.yml/badge.svg)](https://github.com/abd19990044-commits/uv-vis-spectrum-studio/actions/workflows/ci.yml)
[![Windows](https://github.com/abd19990044-commits/uv-vis-spectrum-studio/actions/workflows/windows-installer.yml/badge.svg)](https://github.com/abd19990044-commits/uv-vis-spectrum-studio/actions/workflows/windows-installer.yml)
[![Linux / macOS](https://github.com/abd19990044-commits/uv-vis-spectrum-studio/actions/workflows/cross-platform-desktop.yml/badge.svg)](https://github.com/abd19990044-commits/uv-vis-spectrum-studio/actions/workflows/cross-platform-desktop.yml)
[![Python distribution](https://github.com/abd19990044-commits/uv-vis-spectrum-studio/actions/workflows/python-distribution.yml/badge.svg)](https://github.com/abd19990044-commits/uv-vis-spectrum-studio/actions/workflows/python-distribution.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-3.1.1-blue.svg)](CHANGELOG.md)

**UV-Vis Spectrum Studio** is open-source scientific software for UV-Vis spectroscopy, analytical chemistry, chemometrics, publication-quality visualization, quantitative analysis, analytical-method validation, multicomponent spectrophotometry, peak fitting/deconvolution, Fourier/wavelet analysis, and reproducible project archives.

It is designed for analytical chemists, spectroscopy researchers, method-development laboratories, students, and scientists who would otherwise need to combine spreadsheets, plotting software, custom scripts, and separate chemometric tools.

**Current release line: v3.1.1**

**Qualification status (2026-09-24):** v3.1.1 is a research release candidate.
See [PRODUCTION_REVIEW_2026-09-24.md](PRODUCTION_REVIEW_2026-09-24.md) for executed
gates and remaining native desktop qualification. This supersedes the earlier
100-test summary; passing source tests does not qualify Windows/macOS installers.

**Scientific hardening update (2026-09-23):** Wavelength-integral units are
Abs·nm or Abs·Å; they are not Å/cm². Absolute area splits line segments at
zero crossings. Calibration supports independently prepared blanks and
additional regression diagnostics. Small-sample PLS cross-validation limits
components to the smallest training fold. See
[SCIENTIFIC_REVIEW_2026-09-23.md](SCIENTIFIC_REVIEW_2026-09-23.md) for verification
and remaining release gates.

> **Scientific-use statement:** UV-Vis Spectrum Studio is research and analytical-support software. It is not represented by default as a validated GMP, GLP, 21 CFR Part 11, or ISO/IEC 17025 system. Laboratories remain responsible for software qualification, analytical-method validation, access controls, data-integrity controls, and regulatory compliance required by their quality system.

---

## Scientific capabilities

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

Fourth-derivative spectroscopy is supported with numerical safeguards rather than a simple `deriv=4` switch. The software checks or reports effective Savitzky-Golay polynomial order, valid odd window length, wavelength spacing/grid nonuniformity, median Δλ, optional points-per-FWHM, smoothing-window/FWHM ratio, and high-order noise-amplification cautions.

These diagnostics are not universal acceptance limits. Appropriate scan interval, bandwidth, smoothing, and S/N depend on the instrument, spectral band shape, and validated method.

### Analytical validation

- Linear calibration with slope, intercept, R², and Sy/x.
- Sample SD from independently prepared blanks as an explicit LOD/LOQ option.
- Slope/intercept standard errors and 95% confidence intervals.
- LOD = 3.3σ/|S| and LOQ = 10σ/|S|.
- Manual or regression-derived σ.
- Residual plots and tables.
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

- Simultaneous equations with absorptivity-matrix condition number.
- Warning/rejection of severely ill-conditioned systems.
- Absorbance-ratio / Q-analysis.
- Dual-wavelength analysis.
- Ratio spectra, mean-centered ratio spectra, and derivative-ratio spectra.
- Job's method, mole-ratio method, standard addition, and interpolated isosbestic-point detection.

### Peak fitting and deconvolution

- Gaussian, Lorentzian, Voigt, and common-FWHM pseudo-Voigt models.
- Multiple overlapping components.
- Polynomial baselines of order 0–3.
- Peak center, amplitude, FWHM, area, RMSE, and R².
- Covariance and parameter-identifiability diagnostics where available.

### Fourier and wavelet analysis

- FFT amplitude/power analysis and common windows.
- Optional detrending and dominant-period estimation.
- DWT denoising with universal-threshold support.
- CWT and scalograms.

### Chemometrics

Pretreatment includes mean centering, autoscaling, SNV, MSC, detrending, and Savitzky-Golay derivatives. Regression includes PLS, PCR, OLS, Ridge, Lasso, Elastic Net, SVR-RBF, KNN, Random Forest, Extra Trees, and Gradient Boosting. Classification includes LDA, QDA, logistic regression, SVM-RBF, KNN, Gaussian Naive Bayes, Random Forest, Extra Trees, and Gradient Boosting.

Exploratory/validation tools include PCA, Hotelling T², Q residuals, ICA, NMF/MCR-like decomposition, K-means, Ward clustering, Kennard-Stone, SPXY, latent-variable screening, nested PLS cross-validation, Y-randomization, VIP screening, and interval PLS.

Supervised preprocessing is fold-safe for operations that learn population statistics: MSC references, centering, and scaling are fitted from training folds rather than the entire dataset.

> Variable selection performed on all samples can still bias performance. Confirmatory studies should perform selection/tuning inside nested validation or evaluate the locked final model on an untouched independent test set.

---

## Reproducible `.uvvisproj` projects

Project files preserve raw spectral arrays separately from processing settings so reopening a project does not process already processed data twice. Projects can store raw spectra, appearance metadata, source names and hashes, analyst/instrument fields, processing settings, audit information, application/environment versions, and embedded build provenance.

Current archives contain SHA-256 member integrity information. Modified members are detected when reopened. This is a **tamper-evident integrity mechanism**, not an authenticated regulatory audit-trail/electronic-signature system.

---

## Publication export

- PNG at 300, 600, 720, 900, and 1200 DPI.
- SVG and PDF.
- Processed/AUC CSV and peak tables.
- User-defined dimensions and publication fonts.
- Color or black-and-white output.
- Direct save to a selected local folder in desktop builds.

---

## Downloads and platform coverage

The same scientific core is tested before packaging. Desktop binaries are architecture-specific.

| Platform | Planned/release asset | Architecture |
|---|---|---|
| Windows | Inno Setup `.exe` installer | x86_64 / x64-compatible |
| Linux | portable `.tar.gz` | x86_64 and ARM64 |
| macOS | `.app` in `.zip` plus `.dmg` | Intel x86_64 and Apple Silicon ARM64 |
| Python | `.whl` + source `.tar.gz` | OS-independent source distribution where dependencies are available |
| Source | GitHub source archive | Portable fallback for unsupported binary targets |

Windows Authenticode signing is supported; when only the self-signed fallback is available, Windows may display SmartScreen warnings. macOS builds are architecture-native; until Apple Developer ID signing/notarization is configured, Gatekeeper may require explicit user approval.

The current GitHub Actions build matrix uses GitHub-hosted x64/ARM64 Linux and Intel/ARM64 macOS runners. GitHub documents `macos-15-intel` for Intel and `macos-15` for ARM64, and provides x64 and ARM64 Ubuntu runners. Platform assets therefore represent separately built native binaries rather than cross-compiled assumptions.

Each packaged release is expected to pass scientific tests, compilation checks, PyInstaller packaging, packaged application/server self-test, and SHA-256 generation. Release jobs also create dependency lock snapshots and build-provenance files.

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
app.py                                      Streamlit entry point
desktop_launcher.py                         Desktop/server launcher
uvvis_studio/analysis.py                    Spectral processing and metrics
uvvis_studio/io.py                          File import and cleaning
uvvis_studio/export.py                      High-resolution/vector export
uvvis_studio/transforms.py                  FFT and wavelet analysis
uvvis_studio/quantitation.py                Calibration and direct-entry methods
uvvis_studio/validation.py                  Analytical-method validation
uvvis_studio/quality.py                     Spectroscopy/derivative QC
uvvis_studio/multicomponent.py              Multicomponent spectrophotometry
uvvis_studio/peakfit.py                     Peak fitting/deconvolution
uvvis_studio/project.py                     Reproducible `.uvvisproj` format
uvvis_studio/chemometrics.py                Core chemometrics/preprocessing
uvvis_studio/chemometrics_advanced.py       Advanced validation/selection
uvvis_studio/*_ui.py                        Streamlit presentation layer
installer/                                  Windows Inno Setup
.github/workflows/ci.yml                    Python CI
.github/workflows/windows-installer.yml     Windows release build
.github/workflows/cross-platform-desktop.yml Linux/macOS x64+ARM64 builds
.github/workflows/python-distribution.yml   Wheel/sdist build
CITATION.cff                                Citation File Format metadata
.zenodo.json                                Zenodo GitHub-release metadata
codemeta.json                               CodeMeta interoperability metadata
ZENODO.md                                   DOI/archive release procedure
CHANGELOG.md                                Release history
LICENSE                                     Canonical MIT License
LICENSE-NOTICE.md                           Scientific/licensing explanation
```

---

## Citation and Zenodo

If UV-Vis Spectrum Studio contributes materially to research, cite the **exact software release** used. GitHub reads [`CITATION.cff`](CITATION.cff) to provide its citation interface.

The repository intentionally contains both `CITATION.cff` and `.zenodo.json`. Zenodo currently gives `.zenodo.json` precedence when both are present, while `CITATION.cff` remains useful to GitHub and citation tooling. After Zenodo archives a release, prefer the DOI assigned to that archived version. No DOI is hard-coded before Zenodo actually assigns one.

Zenodo readiness includes semantic version metadata, MIT licensing, changelog, CodeMeta metadata, cross-platform release workflows, checksums, dependency snapshots, and build provenance. See [`ZENODO.md`](ZENODO.md) for the release procedure.

A software DOI identifies and preserves an archived software release; it does **not** certify analytical-method validation or regulatory compliance.

---

## License

UV-Vis Spectrum Studio is released under the **MIT License**. See [`LICENSE`](LICENSE).

The canonical MIT text is intentionally left unmodified so that GitHub, Zenodo, package registries, institutions, license scanners, and downstream users can identify it unambiguously. [`LICENSE-NOTICE.md`](LICENSE-NOTICE.md) documents third-party and scientific-use responsibilities without adding restrictions to the MIT License.

---

## Release history

See [`CHANGELOG.md`](CHANGELOG.md).

---

## Author

**Abdulsalam S. Hasan**  
University of Mosul · College of Science · Department of Chemistry

Repository: https://github.com/abd19990044-commits/uv-vis-spectrum-studio
