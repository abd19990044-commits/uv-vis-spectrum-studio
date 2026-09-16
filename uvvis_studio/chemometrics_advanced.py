from __future__ import annotations

import numpy as np
from sklearn.cross_decomposition import PLSRegression
from sklearn.metrics import r2_score, mean_squared_error
from sklearn.model_selection import KFold, cross_val_predict


def kennard_stone(X, n_train: int):
    X=np.asarray(X,dtype=float)
    if X.ndim!=2 or len(X)<3: raise ValueError("Kennard-Stone requires at least three samples.")
    n_train=max(2,min(int(n_train),len(X)-1))
    xc=X-X.mean(axis=0); scale=X.std(axis=0,ddof=1); scale[scale==0]=1; Z=xc/scale
    d=np.sqrt(((Z[:,None,:]-Z[None,:,:])**2).sum(axis=2)); i,j=np.unravel_index(np.argmax(d),d.shape); selected=[int(i),int(j)]
    while len(selected)<n_train:
        remaining=[k for k in range(len(X)) if k not in selected]
        k=max(remaining,key=lambda r:min(d[r,s] for s in selected)); selected.append(int(k))
    test=[k for k in range(len(X)) if k not in selected]
    return np.array(selected,dtype=int),np.array(test,dtype=int)


def spxy(X,y,n_train:int,alpha:float=0.5):
    X=np.asarray(X,dtype=float); y=np.asarray(y,dtype=float).reshape(-1)
    if len(y)!=len(X): raise ValueError("SPXY needs one y value per sample.")
    xs=(X-X.mean(axis=0))/(X.std(axis=0,ddof=1)+1e-15); ys=(y-y.mean())/(y.std(ddof=1)+1e-15)
    dx=np.sqrt(((xs[:,None,:]-xs[None,:,:])**2).sum(axis=2)); dy=np.abs(ys[:,None]-ys[None,:]); d=(1-float(alpha))*dx+float(alpha)*dy
    n_train=max(2,min(int(n_train),len(X)-1)); i,j=np.unravel_index(np.argmax(d),d.shape); selected=[int(i),int(j)]
    while len(selected)<n_train:
        rem=[k for k in range(len(X)) if k not in selected]; k=max(rem,key=lambda r:min(d[r,s] for s in selected)); selected.append(int(k))
    return np.array(selected,dtype=int),np.array([k for k in range(len(X)) if k not in selected],dtype=int)


def optimize_pls_components(X,y,max_components=15,cv_folds=5):
    X=np.asarray(X,dtype=float); y=np.asarray(y,dtype=float).reshape(-1); maxc=max(1,min(int(max_components),X.shape[1],len(X)-1)); folds=max(2,min(int(cv_folds),len(X)))
    cv=KFold(n_splits=folds,shuffle=True,random_state=42); rows=[]
    for n in range(1,maxc+1):
        pred=np.asarray(cross_val_predict(PLSRegression(n_components=n,scale=True),X,y,cv=cv)).reshape(-1); rows.append({"components":n,"r2_cv":float(r2_score(y,pred)),"rmsecv":float(np.sqrt(mean_squared_error(y,pred)))})
    best=min(rows,key=lambda r:r["rmsecv"])
    return {"results":rows,"best_components":best["components"],"best_rmsecv":best["rmsecv"],"best_r2_cv":best["r2_cv"]}


def y_randomization_test(X,y,n_components=2,permutations=100,cv_folds=5,random_state=42):
    X=np.asarray(X,dtype=float); y=np.asarray(y,dtype=float).reshape(-1); rng=np.random.default_rng(random_state); folds=max(2,min(int(cv_folds),len(X))); cv=KFold(n_splits=folds,shuffle=True,random_state=42)
    nc=max(1,min(int(n_components),X.shape[1],len(X)-1)); pred=np.asarray(cross_val_predict(PLSRegression(n_components=nc,scale=True),X,y,cv=cv)).reshape(-1); observed=float(r2_score(y,pred)); null=[]
    for _ in range(max(10,int(permutations))):
        yp=rng.permutation(y); pp=np.asarray(cross_val_predict(PLSRegression(n_components=nc,scale=True),X,yp,cv=cv)).reshape(-1); null.append(float(r2_score(yp,pp)))
    null=np.asarray(null); p=float((1+np.sum(null>=observed))/(len(null)+1))
    return {"observed_q2":observed,"permuted_q2":null,"p_value":p,"null_mean":float(np.mean(null)),"null_sd":float(np.std(null,ddof=1))}


def vip_threshold_select(vip,wavelengths,threshold=1.0):
    vip=np.asarray(vip,dtype=float); wl=np.asarray(wavelengths,dtype=float); m=np.isfinite(vip)&np.isfinite(wl)&(vip>=float(threshold)); return {"indices":np.flatnonzero(m),"wavelengths":wl[m],"vip":vip[m]}


def interval_pls(X,y,wavelengths,n_intervals=10,n_components=2,cv_folds=5):
    X=np.asarray(X,dtype=float); y=np.asarray(y,dtype=float).reshape(-1); wl=np.asarray(wavelengths,dtype=float); idx_chunks=np.array_split(np.arange(X.shape[1]),max(2,min(int(n_intervals),X.shape[1]))); rows=[]
    cv=KFold(n_splits=max(2,min(int(cv_folds),len(X))),shuffle=True,random_state=42)
    for i,idx in enumerate(idx_chunks):
        if len(idx)<1: continue
        nc=max(1,min(int(n_components),len(idx),len(X)-1)); pred=np.asarray(cross_val_predict(PLSRegression(n_components=nc,scale=True),X[:,idx],y,cv=cv)).reshape(-1); rows.append({"interval":i+1,"start_nm":float(wl[idx[0]]),"end_nm":float(wl[idx[-1]]),"variables":len(idx),"q2":float(r2_score(y,pred)),"rmsecv":float(np.sqrt(mean_squared_error(y,pred))),"indices":idx})
    return {"results":rows,"best":min(rows,key=lambda r:r["rmsecv"]) if rows else None}
