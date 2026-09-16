from __future__ import annotations

import numpy as np
from scipy.optimize import curve_fit
from scipy.special import wofz


def gaussian(x, amp, center, sigma):
    sigma=max(abs(float(sigma)),1e-12)
    return float(amp)*np.exp(-0.5*((x-float(center))/sigma)**2)


def lorentzian(x, amp, center, gamma):
    gamma=max(abs(float(gamma)),1e-12)
    return float(amp)*(gamma**2)/((x-float(center))**2+gamma**2)


def voigt(x, amp, center, sigma, gamma):
    sigma=max(abs(float(sigma)),1e-12); gamma=max(abs(float(gamma)),1e-12)
    z=((x-float(center))+1j*gamma)/(sigma*np.sqrt(2)); profile=np.real(wofz(z))/(sigma*np.sqrt(2*np.pi)); mx=np.max(profile)
    return float(amp)*profile/mx if mx>0 else np.zeros_like(x,dtype=float)


def pseudo_voigt(x, amp, center, width, eta):
    eta=float(np.clip(eta,0,1)); return eta*lorentzian(x,amp,center,width)+(1-eta)*gaussian(x,amp,center,width)


def _component(x, kind, params):
    if kind=="Gaussian": return gaussian(x,*params)
    if kind=="Lorentzian": return lorentzian(x,*params)
    if kind=="Voigt": return voigt(x,*params)
    if kind=="Pseudo-Voigt": return pseudo_voigt(x,*params)
    raise ValueError(f"Unsupported peak shape: {kind}")


def fit_peaks(x,y,centers,kind="Gaussian",baseline_order=1):
    x=np.asarray(x,dtype=float); y=np.asarray(y,dtype=float); m=np.isfinite(x)&np.isfinite(y); x=x[m]; y=y[m]
    centers=[float(c) for c in centers]
    if len(x)<8 or not centers: raise ValueError("Peak fitting requires spectral data and at least one initial peak center.")
    span=max(float(np.ptp(x)),1e-6); amp=max(float(np.ptp(y)),1e-6); width=max(span/(12*max(len(centers),1)),np.median(np.diff(np.sort(x)))*2)
    p0=[]; lo=[]; hi=[]
    for c in centers:
        local=float(np.interp(c,x,y)-np.nanmin(y)); a=max(local,amp/5)
        if kind in {"Gaussian","Lorentzian"}: p0 += [a,c,width]; lo += [0,float(x.min()),1e-9]; hi += [np.inf,float(x.max()),span]
        elif kind=="Voigt": p0 += [a,c,width,width]; lo += [0,float(x.min()),1e-9,1e-9]; hi += [np.inf,float(x.max()),span,span]
        else: p0 += [a,c,width,0.5]; lo += [0,float(x.min()),1e-9,0]; hi += [np.inf,float(x.max()),span,1]
    bo=max(0,min(int(baseline_order),3)); coeff=np.polyfit(x,y,bo); p0 += list(coeff); lo += [-np.inf]*(bo+1); hi += [np.inf]*(bo+1)
    npar={"Gaussian":3,"Lorentzian":3,"Voigt":4,"Pseudo-Voigt":4}[kind]
    def model(xx,*pp):
        out=np.zeros_like(xx,dtype=float); k=0
        for _ in centers: out += _component(xx,kind,pp[k:k+npar]); k += npar
        return out + np.polyval(pp[k:],xx)
    popt,pcov=curve_fit(model,x,y,p0=p0,bounds=(lo,hi),maxfev=100000)
    fit=model(x,*popt); residual=y-fit; ss_res=float(np.sum(residual**2)); ss_tot=float(np.sum((y-np.mean(y))**2)); r2=1-ss_res/ss_tot if ss_tot>0 else 1.0
    comps=[]; k=0
    for i in range(len(centers)):
        pars=popt[k:k+npar]; curve=_component(x,kind,pars); area=float(np.trapezoid(curve,x)); center=float(pars[1])
        if kind=="Gaussian": fwhm=2.354820045*abs(float(pars[2]))
        elif kind=="Lorentzian": fwhm=2*abs(float(pars[2]))
        elif kind=="Pseudo-Voigt": fwhm=2.354820045*abs(float(pars[2]))
        else:
            sigma,gamma=abs(float(pars[2])),abs(float(pars[3])); fG=2.354820045*sigma; fL=2*gamma; fwhm=0.5346*fL+np.sqrt(0.2166*fL*fL+fG*fG)
        comps.append({"peak":i+1,"center":center,"amplitude":float(pars[0]),"fwhm":float(fwhm),"area":area,"curve":curve,"parameters":np.asarray(pars)})
        k += npar
    return {"x":x,"y":y,"fit":fit,"residual":residual,"components":comps,"baseline":np.polyval(popt[k:],x),"r2":r2,"rmse":float(np.sqrt(np.mean(residual**2))),"covariance":pcov,"parameters":popt}
