from __future__ import annotations

from dataclasses import dataclass
import numpy as np
from scipy import stats


@dataclass
class LinearityValidation:
    slope: float
    intercept: float
    r2: float
    syx: float
    slope_se: float
    intercept_se: float
    slope_ci95: tuple[float, float]
    intercept_ci95: tuple[float, float]
    residuals: np.ndarray
    predicted: np.ndarray
    lod_33: float | None
    loq_10: float | None


def linearity_validation(x, y, sigma: float | None = None) -> LinearityValidation:
    x=np.asarray(x,dtype=float).reshape(-1); y=np.asarray(y,dtype=float).reshape(-1)
    m=np.isfinite(x)&np.isfinite(y); x=x[m]; y=y[m]
    if len(x)<3 or np.ptp(x)<=0: raise ValueError("At least three finite calibration levels with non-zero concentration range are required.")
    X=np.column_stack([np.ones(len(x)),x]); beta=np.linalg.lstsq(X,y,rcond=None)[0]; pred=X@beta; res=y-pred
    dof=max(len(x)-2,1); syx=float(np.sqrt(np.sum(res**2)/dof)); cov=(syx**2)*np.linalg.inv(X.T@X)
    se_i,se_s=np.sqrt(np.diag(cov)); tcrit=float(stats.t.ppf(0.975,dof)) if dof>0 else np.nan
    ss_tot=float(np.sum((y-np.mean(y))**2)); r2=1-float(np.sum(res**2))/ss_tot if ss_tot>0 else 1.0
    sig=syx if sigma is None else float(sigma); slope=float(beta[1]); lod=(3.3*sig/slope) if slope!=0 else None; loq=(10*sig/slope) if slope!=0 else None
    return LinearityValidation(slope,float(beta[0]),r2,syx,float(se_s),float(se_i),(slope-tcrit*se_s,slope+tcrit*se_s),(float(beta[0]-tcrit*se_i),float(beta[0]+tcrit*se_i)),res,pred,lod,loq)


def precision_summary(values, reference: float | None = None) -> dict:
    a=np.asarray(values,dtype=float); a=a[np.isfinite(a)]
    if len(a)<2: raise ValueError("At least two replicate results are required.")
    mean=float(np.mean(a)); sd=float(np.std(a,ddof=1)); rsd=100*sd/abs(mean) if mean else np.nan
    out={"n":len(a),"mean":mean,"sd":sd,"rsd_percent":rsd,"min":float(np.min(a)),"max":float(np.max(a))}
    if reference is not None and float(reference)!=0: out["recovery_percent"]=100*mean/float(reference); out["bias_percent"]=100*(mean-float(reference))/float(reference)
    return out


def recovery_summary(found, nominal) -> dict:
    f=np.asarray(found,dtype=float); n=np.asarray(nominal,dtype=float); m=np.isfinite(f)&np.isfinite(n)&(n!=0); f=f[m]; n=n[m]
    if len(f)<2: raise ValueError("At least two valid recovery pairs are required.")
    rec=100*f/n
    return {"recovery_percent":rec,"mean_recovery_percent":float(np.mean(rec)),"sd":float(np.std(rec,ddof=1)),"rsd_percent":float(100*np.std(rec,ddof=1)/np.mean(rec))}


def robustness_summary(values, factors=None) -> dict:
    a=np.asarray(values,dtype=float); a=a[np.isfinite(a)]
    if len(a)<2: raise ValueError("At least two robustness results are required.")
    mean=float(np.mean(a)); sd=float(np.std(a,ddof=1)); result={"mean":mean,"sd":sd,"rsd_percent":100*sd/abs(mean) if mean else np.nan,"range":float(np.ptp(a))}
    if factors is not None: result["factors"]=list(factors)
    return result


def lack_of_fit_test(concentration, response) -> dict:
    x=np.asarray(concentration,dtype=float); y=np.asarray(response,dtype=float); m=np.isfinite(x)&np.isfinite(y); x=x[m]; y=y[m]
    levels=np.unique(x)
    if len(levels)<3 or len(x)<=len(levels): raise ValueError("Lack-of-fit requires replicated responses at at least three concentration levels.")
    fit=linearity_validation(x,y); ss_res=float(np.sum(fit.residuals**2))
    ss_pe=0.0; df_pe=0
    for level in levels:
        vals=y[x==level]
        if len(vals)>1: ss_pe+=float(np.sum((vals-np.mean(vals))**2)); df_pe+=len(vals)-1
    df_lof=(len(x)-2)-df_pe
    if df_pe<=0 or df_lof<=0: raise ValueError("Insufficient replicated data for lack-of-fit partitioning.")
    ss_lof=max(ss_res-ss_pe,0.0); f=(ss_lof/df_lof)/(ss_pe/df_pe) if ss_pe>0 else np.inf; p=float(stats.f.sf(f,df_lof,df_pe))
    return {"ss_pure_error":ss_pe,"ss_lack_of_fit":ss_lof,"df_pure_error":df_pe,"df_lack_of_fit":df_lof,"f":float(f),"p_value":p}
