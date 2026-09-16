from __future__ import annotations

from dataclasses import asdict
from io import BytesIO
from pathlib import Path
import re

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from uvvis_studio.analysis import (
    absorbance_to_transmittance, calculate_metrics, crop_xy, estimate_snr,
    integrate_range, peak_table, process_spectrum, signal_at_wavelength,
    spectral_arithmetic, transmittance_to_absorbance, zero_crossings,
)
from uvvis_studio.chemometrics_ui import render_chemometrics
from uvvis_studio.export import figure_png_bytes, figure_vector_bytes
from uvvis_studio.io import clean_xy, detect_wavelength_column, numeric_signal_columns, read_table
from uvvis_studio.quantitation import isosbestic_points, job_method, linear_calibration, mole_ratio_method, standard_addition
from uvvis_studio.transforms import cwt_analysis, fft_analysis, wavelet_denoise

APP_NAME = "UV-Vis Spectrum Studio"
COLORS = ["#2563EB", "#DC2626", "#059669", "#7C3AED", "#EA580C", "#0891B2", "#DB2777", "#475569"]
LINE_STYLES = {"Solid":"solid","Dashed":"dash","Dotted":"dot","Dash-dot":"dashdot","Long dash":"longdash","Long dash-dot":"longdashdot"}
BW_STYLES = ["solid","dash","dot","dashdot","longdash","longdashdot"]
FONT_FAMILIES = ["Times New Roman","Arial","Calibri","Cambria","Georgia","Verdana","Courier New"]
DERIVATIVE_LABELS = ["Original spectrum (0D)","First derivative (1D)","Second derivative (2D)","Third derivative (3D)","Fourth derivative (4D)"]
DERIVATIVE_Y = ["Absorbance (a.u.)","dA/dλ","d²A/dλ²","d³A/dλ³","d⁴A/dλ⁴"]


def safe_filename(name: str, fallback: str = "uvvis_spectrum") -> str:
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", str(name)).strip(" .")
    return name or fallback


def choose_directory(initial: str) -> str | None:
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk(); root.withdraw(); root.attributes("-topmost", True)
        value = filedialog.askdirectory(initialdir=initial or str(Path.home()))
        root.destroy()
        return value or None
    except Exception:
        return None


def save_bytes(folder: str, filename: str, data: bytes) -> Path:
    outdir = Path(folder).expanduser()
    outdir.mkdir(parents=True, exist_ok=True)
    target = outdir / safe_filename(filename)
    target.write_bytes(data)
    return target


st.set_page_config(page_title=APP_NAME,page_icon="🔬",layout="wide",initial_sidebar_state="expanded")
st.markdown("""<style>
#MainMenu,[data-testid="stToolbar"],[data-testid="stDecoration"],[data-testid="stStatusWidget"]{display:none!important}
header[data-testid="stHeader"]{height:0!important;min-height:0!important;background:transparent!important}
.stApp{background:#f7f9fc}.block-container{padding-top:1rem;max-width:1750px}
[data-testid="stSidebar"]{background:#fff;border-right:1px solid #e5e7eb}
.hero{padding:1.05rem 1.25rem;border:1px solid #dbe4f0;border-radius:16px;background:linear-gradient(135deg,#fff,#eef6ff);margin-bottom:.8rem}
.hero h1{margin:0;color:#0f172a;font-size:1.9rem}.hero p{margin:.35rem 0 0;color:#475569}
div[data-testid="stMetric"]{background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:.55rem .75rem}
.stButton>button,.stDownloadButton>button{border-radius:10px;min-height:2.4rem}
</style>""",unsafe_allow_html=True)
st.markdown('<div class="hero"><h1>🔬 UV-Vis Spectrum Studio</h1><p>Integrated analytical spectroscopy, chemometrics, quantitative analysis, transforms, stoichiometry and publication tools.</p></div>',unsafe_allow_html=True)

with st.sidebar:
    st.markdown("### Spectral workspace")
    files=st.file_uploader("Load UV–Vis files",type=["xlsx","xls","xlsm","csv","txt","dat","asc","tsv"],accept_multiple_files=True)
    st.caption("Excel, CSV, TXT, DAT, ASC and TSV. No demo data are loaded automatically.")

spectra=[]; errors=[]
if files:
    for i,up in enumerate(files):
        try:
            df=read_table(BytesIO(up.getvalue()),up.name); auto=detect_wavelength_column(df); cols=[str(c) for c in df.columns]
            with st.sidebar.expander(f"Curve setup · {up.name}",expanded=i==0):
                xcol=st.selectbox("Wavelength column",cols,index=cols.index(auto),key=f"x{i}")
                yopts=numeric_signal_columns(df,xcol); ys=st.multiselect("Signal columns",yopts,default=yopts[:1],key=f"y{i}")
                for j,ycol in enumerate(ys):
                    x,y=clean_xy(df,xcol,ycol); default_name=Path(up.name).stem if len(ys)==1 else f"{Path(up.name).stem} · {ycol}"
                    name=st.text_input("Curve display name",value=default_name,key=f"name{i}_{j}")
                    c1,c2=st.columns(2); color=c1.color_picker("Color",COLORS[len(spectra)%len(COLORS)],key=f"color{i}_{j}")
                    style_name=c2.selectbox("Line style",list(LINE_STYLES),index=0,key=f"style{i}_{j}")
                    spectra.append({"name":name,"x":x,"y":y,"color":color,"dash":LINE_STYLES[style_name],"source":up.name,"column":ycol})
        except Exception as exc: errors.append(f"{up.name}: {exc}")
for e in errors: st.error(e)
if spectra:
    allx=np.concatenate([s["x"] for s in spectra]); xlo,xhi=float(np.nanmin(allx)),float(np.nanmax(allx))
else: xlo,xhi=200.0,800.0

with st.sidebar:
    st.divider(); st.markdown("### Processing")
    derivative_order=st.selectbox("Derivative order",range(5),format_func=lambda v:DERIVATIVE_LABELS[v])
    if derivative_order>=3: st.warning("3D/4D strongly amplify noise. Smoothing remains OFF unless explicitly enabled.")
    crop=st.toggle("Limit wavelength range",False); cc1,cc2=st.columns(2); xmin=cc1.number_input("X min",value=xlo,disabled=not crop); xmax=cc2.number_input("X max",value=xhi,disabled=not crop)
    st.markdown("#### Smoothing — OFF by default")
    smoothing_method=st.selectbox("Smoothing method",["None","Savitzky-Golay","Moving average","Gaussian"],index=0)
    window,poly,gaussian_sigma=11,max(3,derivative_order+1),2.0
    if smoothing_method in {"Savitzky-Golay","Moving average"}:
        sc1,sc2=st.columns(2); window=sc1.number_input("Window",3,201,11,2); poly=sc2.number_input("Polynomial order",1,9,max(3,derivative_order+1),1,disabled=smoothing_method!="Savitzky-Golay")
    elif smoothing_method=="Gaussian": gaussian_sigma=st.number_input("Gaussian σ (points)",0.1,50.0,2.0,0.1)
    st.markdown("#### Baseline / normalization")
    baseline_method=st.selectbox("Baseline",["None","ALS","Linear endpoints","Polynomial edges"],index=0); blam,bp,baseline_poly_order,baseline_edge_fraction=1_000_000.0,0.01,2,0.10
    if baseline_method=="ALS": blam=st.number_input("ALS λ",1.0,value=1_000_000.0,format="%.0f"); bp=st.number_input("ALS p",0.0001,0.5,0.01,format="%.4f")
    elif baseline_method in {"Linear endpoints","Polynomial edges"}:
        baseline_edge_fraction=st.slider("Edge fraction",0.02,0.40,0.10,0.01)
        if baseline_method=="Polynomial edges": baseline_poly_order=st.number_input("Polynomial order",1,5,2)
    norm=st.selectbox("Normalization",["None","Max = 1","Min-Max 0–1","Area = 1"],index=0)
    conversion=st.selectbox("Signal conversion",["None","Absorbance → %Transmittance","%Transmittance → Absorbance"],index=0)
    st.markdown("#### Manual AUC")
    auc_enabled=st.toggle("Calculate area in manual range",True); ac1,ac2=st.columns(2); auc_min=ac1.number_input("AUC from (nm)",value=xlo,disabled=not auc_enabled); auc_max=ac2.number_input("AUC to (nm)",value=xhi,disabled=not auc_enabled); shade_auc=st.toggle("Shade selected AUC",False,disabled=not auc_enabled)
    st.divider(); st.markdown("### Publication style")
    title=st.text_input("Figure title","UV–Vis spectra"); xtitle=st.text_input("X-axis title","Wavelength (nm)"); ytitle=st.text_input("Y-axis title",DERIVATIVE_Y[derivative_order])
    bw_mode=st.toggle("Black & white mode",False); bw_auto=st.toggle("Auto B&W patterns",False,disabled=not bw_mode,help="Off preserves each curve's manually selected line style.")
    font_family=st.selectbox("Font",FONT_FAMILIES,index=0); linewidth=st.slider("Line width",0.5,6.0,2.0,0.1); fontsize=st.slider("Text size",8,32,14); titlesize=st.slider("Title size",10,40,18); grid=st.toggle("Grid",False); legend=st.toggle("Legend",True)
    legendpos=st.selectbox("Legend position",["Top right","Top left","Bottom right","Bottom left","Outside right"]); label_peaks=st.toggle("Label peaks",False); peak_prominence_pct=st.slider("Peak prominence (% Y range)",0.1,50.0,3.0,0.1); peak_distance=st.number_input("Minimum peak distance (points)",1,10000,1); offset=st.number_input("Vertical offset",value=0.0,step=0.05)

if spectra and len(spectra)>=2:
    with st.sidebar.expander("Blank/reference & spectral arithmetic"):
        arithmetic=st.selectbox("Operation",["None","Blank/reference subtraction","Difference A − B","Ratio A / B","Add A + B"])
        if arithmetic!="None":
            names=[s["name"] for s in spectra]; a_name=st.selectbox("Spectrum A",names,0); b_name=st.selectbox("Spectrum B/reference",names,min(1,len(names)-1)); sa=next(s for s in spectra if s["name"]==a_name); sb=next(s for s in spectra if s["name"]==b_name)
            xo,yo=spectral_arithmetic(sa["x"],sa["y"],sb["x"],sb["y"],arithmetic); dname=st.text_input("Derived curve name",f"{a_name} · {arithmetic} · {b_name}"); spectra.append({"name":dname,"x":xo,"y":yo,"color":"#111827","dash":"solid","source":"Derived","column":arithmetic})

processed=[]
for idx,s in enumerate(spectra):
    x,y=crop_xy(s["x"],s["y"],xmin if crop else None,xmax if crop else None)
    if len(x)<2: continue
    if conversion=="Absorbance → %Transmittance": y=absorbance_to_transmittance(y)
    elif conversion=="%Transmittance → Absorbance": y=transmittance_to_absorbance(y)
    x,yp=process_spectrum(x,y,smoothing_method=smoothing_method,window=int(window),polyorder=int(poly),gaussian_sigma=float(gaussian_sigma),baseline_method=baseline_method,baseline_lambda=float(blam),baseline_p=float(bp),baseline_poly_order=int(baseline_poly_order),baseline_edge_fraction=float(baseline_edge_fraction),normalization=norm,derivative_order=int(derivative_order))
    processed.append({**s,"x":x,"analysis_y":yp,"plot_y":yp+idx*float(offset)})

fig=None; metrics=[]; auc_rows=[]; zero_rows=[]; peak_rows=[]; merged=None
if processed:
    fig=go.Figure()
    for idx,s in enumerate(processed):
        dash=BW_STYLES[idx%len(BW_STYLES)] if (bw_mode and bw_auto) else s["dash"]; color="#000000" if bw_mode else s["color"]
        fig.add_trace(go.Scatter(x=s["x"],y=s["plot_y"],mode="lines",name=s["name"],line=dict(color=color,width=linewidth,dash=dash),hovertemplate=f"<b>{s['name']}</b><br>λ=%{{x:.4f}} nm<br>Signal=%{{y:.8g}}<extra></extra>"))
        yrange=float(np.nanmax(s["analysis_y"])-np.nanmin(s["analysis_y"])); prominence=max(yrange*peak_prominence_pct/100.0,np.finfo(float).eps); peaks=peak_table(s["x"],s["analysis_y"],prominence=prominence,distance=int(peak_distance)); peak_rows.extend([{"Curve":s["name"],**p} for p in peaks])
        if label_peaks and peaks: fig.add_trace(go.Scatter(x=[p["wavelength_nm"] for p in peaks],y=[signal_at_wavelength(s["x"],s["plot_y"],p["wavelength_nm"]) for p in peaks],mode="markers+text",marker=dict(size=6,color=color),text=[f"{p['wavelength_nm']:.1f}" for p in peaks],textposition="top center",showlegend=False,hoverinfo="skip"))
        if auc_enabled:
            signed_auc,absolute_auc,xa,ya=integrate_range(s["x"],s["analysis_y"],auc_min,auc_max)
            if len(xa)>=2:
                auc_rows.append({"Curve":s["name"],"From (nm)":float(xa[0]),"To (nm)":float(xa[-1]),"Signed AUC":signed_auc,"Absolute AUC":absolute_auc})
                if shade_auc: fig.add_trace(go.Scatter(x=xa,y=ya+idx*float(offset),fill="tozeroy",mode="none",showlegend=False,hoverinfo="skip",fillcolor="rgba(80,80,80,.10)" if bw_mode else "rgba(37,99,235,.08)"))
        metrics.append({"Curve":s["name"],**asdict(calculate_metrics(s["x"],s["analysis_y"],prominence=prominence))})
        if derivative_order>0: zero_rows.extend([{"Curve":s["name"],**z} for z in zero_crossings(s["x"],s["analysis_y"],tolerance=max(yrange*1e-8,0))])
        part=pd.DataFrame({"Wavelength_nm":s["x"],s["name"]:s["analysis_y"]}); merged=part if merged is None else pd.merge(merged,part,on="Wavelength_nm",how="outer")
    if merged is not None: merged=merged.sort_values("Wavelength_nm")
    pos={"Top right":dict(x=.99,y=.99,xanchor="right",yanchor="top"),"Top left":dict(x=.01,y=.99,xanchor="left",yanchor="top"),"Bottom right":dict(x=.99,y=.01,xanchor="right",yanchor="bottom"),"Bottom left":dict(x=.01,y=.01,xanchor="left",yanchor="bottom"),"Outside right":dict(x=1.02,y=1,xanchor="left",yanchor="top")}
    fig.update_layout(title=dict(text=title,font=dict(size=titlesize,family=font_family),x=.5,xanchor="center"),xaxis_title=xtitle,yaxis_title=ytitle,font=dict(size=fontsize,family=font_family,color="#000"),template="plotly_white",showlegend=legend,legend=pos[legendpos],hovermode="closest",margin=dict(l=80,r=145 if legendpos=="Outside right" else 35,t=75,b=70),paper_bgcolor="white",plot_bgcolor="white")
    fig.update_xaxes(showgrid=grid,mirror=True,ticks="outside",showline=True,linecolor="#111827",showspikes=True,spikemode="across",spikesnap="cursor"); fig.update_yaxes(showgrid=grid,mirror=True,ticks="outside",showline=True,linecolor="#111827",showspikes=True,spikemode="across",spikesnap="cursor")
    if crop: fig.update_xaxes(range=[xmin,xmax])

tabs=st.tabs(["📈 Spectra","∂ Derivatives & AUC","〰 FFT / Wavelet","📏 Calibration","🧪 Stoichiometry","➕ Standard addition","🧮 Chemometrics","📊 Data & metrics","💾 Publication export"])
with tabs[0]:
    if fig is None: st.info("Load one or more spectra from the left panel. Quantitation and stoichiometry tabs work without a spectral file.")
    else:
        st.plotly_chart(fig,use_container_width=True,config={"displaylogo":False,"scrollZoom":True,"responsive":True}); st.caption(f"Smoothing: {smoothing_method}. Baseline: {baseline_method}. Normalization: {norm}. These are never enabled automatically.")
        if len(processed)>=2:
            st.markdown("#### Isosbestic-point analysis"); names=[s["name"] for s in processed]; ic1,ic2=st.columns(2); ia=ic1.selectbox("Spectrum 1",names,0,key="iso_a"); ib=ic2.selectbox("Spectrum 2",names,min(1,len(names)-1),key="iso_b"); a=next(s for s in processed if s["name"]==ia); b=next(s for s in processed if s["name"]==ib); pts=isosbestic_points(a["x"],a["analysis_y"],b["x"],b["analysis_y"]); st.dataframe(pd.DataFrame(pts).rename(columns={"wavelength_nm":"Wavelength (nm)","signal":"Signal"}),use_container_width=True,hide_index=True) if pts else st.info("No interpolated crossing was detected in the common wavelength range.")
with tabs[1]:
    st.markdown("#### Derivative spectroscopy 0D–4D"); st.write(f"Current display: **{DERIVATIVE_LABELS[derivative_order]}**")
    if derivative_order>=3: st.warning("Third/fourth derivatives amplify noise strongly. Enable smoothing only when analytically justified and report all parameters.")
    st.markdown("#### Manual-range area under the curve"); st.dataframe(pd.DataFrame(auc_rows),use_container_width=True,hide_index=True) if auc_rows else st.info("Enable AUC in the sidebar and enter the range manually.")
    if derivative_order>0: st.markdown("#### Zero crossings"); st.dataframe(pd.DataFrame(zero_rows).rename(columns={"wavelength_nm":"Zero crossing (nm)"}),use_container_width=True,hide_index=True) if zero_rows else st.info("No zero crossings detected.")
with tabs[2]:
    if not processed: st.info("Load a spectrum to use Fourier and wavelet analysis.")
    else:
        names=[s["name"] for s in processed]; target_name=st.selectbox("Curve",names,key="transform_curve"); target=next(s for s in processed if s["name"]==target_name)
        st.markdown("#### Fourier transform (FFT)"); fc1,fc2=st.columns(2); fft_window=fc1.selectbox("FFT window",["Hann","Hamming","Blackman","None"]); fft_detrend=fc2.toggle("Linear detrend before FFT",True); fr=fft_analysis(target["x"],target["analysis_y"],detrend=fft_detrend,window=fft_window); st.metric("Dominant spectral period",f"{fr['dominant_period_nm']:.4g} nm" if np.isfinite(fr['dominant_period_nm']) else "—"); ffig=go.Figure(go.Scatter(x=fr["frequency_per_nm"],y=fr["power"],mode="lines")); ffig.update_layout(template="plotly_white",xaxis_title="Spatial frequency (cycles/nm)",yaxis_title="FFT power",title="FFT power spectrum"); st.plotly_chart(ffig,use_container_width=True)
        st.markdown("#### Wavelet denoising — preview only, never automatic"); wc1,wc2,wc3=st.columns(3); wavelet=wc1.selectbox("DWT wavelet",["db4","db6","sym4","coif3"]); threshold_scale=wc2.number_input("Threshold scale",0.1,5.0,1.0,0.1); threshold_mode=wc3.selectbox("Threshold mode",["soft","hard"]); den=wavelet_denoise(target["analysis_y"],wavelet=wavelet,threshold_scale=threshold_scale,mode=threshold_mode); wfig=go.Figure(); wfig.add_trace(go.Scatter(x=target["x"],y=target["analysis_y"],name="Current spectrum")); wfig.add_trace(go.Scatter(x=target["x"],y=den,name="Wavelet-denoised preview",line=dict(dash="dash"))); wfig.update_layout(template="plotly_white",xaxis_title="Wavelength (nm)",yaxis_title="Signal"); st.plotly_chart(wfig,use_container_width=True)
        st.markdown("#### Continuous wavelet transform (CWT)"); cw1,cw2,cw3=st.columns(3); cwave=cw1.selectbox("CWT wavelet",["morl","mexh","gaus1","gaus2"]); smin=cw2.number_input("Min scale",1,128,1); smax=cw3.number_input("Max scale",2,256,64); cwt=cwt_analysis(target["x"],target["analysis_y"],wavelet=cwave,min_scale=int(smin),max_scale=int(smax)); hfig=go.Figure(go.Heatmap(x=cwt["x_nm"],y=cwt["scales"],z=cwt["power"],colorscale="Viridis")); hfig.update_layout(template="plotly_white",xaxis_title="Wavelength (nm)",yaxis_title="Wavelet scale",title="CWT scalogram"); st.plotly_chart(hfig,use_container_width=True)
with tabs[3]:
    st.markdown("#### Beer–Lambert calibration curve"); st.caption("Enter concentration and analytical response directly. No Excel file is required."); cal=st.data_editor(pd.DataFrame({"Concentration":[0.,1.,2.,3.,4.],"Response":[np.nan]*5}),num_rows="dynamic",use_container_width=True,key="calibration_table"); c1,c2,c3,c4=st.columns(4); unit=c1.selectbox("Concentration unit",["µg/mL","mg/L","mmol/L","mol/L"]); mw=c2.number_input("Molecular weight (g/mol)",min_value=0.0,value=0.0,step=0.001); path=c3.number_input("Path length (cm)",min_value=0.001,value=1.0,step=0.1); sigma_mode=c4.selectbox("σ for LOD/LOQ",["Regression residual SD (Sy/x)","Manual blank/response SD"]); sigma_manual=None
    if sigma_mode=="Manual blank/response SD": sigma_manual=st.number_input("σ value",min_value=0.0,value=0.0,format="%.8g")
    cx=pd.to_numeric(cal["Concentration"],errors="coerce").to_numpy(float); cy=pd.to_numeric(cal["Response"],errors="coerce").to_numpy(float); mask=np.isfinite(cx)&np.isfinite(cy)
    if np.count_nonzero(mask)>=3:
        try:
            cr=linear_calibration(cx[mask],cy[mask],sigma=sigma_manual,molecular_weight_g_mol=(mw or None),path_length_cm=path,concentration_unit=unit); km1,km2,km3,km4=st.columns(4); km1.metric("Slope",f"{cr.slope:.8g}"); km2.metric("Intercept",f"{cr.intercept:.8g}"); km3.metric("R²",f"{cr.r2:.8f}"); km4.metric("Sy/x",f"{cr.syx:.8g}"); lm1,lm2,lm3=st.columns(3); lm1.metric("LOD",f"{cr.lod:.8g} {unit}" if cr.lod is not None else "—"); lm2.metric("LOQ",f"{cr.loq:.8g} {unit}" if cr.loq is not None else "—"); lm3.metric("Molar absorptivity ε",f"{cr.epsilon_L_mol_cm:.8g} L·mol⁻¹·cm⁻¹" if cr.epsilon_L_mol_cm is not None else "MW/unit needed"); cfig=go.Figure(); cfig.add_trace(go.Scatter(x=cx[mask],y=cy[mask],mode="markers",name="Standards")); order=np.argsort(cx[mask]); xx=cx[mask][order]; cfig.add_trace(go.Scatter(x=xx,y=cr.intercept+cr.slope*xx,mode="lines",name="Linear fit")); cfig.update_layout(template="plotly_white",xaxis_title=f"Concentration ({unit})",yaxis_title="Response",title="Calibration curve"); st.plotly_chart(cfig,use_container_width=True); st.dataframe(pd.DataFrame({"Concentration":cx[mask],"Observed":cy[mask],"Predicted":cr.predicted,"Residual":cr.residuals}),use_container_width=True,hide_index=True)
        except Exception as exc: st.error(str(exc))
    else: st.info("Enter at least three complete concentration/response pairs.")
with tabs[4]:
    jtab,mrtab=st.tabs(["Job method","Mole-ratio method"])
    with jtab:
        jdf=st.data_editor(pd.DataFrame({"Mole fraction A":[0.1,0.2,0.3,0.4,0.5,0.6,0.7,0.8,0.9],"Response":[np.nan]*9}),num_rows="dynamic",use_container_width=True,key="job_table"); jx=pd.to_numeric(jdf.iloc[:,0],errors="coerce").to_numpy(float); jy=pd.to_numeric(jdf.iloc[:,1],errors="coerce").to_numpy(float); jm=np.isfinite(jx)&np.isfinite(jy)
        if np.count_nonzero(jm)>=3:
            try: jr=job_method(jx[jm],jy[jm]); st.metric("Estimated mole fraction at maximum",f"{jr['x_peak']:.5f}"); st.metric("Estimated A:B molar ratio",f"{jr['ratio_a_to_b']:.5g}:1"); jf=go.Figure(go.Scatter(x=jr["x"],y=jr["y"],mode="lines+markers")); jf.update_layout(template="plotly_white",xaxis_title="Mole fraction A",yaxis_title="Response",title="Job plot"); st.plotly_chart(jf,use_container_width=True)
            except Exception as exc: st.error(str(exc))
        else: st.info("Enter at least three complete Job-method points.")
    with mrtab:
        mrdf=st.data_editor(pd.DataFrame({"Reagent/analyte molar ratio":[0.,0.5,1.,1.5,2.,2.5,3.],"Response":[np.nan]*7}),num_rows="dynamic",use_container_width=True,key="mr_table"); mx=pd.to_numeric(mrdf.iloc[:,0],errors="coerce").to_numpy(float); my=pd.to_numeric(mrdf.iloc[:,1],errors="coerce").to_numpy(float); mm=np.isfinite(mx)&np.isfinite(my)
        if np.count_nonzero(mm)>=6:
            try: mr=mole_ratio_method(mx[mm],my[mm]); st.metric("Segmented-regression breakpoint",f"{mr['breakpoint_ratio']:.6g}"); mf=go.Figure(go.Scatter(x=mr["x"],y=mr["y"],mode="markers",name="Data")); x1=np.linspace(np.min(mr["x"]),mr["breakpoint_ratio"],100); x2=np.linspace(mr["breakpoint_ratio"],np.max(mr["x"]),100); mf.add_trace(go.Scatter(x=x1,y=mr["intercept1"]+mr["slope1"]*x1,mode="lines",name="Segment 1")); mf.add_trace(go.Scatter(x=x2,y=mr["intercept2"]+mr["slope2"]*x2,mode="lines",name="Segment 2",line=dict(dash="dash"))); mf.update_layout(template="plotly_white",xaxis_title="Reagent/analyte molar ratio",yaxis_title="Response",title="Mole-ratio plot"); st.plotly_chart(mf,use_container_width=True); st.write(f"Segment R²: {mr['r2_1']:.6f} and {mr['r2_2']:.6f}")
            except Exception as exc: st.error(str(exc))
        else: st.info("Enter at least six complete mole-ratio points.")
with tabs[5]:
    sadf=st.data_editor(pd.DataFrame({"Added concentration":[0.,1.,2.,3.,4.],"Response":[np.nan]*5}),num_rows="dynamic",use_container_width=True,key="sa_table"); dilution=st.number_input("Overall dilution factor back to original sample",min_value=0.000001,value=1.0,step=0.1); sx=pd.to_numeric(sadf.iloc[:,0],errors="coerce").to_numpy(float); sy=pd.to_numeric(sadf.iloc[:,1],errors="coerce").to_numpy(float); sm=np.isfinite(sx)&np.isfinite(sy)
    if np.count_nonzero(sm)>=3:
        try: sr=standard_addition(sx[sm],sy[sm],dilution_factor=dilution); s1,s2,s3,s4=st.columns(4); s1.metric("Slope",f"{sr['slope']:.8g}"); s2.metric("R²",f"{sr['r2']:.8f}"); s3.metric("x-intercept",f"{sr['x_intercept']:.8g}"); s4.metric("Original sample concentration",f"{sr['sample_concentration_original']:.8g}"); sf=go.Figure(); sf.add_trace(go.Scatter(x=sx[sm],y=sy[sm],mode="markers",name="Data")); xx=np.linspace(min(np.min(sx[sm]),sr['x_intercept']),np.max(sx[sm]),150); sf.add_trace(go.Scatter(x=xx,y=sr['intercept']+sr['slope']*xx,mode="lines",name="Fit")); sf.update_layout(template="plotly_white",xaxis_title="Added concentration",yaxis_title="Response",title="Standard-addition plot"); st.plotly_chart(sf,use_container_width=True)
        except Exception as exc: st.error(str(exc))
    else: st.info("Enter at least three complete standard-addition points.")
with tabs[6]:
    render_chemometrics(processed)
with tabs[7]:
    if processed:
        md=pd.DataFrame(metrics).rename(columns={"lambda_max":"λmax (nm)","y_max":"Signal at λmax","lambda_min":"λmin (nm)","y_min":"Signal at λmin","area":"Signed AUC full","absolute_area":"Absolute AUC full","centroid":"Centroid (nm)","fwhm":"FWHM (nm)","peak_count":"Peaks"}); st.markdown("#### Spectral metrics"); st.dataframe(md,use_container_width=True,hide_index=True); st.markdown("#### Detected peaks"); st.dataframe(pd.DataFrame(peak_rows),use_container_width=True,hide_index=True) if peak_rows else st.info("No peaks at the current prominence threshold.")
        st.markdown("#### Signal at selected wavelengths"); wtxt=st.text_input("Wavelengths (comma separated)","270",key="extract_wavelengths"); req=[]
        for t in wtxt.replace(";",",").split(","):
            try:req.append(float(t.strip()))
            except:pass
        rows=[{"Curve":s["name"],"Wavelength (nm)":w,"Signal":signal_at_wavelength(s["x"],s["analysis_y"],w)} for s in processed for w in req]
        if rows: st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
        st.markdown("#### S/N estimate"); n1,n2=st.columns(2); nmin=n1.number_input("Noise region from",value=max(xlo,xhi-(xhi-xlo)*.1),key="snr_min"); nmax=n2.number_input("Noise region to",value=xhi,key="snr_max"); sn=[{"Curve":s["name"],**estimate_snr(s["x"],s["analysis_y"],nmin,nmax)} for s in processed]; st.dataframe(pd.DataFrame(sn),use_container_width=True,hide_index=True); st.markdown("#### Processed data"); st.dataframe(merged,use_container_width=True,hide_index=True,height=420)
    else: st.info("Load spectra to view spectral metrics and processed data.")
with tabs[8]:
    if fig is None: st.info("Load spectra to export a spectral figure.")
    else:
        e1,e2,e3=st.columns(3); win=e1.number_input("Width (in)",2.0,20.0,7.0,.25); hin=e2.number_input("Height (in)",2.0,20.0,5.0,.25); dpi=e3.select_slider("PNG DPI",[300,600,720,900,1200],600)
        try: png_bytes=figure_png_bytes(fig,win,hin,int(dpi))
        except Exception as exc: png_bytes=None; st.error(f"PNG export error: {exc}")
        try: svg_bytes=figure_vector_bytes(fig,"svg",win,hin)
        except Exception: svg_bytes=None
        try: pdf_bytes=figure_vector_bytes(fig,"pdf",win,hin)
        except Exception: pdf_bytes=None
        d1,d2,d3,d4=st.columns(4)
        if png_bytes: d1.download_button(f"PNG · {dpi} DPI",png_bytes,"uvvis_spectrum.png","image/png",use_container_width=True)
        if svg_bytes: d2.download_button("SVG",svg_bytes,"uvvis_spectrum.svg","image/svg+xml",use_container_width=True)
        if pdf_bytes: d3.download_button("PDF",pdf_bytes,"uvvis_spectrum.pdf","application/pdf",use_container_width=True)
        d4.download_button("Processed CSV",merged.to_csv(index=False).encode("utf-8-sig"),"uvvis_processed.csv","text/csv",use_container_width=True)
        st.divider(); st.markdown("#### Save directly to a selected folder")
        default_dir=str(Path.home()/"Documents"/"UVVis Spectrum Studio")
        if "export_dir" not in st.session_state: st.session_state.export_dir=default_dir
        if st.button("Browse folder…",key="browse_export"):
            chosen=choose_directory(st.session_state.export_dir)
            if chosen: st.session_state.export_dir=chosen
        folder=st.text_input("Save folder",key="export_dir",help="Enter or browse to any writable Windows folder. The folder is created if it does not exist.")
        f1,f2=st.columns(2); base=f1.text_input("Base file name","uvvis_spectrum"); fmt=f2.selectbox("Format to save",["PNG","SVG","PDF","CSV processed data"])
        if st.button("Save to this folder",type="primary",use_container_width=True):
            try:
                base=safe_filename(base)
                if fmt=="PNG":
                    if png_bytes is None: raise RuntimeError("PNG bytes are unavailable.")
                    target=save_bytes(folder,base+".png",png_bytes)
                elif fmt=="SVG":
                    if svg_bytes is None: raise RuntimeError("SVG bytes are unavailable.")
                    target=save_bytes(folder,base+".svg",svg_bytes)
                elif fmt=="PDF":
                    if pdf_bytes is None: raise RuntimeError("PDF bytes are unavailable.")
                    target=save_bytes(folder,base+".pdf",pdf_bytes)
                else:
                    target=save_bytes(folder,base+"_processed.csv",merged.to_csv(index=False).encode("utf-8-sig"))
                st.success(f"Saved successfully: {target}")
            except Exception as exc: st.error(f"Could not save to the selected path: {exc}")
        if auc_rows: st.download_button("AUC CSV",pd.DataFrame(auc_rows).to_csv(index=False).encode("utf-8-sig"),"uvvis_auc.csv","text/csv")
        if peak_rows: st.download_button("Peaks CSV",pd.DataFrame(peak_rows).to_csv(index=False).encode("utf-8-sig"),"uvvis_peaks.csv","text/csv")
st.divider(); st.caption("UV-Vis Spectrum Studio · spectroscopy, analytical chemistry and chemometrics workspace")