# UV-Vis Spectrum Studio

**UV-Vis Spectrum Studio** is a Windows/Desktop and Streamlit-based analytical spectroscopy suite for UV-Vis data processing, quantitative analysis, publication-quality plotting, transform analysis, analytical-method validation, multicomponent spectrophotometry, peak deconvolution, and chemometrics.

The goal is to provide analytical chemists and spectroscopy researchers with one reproducible workspace for common tasks that would otherwise require combinations of Excel, Origin, separate chemometric software, and custom scripts.

## Highlights in v3.0

Version 3.0 adds a new advanced analytical layer on top of the existing spectroscopy suite:

- Analytical method validation with linearity statistics, 95% confidence intervals, Sy/x, LOD and LOQ.
- Lack-of-fit testing when replicated calibration levels are available.
- Precision, SD, RSD, recovery and bias summaries.
- Multicomponent UV-Vis analysis using simultaneous equations, absorbance-ratio/Q-analysis and dual-wavelength calculations.
- Ratio-spectrum workflows including raw ratio, mean-centering, first derivative and second derivative ratio spectra.
- Peak fitting and deconvolution using Gaussian, Lorentzian, Voigt and pseudo-Voigt functions.
- Portable `.uvvisproj` project files that package spectra, settings and project notes.
- Advanced chemometric validation with Kennard-Stone and SPXY sample splitting.
- PLS latent-component optimization by RMSECV/Q².
- Y-randomization / permutation testing.
- VIP-threshold wavelength selection.
- Interval PLS (iPLS) wavelength-region screening.
- Expanded packaged self-tests so v3 scientific modules must import successfully before a Windows installer is published.

## Core spectroscopy

- Import Excel, CSV, TXT, DAT, ASC and TSV spectra.
- Automatic wavelength-column detection using numeric data beginning around 200 nm or higher.
- Overlay multiple spectra.
- Editable name, color and line style for every curve.
- All curves are **Solid** by default; styles change only when selected by the user.
- Black-and-white publication mode with optional automatic line-pattern assignment.
- Interactive cursor, hover, zoom, pan and spike guides.
- Manual X/Y axis titles, ranges, figure dimensions, fonts, line widths, legends and grids.
- Vertical offsets.
- Absorbance ↔ %Transmittance conversion.
- Blank/reference subtraction and spectral difference, ratio and addition.

## Spectral processing

Processing is **never enabled automatically**. The user explicitly chooses every transformation.

- Savitzky-Golay smoothing.
- Moving-average smoothing.
- Gaussian smoothing.
- ALS baseline correction.
- Linear-endpoint baseline correction.
- Polynomial-edge baseline correction.
- Max, Min-Max and area normalization.
- Derivative spectroscopy from **0D through 4D**.
- Zero-crossing analysis.
- Peak detection and annotations.
- λmax / λmin.
- FWHM.
- Spectral centroid.
- Signal extraction at selected wavelengths.
- S/N estimation from a user-defined noise region.

## Manual area under the curve

The user can enter the integration range directly. The software reports:

- Signed AUC.
- Absolute AUC.
- Exact integration limits.
- Interpolated boundary values when limits fall between measured wavelength points.
- Optional shaded AUC region.
- CSV export.

## Fourier and wavelet analysis

- FFT power spectrum.
- Hann, Hamming and Blackman windows.
- Optional detrending.
- Dominant spectral-period estimation.
- DWT wavelet denoising preview.
- Soft / hard thresholding.
- db4, db6, sym4 and coif3 wavelets.
- Continuous Wavelet Transform (CWT).
- CWT scalograms.

Wavelet denoising is preview-only unless the user explicitly decides to use the processed result.

## Quantitative analysis

### Beer-Lambert calibration

Direct manual entry is supported without Excel. Outputs include:

- Slope and intercept.
- R².
- Sy/x.
- Predicted responses and residuals.
- Calibration plot.
- LOD and LOQ.
- Molar absorptivity, ε, in L·mol⁻¹·cm⁻¹ when molecular weight, concentration unit and path length are provided.

Supported concentration units include µg/mL, mg/L, mmol/L and mol/L.

### Advanced analytical-method validation

The v3 validation engine adds:

- Slope and intercept standard errors.
- 95% confidence intervals.
- Regression-residual diagnostics.
- LOD = 3.3σ/S and LOQ = 10σ/S.
- Manual or regression-based σ.
- Lack-of-fit test with pure-error partitioning when replicate calibration measurements are supplied.
- Precision summary: n, mean, SD, RSD, min and max.
- Recovery and bias summaries.
- Robustness summary functions in the scientific core.

## Stoichiometric and multicomponent spectrophotometry

Existing direct-entry methods:

- Job's method of continuous variations.
- Mole-ratio method with segmented-regression breakpoint estimation.
- Standard addition with x-intercept estimation.
- Interpolated isosbestic-point detection.

v3 multicomponent methods:

- Two-component simultaneous equations.
- Absorbance-ratio / Q-analysis.
- Dual-wavelength calculation.
- Ratio-spectrum calculation from loaded curves.
- Mean-centered ratio spectra.
- First- and second-derivative ratio spectra.

## Peak fitting and deconvolution

A dedicated peak-fitting workspace supports:

- Gaussian peaks.
- Lorentzian peaks.
- Voigt peaks.
- Pseudo-Voigt peaks.
- Multiple overlapping peaks in a single fit.
- Baseline polynomial orders 0–3.
- Peak center.
- Amplitude.
- FWHM.
- Integrated peak area.
- Total fitted curve and component curves.
- RMSE and R² fit diagnostics.

Initial peak centers are supplied by the analyst so the fitting remains transparent and controllable.

## Chemometrics

### Pretreatment

- Mean centering.
- Autoscaling.
- SNV.
- MSC.
- Linear detrending.
- Savitzky-Golay first derivative.
- Savitzky-Golay second derivative.

Chemometric preprocessing is never activated automatically.

### Exploratory analysis and decomposition

- PCA scores and loadings.
- Explained and cumulative variance.
- Hotelling T².
- Q residuals.
- ICA.
- NMF / MCR-like decomposition.

### Regression / calibration models

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

Evaluation includes cross-validation, R²/Q²-style performance, RMSECV, MAECV, observed-vs-predicted plots and residuals.

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

Outputs include cross-validated accuracy, balanced accuracy and confusion matrices where statistically supportable.

### Clustering

- K-means.
- Hierarchical Ward clustering.
- PCA-space cluster visualization.

### Advanced chemometric validation in v3

- **Kennard-Stone** deterministic sample selection.
- **SPXY** sample selection using combined spectral and response distances.
- Automatic **PLS component optimization** across user-defined component ranges.
- RMSECV and Q² comparison versus latent-component count.
- **Y-randomization / permutation testing** for assessing spurious calibration performance.
- PLS **VIP threshold** wavelength selection.
- **Interval PLS (iPLS)** for screening wavelength regions by cross-validated RMSE.

The application warns when sample size is too small for robust modeling. External validation, avoidance of data leakage and full preprocessing disclosure remain the analyst's responsibility.

## Project / session files

v3 introduces a portable `.uvvisproj` format. A project package can contain:

- Spectral X/Y arrays.
- Curve names.
- Curve colors and line styles.
- Source metadata.
- Serializable application settings.
- User notes.

The format is ZIP-based and stores numerical arrays in compressed NumPy form plus project metadata in JSON.

## Publication-quality export

- PNG at 300, 600, 720, 900 and 1200 DPI.
- SVG vector export.
- PDF vector export.
- Processed CSV export.
- AUC CSV export.
- Peak-table CSV export.
- User-defined figure dimensions.
- Publication fonts including Times New Roman, Arial, Calibri, Cambria and Georgia.
- Black-and-white figures with solid/dashed/dotted/dash-dot patterns.

### Direct save to disk

The Windows build supports direct saving to a selected folder:

1. Browse to a destination or enter a path manually.
2. Enter a base filename.
3. Select PNG, SVG, PDF or processed CSV.
4. Save directly to disk.

The application reports the final saved path after a successful write.

## Windows desktop application

The desktop distribution uses:

- PyInstaller.
- pywebview.
- Inno Setup.
- GitHub Actions.
- Authenticode signing support.

The packaged application launches as a desktop window while Streamlit runs only on localhost in the background.

Before publication, the Windows workflow runs the scientific tests, builds the frozen application, imports the scientific modules from the packaged executable, starts the packaged local server, builds the installer and signs the output.

Installers are distributed through **GitHub Releases**.

## Installation from source

Python 3.11 or newer is recommended.

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux/macOS
source .venv/bin/activate

pip install -r requirements.txt
streamlit run app.py
```

For the full Windows/Desktop dependencies:

```bash
pip install -r requirements-desktop.txt
```

## Tests

```bash
pytest -q
```

The v3 tests include synthetic checks for analytical validation, LOD/LOQ, recovery, simultaneous-equation analysis, dual-wavelength calculation, peak deconvolution, project-file round-tripping, Kennard-Stone splitting, PLS optimization and Y-randomization.

## Project structure

```text
app.py                               Main Streamlit interface
desktop_launcher.py                  Windows desktop launcher
uvvis_studio/analysis.py             Spectral processing and metrics
uvvis_studio/io.py                   File import and wavelength detection
uvvis_studio/export.py               High-resolution/vector export
uvvis_studio/transforms.py           FFT and wavelet analysis
uvvis_studio/quantitation.py         Calibration, stoichiometry, standard addition
uvvis_studio/validation.py           Analytical-method validation
uvvis_studio/multicomponent.py       Multicomponent UV-Vis methods
uvvis_studio/peakfit.py              Peak fitting and deconvolution
uvvis_studio/project.py              Portable .uvvisproj project format
uvvis_studio/chemometrics.py         Core multivariate models
uvvis_studio/chemometrics_advanced.py Advanced validation and variable selection
uvvis_studio/chemometrics_ui.py      Chemometrics/advanced-suite entry point
installer/                           Inno Setup configuration
.github/workflows/                   CI and Windows installer workflows
tests/                               Scientific regression tests
```

## Scientific-use note

UV-Vis Spectrum Studio is a research and analytical support tool. Numerical output should be reviewed by a qualified analyst before use in publications, validated QC procedures or regulatory submissions. Smoothing, derivatives, baseline correction, wavelength selection, calibration strategy, train/test partitioning and chemometric validation parameters should be reported explicitly in scientific work.

## Planned next additions

Potential future modules include PLS-DA, SIMCA, OSC/EMSC, Monte-Carlo CV, SPA/CARS/UVE variable selection, leverage/influence diagnostics, kinetic spectrophotometry, binding/pKa fitting, replicate confidence bands, DOE/robustness designs and automated PDF/DOCX analytical reports.

## Author

**Abdulsalam S. Hasan**

## License

See the `LICENSE` file in this repository.
