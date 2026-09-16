from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from .chemometrics import (
    classification_analysis,
    cluster_samples,
    pca_analysis,
    pls_with_vip,
    preprocess_matrix,
    regression_analysis,
    unsupervised_decomposition,
)


def _align_spectra(processed: list[dict]) -> tuple[np.ndarray, np.ndarray, list[str]]:
    if len(processed) < 2:
        raise ValueError("Load at least two spectra/samples for chemometric analysis.")
    lo = max(float(np.min(s["x"])) for s in processed)
    hi = min(float(np.max(s["x"])) for s in processed)
    if hi <= lo:
        raise ValueError("The spectra do not share a common wavelength interval.")
    n = min(max(50, min(len(s["x"]) for s in processed)), 5000)
    wl = np.linspace(lo, hi, n)
    X = np.vstack([np.interp(wl, s["x"], s["analysis_y"]) for s in processed])
    names = [str(s["name"]) for s in processed]
    return wl, X, names


def render_chemometrics(processed: list[dict]) -> None:
    st.markdown("### Chemometrics")
    st.caption("Multivariate spectroscopy workspace: preprocessing, exploratory analysis, calibration, classification, variable importance and clustering. No preprocessing is applied unless selected.")
    if len(processed) < 2:
        st.info("Load at least two spectra. For supervised calibration/classification, a practical dataset should contain substantially more samples than this minimum.")
        return

    try:
        wl, Xraw, names = _align_spectra(processed)
    except Exception as exc:
        st.error(str(exc))
        return

    st.write(f"Samples: **{Xraw.shape[0]}** · aligned variables: **{Xraw.shape[1]}** · common range: **{wl[0]:.2f}–{wl[-1]:.2f} nm**")
    if Xraw.shape[0] < 10:
        st.warning("The current sample count is small for robust multivariate validation. Treat model metrics as exploratory and increase independent samples before reporting a final model.")

    with st.expander("Preprocessing pipeline", expanded=True):
        c1,c2,c3,c4=st.columns(4)
        use_snv=c1.toggle("SNV",False,key="chem_snv")
        use_msc=c2.toggle("MSC",False,key="chem_msc")
        detrend=c3.toggle("Linear detrend",False,key="chem_detrend")
        center=c4.toggle("Mean center",False,key="chem_center")
        c5,c6,c7=st.columns(3)
        autoscale=c5.toggle("Autoscale variables",False,key="chem_autoscale")
        deriv=c6.selectbox("Savitzky–Golay derivative",[0,1,2],index=0,key="chem_deriv")
        sg_window=c7.number_input("SG window",3,101,11,2,key="chem_sg_window")
        sg_poly=st.number_input("SG polynomial order",1,7,2,1,key="chem_sg_poly")
    try:
        X=preprocess_matrix(Xraw,use_snv=use_snv,use_msc=use_msc,detrend=detrend,mean_center=center,autoscale=autoscale,derivative_order=int(deriv),savgol_window=int(sg_window),savgol_polyorder=int(sg_poly))
    except Exception as exc:
        st.error(f"Preprocessing error: {exc}")
        return

    explore,regtab,clstab,vartab,cluster_tab=st.tabs(["PCA / decomposition","Regression / calibration","Classification","VIP / variables","Clustering"])

    with explore:
        method=st.selectbox("Decomposition",["PCA","ICA","NMF / MCR-like"],key="chem_decomp")
        max_comp=max(1,min(X.shape[0],X.shape[1],20))
        ncomp=st.slider("Components",1,max_comp,min(3,max_comp),key="chem_ncomp")
        try:
            dec=unsupervised_decomposition(X,method,ncomp)
            scores=np.asarray(dec["scores"])
            if method=="PCA":
                p=pca_analysis(X,ncomp)
                ev=100*np.asarray(p["explained_variance_ratio"])
                st.dataframe(pd.DataFrame({"PC":np.arange(1,len(ev)+1),"Explained variance (%)":ev,"Cumulative (%)":100*np.asarray(p["cumulative_variance"])}),hide_index=True,use_container_width=True)
                if scores.shape[1]>=2:
                    f=go.Figure(go.Scatter(x=scores[:,0],y=scores[:,1],mode="markers+text",text=names,textposition="top center"))
                    f.update_layout(template="plotly_white",title="PCA scores",xaxis_title=f"PC1 ({ev[0]:.2f}%)",yaxis_title=f"PC2 ({ev[1]:.2f}%)")
                    st.plotly_chart(f,use_container_width=True,config={"displaylogo":False})
                    ld=np.asarray(p["loadings"])
                    lf=go.Figure(); lf.add_trace(go.Scatter(x=wl,y=ld[:,0],name="PC1 loading")); lf.add_trace(go.Scatter(x=wl,y=ld[:,1],name="PC2 loading")); lf.update_layout(template="plotly_white",xaxis_title="Wavelength (nm)",yaxis_title="Loading",title="PCA loadings"); st.plotly_chart(lf,use_container_width=True,config={"displaylogo":False})
                od=pd.DataFrame({"Sample":names,"Hotelling T²":p["hotelling_t2"],"Q residual":p["q_residual"]}); st.markdown("#### PCA diagnostics / outlier screening"); st.dataframe(od,use_container_width=True,hide_index=True)
            else:
                st.dataframe(pd.DataFrame(scores,index=names,columns=[f"Component {i+1}" for i in range(scores.shape[1])]),use_container_width=True)
                if scores.shape[1]>=2:
                    f=go.Figure(go.Scatter(x=scores[:,0],y=scores[:,1],mode="markers+text",text=names,textposition="top center")); f.update_layout(template="plotly_white",xaxis_title="Component 1",yaxis_title="Component 2",title=f"{method} scores"); st.plotly_chart(f,use_container_width=True)
        except Exception as exc: st.error(str(exc))

    target_table=pd.DataFrame({"Sample":names,"Y / concentration":[np.nan]*len(names),"Class":[""]*len(names)})
    edited=st.data_editor(target_table,use_container_width=True,hide_index=True,key="chem_targets",disabled=["Sample"])

    with regtab:
        st.caption("Enter one numerical response/concentration for every sample in the table above.")
        y=pd.to_numeric(edited["Y / concentration"],errors="coerce").to_numpy(float)
        good=np.isfinite(y)
        models=["PLS","PCR","Linear regression","Ridge","Lasso","Elastic Net","SVR (RBF)","KNN","Random Forest","Extra Trees","Gradient Boosting"]
        r1,r2,r3=st.columns(3); model_name=r1.selectbox("Regression model",models,key="chem_reg_model"); comp=r2.number_input("Latent components",1,max(1,min(X.shape[0]-1,X.shape[1])),min(3,max(1,min(X.shape[0]-1,X.shape[1]))),key="chem_reg_comp",disabled=model_name not in {"PLS","PCR"}); cv=r3.number_input("CV folds",2,max(2,X.shape[0]),min(5,max(2,X.shape[0])),key="chem_reg_cv")
        if np.count_nonzero(good)>=5:
            try:
                rr=regression_analysis(X[good],y[good],model_name,n_components=int(comp),cv_folds=int(cv))
                a,b,c=st.columns(3); a.metric("CV R² / Q²",f"{rr.r2_cv:.5f}"); b.metric("RMSECV",f"{rr.rmse_cv:.6g}"); c.metric("MAECV",f"{rr.mae_cv:.6g}")
                pf=go.Figure(go.Scatter(x=rr.observed,y=rr.predicted_cv,mode="markers",text=np.asarray(names)[good])); lo=float(min(np.min(rr.observed),np.min(rr.predicted_cv))); hi=float(max(np.max(rr.observed),np.max(rr.predicted_cv))); pf.add_trace(go.Scatter(x=[lo,hi],y=[lo,hi],mode="lines",name="Ideal")); pf.update_layout(template="plotly_white",title=f"{model_name} cross-validated prediction",xaxis_title="Reference",yaxis_title="Predicted"); st.plotly_chart(pf,use_container_width=True)
                st.dataframe(pd.DataFrame({"Sample":np.asarray(names)[good],"Reference":rr.observed,"CV predicted":rr.predicted_cv,"Residual":rr.observed-rr.predicted_cv}),use_container_width=True,hide_index=True)
            except Exception as exc: st.error(str(exc))
        else: st.info("At least five numerical sample responses are required to run cross-validation.")

    with clstab:
        labels=edited["Class"].fillna("").astype(str).str.strip().to_numpy(); valid=labels!=""
        models=["LDA","QDA","Logistic regression","SVM (RBF)","KNN","Gaussian Naive Bayes","Random Forest","Extra Trees","Gradient Boosting"]
        q1,q2=st.columns(2); model_name=q1.selectbox("Classification model",models,key="chem_cls_model"); cv=q2.number_input("CV folds",2,max(2,X.shape[0]),min(5,max(2,X.shape[0])),key="chem_cls_cv")
        if np.count_nonzero(valid)>=6 and len(np.unique(labels[valid]))>=2:
            try:
                cr=classification_analysis(X[valid],labels[valid],model_name,cv_folds=int(cv)); a,b=st.columns(2); a.metric("CV accuracy",f"{cr.accuracy_cv:.4f}"); b.metric("Balanced accuracy",f"{cr.balanced_accuracy_cv:.4f}"); st.dataframe(pd.DataFrame(cr.confusion,index=cr.classes,columns=cr.classes),use_container_width=True); st.dataframe(pd.DataFrame({"Sample":np.asarray(names)[valid],"Observed":cr.observed,"CV predicted":cr.predicted_cv}),use_container_width=True,hide_index=True)
            except Exception as exc: st.error(str(exc))
        else: st.info("Enter class labels for at least six samples spanning at least two classes.")

    with vartab:
        y=pd.to_numeric(edited["Y / concentration"],errors="coerce").to_numpy(float); good=np.isfinite(y)
        if np.count_nonzero(good)>=5:
            max_pls=max(1,min(np.count_nonzero(good)-1,X.shape[1],15)); nc=st.slider("PLS components for VIP",1,max_pls,min(3,max_pls),key="chem_vip_comp")
            try:
                vr=pls_with_vip(X[good],y[good],nc); vip=np.asarray(vr["vip"]); vf=go.Figure(go.Scatter(x=wl,y=vip,mode="lines",name="VIP")); vf.add_hline(y=1.0,line_dash="dash",annotation_text="VIP = 1"); vf.update_layout(template="plotly_white",title="PLS Variable Importance in Projection",xaxis_title="Wavelength (nm)",yaxis_title="VIP"); st.plotly_chart(vf,use_container_width=True); important=pd.DataFrame({"Wavelength (nm)":wl,"VIP":vip}).sort_values("VIP",ascending=False); st.dataframe(important.head(50),use_container_width=True,hide_index=True)
            except Exception as exc: st.error(str(exc))
        else: st.info("Enter numerical Y values to calculate PLS VIP scores.")

    with cluster_tab:
        c1,c2=st.columns(2); method=c1.selectbox("Clustering",["K-means","Hierarchical (Ward)"],key="chem_cluster_method"); nc=c2.number_input("Clusters",2,max(2,min(10,X.shape[0])),min(3,max(2,min(10,X.shape[0]))),key="chem_clusters")
        try:
            lab=cluster_samples(X,method,int(nc)); p=pca_analysis(X,2); sc=p["scores"]; cf=go.Figure(go.Scatter(x=sc[:,0],y=sc[:,1],mode="markers+text",text=names,textposition="top center",marker=dict(color=lab,colorscale="Viridis",size=10))); cf.update_layout(template="plotly_white",title=f"{method} clusters displayed in PCA space",xaxis_title="PC1",yaxis_title="PC2"); st.plotly_chart(cf,use_container_width=True); st.dataframe(pd.DataFrame({"Sample":names,"Cluster":lab+1}),use_container_width=True,hide_index=True)
        except Exception as exc: st.error(str(exc))
