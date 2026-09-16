from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from .chemometrics import pls_with_vip
from .chemometrics_advanced import kennard_stone, spxy, optimize_pls_components, y_randomization_test, vip_threshold_select, interval_pls
from .chemometrics_ui_legacy import _align_spectra


def render_advanced_chemometrics(processed: list[dict]) -> None:
    st.markdown("### Advanced chemometric validation")
    st.caption("Dataset splitting, component optimization, Y-randomization and wavelength/interval selection for publication-oriented model validation.")
    if len(processed)<5:
        st.info("Load at least five spectra to use advanced chemometric validation.")
        return
    try: wl,X,names=_align_spectra(processed)
    except Exception as exc: st.error(str(exc)); return
    targets=st.data_editor(pd.DataFrame({"Sample":names,"Y":[np.nan]*len(names)}),use_container_width=True,hide_index=True,key="chem_adv_targets",disabled=["Sample"])
    y=pd.to_numeric(targets["Y"],errors="coerce").to_numpy(float); good=np.isfinite(y)
    if np.count_nonzero(good)<5:
        st.info("Enter at least five numerical Y values to activate the advanced tools.")
        return
    Xg=X[good]; yg=y[good]; ng=np.asarray(names)[good]
    spl,optt,randt,vart=st.tabs(["Train/test splitting","PLS optimization","Y-randomization","Variable selection"])
    with spl:
        c1,c2,c3=st.columns(3); method=c1.selectbox("Split method",["Kennard-Stone","SPXY"]); frac=c2.slider("Training fraction",0.5,0.9,0.7,0.05); alpha=c3.slider("SPXY Y-weight",0.0,1.0,0.5,0.05,disabled=method!="SPXY")
        ntrain=max(2,min(len(Xg)-1,int(round(len(Xg)*frac))))
        try:
            tr,te=kennard_stone(Xg,ntrain) if method=="Kennard-Stone" else spxy(Xg,yg,ntrain,alpha)
            st.write(f"Training samples: **{len(tr)}** · Test samples: **{len(te)}**")
            st.dataframe(pd.DataFrame({"Sample":ng,"Set":["Train" if i in set(tr.tolist()) else "Test" for i in range(len(ng))]}),use_container_width=True,hide_index=True)
        except Exception as exc: st.error(str(exc))
    with optt:
        c1,c2=st.columns(2); maxc=c1.number_input("Maximum PLS components",1,max(1,min(20,len(Xg)-1,Xg.shape[1])),min(10,max(1,min(20,len(Xg)-1,Xg.shape[1])))); cv=c2.number_input("CV folds",2,len(Xg),min(5,len(Xg)))
        try:
            r=optimize_pls_components(Xg,yg,int(maxc),int(cv)); st.metric("Optimal components",r["best_components"]); st.metric("Best RMSECV",f"{r['best_rmsecv']:.6g}"); st.metric("Best Q²",f"{r['best_r2_cv']:.5f}"); d=pd.DataFrame(r["results"]); f=go.Figure(); f.add_trace(go.Scatter(x=d["components"],y=d["rmsecv"],mode="lines+markers",name="RMSECV")); f.update_layout(template="plotly_white",xaxis_title="PLS components",yaxis_title="RMSECV",title="PLS component optimization"); st.plotly_chart(f,use_container_width=True)
        except Exception as exc: st.error(str(exc))
    with randt:
        c1,c2,c3=st.columns(3); nc=c1.number_input("PLS components",1,max(1,min(15,len(Xg)-1,Xg.shape[1])),min(3,max(1,min(15,len(Xg)-1,Xg.shape[1]))),key="chem_rand_nc"); perms=c2.number_input("Permutations",10,1000,100,10); cv=c3.number_input("CV folds",2,len(Xg),min(5,len(Xg)),key="chem_rand_cv")
        if st.button("Run Y-randomization",key="chem_rand_run"):
            try:
                r=y_randomization_test(Xg,yg,int(nc),int(perms),int(cv)); a,b,c=st.columns(3); a.metric("Observed Q²",f"{r['observed_q2']:.5f}"); b.metric("Permutation p",f"{r['p_value']:.5f}"); c.metric("Null mean Q²",f"{r['null_mean']:.5f}"); hist=go.Figure(go.Histogram(x=r["permuted_q2"],nbinsx=30)); hist.add_vline(x=r["observed_q2"],line_dash="dash",annotation_text="Observed Q²"); hist.update_layout(template="plotly_white",xaxis_title="Permuted Q²",title="Y-randomization test"); st.plotly_chart(hist,use_container_width=True)
            except Exception as exc: st.error(str(exc))
    with vart:
        v1,v2=st.tabs(["VIP threshold","Interval PLS (iPLS)"])
        with v1:
            nc=st.number_input("PLS components for VIP",1,max(1,min(15,len(Xg)-1,Xg.shape[1])),min(3,max(1,min(15,len(Xg)-1,Xg.shape[1]))),key="chem_adv_vip_nc"); thr=st.number_input("VIP threshold",0.0,10.0,1.0,0.05)
            try:
                vr=pls_with_vip(Xg,yg,int(nc)); sel=vip_threshold_select(vr["vip"],wl,thr); st.write(f"Selected wavelengths: **{len(sel['indices'])} / {len(wl)}**"); vf=go.Figure(go.Scatter(x=wl,y=vr["vip"],mode="lines")); vf.add_hline(y=thr,line_dash="dash"); vf.update_layout(template="plotly_white",xaxis_title="Wavelength (nm)",yaxis_title="VIP",title="VIP wavelength selection"); st.plotly_chart(vf,use_container_width=True); st.dataframe(pd.DataFrame({"Wavelength (nm)":sel["wavelengths"],"VIP":sel["vip"]}).sort_values("VIP",ascending=False).head(100),use_container_width=True,hide_index=True)
            except Exception as exc: st.error(str(exc))
        with v2:
            c1,c2,c3=st.columns(3); intervals=c1.number_input("Intervals",2,min(50,Xg.shape[1]),min(10,max(2,Xg.shape[1]//10))); nc=c2.number_input("PLS components",1,max(1,min(10,len(Xg)-1)),min(3,max(1,min(10,len(Xg)-1))),key="chem_ipls_nc"); cv=c3.number_input("CV folds",2,len(Xg),min(5,len(Xg)),key="chem_ipls_cv")
            try:
                rr=interval_pls(Xg,yg,wl,int(intervals),int(nc),int(cv)); table=pd.DataFrame([{k:v for k,v in row.items() if k!="indices"} for row in rr["results"]]).sort_values("rmsecv"); st.dataframe(table,use_container_width=True,hide_index=True); best=rr["best"]; st.success(f"Best interval: {best['start_nm']:.2f}–{best['end_nm']:.2f} nm · RMSECV={best['rmsecv']:.6g} · Q²={best['q2']:.5f}")
            except Exception as exc: st.error(str(exc))
