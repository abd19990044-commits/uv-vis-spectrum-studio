# Changelog

All notable changes to UV-Vis Spectrum Studio are documented here.

The project follows semantic versioning for public releases where practical.

## 3.1.1 — 2026-09-24

- Correct spectral integration dimensions, zero-crossing absolute area and centroid integration.
- Stabilize OLS/WLS, Mandel, Breusch–Pagan and inverse prediction across measurement units.
- Report undefined lack-of-fit inference for zero pure error and undefined R² for constant responses.
- Add independent blank statistics and calibration diagnostics to the research workflow.
- Bound PLS/PCR components to training-fold rank; correct SPXY scaling and duplicate split indices.
- Preserve first observations in headerless text files and support scans beginning at 190 nm.
- Validate nested array headers, decompressed sizes, complete integrity manifests and widget settings.
- Repair comparison view, AUC callbacks, units, project restoration and stale export invalidation.
- Preserve typography proportions in raster exports and automatic physical axis titles.
- Require Pillow 12.3 or newer after dependency auditing.
- Repair installed entry point; add scientific, archive and actual-browser regression gates.
- Record release evidence and pending native desktop qualification separately.

## 3.1.0 — 2026-09-17

### Scientific hardening

- Added Mandel fitting test for linear-versus-quadratic calibration assessment.
- Added inverse-prediction confidence intervals for unknown concentration estimates.
- Added absorbance-quality diagnostics and high-order derivative safeguards.
- Added explicit fourth-derivative sampling/window diagnostics.
- Added absorptivity-matrix condition-number safeguards for simultaneous-equation analysis.
- Added fold-safe supervised preprocessing to reduce chemometric cross-validation leakage.
- Added nested PLS cross-validation for less biased latent-variable model-selection assessment.
- Added weighted linear calibration with 1/x, 1/x², 1/y, 1/y², and custom weights.
- Added Breusch–Pagan and residual diagnostics for heteroscedasticity assessment; weighting remains an analyst-selected model choice rather than an automatic decision.
- Corrected pseudo-Voigt semantics to use a common FWHM parameterization.
- Added peak-fit covariance/parameter-identifiability diagnostics.
- Added `REFERENCES.md` documenting primary scientific references for major numerical and chemometric algorithms and methodological guidance.

### Reproducibility and integrity

- Project format upgraded with SHA-256 integrity verification for tamper-evident `.uvvisproj` archives.
- Added analyst, instrument, source hashes, processing audit trail, package versions, Python version, platform, and build provenance metadata.
- Added release dependency snapshots and SHA-256 checksums in CI packaging workflows.

### File import

- Added text decoding fallbacks for UTF-8, CP1252, Windows-1256, and Latin-1.
- Duplicate wavelengths are averaged deterministically by default instead of silently retaining the first observation.

### Distribution

- Windows installer and portable desktop build.
- macOS Intel and Apple Silicon desktop application archives and DMG images.
- Linux x86_64 and ARM64 portable desktop bundles.
- Standard Python source distribution and wheel for source-based installation.
- Added Zenodo/CITATION metadata for future DOI archiving.

## 3.0.1

- Added full `.uvvisproj` workspace restoration of raw spectra, curve appearance, processing parameters, publication settings, and project notes.
- Added v3 analytical suite: validation, multicomponent spectroscopy, peak fitting/deconvolution, project persistence, and advanced chemometrics.

## Earlier versions

Earlier releases established the core UV-Vis plotting, processing, derivative spectroscopy, quantitative analysis, FFT/wavelet tools, publication export, and initial Windows desktop packaging.
