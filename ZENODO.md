# Zenodo archival guide

UV-Vis Spectrum Studio is prepared for future software archiving through Zenodo.

## Before the first DOI release

1. Ensure the repository is public and the intended release commit is final.
2. Confirm the software version is identical in:
   - `uvvis_studio/__init__.py`
   - `pyproject.toml`
   - `CITATION.cff`
   - `.zenodo.json`
   - platform packaging configuration.
3. Ensure CI passes on the supported Python versions.
4. Ensure Windows, Linux, macOS, and Python-distribution workflows complete successfully for the release commit/tag.
5. Review `LICENSE`, `LICENSE-NOTICE.md`, `README.md`, `CHANGELOG.md`, `CITATION.cff`, and `.zenodo.json`.
6. Do not insert a fabricated DOI. Add the DOI only after Zenodo assigns it.

## GitHub → Zenodo

1. Sign in to Zenodo using the account that controls the GitHub repository.
2. Enable the repository in Zenodo's GitHub integration.
3. Create an immutable Git tag such as `v3.1.0` from the verified release commit.
4. Create/publish the corresponding GitHub Release.
5. Zenodo should archive the release and assign a version DOI. Zenodo also provides a concept DOI for the software record as a whole.
6. Check the Zenodo draft/record carefully before relying on it for citation:
   - title,
   - author name,
   - software version,
   - publication date,
   - MIT license,
   - description,
   - keywords,
   - linked GitHub repository.
7. After the DOI exists, add the Zenodo DOI badge and DOI identifier to the next repository metadata update. Do not rewrite an already immutable tagged release merely to insert its own DOI.

## Release assets

GitHub Actions creates platform-specific release artifacts where supported:

- Windows x64 Inno Setup installer, checksum, environment lock, and signing certificate when the self-signed fallback is used.
- Linux x86_64 portable `tar.gz`, SHA-256 file, environment lock, and build information.
- macOS Apple Silicon application `zip` and `dmg` when packaging succeeds, SHA-256 file, environment lock, and build information.
- Python source distribution (`sdist`) and wheel with SHA-256 checksums for source-based installation across supported Python platforms.

Binary architecture support must be described exactly as built. A source distribution is not evidence that every binary dependency is available on every CPU architecture.

## Scientific release policy

A software DOI records a specific software release; it does not certify analytical-method validation, regulatory compliance, or fitness for a particular laboratory procedure. Publications should report both the software version/DOI and the analytical validation relevant to the study.

For reproducibility, archive the exact `.uvvisproj` project, source data (when licensing and confidentiality permit), processing settings, and relevant instrument/method metadata alongside the publication or in an appropriate research-data repository.
