import numpy as np

from uvvis_studio.validation import linearity_validation, recovery_summary
from uvvis_studio.multicomponent import simultaneous_equations, dual_wavelength
from uvvis_studio.peakfit import fit_peaks
from uvvis_studio.project import project_bytes, load_project
from uvvis_studio.chemometrics_advanced import kennard_stone, optimize_pls_components, y_randomization_test


def test_linearity_validation_and_lod_loq():
    x=np.array([0,1,2,3,4,5],float); y=0.02+0.5*x
    r=linearity_validation(x,y,sigma=0.01)
    assert abs(r.slope-0.5)<1e-10
    assert r.r2>0.999999
    assert abs(r.lod_33-0.066)<1e-10
    assert abs(r.loq_10-0.2)<1e-10


def test_recovery_summary():
    r=recovery_summary([9.9,10.1,10.0],[10,10,10])
    assert abs(r["mean_recovery_percent"]-100)<1e-10


def test_simultaneous_equations():
    # cA=2, cB=3 for chosen absorptivities
    r=simultaneous_equations(8,7,1,2,2,1,1)
    assert np.allclose([r["concentration_A"],r["concentration_B"]],[2,3])


def test_dual_wavelength():
    r=dual_wavelength(0.8,0.2,0.5,0.1,10)
    assert abs(r["concentration"]-15)<1e-12


def test_peakfit_gaussian():
    x=np.linspace(250,350,500); y=0.05+1.2*np.exp(-0.5*((x-300)/8)**2)
    r=fit_peaks(x,y,[300],"Gaussian",0)
    assert abs(r["components"][0]["center"]-300)<0.2
    assert r["r2"]>0.999


def test_project_roundtrip():
    spectra=[{"name":"A","x":np.array([200,201,202.]),"analysis_y":np.array([0.1,0.2,0.3]),"color":"#000000","dash":"solid"}]
    b=project_bytes(spectra,{"mode":"test"},"note")
    p=load_project(b)
    assert p["notes"]=="note"
    assert p["settings"]["mode"]=="test"
    assert p["spectra"][0]["name"]=="A"
    assert np.allclose(p["spectra"][0]["analysis_y"],[0.1,0.2,0.3])


def test_kennard_stone_split():
    X=np.arange(60,dtype=float).reshape(10,6)
    tr,te=kennard_stone(X,7)
    assert len(tr)==7 and len(te)==3
    assert len(set(tr).intersection(set(te)))==0


def test_pls_optimization_and_randomization():
    rng=np.random.default_rng(2); X=rng.normal(size=(24,30)); coef=np.zeros(30); coef[:3]=[2,-1,0.5]; y=X@coef+rng.normal(0,0.05,24)
    op=optimize_pls_components(X,y,5,4)
    assert 1<=op["best_components"]<=5
    yr=y_randomization_test(X,y,2,20,4,3)
    assert np.isfinite(yr["observed_q2"])
    assert 0<=yr["p_value"]<=1
