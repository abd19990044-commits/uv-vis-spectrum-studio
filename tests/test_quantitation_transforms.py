import numpy as np
from uvvis_studio.quantitation import independent_blank_statistics, linear_calibration, standard_addition, job_method, mole_ratio_method, isosbestic_points
from uvvis_studio.transforms import fft_analysis, wavelet_denoise


def test_linear_calibration_and_epsilon():
    c=np.array([1.,2.,3.,4.,5.]); a=0.2*c+0.01
    r=linear_calibration(c,a,sigma=0.002,molecular_weight_g_mol=200,path_length_cm=1,concentration_unit='µg/mL')
    assert abs(r.slope-0.2)<1e-12 and r.r2>0.999999
    assert abs(r.epsilon_L_mol_cm-40000)<1e-8
    assert r.lod is not None and r.loq is not None


def test_independent_blank_sigma_and_invalid_calibration_pairs():
    blanks = [0.0031, 0.0027, 0.0034, 0.0029, 0.0032,
              0.0030, 0.0035, 0.0028, 0.0033, 0.0031]
    summary = independent_blank_statistics(blanks)
    assert summary["n"] == 10
    assert np.isclose(summary["mean"], 0.0031)
    assert np.isclose(summary["sd"], np.std(blanks, ddof=1))
    with np.testing.assert_raises(ValueError):
        linear_calibration([0, 1, 2], [0, 1])
    with np.testing.assert_raises(ValueError):
        linear_calibration([0, 1, 2], [0, 1, 2], sigma=-0.01)


def test_standard_addition():
    x=np.array([0.,1.,2.,3.]); y=2*x+4
    r=standard_addition(x,y)
    assert abs(r['sample_concentration_final']-2)<1e-12


def test_job_method_peak():
    x=np.linspace(0.1,0.9,9); y=1-(x-0.5)**2
    r=job_method(x,y)
    assert abs(r['x_peak']-0.5)<0.05


def test_mole_ratio_breakpoint():
    x=np.linspace(0,4,17); y=np.where(x<=2,x,2+0.1*(x-2))
    r=mole_ratio_method(x,y)
    assert abs(r['breakpoint_ratio']-2)<0.3


def test_isosbestic():
    x=np.linspace(200,400,201); y1=x-300; y2=-(x-300)
    pts=isosbestic_points(x,y1,x,y2)
    assert pts and abs(pts[0]['wavelength_nm']-300)<1e-8


def test_fft_and_wavelet():
    x=np.linspace(200,400,1001); y=np.sin(2*np.pi*(x-200)/20)
    r=fft_analysis(x,y)
    assert abs(r['dominant_period_nm']-20)<0.5
    den=wavelet_denoise(y+0.2*np.sin(2*np.pi*(x-200)/1.5))
    assert den.shape==y.shape
