from __future__ import annotations

from io import BytesIO
import json
import zipfile
from datetime import datetime, timezone
import numpy as np

PROJECT_VERSION = 1


def project_bytes(processed: list[dict], settings: dict | None = None, notes: str = "") -> bytes:
    meta={"format":"UVVisSpectrumStudioProject","version":PROJECT_VERSION,"created_utc":datetime.now(timezone.utc).isoformat(),"notes":str(notes),"settings":settings or {},"spectra":[]}
    bio=BytesIO()
    with zipfile.ZipFile(bio,"w",zipfile.ZIP_DEFLATED) as z:
        for i,s in enumerate(processed):
            x=np.asarray(s.get("x",[]),dtype=float); y=np.asarray(s.get("analysis_y",s.get("y",[])),dtype=float)
            name=f"spectra/{i:04d}.npz"; arr=BytesIO(); np.savez_compressed(arr,x=x,y=y); z.writestr(name,arr.getvalue())
            meta["spectra"].append({"name":str(s.get("name",f"Spectrum {i+1}")),"color":str(s.get("color","#2563EB")),"dash":str(s.get("dash","solid")),"source":str(s.get("source","project")),"column":str(s.get("column","signal")),"file":name})
        z.writestr("project.json",json.dumps(meta,ensure_ascii=False,indent=2))
    return bio.getvalue()


def load_project(data: bytes) -> dict:
    with zipfile.ZipFile(BytesIO(data),"r") as z:
        meta=json.loads(z.read("project.json").decode("utf-8"))
        if meta.get("format")!="UVVisSpectrumStudioProject": raise ValueError("Not a UV-Vis Spectrum Studio project file.")
        spectra=[]
        for item in meta.get("spectra",[]):
            with np.load(BytesIO(z.read(item["file"]))) as arr:
                x=np.asarray(arr["x"],dtype=float); y=np.asarray(arr["y"],dtype=float)
            spectra.append({"name":item.get("name","Spectrum"),"x":x,"y":y,"analysis_y":y.copy(),"plot_y":y.copy(),"color":item.get("color","#2563EB"),"dash":item.get("dash","solid"),"source":item.get("source","project"),"column":item.get("column","signal")})
        return {"metadata":meta,"spectra":spectra,"settings":meta.get("settings",{}),"notes":meta.get("notes","")}
