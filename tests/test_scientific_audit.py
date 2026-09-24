from __future__ import annotations

import numpy as np
import pytest
from scipy import stats

from uvvis_studio.analysis import (
    absorbance_to_transmittance,
    calculate_metrics,
    derivative,
    estimate_snr,
    integrate_range,
    normalize,
    peak_table,
    process_spectrum,
    smooth_signal,
    transmittance_to_absorbance,
    zero_crossings,
)
from uvvis_studio.chemometrics import (
    SpectralPreprocessor,
    _msc_rows,
    msc,
    snv,
)
from uvvis_studio.chemometrics_advanced import (
    kennard_stone,
    nested_pls_evaluation,
    optimize_pls_components,
    spxy,
    vip_threshold_select,
    y_randomization_test,
)
from uvvis_studio.multicomponent import (
    derivative_ratio,
    dual_wavelength,
    q_absorbance_ratio,
    ratio_spectrum,
    simultaneous_equations,
)
from uvvis_studio.peakfit import fit_peaks, gaussian, lorentzian
from uvvis_studio.quantitation import (
    calculate_molar_absorptivity,
    isosbestic_points,
    job_method,
    linear_calibration,
    mole_ratio_method,
    standard_addition,
    weighted_linear_calibration,
)
from uvvis_studio.validation import (
    inverse_prediction_interval,
    lack_of_fit_test,
    linearity_validation,
    mandel_fitting_test,
    precision_summary,
    recovery_summary,
)


# =========================================================================
# 1. REFERENCE NUMERICAL DATASET VALIDATION (INDEPENDENT ORACLE)
# =========================================================================

def test_reference_numerical_dataset_independent_validation():
    """Verify the benchmark analytical dataset against first-principles formulas."""
    conc = np.array([0, 1, 2, 4, 6, 8, 10], dtype=float)
    absorbance = np.array([0.003, 0.081, 0.161, 0.319, 0.481, 0.636, 0.798], dtype=float)
    blanks = np.array([0.0031, 0.0027, 0.0034, 0.0029, 0.0032, 0.0030, 0.0035, 0.0028, 0.0033, 0.0031], dtype=float)
    mw = 230.26  # g/mol
    path_length = 1.0  # cm

    # --- Independent First-Principles Calculations ---
    n = len(conc)
    x_bar = np.mean(conc)
    y_bar = np.mean(absorbance)
    s_xx = np.sum((conc - x_bar) ** 2)
    s_yy = np.sum((absorbance - y_bar) ** 2)
    s_xy = np.sum((conc - x_bar) * (absorbance - y_bar))

    expected_slope = s_xy / s_xx
    expected_intercept = y_bar - expected_slope * x_bar
    expected_r2 = (s_xy ** 2) / (s_xx * s_yy)

    residuals_indep = absorbance - (expected_intercept + expected_slope * conc)
    dof = n - 2
    expected_syx = np.sqrt(np.sum(residuals_indep ** 2) / dof)

    # Blank statistics (independent ddof=1 sample SD)
    expected_blank_mean = np.mean(blanks)
    expected_blank_sd = np.std(blanks, ddof=1)

    # LOD/LOQ using independent blank SD
    expected_lod = 3.3 * expected_blank_sd / expected_slope
    expected_loq = 10.0 * expected_blank_sd / expected_slope

    # Molar absorptivity (L / (mol * cm))
    # 1 µg/mL = 1e-3 g/L; c_molar = c_mass * 1e-3 / MW
    # A = eps * c_molar * l = eps * (c_mass * 1e-3 / MW) * l
    # slope = eps * 1e-3 * l / MW => eps = slope * MW * 1000 / l
    expected_eps = expected_slope * mw * 1000.0 / path_length

    # Compare with expected values from audit specification
    assert abs(expected_slope - 0.07949147) < 1e-6
    assert abs(expected_intercept - 0.0021092) < 1e-6
    assert abs(expected_r2 - 0.9999788) < 1e-6
    assert abs(expected_blank_mean - 0.00310) < 1e-5
    assert abs(expected_blank_sd - 0.0002582) < 1e-6
    assert abs(expected_lod - 0.01072) < 1e-4
    assert abs(expected_loq - 0.03248) < 1e-4
    assert abs(expected_eps - 18303.71) < 0.1

    # --- Call Software Implementation Under Test ---
    cal_res = linear_calibration(
        conc,
        absorbance,
        sigma=expected_blank_sd,
        molecular_weight_g_mol=mw,
        path_length_cm=path_length,
        concentration_unit="µg/mL",
    )

    assert abs(cal_res.slope - expected_slope) < 1e-9
    assert abs(cal_res.intercept - expected_intercept) < 1e-9
    assert abs(cal_res.r2 - expected_r2) < 1e-9
    assert abs(cal_res.syx - expected_syx) < 1e-9
    assert abs(cal_res.lod - expected_lod) < 1e-9
    assert abs(cal_res.loq - expected_loq) < 1e-9
    assert abs(cal_res.epsilon_L_mol_cm - expected_eps) < 1e-7

    # Test LinearityValidation
    val_res = linearity_validation(
        conc,
        absorbance,
        sigma=expected_blank_sd,
        molecular_weight_g_mol=mw,
        path_length_cm=path_length,
        concentration_unit="µg/mL",
    )
    assert abs(val_res.slope - expected_slope) < 1e-9
    assert abs(val_res.intercept - expected_intercept) < 1e-9
    assert abs(val_res.epsilon_L_mol_cm - expected_eps) < 1e-7


# =========================================================================
# 2. MOLAR ABSORPTIVITY UNIT CONVERSIONS
# =========================================================================

def test_molar_absorptivity_unit_conversions():
    """Verify unit conversions for molar absorptivity across analytical units."""
    slope = 0.05
    l = 1.0
    mw = 200.0  # g/mol

    # mol/L (M) -> eps = slope / l
    assert calculate_molar_absorptivity(slope, l, mw, "mol/L") == pytest.approx(0.05)
    assert calculate_molar_absorptivity(slope, l, None, "M") == pytest.approx(0.05)

    # mmol/L (mM) -> eps = slope * 1000 / l
    assert calculate_molar_absorptivity(slope, l, mw, "mmol/L") == pytest.approx(50.0)
    assert calculate_molar_absorptivity(slope, l, None, "mM") == pytest.approx(50.0)

    # µmol/L (µM) -> eps = slope * 1e6 / l
    assert calculate_molar_absorptivity(slope, l, None, "µM") == pytest.approx(50000.0)
    assert calculate_molar_absorptivity(slope, l, None, "uM") == pytest.approx(50000.0)

    # g/L or mg/mL -> eps = slope * mw / l
    assert calculate_molar_absorptivity(slope, l, mw, "g/L") == pytest.approx(10.0)
    assert calculate_molar_absorptivity(slope, l, mw, "mg/mL") == pytest.approx(10.0)

    # µg/mL or mg/L -> eps = slope * mw * 1000 / l
    assert calculate_molar_absorptivity(slope, l, mw, "µg/mL") == pytest.approx(10000.0)
    assert calculate_molar_absorptivity(slope, l, mw, "mg/L") == pytest.approx(10000.0)

    # ng/mL -> eps = slope * mw * 1e6 / l
    assert calculate_molar_absorptivity(slope, l, mw, "ng/mL") == pytest.approx(10000000.0)

    # Invalid cases
    assert calculate_molar_absorptivity(slope, 0.0, mw, "mol/L") is None
    assert calculate_molar_absorptivity(slope, l, None, "µg/mL") is None


# =========================================================================
# 3. SPECTRAL FUNDAMENTALS AND GRID INVARIANTS
# =========================================================================

def test_absorbance_transmittance_roundtrip():
    """Verify A <-> %T round-trip conversion accuracy."""
    a_values = np.array([0.001, 0.05, 0.1, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0])
    t_values = absorbance_to_transmittance(a_values)
    a_recovered = transmittance_to_absorbance(t_values)
    np.testing.assert_allclose(a_values, a_recovered, rtol=1e-12)

    # Boundary cases
    assert np.isnan(transmittance_to_absorbance(np.array([0.0, -5.0]))).all()
    assert abs(absorbance_to_transmittance(0.0) - 100.0) < 1e-12


def test_wavelength_orientation_invariance():
    """Verify ascending and descending wavelength arrays yield identical positive metrics."""
    x_asc = np.linspace(200, 800, 601)
    x_desc = x_asc[::-1]
    y_asc = np.exp(-0.5 * ((x_asc - 500) / 25) ** 2)
    y_desc = y_asc[::-1]

    # Calculate metrics
    m_asc = calculate_metrics(x_asc, y_asc)
    m_desc = calculate_metrics(x_desc, y_desc)

    assert abs(m_asc.area - m_desc.area) < 1e-10
    assert m_desc.area > 0
    assert abs(m_asc.absolute_area - m_desc.absolute_area) < 1e-10
    assert m_desc.absolute_area > 0
    assert abs(m_asc.centroid - m_desc.centroid) < 1e-10
    assert abs(m_asc.lambda_max - m_desc.lambda_max) < 1e-10
    assert abs(m_asc.fwhm - m_desc.fwhm) < 1e-10

    # Normalization Area = 1 must preserve positive sign on both orientations
    norm_asc = normalize(x_asc, y_asc, "Area = 1")
    norm_desc = normalize(x_desc, y_desc, "Area = 1")
    assert (norm_asc >= 0).all()
    assert (norm_desc >= 0).all()
    np.testing.assert_allclose(norm_asc, norm_desc[::-1], rtol=1e-10)

    # Integrate range
    auc_asc, abs_auc_asc, _, _ = integrate_range(x_asc, y_asc, 450, 550)
    auc_desc, abs_auc_desc, _, _ = integrate_range(x_desc, y_desc, 450, 550)
    assert abs(auc_asc - auc_desc) < 1e-10
    assert auc_desc > 0
    assert abs(abs_auc_asc - abs_auc_desc) < 1e-10


def test_signed_vs_absolute_area_preserves_negative_signals():
    """Verify that signed area preserves genuine negative signals without artificial abs() distortion."""
    x_asc = np.linspace(200, 800, 601)
    x_desc = x_asc[::-1]
    # Net negative signal (e.g. inverted baseline / blank subtraction over-correction)
    y_asc = -0.5 * np.exp(-0.5 * ((x_asc - 500) / 30) ** 2)
    y_desc = y_asc[::-1]

    # Calculate metrics on ascending and descending
    m_asc = calculate_metrics(x_asc, y_asc)
    m_desc = calculate_metrics(x_desc, y_desc)

    # Signed area MUST be negative on BOTH orientations (orientation-invariant and scientifically correct)
    assert m_asc.area < 0.0
    assert m_desc.area < 0.0
    assert abs(m_asc.area - m_desc.area) < 1e-10

    # Absolute area MUST be positive
    assert m_asc.absolute_area > 0.0
    assert m_desc.absolute_area > 0.0
    assert abs(m_asc.absolute_area - m_desc.absolute_area) < 1e-10
    assert abs(m_asc.area + m_asc.absolute_area) < 1e-10  # since y is strictly <= 0, signed_area = -absolute_area

    # integrate_range must also preserve signed area distinction
    s_auc_asc, a_auc_asc, _, _ = integrate_range(x_asc, y_asc, 450, 550)
    s_auc_desc, a_auc_desc, _, _ = integrate_range(x_desc, y_desc, 450, 550)
    assert s_auc_asc < 0.0
    assert s_auc_desc < 0.0
    assert abs(s_auc_asc - s_auc_desc) < 1e-10
    assert a_auc_asc > 0.0
    assert abs(a_auc_asc - a_auc_desc) < 1e-10


def test_signal_at_wavelength_and_zero_crossings_descending():
    """Verify signal_at_wavelength, zero_crossings, and spectral_arithmetic on descending grids."""
    from uvvis_studio.analysis import signal_at_wavelength, zero_crossings, spectral_arithmetic

    x_asc = np.linspace(200, 800, 601)
    x_desc = x_asc[::-1]
    y_asc = np.sin((x_asc - 200) / 100)
    y_desc = y_asc[::-1]

    # signal_at_wavelength
    sig_asc = signal_at_wavelength(x_asc, y_asc, 350.0)
    sig_desc = signal_at_wavelength(x_desc, y_desc, 350.0)
    assert abs(sig_asc - sig_desc) < 1e-10
    assert abs(sig_asc - np.sin(1.5)) < 1e-10

    # zero_crossings
    zc_asc = zero_crossings(x_asc, y_asc)
    zc_desc = zero_crossings(x_desc, y_desc)
    assert len(zc_asc) == len(zc_desc)
    for a, d in zip(zc_asc, zc_desc):
        assert abs(a["wavelength_nm"] - d["wavelength_nm"]) < 1e-6

    # spectral_arithmetic
    xa, ya = spectral_arithmetic(x_asc, y_asc, x_desc, y_desc, "Subtract B from A")
    np.testing.assert_allclose(ya, 0.0, atol=1e-10)


def test_peak_fwhm_against_analytical_gaussian():
    """Verify FWHM on synthetic Gaussian peak matches 2*sqrt(2*ln(2))*sigma."""
    sigma = 12.5
    center = 520.0
    x = np.linspace(400, 640, 2401)
    y = np.exp(-0.5 * ((x - center) / sigma) ** 2)

    metrics = calculate_metrics(x, y)
    exact_fwhm = 2.0 * np.sqrt(2.0 * np.log(2.0)) * sigma
    assert abs(metrics.fwhm - exact_fwhm) < 1e-3
    assert abs(metrics.lambda_max - center) < 1e-4


# =========================================================================
# 4. DERIVATIVE SPECTROSCOPY (EXACT 0D TO 4D TESTS)
# =========================================================================

def test_higher_order_derivatives_exact_analytical():
    """Verify Savitzky-Golay and numerical gradients against exact 1st-4th derivatives."""
    # f(x) = exp(-x^2 / 2)
    # f'(x) = -x * f(x)
    # f''(x) = (x^2 - 1) * f(x)
    # f'''(x) = (3x - x^3) * f(x)
    # f''''(x) = (x^4 - 6x^2 + 3) * f(x)
    x = np.linspace(-3.5, 3.5, 701)
    y = np.exp(-x**2 / 2.0)

    d1_exact = -x * y
    d2_exact = (x**2 - 1.0) * y
    d3_exact = (3.0 * x - x**3) * y
    d4_exact = (x**4 - 6.0 * x**2 + 3.0) * y

    # Interior slice to exclude filter edge transients
    interior = slice(35, -35)

    d1_calc = derivative(x, y, order=1, window=17, polyorder=5)
    d2_calc = derivative(x, y, order=2, window=17, polyorder=5)
    d3_calc = derivative(x, y, order=3, window=19, polyorder=5)
    d4_calc = derivative(x, y, order=4, window=21, polyorder=5)

    assert np.max(np.abs(d1_calc[interior] - d1_exact[interior])) < 1e-5
    assert np.max(np.abs(d2_calc[interior] - d2_exact[interior])) < 1e-4
    assert np.max(np.abs(d3_calc[interior] - d3_exact[interior])) < 1e-3
    assert np.max(np.abs(d4_calc[interior] - d4_exact[interior])) < 1e-2


# =========================================================================
# 5. MULTICOMPONENT ANALYSIS INDEPENDENT VERIFICATION
# =========================================================================

def test_simultaneous_equations_independent_oracle():
    """Verify 2-component simultaneous equations against direct matrix inverse."""
    c_a_true = 15.0  # µmol/L
    c_b_true = 25.0  # µmol/L
    eps_a1, eps_b1 = 1200.0, 300.0
    eps_a2, eps_b2 = 400.0, 950.0
    path = 1.0

    a1 = (eps_a1 * c_a_true + eps_b1 * c_b_true) * 1e-6
    a2 = (eps_a2 * c_a_true + eps_b2 * c_b_true) * 1e-6

    res = simultaneous_equations(
        a1, a2,
        eps_a1 * 1e-6, eps_a2 * 1e-6,
        eps_b1 * 1e-6, eps_b2 * 1e-6,
        path_length_cm=path,
    )

    assert abs(res["concentration_A"] - c_a_true) < 1e-9
    assert abs(res["concentration_B"] - c_b_true) < 1e-9
    assert res["conditioning_status"] == "acceptable"


def test_q_absorbance_ratio_oracle():
    """Verify Q-absorbance ratio method against true component concentrations."""
    ca_true = 8.0
    cb_true = 12.0
    total = ca_true + cb_true
    eps_iso = 500.0
    eps_a_lam = 800.0
    eps_b_lam = 200.0

    a_iso = eps_iso * total
    a_lam = eps_a_lam * ca_true + eps_b_lam * cb_true

    q_res = q_absorbance_ratio(a_iso, a_lam, eps_iso, eps_a_lam, eps_iso, eps_b_lam)
    assert abs(q_res["concentration_A"] - ca_true) < 1e-9
    assert abs(q_res["concentration_B"] - cb_true) < 1e-9
    assert abs(q_res["total_concentration"] - total) < 1e-9


# =========================================================================
# 6. METHOD VALIDATION & STATISTICAL TESTS
# =========================================================================

def test_mandel_fitting_test_diagnostics():
    """Verify Mandel test correctly detects quadratic curvature."""
    x = np.linspace(1, 10, 10)
    # Strictly linear data
    y_lin = 2.0 * x + 1.0 + np.random.RandomState(42).normal(0, 0.001, size=len(x))
    res_lin = mandel_fitting_test(x, y_lin)
    assert not res_lin["quadratic_improvement_significant"]

    # Strongly quadratic data
    y_quad = 0.5 * x**2 + 2.0 * x + 1.0
    res_quad = mandel_fitting_test(x, y_quad)
    assert res_quad["quadratic_improvement_significant"]
    assert res_quad["f"] > res_quad["f_critical"]


def test_lack_of_fit_test():
    """Verify Lack-of-Fit partitioning on replicated standards."""
    # Replicates at 4 levels
    x = np.array([1, 1, 1, 2, 2, 2, 3, 3, 3, 4, 4, 4], dtype=float)
    y = 2.5 * x + 0.1 + np.random.RandomState(42).normal(0, 0.02, size=len(x))

    lof = lack_of_fit_test(x, y)
    assert lof["df_pure_error"] == 8  # 4 levels * (3-1)
    assert lof["df_lack_of_fit"] == 2  # (12-2) - 8
    assert lof["p_value"] > 0.05  # Linear data has no significant lack of fit


def test_inverse_prediction_interval():
    """Verify inverse prediction estimates concentration and SE."""
    x = np.array([1, 2, 3, 4, 5], dtype=float)
    y = 0.5 * x + 0.1
    # For y0 = 1.6, x0 should be (1.6 - 0.1) / 0.5 = 3.0
    res = inverse_prediction_interval(x, y, unknown_response=1.6, confidence=0.95)
    assert abs(res["concentration"] - 3.0) < 1e-9
    assert res["lower"] < 3.0 < res["upper"]


# =========================================================================
# 7. PEAK DECONVOLUTION & FIT
# =========================================================================

def test_peak_deconvolution_gaussian_fit():
    """Verify nonlinear deconvolution recovers synthetic Gaussian parameters."""
    x = np.linspace(400, 600, 401)
    # Synthetic two-peak mixture with baseline: y = g1 + g2 + 0.05
    p1_amp, p1_center, p1_sigma = 0.8, 480.0, 10.0
    p2_amp, p2_center, p2_sigma = 0.5, 530.0, 12.0
    g1 = gaussian(x, p1_amp, p1_center, p1_sigma)
    g2 = gaussian(x, p2_amp, p2_center, p2_sigma)
    y = g1 + g2 + 0.05

    fit_res = fit_peaks(x, y, centers=[478.0, 532.0], kind="Gaussian", baseline_order=0)

    assert fit_res["r2"] > 0.999
    c1 = fit_res["components"][0]
    c2 = fit_res["components"][1]

    assert abs(c1["center"] - p1_center) < 0.5
    assert abs(c2["center"] - p2_center) < 0.5
    assert abs(c1["amplitude"] - p1_amp) < 0.05
    assert abs(c2["amplitude"] - p2_amp) < 0.05


# =========================================================================
# 8. CHEMOMETRICS PREPROCESSING & LEAKAGE PREVENTION
# =========================================================================

def test_chemometrics_fold_safe_preprocessor():
    """Verify SpectralPreprocessor fits MSC reference and centering on training data only."""
    rng = np.random.RandomState(42)
    X_train = rng.normal(1.0, 0.2, size=(10, 50))
    X_test = rng.normal(5.0, 0.2, size=(5, 50))

    prep = SpectralPreprocessor(use_msc=True, mean_center=True)
    prep.fit(X_train)

    # Reference must equal mean of training set only
    np.testing.assert_allclose(prep.msc_reference_, X_train.mean(axis=0))

    # Reference must NOT equal mean of combined training+test set (leakage check)
    combined_mean = np.vstack([X_train, X_test]).mean(axis=0)
    assert not np.allclose(prep.msc_reference_, combined_mean)

    # Center must equal mean of MSC-corrected training set only
    msc_train = _msc_rows(X_train, prep.msc_reference_)
    np.testing.assert_allclose(prep.center_, msc_train.mean(axis=0))

    # Transforming test set succeeds and preserves output dimensions
    X_test_trans = prep.transform(X_test)
    assert X_test_trans.shape == (5, 50)


def test_vip_threshold_selection():
    """Verify VIP threshold selection returns expected indices and wavelengths."""
    vip = np.array([0.5, 1.2, 0.8, 1.5, 2.0, 0.3])
    wl = np.array([400, 410, 420, 430, 440, 450])

    sel = vip_threshold_select(vip, wl, threshold=1.0)
    np.testing.assert_array_equal(sel["indices"], [1, 3, 4])
    np.testing.assert_array_equal(sel["wavelengths"], [410, 430, 440])


# =========================================================================
# 9. EXTENDED SECTION 2-5 VERIFICATION (AUC REFERENCE, FFT, WAVELET, UNITS)
# =========================================================================

def test_auc_independent_reference_dataset():
    """Verify Section 3 independent reference dataset on 255-285 nm returns exact 11.175 Abs*nm."""
    # Reference dataset from user specification:
    # Wavelength (nm): 250, 255, 260, 265, 270, 275, 280, 285, 290
    # Absorbance:      0.120, 0.180, 0.280, 0.410, 0.520, 0.470, 0.350, 0.230, 0.150
    x = np.array([250.0, 255.0, 260.0, 265.0, 270.0, 275.0, 280.0, 285.0, 290.0])
    y = np.array([0.120, 0.180, 0.280, 0.410, 0.520, 0.470, 0.350, 0.230, 0.150])

    # Composite trapezoidal rule on [255, 285]:
    # dx = 5 nm
    # Area = 5 * (0.180/2 + 0.280 + 0.410 + 0.520 + 0.470 + 0.350 + 0.230/2) = 11.175 Abs*nm
    signed_auc, abs_auc, xx, yy = integrate_range(x, y, 255.0, 285.0)

    assert abs(signed_auc - 11.175) < 1e-10
    assert abs(abs_auc - 11.175) < 1e-10
    assert len(xx) == 7
    assert xx[0] == 255.0 and xx[-1] == 285.0

    # Must also work if x is descending
    signed_desc, abs_desc, xx_d, _ = integrate_range(x[::-1], y[::-1], 255.0, 285.0)
    assert abs(signed_desc - 11.175) < 1e-10
    assert abs(abs_desc - 11.175) < 1e-10


def test_auc_interpolated_boundaries():
    """Verify integrate_range correctly interpolates boundary points between sampled wavelengths."""
    x = np.array([250.0, 255.0, 260.0, 265.0, 270.0, 275.0, 280.0, 285.0, 290.0])
    y = np.array([0.120, 0.180, 0.280, 0.410, 0.520, 0.470, 0.350, 0.230, 0.150])

    # Non-integer boundaries: 256.5 nm and 283.5 nm
    # y(256.5) = 0.180 + (1.5/5)*(0.280 - 0.180) = 0.210
    # y(283.5) = 0.350 + (3.5/5)*(0.230 - 0.350) = 0.266
    s_auc, a_auc, xx, yy = integrate_range(x, y, 256.5, 283.5)

    assert abs(xx[0] - 256.5) < 1e-10
    assert abs(xx[-1] - 283.5) < 1e-10
    assert abs(yy[0] - 0.210) < 1e-10
    assert abs(yy[-1] - 0.266) < 1e-10
    assert s_auc > 0 and s_auc < 11.175


def test_derivative_and_auc_units_dimensional_consistency():
    """Verify physical units for derivative orders 0D-4D and corresponding AUC integrals."""
    from uvvis_studio.analysis import derivative_unit, auc_unit

    assert derivative_unit(0) == "Abs"
    assert derivative_unit(1) == "Abs/nm"
    assert derivative_unit(2) == "Abs/nm²"
    assert derivative_unit(3) == "Abs/nm³"
    assert derivative_unit(4) == "Abs/nm⁴"

    assert auc_unit(0) == "Abs·nm"
    assert auc_unit(1) == "Abs"
    assert auc_unit(2) == "Abs/nm"
    assert auc_unit(3) == "Abs/nm²"
    assert auc_unit(4) == "Abs/nm³"


def test_fft_sinusoidal_dominant_period():
    """Verify Fourier transform correctly recovers known spatial frequency and period."""
    from uvvis_studio.transforms import fft_analysis

    # 50 nm spatial modulation + 20 nm secondary modulation
    x = np.linspace(200.0, 800.0, 1201)  # dx = 0.5 nm
    y = 0.50 + 0.35 * np.sin(2.0 * np.pi * (x - 200.0) / 50.0) + 0.10 * np.sin(2.0 * np.pi * (x - 200.0) / 20.0)

    res = fft_analysis(x, y, detrend=True, window="Hann")

    assert abs(res["dominant_period_nm"] - 50.0) < 1.0  # within 1 nm of exact 50 nm period
    assert abs(res["dominant_frequency_per_nm"] - 0.02) < 0.001  # 1/50 = 0.02 cycles/nm
    assert res["dc_component"] > 0
    assert res["grid_uniform"] is True


def test_grid_uniformity_diagnostics():
    """Verify grid uniformity detection for both equidistant and irregular wavelength arrays."""
    from uvvis_studio.transforms import check_grid_uniformity

    uniform_x = np.linspace(200.0, 800.0, 601)
    diag_u = check_grid_uniformity(uniform_x)
    assert diag_u["is_uniform"] is True
    assert abs(diag_u["median_dx"] - 1.0) < 1e-10

    # Nonuniform grid
    nonunif_x = np.array([200.0, 201.0, 202.5, 203.0, 205.0, 208.0])
    diag_nu = check_grid_uniformity(nonunif_x)
    assert diag_nu["is_uniform"] is False
    assert diag_nu["relative_spread"] > 0.5


def test_wavelet_denoise_threshold_rules():
    """Verify DWT denoising with VisuShrink, SURE, and Minimax rules."""
    from uvvis_studio.transforms import wavelet_denoise_full

    np.random.seed(42)
    x = np.linspace(200.0, 400.0, 201)
    clean = np.exp(-0.5 * ((x - 300.0) / 10.0)**2)
    noisy = clean + np.random.normal(0, 0.05, size=len(x))

    for rule in ["VisuShrink", "SURE", "Minimax"]:
        res = wavelet_denoise_full(noisy, wavelet="db4", threshold_rule=rule)
        assert len(res["denoised"]) == len(x)
        assert res["threshold"] > 0
        assert res["sigma"] > 0
        # Denoised signal must have reduced variance relative to noisy signal
        assert np.var(res["denoised"] - clean) < np.var(noisy - clean)


def test_cwt_analysis_cone_of_influence():
    """Verify CWT scalogram returns valid coefficients, pseudo-periods, and COI."""
    from uvvis_studio.transforms import cwt_analysis

    x = np.linspace(200.0, 400.0, 201)
    y = np.sin(x / 10.0)

    res = cwt_analysis(x, y, wavelet="morl", min_scale=1, max_scale=16)
    assert res["coefficients"].shape == (16, 201)
    assert len(res["cone_of_influence_nm"]) == 16
    assert np.all(res["cone_of_influence_nm"] > 0)

