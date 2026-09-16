# UV-Vis Spectrum Studio

Professional web application for UV-Vis spectroscopy plotting and analysis.

## Features
- Import Excel, TXT, CSV, DAT, ASC, TSV spectra
- Automatic wavelength-column detection (numeric data starting at 200 nm or higher)
- Overlay multiple spectra with per-curve colors and names
- Interactive Plotly cursor, zoom, pan, and hover readout
- Manual axis labels, ranges, plot dimensions, fonts, line widths, and legend controls
- Savitzky-Golay smoothing
- First and second derivatives
- ALS baseline correction
- Normalization and vertical offsets
- Peak detection and peak tables
- AUC, spectral centroid, FWHM, lambda max/min, peak wavelength/intensity/prominence
- Processed-data export to CSV
- Publication export to PNG (300-1200 DPI), SVG, and PDF

## Run locally
```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

pip install -r requirements.txt
streamlit run app.py
```

## Tests
```bash
pytest -q
```

## Scientific note
All numerical processing is isolated from the Streamlit interface in `uvvis_studio/`, allowing the algorithms to be tested independently of the UI.
