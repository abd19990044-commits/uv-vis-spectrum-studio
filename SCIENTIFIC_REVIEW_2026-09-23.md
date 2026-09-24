> Release-readiness status is superseded by PRODUCTION_REVIEW_2026-09-24.md. This is the first review pass.

# Scientific and software review — 2026-09-23

## Scope and finding

Reviewed the supplied source archive as an analytical research application.
The archive already included derivatives (0–4), selectable interval AUC,
Fourier/wavelet transforms, chemometrics, plot controls, project archives,
calibration, method validation, and test suites. Earlier reports in the archive
called the project release-ready, but the following issues survived those
reviews. The fixes below supersede those claims for the areas affected.

| Area | Observed defect | Correction |
| --- | --- | --- |
| Spectral integral | The application labeled a wavelength integral as Å/cm² and divided by an assumed 1 cm² cell area. Wavelength integration does not involve the cuvette's beam cross section. | Display Abs·nm and Abs·Å (or the corresponding processed-ordinate unit). Multiply by 10 only when converting nm to Å. Remove the cell-area argument. |
| Signed curves | Integrating the absolute endpoint values of a segment that crosses zero overstates the absolute area. | Interpolate the zero crossing and integrate the two resulting segments. Use the same integral for area normalization and the centroid denominator. |
| Blank-based limits | The calibration page provided only manual response SD, hiding blank preparation count and the sample-SD convention. | Accept separately prepared blank responses, require at least three and calculate SD with ddof=1. Show n, mean, and SD. |
| Calibration input | Mismatched concentration/response lengths could broadcast or fail obscurely; a negative sigma was silently made positive. | Reject mismatched lengths and negative/nonfinite sigma with explicit errors. |
| PLS cross-validation | Component selection was bounded by all samples but could exceed the smallest *training fold*, crashing on small datasets. | Bound component count by the smallest inner/CV training fold for optimization, nested CV, Y-randomization, and interval PLS. Reject folds with fewer than two training samples. |
| Interpretation | The main calibration view lacked a residual chart and direct access to key diagnostics. | Show 95% coefficient intervals, residuals, Mandel curvature comparison, replicated-level lack of fit, Breusch–Pagan variance diagnostic, and approximate inverse prediction where data support them. |
| Interval UI | Edited AUC bounds could be reflected in the results before the plotted interval was updated; reset widgets could retain stale inputs. | Apply the interval and reset widget values in button callbacks before the next render so shaded plot and reported AUC use the same bounds. |

## Independent numeric checks

1. A linear signal from 0 to 2 nm with responses -1 and +1 has
   **signed integral 0** and **absolute integral 1 signal·nm**.
   Integrating absolute *endpoints* would incorrectly report 2.
2. A measured positive region with 11.175 Abs·nm corresponds to
   **111.75 Abs·Å**, without an area correction.
3. Ten independent blank responses
   (0.0031, 0.0027, 0.0034, 0.0029, 0.0032, 0.0030, 0.0035,
   0.0028, 0.0033, 0.0031) have sample SD
   **0.0002581988897 Abs**. At slope 0.0794914676
   Abs/(µg/mL), the formula 3.3σ/|S| gives
   **0.0107188402 µg/mL** and 10σ/|S| gives
   **0.0324813339 µg/mL**. These are *calculated detection
   estimates*, not evidence that the method quantifies reliably at LOQ.

## Verification performed here

- Full automated pytest suite, including new zero-crossing, blank-input,
  invalid-sigma, and small-sample PLS regression cases: **passed**.
- Python compilation of app, launcher, package, and tests: **passed**.
- Desktop launcher self-test: **passed in this Linux runtime**.
- Streamlit AppTest initial rendering: **passed within the pytest suite**.
- Streamlit local HTTP health endpoint: **responded ok**.

## Limits before a production or regulated release

The source is a runnable **research build**. This work did not qualify a
Windows installer, test real Shimadzu/JASCO file exports, run a full browser
acceptance pass on the amended calibration interface, or conduct independent
method validation with reference materials. The inherited reports refer to
artifacts and screenshots absent from this compact source archive and should
not be cited as evidence for this amended build. CI must be rerun on the
target operating systems, and analytical results should be checked against
independent laboratory data before use in a publication or routine QC.

For blanks, each entered value should come from an independent preparation
carried through the full analytical procedure and measured against the
documented instrument reference. The analyst must report the sigma source,
calibration range, units, and preparation protocol. An R² value and a
calculated LOD/LOQ do not establish selectivity, accuracy, precision, or
robustness.
