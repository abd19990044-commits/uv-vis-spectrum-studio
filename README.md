# UV-Vis Spectrum Studio

**UV-Vis Spectrum Studio** is a Windows/Desktop and Streamlit-based analytical spectroscopy suite for UV-Vis data processing, quantitative analysis, publication-quality plotting, transform analysis, and chemometrics.

The project is designed for analytical chemists and spectroscopy researchers who want one workspace for routine spectral processing, calibration, stoichiometric methods, advanced signal analysis, and multivariate modeling without depending on Excel or Origin for common workflows.

## Core spectroscopy features

- Import Excel, CSV, TXT, DAT, ASC, TSV and related tabular spectra.
- Automatic wavelength-column detection using numeric data beginning at approximately 200 nm or higher.
- Overlay multiple spectra in one figure.
- Editable display name for every curve.
- Independent curve color and line style.
- All curves use **Solid** lines by default; the user can change them manually.
- Dedicated black-and-white publication mode with optional automatic line-pattern assignment.
- Interactive cursor, hover readout, zoom, pan, spikes and reset controls.
- Manual X/Y axis titles, ranges, plot dimensions, font family, font size, line width, legend position and grid settings.
- Vertical offsets for stacked spectra.
- Absorbance ↔ %Transmittance conversion.
- Blank/reference subtraction and spectrum arithmetic: difference, ratio and addition.

## Spectral processing

Processing methods are **not enabled automatically**. The original spectrum remains unmodified unless the user explicitly selects a method.

- Savitzky-Golay smoothing.
- Moving-average smoothing.
- Gaussian smoothing.
- ALS baseline correction.
- Linear-endpoint baseline correction.
- Polynomial-edge baseline correction.
- Max normalization.
- Min-Max normalization.
- Area normalization.
- Derivative spectroscopy from **0D to 4D**.
- Zero-crossing analysis for derivative spectra.
- Peak detection with configurable prominence and minimum distance.
- Peak annotations directly on the figure.
- λmax and λmin.
- Signal at λmax/λmin.
- FWHM.
- Spectral centroid.
- Peak count, wavelength, intensity and prominence.
- Signal extraction at user-specified wavelengths.
- Signal-to-noise estimation from a user-defined noise region.

## Area under the curve

The program supports manual wavelength-range integration.

For each selected range it can report:

- Signed AUC.
- Absolute AUC.
- Exact selected wavelength limits.
- Optional shaded AUC region on the plot.
- CSV export of AUC results.

Boundary values are interpolated when the requested integration limit lies between measured wavelength points.

## Fourier and wavelet analysis

A dedicated transform-analysis workspace includes:

- FFT power-spectrum analysis.
- Hann, Hamming and Blackman windows.
- Optional linear detrending before FFT.
- Dominant spectral-period estimation.
- Discrete Wavelet Transform denoising preview.
- Soft and hard thresholding.
- Wavelets including db4, db6, sym4 and coif3.
- Continuous Wavelet Transform (CWT).
- CWT scalograms with selectable scales and wavelet families.

Wavelet denoising is shown as a preview and is never applied automatically.

## Quantitative analytical chemistry

### Beer-Lambert calibration

Calibration data can be entered directly inside the application; Excel is not required.

The calibration module reports:

- Slope.
- Intercept.
- R².
- Regression residual standard deviation (Sy/x).
- Predicted responses.
- Residuals.
- Calibration curve.
- LOD.
- LOQ.
- Molar absorptivity, ε, in L·mol⁻¹·cm⁻¹ when molecular weight, concentration unit and path length are supplied.

Supported concentration units include:

- µg/mL.
- mg/L.
- mmol/L.
- mol/L.

For LOD/LOQ, the user can use the regression residual SD or provide a manual blank/response standard deviation.

## Stoichiometric methods

The application contains direct-entry workspaces for:

- **Job's method of continuous variations**.
- **Mole-ratio method** with segmented-regression breakpoint estimation.
- **Standard-addition method** with x-intercept and original-sample concentration calculation.
- Isosbestic-point detection between two spectra using interpolation in the common wavelength range.

These modules work without uploading an external spreadsheet.

## Chemometrics

A dedicated **Chemometrics** section is included for multivariate spectroscopy and analytical modeling.

### Spectral pretreatment

- Mean centering.
- Autoscaling.
- SNV.
- MSC.
- Linear detrending.
- Savitzky-Golay first derivative.
- Savitzky-Golay second derivative.

Chemometric preprocessing is never enabled automatically.

### Exploratory analysis and decomposition

- PCA.
- PCA scores.
- PCA loadings.
- Explained variance.
- Cumulative explained variance.
- Hotelling T² diagnostics.
- Q-residual diagnostics.
- ICA.
- NMF / MCR-like non-negative decomposition.

### Multivariate regression and calibration

- PLS regression.
- PCR.
- Ordinary linear regression.
- Ridge regression.
- Lasso.
- Elastic Net.
- SVR with RBF kernel.
- K-nearest-neighbors regression.
- Random Forest regression.
- Extra Trees regression.
- Gradient Boosting regression.

Model evaluation includes, where applicable:

- Cross-validation.
- R² / Q²-style CV performance.
- RMSECV.
- MAECV.
- Observed-versus-predicted plots.
- Residual analysis.

### Variable importance

- PLS VIP scores.
- VIP versus wavelength plots.
- Ranked important variables / wavelengths.

### Classification

- LDA.
- QDA.
- Logistic regression.
- SVM-RBF.
- KNN classification.
- Gaussian Naive Bayes.
- Random Forest classification.
- Extra Trees classification.
- Gradient Boosting classification.

Classification outputs include cross-validated accuracy, balanced accuracy and confusion matrices when the data support them.

### Unsupervised clustering

- K-means clustering.
- Hierarchical Ward clustering.
- PCA-space visualization of clusters.

The software warns when the number of samples is too small for a robust chemometric model. Multivariate model performance should always be interpreted with appropriate external validation, sample-size considerations, preprocessing disclosure and avoidance of data leakage.

## Publication-quality export

The publication workspace supports:

- PNG export at 300, 600, 720, 900 and 1200 DPI.
- SVG vector export.
- PDF vector export.
- Processed CSV export.
- AUC CSV export.
- Peak-table CSV export.
- User-defined figure width and height in inches.
- Publication-friendly fonts including Times New Roman, Arial, Calibri, Cambria, Georgia and others.
- Black-and-white figures with editable solid/dashed/dotted/dash-dot line patterns.

### Direct save to disk

The Windows/Desktop build includes direct saving to a user-selected folder.

The user can:

1. Browse for a destination folder or type a path manually.
2. Enter the desired file name.
3. Select PNG, SVG, PDF or CSV.
4. Save the output directly to that folder.

The application displays the final saved path after successful export.

## Windows desktop version

The repository includes a Windows packaging workflow based on:

- PyInstaller.
- pywebview.
- Inno Setup.
- GitHub Actions.
- Authenticode signing support.

The packaged application launches as a desktop window while Streamlit runs locally in the background.

The Windows build includes an internal packaged-server self-test before an installer is published. The test verifies that the main scientific modules are importable and that the local application server starts successfully.

Installers are distributed through the repository's **GitHub Releases** page.

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

For the full Windows/Desktop dependency set:

```bash
pip install -r requirements-desktop.txt
```

## Tests

Run the scientific test suite with:

```bash
pytest -q
```

The repository also uses GitHub Actions CI across supported Python versions and compiles the application modules as part of automated verification.

## Project structure

```text
app.py                         Main Streamlit user interface
desktop_launcher.py            Windows desktop launcher
uvvis_studio/analysis.py       Spectral processing and metrics
uvvis_studio/io.py             Spectral file import and wavelength detection
uvvis_studio/export.py         High-resolution and vector export
uvvis_studio/transforms.py     FFT and wavelet analysis
uvvis_studio/quantitation.py   Calibration, stoichiometry and standard addition
uvvis_studio/chemometrics.py   Multivariate preprocessing and modeling
installer/                     Inno Setup configuration
build_assets/                  Windows build assets
.github/workflows/             CI and Windows-installer workflows
tests/                         Scientific regression tests
```

## Scientific-use notes

UV-Vis Spectrum Studio is intended to support analytical and spectroscopy research workflows, but numerical output should be reviewed by a qualified analyst before being used in publications, regulatory submissions or validated quality-control procedures.

Important methodological parameters—such as smoothing window, polynomial order, derivative order, baseline settings, wavelength range, calibration model and cross-validation strategy—should be reported when results are published.

## Current development direction

Planned advanced chemometric capabilities include methods such as:

- PLS-DA.
- SIMCA.
- OSC / EMSC.
- Kennard-Stone and SPXY sample selection.
- Monte-Carlo cross-validation.
- Permutation testing and Y-randomization.
- Interval-PLS.
- SPA and CARS variable selection.
- Additional leverage and influence diagnostics.

These methods will be added only with explicit validation and tests rather than as unverified UI options.

## Author

**Abdulsalam S. Hasan**

## License

See the `LICENSE` file in this repository.
