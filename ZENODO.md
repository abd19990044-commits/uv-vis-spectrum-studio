# Zenodo archival guide

UV-Vis Spectrum Studio is prepared for software archiving through the GitHub–Zenodo integration. The release process is intentionally **draft-first** so that Zenodo never receives a partially assembled multi-platform release.

## Metadata files and precedence

The repository contains:

- `.zenodo.json` — Zenodo-specific release metadata;
- `CITATION.cff` — portable citation metadata used by GitHub and citation tooling;
- `codemeta.json` — interoperable software metadata for indexing and research-software tooling.

When both `.zenodo.json` and `CITATION.cff` are present, Zenodo's GitHub integration uses the Zenodo-specific metadata for the archived release. `CITATION.cff` is intentionally retained for GitHub's **Cite this repository** interface and for other citation tools.

No DOI is hard-coded before Zenodo actually assigns it.

## Release architecture

A normal push to `main` may build CI artifacts, but it does **not** constitute an archived scientific release. An official release begins with an immutable version tag such as `v3.1.0`.

Tag-triggered workflows build and upload their assets to a **draft GitHub Release**. The draft remains unpublished while Windows, Linux, macOS, and Python-distribution quality gates run. Only after all intended platform artifacts and metadata have been verified should the maintainer manually choose **Publish release** in GitHub. Publication of that completed GitHub Release is the archival gate seen by Zenodo.

This separation is deliberate:

1. **development/main build** → temporary GitHub Actions artifacts;
2. **version tag** → immutable source point + draft GitHub Release;
3. **platform QA** → all release assets, checksums, build information, and package smoke tests verified;
4. **Publish release** → completed public GitHub Release;
5. **Zenodo ingestion** → DOI-bearing archived software record.

## Before the first DOI release

1. Ensure the repository is public and the intended release commit is final.
2. Confirm the software version is identical in:
   - `uvvis_studio/__init__.py`;
   - `pyproject.toml`;
   - `CITATION.cff`;
   - `.zenodo.json`;
   - `codemeta.json`;
   - Windows and cross-platform packaging configuration.
3. Confirm the release date and changelog entry.
4. Ensure CI passes on the supported Python versions.
5. Ensure the release builds complete for every target you intend to claim:
   - Windows x64;
   - Linux x86_64;
   - Linux ARM64;
   - macOS Intel x86_64;
   - macOS Apple Silicon ARM64;
   - Python wheel and source distribution.
6. Confirm packaged self-tests pass for every desktop target that is being released.
7. Confirm the Python wheel is installed and exercised in a clean virtual environment and that `uvvis-spectrum-studio --version` reports the tagged version.
8. Review `LICENSE`, `LICENSE-NOTICE.md`, `README.md`, `CHANGELOG.md`, `CITATION.cff`, `.zenodo.json`, and `codemeta.json`.
9. Verify SHA-256 files, dependency snapshots, build provenance, and architecture labels emitted by CI.
10. Review known platform limitations, including signing/notarization and browser requirements for publication export.
11. Do **not** insert a fabricated or anticipated DOI. Add a DOI only after Zenodo assigns it.

## GitHub → Zenodo procedure

1. Sign in to Zenodo and connect the GitHub account that controls this repository.
2. Synchronize the Zenodo GitHub repository list and enable `uv-vis-spectrum-studio`.
3. From the verified release commit, create and push an immutable tag such as `v3.1.0`.
4. Wait for all tag-triggered workflows to finish. They should populate a **draft** GitHub Release rather than publish it automatically.
5. Inspect the draft release. Confirm the expected platform assets, checksums, build information, dependency snapshots, and source/Python distributions are present.
6. Re-download or independently verify representative artifacts where practical, especially the Windows installer and packaged desktop applications.
7. Only after the draft passes release QA, choose **Publish release** in GitHub.
8. Wait for Zenodo to ingest and archive the published GitHub Release.
9. Inspect the Zenodo record before citing it. Verify:
   - title;
   - creator and affiliation;
   - software version;
   - publication date;
   - MIT license;
   - description;
   - keywords;
   - linked repository;
   - archived release/source files.
10. After Zenodo assigns the DOI, add it to the **next development revision** of citation/documentation metadata if desired. Do not rewrite an immutable historical tag solely to make it refer to its own DOI.
11. For publications, cite the DOI of the exact software version used whenever possible.

## Release assets

GitHub Actions are configured to build architecture-specific assets from the same tested scientific core:

- **Windows x64** — Inno Setup installer, portable ZIP, SHA-256 checksums, environment lock snapshot, build information, and Authenticode signing where configured. The fallback self-signed certificate does not eliminate Windows SmartScreen warnings.
- **Linux x86_64** — portable `tar.gz`, SHA-256 manifest, dependency snapshot, build information, and bundled Chrome-for-Testing for Kaleido publication export.
- **Linux ARM64** — portable `tar.gz`, SHA-256 manifest, dependency snapshot, and build information. Chrome-for-Testing does not currently provide a `linux-arm64` binary through Kaleido; publication raster/vector export therefore requires a compatible system Chrome/Chromium, optionally specified with `BROWSER_PATH`.
- **macOS Intel x86_64** — `.app` packaged in ZIP plus DMG, checksums, dependency snapshot, and build information.
- **macOS Apple Silicon ARM64** — `.app` packaged in ZIP plus DMG, checksums, dependency snapshot, and build information.
- **Python** — wheel and source distribution, `twine` validation, isolated-wheel installation/CLI smoke test, build-environment snapshot, build information, and SHA-256 manifest.

macOS CI currently applies an **ad-hoc signature** for bundle consistency. This is not Apple Developer ID signing or notarization; Gatekeeper may require explicit user approval until Developer ID signing/notarization is configured.

Binary architecture support must be described exactly as built and tested. A source distribution is not evidence that every third-party binary dependency exists for every operating system/CPU pair.

## License policy

The project uses the standard **MIT License**. The canonical `LICENSE` text is intentionally not customized. Scientific-use, third-party dependency, validation, and regulatory caveats belong in `LICENSE-NOTICE.md` and project documentation rather than being inserted into the MIT terms. This preserves unambiguous license detection by Zenodo, GitHub, SPDX tooling, package registries, and institutional scanners.

## Scientific release policy

A software DOI records and identifies a specific software release. It does **not** certify analytical-method validation, instrument qualification, regulatory compliance, or fitness for a particular laboratory procedure.

For reproducibility, publications should report the exact software version/DOI and, where possible, preserve the corresponding `.uvvisproj`, source spectra, analytical conditions, processing parameters, instrument/software export details, and chemometric validation strategy.

## Recommended archived-release checklist

- [ ] core CI passes on all supported Python versions;
- [ ] Windows installer and portable build pass packaged self-test;
- [ ] Linux x86_64 packaged self-test passes;
- [ ] Linux ARM64 packaged self-test passes;
- [ ] macOS Intel packaged self-test passes;
- [ ] macOS Apple Silicon packaged self-test passes;
- [ ] Python wheel installs in an isolated environment and its CLI starts;
- [ ] version metadata agree everywhere;
- [ ] tag version exactly matches package version;
- [ ] release checksums are present and non-empty;
- [ ] build provenance and dependency snapshots are present;
- [ ] changelog and release notes are final;
- [ ] metadata files validate;
- [ ] signing/notarization limitations are accurately documented;
- [ ] Linux ARM64 publication-export browser limitation is documented;
- [ ] Zenodo repository integration is enabled;
- [ ] the GitHub Release remains **draft** until all checks above pass;
- [ ] the release is manually published only after final QA.
