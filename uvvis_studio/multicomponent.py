from __future__ import annotations

import numpy as np


def simultaneous_equations(a1, a2, eps_a1, eps_a2, eps_b1, eps_b2, path_length_cm=1.0):
    A=np.array([[float(eps_a1),float(eps_b1)],[float(eps_a2),float(eps_b2)]],dtype=float)*float(path_length_cm)
    b=np.array([float(a1),float(a2)],dtype=float)
    if abs(np.linalg.det(A))<1e-15: raise ValueError("The absorptivity matrix is singular or ill-conditioned.")
    c=np.linalg.solve(A,b)
    cond=float(np.linalg.cond(A))
    return {"concentration_A":float(c[0]),"concentration_B":float(c[1]),"condition_number":cond,"matrix":A}


def q_absorbance_ratio(a_iso, a_lambda, eps_a_iso, eps_a_lambda, eps_b_iso, eps_b_lambda, path_length_cm=1.0):
    a_iso=float(a_iso); a_lambda=float(a_lambda); l=float(path_length_cm)
    if a_iso==0 or l<=0: raise ValueError("Isoabsorptive absorbance and path length must be non-zero/positive.")
    qa=float(eps_a_lambda)/float(eps_a_iso); qb=float(eps_b_lambda)/float(eps_b_iso); qm=a_lambda/a_iso
    if abs(qa-qb)<1e-15: raise ValueError("Q values for the two components are indistinguishable.")
    total=a_iso/(float(eps_a_iso)*l)
    frac_a=(qm-qb)/(qa-qb); ca=total*frac_a; cb=total-ca
    return {"Qm":qm,"Qa":qa,"Qb":qb,"fraction_A":frac_a,"concentration_A":ca,"concentration_B":cb,"total_concentration":total}


def dual_wavelength(signal1_sample, signal2_sample, signal1_standard, signal2_standard, standard_concentration):
    ds=float(signal1_sample)-float(signal2_sample); dstd=float(signal1_standard)-float(signal2_standard)
    if abs(dstd)<1e-15: raise ValueError("Standard differential response is zero.")
    return {"delta_sample":ds,"delta_standard":dstd,"concentration":float(standard_concentration)*ds/dstd}


def ratio_spectrum(x, numerator, denominator, divisor_scale=1.0):
    x=np.asarray(x,dtype=float); n=np.asarray(numerator,dtype=float); d=np.asarray(denominator,dtype=float)*float(divisor_scale)
    if len(x)!=len(n) or len(x)!=len(d): raise ValueError("Ratio-spectrum arrays must have equal length.")
    out=np.full_like(n,np.nan,dtype=float); mask=np.isfinite(n)&np.isfinite(d)&(np.abs(d)>1e-15); out[mask]=n[mask]/d[mask]
    return x,out


def mean_center_ratio(ratio):
    r=np.asarray(ratio,dtype=float); m=np.isfinite(r)
    out=r.copy(); out[m]=r[m]-np.mean(r[m])
    return out


def derivative_ratio(x, ratio, order=1):
    x=np.asarray(x,dtype=float); y=np.asarray(ratio,dtype=float)
    if int(order)<1: return y.copy()
    out=y.copy()
    for _ in range(int(order)): out=np.gradient(out,x)
    return out
