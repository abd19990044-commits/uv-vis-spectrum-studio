from __future__ import annotations

from dataclasses import asdict
from io import BytesIO
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from uvvis_studio.analysis import calculate_metrics, crop_xy, peak_table, process_spectrum
from uvvis_studio.export import figure_png_bytes, figure_vector_bytes
from uvvis_studio.io import clean_xy, detect_wavelength_column, numeric_signal_columns, read_table

APP_NAME = "UV-Vis Spectrum Studio"
COLORS = ["#2563EB", "#DC2626", "#059669", "#7C3AED", "#EA580C", "#0891B2", "#DB2777", "#475569"]

st.set_page_config(page_title=APP_NAME, page_icon="🔬", layout="wide", initial_sidebar_state="expanded")
st.markdown("""
<style>
.stApp{background:#f7f9fc}.block-container{padding-top:1.3rem;max-width:1600px}
[data-testid="stSidebar"]{background:#fff;border-right:1px solid #e5e7eb}
.hero{padding:1.25rem 1.4rem;border:1px solid #dbe4f0;border-radius:18px;background:linear-gradient(135deg,#fff,#f0f7ff);box-shadow:0 8px 24px rgba(15,23,42,.05);margin-bottom:1rem}
.hero h1{margin:0;color:#0f172a;font-size:2rem}.hero p{margin:.35rem 0 0;color:#475569}
.step{padding:.8rem 1rem;background:#fff;border:1px solid #e5e7eb;border-radius:14px;min-height:85px}.step b{color:#0f172a}.step small{color:#64748b}
div[data-testid="stMetric"]{background:#fff;border:1px solid #e5e7eb;border-radius:14px;padding:.65rem .85rem}.stButton>button,.stDownloadButton>button{border-radius:10px;min-height:2.5rem}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="hero"><h1>🔬 UV-Vis Spectrum Studio</h1><p>Import, compare, analyze and export publication-ready UV–Vis spectra without writing code.</p></div>', unsafe_allow_html=True)
a,b,c=st.columns(3)
with a: st.markdown('<div class="step"><b>1 · Load spectra</b><br><small>Excel, CSV or text. Wavelength is detected automatically.</small></div>',unsafe_allow_html=True)
with b: st.markdown('<div class="step"><b>2 · Adjust & analyze</b><br><small>Overlay, crop, derivatives, AUC, λmax, FWHM and peaks.</small></div>',unsafe_allow_html=True)
with c: st.markdown('<div class="step"><b>3 · Export</b><br><small>PNG up to 1200 DPI, SVG/PDF and processed CSV.</small></div>',unsafe_allow_html=True)


def demo_spectra():
    x=np.linspace(200,800,1201)
    y1=.08+1.02*np.exp(-.5*((x-272)/17)**2)+.34*np.exp(-.5*((x-330)/31)**2)
    y2=.05+.83*np.exp(-.5*((x-301)/22)**2)+.27*np.exp(-.5*((x-365)/38)**2)
    return [
        {"name":"Demo A","x":x,"y":y1,"color":COLORS[0],"source":"Built-in demo","column":"Absorbance"},
        {"name":"Demo B","x":x,"y":y2,"color":COLORS[1],"source":"Built-in demo","column":"Absorbance"},
    ]

with st.sidebar:
    st.markdown("### Workspace")
    mode=st.radio("Interface mode",["Basic","Advanced"],horizontal=True,help="Basic mode keeps only the most common controls visible.")
    use_demo=st.toggle("Use built-in demo spectra",False,help="Explore the program before uploading laboratory data.")
    st.divider(); st.markdown("### 1 · Load data")
    files=st.file_uploader("Drop UV–Vis files here",type=["xlsx","xls","xlsm","csv","txt","dat","asc","tsv"],accept_multiple_files=True)
    st.caption("Accepted: Excel, CSV, TXT, DAT, ASC and TSV.")

spectra=[]; errors=[]
if use_demo:
    spectra=demo_spectra()
elif files:
    for i,up in enumerate(files):
        try:
            df=read_table(BytesIO(up.getvalue()),up.name)
            auto=detect_wavelength_column(df); options=[str(c) for c in df.columns]
            with st.sidebar.expander(f"⚙️ {up.name}",expanded=i==0):
                xcol=st.selectbox("Wavelength column",options,index=options.index(auto),key=f"x{i}")
                yopts=numeric_signal_columns(df,xcol)
                ys=st.multiselect("Signal columns",yopts,default=yopts[:1],key=f"y{i}")
                for j,ycol in enumerate(ys):
                    x,y=clean_xy(df,xcol,ycol)
                    default=Path(up.name).stem if len(ys)==1 else f"{Path(up.name).stem} · {ycol}"
                    name=st.text_input("Curve name",default,key=f"n{i}_{j}")
                    color=st.color_picker("Curve color",COLORS[len(spectra)%len(COLORS)],key=f"c{i}_{j}")
                    spectra.append({"name":name,"x":x,"y":y,"color":color,"source":up.name,"column":ycol})
        except Exception as exc: errors.append(f"{up.name}: {exc}")

for e in errors: st.error(e)
if not spectra:
    st.info("👈 Upload one or more spectra, or switch on **Use built-in demo spectra**.")
    with st.expander("How should my file look?"):
        st.markdown("A simple two-column file works well: **Wavelength** and **Absorbance**. The wavelength column can have any name; the app detects a numeric column beginning at 200 nm or above, and you can override it manually.")
    st.stop()

allx=np.concatenate([s["x"] for s in spectra]); xlo,xhi=float(np.nanmin(allx)),float(np.nanmax(allx))
with st.sidebar:
    st.divider(); st.markdown("### 2 · Figure")
    title=st.text_input("Figure title","UV–Vis spectra"); xtitle=st.text_input("X-axis title","Wavelength (nm)")
    crop=st.toggle("Limit wavelength range",False); p,q=st.columns(2)
    xmin=p.number_input("X min",value=xlo,disabled=not crop); xmax=q.number_input("X max",value=xhi,disabled=not crop)
    linewidth=st.slider("Line width",.5,6.,2.2,.1); fontsize=st.slider("Text size",8,32,15); titlesize=st.slider("Title size",10,40,20)
    grid=st.toggle("Show grid",False); legend=st.toggle("Show legend",True)
    legendpos=st.selectbox("Legend position",["Top right","Top left","Bottom right","Bottom left","Outside right"])
    manual_y=st.toggle("Set Y-axis range manually",False); p,q=st.columns(2)
    ymin=p.number_input("Y min",value=0.,disabled=not manual_y); ymax=q.number_input("Y max",value=1.,disabled=not manual_y)

    smooth=False; window=11; poly=3; baseline=False; blam=1_000_000.; bp=.01; norm="None"; deriv=0; offset=0.
    if mode=="Advanced":
        st.divider(); st.markdown("### 3 · Advanced processing"); st.caption("Applied as smoothing → baseline → normalization → derivative.")
        smooth=st.toggle("Savitzky–Golay smoothing",False); p,q=st.columns(2)
        window=p.number_input("Window",3,101,11,2,disabled=not smooth); poly=q.number_input("Polynomial",1,7,3,1,disabled=not smooth)
        baseline=st.toggle("ALS baseline correction",False)
        blam=st.number_input("Baseline λ",1.,value=1_000_000.,format="%.0f",disabled=not baseline)
        bp=st.number_input("Baseline p",.0001,.5,.01,format="%.4f",disabled=not baseline)
        norm=st.selectbox("Normalization",["None","Max = 1","Min-Max 0–1","Area = 1"])
        deriv=st.selectbox("Derivative",[0,1,2],format_func=lambda v:["Original spectrum","First derivative","Second derivative"][v])
        offset=st.number_input("Vertical offset between curves",value=0.,step=.05)
    ydefault="Absorbance (a.u.)" if deriv==0 else ("dA/dλ" if deriv==1 else "d²A/dλ²")
    ytitle=st.text_input("Y-axis title",ydefault)

processed=[]
for idx,s in enumerate(spectra):
    x,y=crop_xy(s["x"],s["y"],xmin if crop else None,xmax if crop else None)
    if len(x)<2: continue
    x,y=process_spectrum(x,y,smooth=smooth,window=int(window),polyorder=int(poly),baseline=baseline,baseline_lambda=float(blam),baseline_p=float(bp),normalization=norm,derivative_order=int(deriv))
    processed.append({**s,"x":x,"yp":y+idx*float(offset)})
if not processed: st.error("No data remain in the selected wavelength range."); st.stop()

fig=go.Figure()
for s in processed:
    fig.add_trace(go.Scatter(x=s["x"],y=s["yp"],mode="lines",name=s["name"],line=dict(color=s["color"],width=linewidth),hovertemplate=f"<b>{s['name']}</b><br>λ = %{{x:.4f}} nm<br>Signal = %{{y:.7g}}<extra></extra>"))
pos={"Top right":dict(x=.99,y=.99,xanchor="right",yanchor="top"),"Top left":dict(x=.01,y=.99,xanchor="left",yanchor="top"),"Bottom right":dict(x=.99,y=.01,xanchor="right",yanchor="bottom"),"Bottom left":dict(x=.01,y=.01,xanchor="left",yanchor="bottom"),"Outside right":dict(x=1.02,y=1,xanchor="left",yanchor="top")}
fig.update_layout(title=dict(text=title,font=dict(size=titlesize),x=.5,xanchor="center"),xaxis_title=xtitle,yaxis_title=ytitle,font=dict(size=fontsize,family="Arial"),template="plotly_white",hovermode="closest",showlegend=legend,legend=pos[legendpos],margin=dict(l=80,r=130 if legendpos=="Outside right" else 35,t=75,b=70),paper_bgcolor="white",plot_bgcolor="white")
fig.update_xaxes(showgrid=grid,gridcolor="#e5e7eb",mirror=True,ticks="outside",showline=True,linewidth=1.2,linecolor="#334155",showspikes=True,spikemode="across",spikesnap="cursor",spikedash="dot")
fig.update_yaxes(showgrid=grid,gridcolor="#e5e7eb",mirror=True,ticks="outside",showline=True,linewidth=1.2,linecolor="#334155",showspikes=True,spikemode="across",spikesnap="cursor",spikedash="dot")
if crop: fig.update_xaxes(range=[xmin,xmax])
if manual_y: fig.update_yaxes(range=[ymin,ymax])

metrics=[]; peaks=[]; merged=None
for s in processed:
    metrics.append({"Curve":s["name"],**asdict(calculate_metrics(s["x"],s["yp"]))})
    peaks.extend([{"Curve":s["name"],**p} for p in peak_table(s["x"],s["yp"])])
    part=pd.DataFrame({"Wavelength_nm":s["x"],s["name"]:s["yp"]}); merged=part if merged is None else pd.merge(merged,part,on="Wavelength_nm",how="outer")
merged=merged.sort_values("Wavelength_nm")

m1,m2,m3,m4=st.columns(4); m1.metric("Curves loaded",len(processed)); m2.metric("Wavelength range",f"{min(float(s['x'][0]) for s in processed):.1f}–{max(float(s['x'][-1]) for s in processed):.1f} nm"); m3.metric("Processing","Original" if deriv==0 else f"Derivative {deriv}"); m4.metric("Points",f"{sum(len(s['x']) for s in processed):,}")
plot_tab,analysis_tab,data_tab,export_tab,help_tab=st.tabs(["📈 Spectrum","🧪 Analysis","📋 Data","💾 Export","❓ Help"])
with plot_tab:
    st.plotly_chart(fig,use_container_width=True,config={"displaylogo":False,"scrollZoom":True,"responsive":True})
    st.caption("Hover for exact values. Drag or scroll to zoom; double-click to reset.")
with analysis_tab:
    md=pd.DataFrame(metrics).rename(columns={"lambda_max":"λmax (nm)","y_max":"Signal at λmax","lambda_min":"λmin (nm)","y_min":"Signal at λmin","area":"AUC","centroid":"Centroid (nm)","fwhm":"FWHM (nm)","peak_count":"Peaks"})
    st.markdown("#### Spectral metrics"); st.dataframe(md,use_container_width=True,hide_index=True)
    st.markdown("#### Detected peaks"); pdp=pd.DataFrame(peaks).rename(columns={"wavelength_nm":"Wavelength (nm)","intensity":"Signal","prominence":"Prominence"})
    st.dataframe(pdp,use_container_width=True,hide_index=True) if not pdp.empty else st.info("No peaks met the automatic prominence criterion.")
with data_tab:
    st.dataframe(merged,use_container_width=True,hide_index=True,height=460)
with export_tab:
    st.markdown("#### Publication export"); st.caption("600 DPI is a strong default for journal figures; SVG/PDF remain vector formats.")
    e1,e2,e3=st.columns(3); win=e1.number_input("Width (inches)",2.,20.,7.,.25); hin=e2.number_input("Height (inches)",2.,20.,5.,.25); dpi=e3.select_slider("PNG resolution",[300,600,720,900,1200],600,format_func=lambda x:f"{x} DPI")
    st.info(f"PNG output: **{round(win*dpi):,} × {round(hin*dpi):,} pixels** at **{dpi} DPI**.")
    d1,d2,d3,d4=st.columns(4)
    try: d1.download_button(f"Download PNG · {dpi} DPI",figure_png_bytes(fig,win,hin,int(dpi)),"uvvis_spectrum.png","image/png",use_container_width=True)
    except Exception as exc: d1.warning(f"PNG unavailable: {exc}")
    try: d2.download_button("Download SVG",figure_vector_bytes(fig,"svg",win,hin),"uvvis_spectrum.svg","image/svg+xml",use_container_width=True)
    except Exception: d2.button("SVG unavailable",disabled=True,use_container_width=True)
    try: d3.download_button("Download PDF",figure_vector_bytes(fig,"pdf",win,hin),"uvvis_spectrum.pdf","application/pdf",use_container_width=True)
    except Exception: d3.button("PDF unavailable",disabled=True,use_container_width=True)
    d4.download_button("Processed CSV",merged.to_csv(index=False).encode("utf-8-sig"),"uvvis_processed.csv","text/csv",use_container_width=True)
with help_tab:
    st.markdown("""#### Quick guide
1. Upload one or more spectra from the left panel.
2. Confirm the detected wavelength column and choose signal columns.
3. Stay in **Basic** mode for routine plotting; use **Advanced** for preprocessing.
4. Hover over curves for precise wavelength/signal values.
5. Read λmax, AUC, FWHM and peaks in **Analysis**.
6. Export publication figures from **Export**.

**Scientific note:** normalization changes scale and derivatives amplify noise; use advanced processing only when analytically justified. Your original uploaded files are never modified.""")

st.divider(); st.caption("UV-Vis Spectrum Studio · Scientific plotting and spectral analysis · Processing is performed locally in the running application.")
