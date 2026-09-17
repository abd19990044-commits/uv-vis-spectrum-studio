# Zenodo archival guide

UV-Vis Spectrum Studio is prepared for future software archiving through the GitHub–Zenodo integration.

## Metadata files and precedence

The repository contains both:

- `.zenodo.json` — Zenodo-specific release metadata;
- `CITATION.cff` — portable citation metadata used by GitHub and citation tooling;
- `codemeta.json` — interoperable software metadata for indexing and research-software tooling.

When both `.zenodo.json` and `CITATION.cff` are present, Zenodo currently uses `.zenodo.json` for GitHub release archiving. `CITATION.cff` is intentionally retained because GitHub uses it for **Cite this repository** and it remains useful to other tools.

## Before the first DOI release

1. Ensure the repository is public and the intended release commit is final.
2. Confirm the software version is identical in:
   - `uvvis_studio/__init__.py`
   - `pyproject.toml`
   - `CITATION.cff`
   - `.zenodo.json`
   - `codemeta.json`
   - Windows and cross-platform packaging workflows/configuration.
3. Confirm the release date and changelog entry.
4. Ensure CI passes on the supported Python versions.
5. Ensure the release builds complete for all intended targets:
   - Windows x64;
   - Linux x86_64;
   - Linux ARM64;
   - macOS Intel x86_64;
   - macOS Apple Silicon ARM64;
   - Python wheel and source distribution.
6. Review `LICENSE`, `LICENSE-NOTICE.md`, `README.md`, `CHANGELOG.md`, `CITATION.cff`, `.zenodo.json`, and `codemeta.json`.
7. Verify SHA-256 files and build provenance emitted by CI.
8. Do **not** insert a fabricated or anticipated DOI. Add the DOI only after Zenodo assigns it.

## GitHub → Zenodo procedure

1. Sign in to Zenodo and connect the GitHub account that controls this repository.
2. In Zenodo's GitHub integration, synchronize the repository list and enable `uv-vis-spectrum-studio`.
3. Create an immutable Git tag such as `v3.1.0` from the verified release commit.
4. Publish the corresponding GitHub Release.
5. Wait for Zenodo to ingest and archive the release.
6. Inspect the resulting Zenodo record before using it in publications. Verify:
   - title;
   - creator and affiliation;
   - software version;
   - publication date;
   - MIT license;
   - description;
   - keywords;
   - linked repository;
   - release files.
7. After Zenodo assigns the DOI, update the **next development revision** of `CITATION.cff`/README with the DOI if desired. Do not rewrite an already immutable tagged release only to make it refer to its own DOI.
8. For papers, cite the exact version DOI used in the analysis rather than only the repository URL whenever possible.

## Release assets

GitHub Actions are configured to create architecture-specific assets from the same tested scientific core:

- **Windows x64** — Inno Setup installer, SHA-256 checksum, environment lock snapshot, build information, and code-signing material where applicable.
- **Linux x86_64** — portable `tar.gz`, SHA-256 manifest, environment lock, and build information.
- **Linux ARM64** — portable `tar.gz`, SHA-256 manifest, environment lock, and build information.
- **macOS Intel x86_64** — `.app` packaged in ZIP plus DMG, checksums, environment lock, and build information.
- **macOS Apple Silicon ARM64** — `.app` packaged in ZIP plus DMG, checksums, environment lock, and build information.
- **Python** — wheel and source distribution with checksums for source-based installation where dependencies are available.

Binary architecture support must be described exactly as built and tested. A source distribution is not evidence that every third-party binary dependency exists for every operating system/CPU pair.

## License policy

The project uses the standard **MIT License**. The canonical `LICENSE` text is intentionally not customized. Scientific-use, third-party dependency, validation, and regulatory caveats belong in `LICENSE-NOTICE.md` and documentation rather than being inserted into the MIT terms. This preserves unambiguous license detection by Zenodo, GitHub, SPDX tooling, package registries, and institutional scanners.

## Scientific release policy

A software DOI records and identifies a specific software release; it does not certify analytical-method validation, instrument qualification, regulatory compliance, or fitness for a particular laboratory procedure.

For reproducibility, publications should report the software version/DOI and, where possible, preserve the corresponding `.uvvisproj`, source spectra, analytical conditions, processing parameters, instrument/software export details, and chemometric validation strategy.

## Recommended first archived release checklist

- [ ] all scientific tests pass;
- [ ] packaged self-tests pass on intended release platforms;
- [ ] version metadata agree everywhere;
- [ ] release checksums are present;
- [ ] changelog is final;
- [ ] metadata files validate;
- [ ] release notes describe scientific changes and known limitations;
- [ ] Zenodo repository integration is enabled;
- [ ] GitHub tag and Release are created only after the above checks pass.
