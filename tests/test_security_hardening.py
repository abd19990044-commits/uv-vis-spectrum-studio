from __future__ import annotations

from io import BytesIO
import json
import zipfile

import numpy as np
import pytest

from uvvis_studio.io import clean_xy, read_table
from uvvis_studio.project import _validate_zip_archive, load_project, project_bytes


def test_project_rejects_path_traversal():
    """Verify load_project rejects archives containing directory traversal filenames."""
    bio = BytesIO()
    with zipfile.ZipFile(bio, "w") as z:
        z.writestr("../malicious.txt", b"evil")
        z.writestr("project.json", b"{}")
    
    with pytest.raises(ValueError, match="Unsafe path detected"):
        load_project(bio.getvalue())


def test_project_rejects_absolute_paths():
    """Verify load_project rejects archives containing absolute paths."""
    bio = BytesIO()
    with zipfile.ZipFile(bio, "w") as z:
        z.writestr("/etc/passwd", b"root:x:0:0")
        z.writestr("project.json", b"{}")
    
    with pytest.raises(ValueError, match="Unsafe path detected"):
        load_project(bio.getvalue())


def test_project_rejects_excessive_member_count():
    """Verify load_project rejects archives with excessive file count (>1000)."""
    bio = BytesIO()
    with zipfile.ZipFile(bio, "w") as z:
        for i in range(1005):
            z.writestr(f"spectra/dummy_{i}.txt", b"0")
        z.writestr("project.json", b"{}")

    with pytest.raises(ValueError, match="too many files"):
        load_project(bio.getvalue())


def test_project_rejects_decompression_bomb():
    """Verify archive validation rejects archives exceeding uncompressed byte limits."""
    bio = BytesIO()
    with zipfile.ZipFile(bio, "w") as z:
        z.writestr("spectra/test.dat", b"0" * 2048)

    with zipfile.ZipFile(bio, "r") as z:
        with pytest.raises(ValueError, match="uncompressed size limit"):
            _validate_zip_archive(z, max_total_uncompressed_bytes=1024)


def test_project_tamper_detection():
    """Verify SHA-256 manifest detects post-hoc archive alteration."""
    spectra = [
        {
            "name": "Std 1",
            "x": np.array([200.0, 250.0, 300.0]),
            "y": np.array([0.1, 0.2, 0.3]),
            "color": "#2563EB",
            "dash": "solid",
        }
    ]
    raw = project_bytes(spectra, notes="Original project")

    # Tamper with the project by replacing project.json content
    in_bio = BytesIO(raw)
    out_bio = BytesIO()
    with zipfile.ZipFile(in_bio, "r") as zin, zipfile.ZipFile(out_bio, "w") as zout:
        for item in zin.infolist():
            content = zin.read(item.filename)
            if item.filename == "project.json":
                meta = json.loads(content.decode("utf-8"))
                meta["notes"] = "TAMPERED PROJECT"
                content = json.dumps(meta).encode("utf-8")
            zout.writestr(item, content)

    with pytest.raises(ValueError, match="Integrity check failed"):
        load_project(out_bio.getvalue())


def test_io_rejects_malformed_empty_and_corrupt_files():
    """Verify read_table handles empty and corrupted files gracefully."""
    with pytest.raises(ValueError, match="Input file is empty"):
        read_table(BytesIO(b""), "empty.csv")

    with pytest.raises(ValueError, match="no usable two-column-or-more"):
        read_table(BytesIO(b"SingleColumnHeader\n1\n2\n3"), "single_col.csv")

    with pytest.raises(ValueError, match="Unsupported file type"):
        read_table(BytesIO(b"data"), "spectrum.unknown_extension")


def test_project_rejects_windows_drive_letter_and_ads_paths():
    """Verify load_project rejects archives containing Windows drive letter paths or ADS."""
    bio = BytesIO()
    with zipfile.ZipFile(bio, "w") as z:
        z.writestr("C:/windows/win.ini", b"[system]")
        z.writestr("project.json", b"{}")

    with pytest.raises(ValueError, match="Unsafe path detected"):
        load_project(bio.getvalue())


def test_project_rejects_invalid_characters():
    """Verify load_project rejects archive member names with control characters."""
    bio = BytesIO()
    with zipfile.ZipFile(bio, "w") as z:
        z.writestr("spectra/test\x1f.dat", b"data")
        z.writestr("project.json", b"{}")

    with pytest.raises(ValueError, match="Invalid character in archive member name"):
        load_project(bio.getvalue())


def test_project_rejects_malformed_zip():
    """Verify load_project cleanly rejects non-zip or corrupt zip data."""
    with pytest.raises(ValueError, match="not a valid UV-Vis Spectrum Studio project"):
        load_project(b"Not a zip file header at all")

    bio = BytesIO()
    with zipfile.ZipFile(bio, "w") as z:
        z.writestr("other.txt", b"hello")
    with pytest.raises(ValueError, match="does not contain project.json"):
        load_project(bio.getvalue())

    bio2 = BytesIO()
    with zipfile.ZipFile(bio2, "w") as z:
        z.writestr("project.json", b"{broken json")
    with pytest.raises(ValueError, match="project.json is not valid UTF-8 JSON"):
        load_project(bio2.getvalue())

