from __future__ import annotations

import json
from pathlib import Path
import re
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from uvvis_studio import __version__  # noqa: E402


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def _capture(pattern: str, text: str, label: str, errors: list[str]) -> str | None:
    match = re.search(pattern, text, flags=re.MULTILINE)
    if not match:
        errors.append(f"Could not read {label}.")
        return None
    return match.group(1)


def main() -> int:
    errors: list[str] = []
    version = __version__

    with (ROOT / "pyproject.toml").open("rb") as handle:
        pyproject_version = tomllib.load(handle)["project"]["version"]
    _expect(pyproject_version == version, f"pyproject.toml version {pyproject_version!r} != {version!r}", errors)

    citation = _text("CITATION.cff")
    citation_version = _capture(r"^version:\s*[\"']?([^\"'\s]+)", citation, "CITATION.cff version", errors)
    if citation_version is not None:
        _expect(citation_version == version, f"CITATION.cff version {citation_version!r} != {version!r}", errors)
    _expect(re.search(r"^license:\s*MIT\s*$", citation, flags=re.MULTILINE) is not None,
            "CITATION.cff must declare license: MIT", errors)

    zenodo = json.loads(_text(".zenodo.json"))
    _expect(zenodo.get("version") == version, f".zenodo.json version {zenodo.get('version')!r} != {version!r}", errors)
    _expect(str(zenodo.get("license", "")).lower() == "mit", ".zenodo.json must declare MIT license", errors)
    _expect(zenodo.get("upload_type") == "software", ".zenodo.json upload_type must be 'software'", errors)
    _expect(bool(zenodo.get("creators")), ".zenodo.json must contain at least one creator", errors)

    codemeta = json.loads(_text("codemeta.json"))
    _expect(codemeta.get("version") == version, f"codemeta.json version {codemeta.get('version')!r} != {version!r}", errors)
    _expect(codemeta.get("@type") == "SoftwareSourceCode", "codemeta.json @type must be SoftwareSourceCode", errors)
    _expect("MIT" in str(codemeta.get("license", "")), "codemeta.json must identify the MIT license", errors)

    installer = _text("installer/uvvis_studio.iss")
    installer_version = _capture(r'^#define\s+MyAppVersion\s+"([^"]+)"', installer, "Inno Setup version", errors)
    if installer_version is not None:
        _expect(installer_version == version, f"installer version {installer_version!r} != {version!r}", errors)

    for workflow in (
        ".github/workflows/windows-installer.yml",
        ".github/workflows/cross-platform-desktop.yml",
        ".github/workflows/python-distribution.yml",
    ):
        workflow_text = _text(workflow)
        workflow_version = _capture(r'^\s*RELEASE_VERSION:\s*[\"\']?([^\"\'\s]+)', workflow_text, f"{workflow} RELEASE_VERSION", errors)
        if workflow_version is not None:
            _expect(workflow_version == version, f"{workflow} release version {workflow_version!r} != {version!r}", errors)

    readme = _text("README.md")
    _expect(f"Current release line: v{version}" in readme, f"README.md does not identify current release line v{version}", errors)

    changelog = _text("CHANGELOG.md")
    _expect(re.search(rf"^##+\s+\[?v?{re.escape(version)}\]?\b", changelog, flags=re.MULTILINE) is not None,
            f"CHANGELOG.md has no heading for version {version}", errors)

    if errors:
        print("Release metadata validation FAILED:", file=sys.stderr)
        for error in errors:
            print(f" - {error}", file=sys.stderr)
        return 1

    print(f"Release metadata validation passed for UV-Vis Spectrum Studio v{version}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
