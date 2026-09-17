# Scientific references

UV-Vis Spectrum Studio implements established numerical and chemometric methods. This file records the primary literature or authoritative guidance behind algorithms used by the project. It is not a claim that the software itself has been independently validated against every reference implementation.

## Analytical calibration and validation

- International Council for Harmonisation (ICH). **ICH Q2(R2): Validation of Analytical Procedures**, Step 5, effective 14 June 2024. The guideline discusses least-squares regression, residual assessment, and the use of weighting where calibration observations have different variability (heteroscedasticity). https://www.ema.europa.eu/en/ich-q2r2-validation-analytical-procedures-scientific-guideline
- Breusch, T. S., & Pagan, A. R. (1979). A simple test for heteroscedasticity and random coefficient variation. *Econometrica, 47*(5), 1287–1294. https://doi.org/10.2307/1911963
- Almeida, A. M., Castel-Branco, M. M., & Falcão, A. C. (2002). Linear regression for calibration lines revisited: weighting schemes for bioanalytical methods. *Journal of Chromatography B, 774*(2), 215–222. https://doi.org/10.1016/S1570-0232(02)00244-1

The weighted-calibration implementation supports empirical 1/x, 1/x², 1/y, 1/y² and analyst-supplied positive weights. Weight choice must be justified from the variance/residual structure and analytical performance; the software does not select a weighting scheme from R² alone.

## Smoothing, derivatives, and baseline correction

- Savitzky, A., & Golay, M. J. E. (1964). Smoothing and differentiation of data by simplified least squares procedures. *Analytical Chemistry, 36*(8), 1627–1639. https://doi.org/10.1021/ac60214a047
- Eilers, P. H. C. (2003). A perfect smoother. *Analytical Chemistry, 75*(14), 3631–3636. https://doi.org/10.1021/ac034173t
- Eilers, P. H. C., & Boelens, H. F. M. (2005). **Baseline Correction with Asymmetric Least Squares Smoothing**. Leiden University Medical Centre report/technical note, 21 October 2005.

## Sample selection and chemometrics

- Kennard, R. W., & Stone, L. A. (1969). Computer aided design of experiments. *Technometrics, 11*(1), 137–148. https://doi.org/10.1080/00401706.1969.10490666
- Galvão, R. K. H., Araujo, M. C. U., José, G. E., Pontes, M. J. C., Silva, E. C., & Saldanha, T. C. B. (2005). A method for calibration and validation subset partitioning. *Talanta, 67*(4), 736–740. https://doi.org/10.1016/j.talanta.2005.03.025

The SPXY implementation follows the extension of Kennard–Stone using joint normalized X- and y-space distances. Both methods form pairwise distance matrices and therefore have O(n²) memory/time scaling in the current implementation; they are intended primarily for conventional analytical calibration-set sizes rather than massive datasets.

## Peak profiles

- Olivero, J. J., & Longbothum, R. L. (1977). Empirical fits to the Voigt line width: A brief review. *Journal of Quantitative Spectroscopy and Radiative Transfer, 17*(2), 233–236. https://doi.org/10.1016/0022-4073(77)90161-3

The peak-fitting module uses the Olivero–Longbothum approximation when reporting Voigt FWHM and uses a common-FWHM formulation for the pseudo-Voigt mixture.

## Reproducibility note

These references document the scientific basis of algorithms. They do not replace method-specific validation, instrument qualification, reference-material studies, or independent comparison against validated software/data when the application requires those controls.
