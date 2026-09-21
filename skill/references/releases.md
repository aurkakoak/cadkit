# Releases

CadKit uses one version in `pyproject.toml` and `desktop/package.json`. The
release workflow checks both against a `vMAJOR.MINOR.PATCH` tag. The current
release targets are macOS Apple Silicon, macOS Intel and Windows x64.

## Development

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and Node 24:

```sh
uv sync --locked --extra desktop
uv run pytest tests -q
cd desktop
npm ci
npm run test:runtime
npm run build
```

`uv.lock` records Python dependencies for all supported platforms, including
the fixed cq_warehouse Git revision. `.python-version` selects Python 3.12.
Use `uv lock --upgrade` deliberately, then test all release targets. Intel Mac
wheels for numerical dependencies need particular care. The consumer package
still supports Python 3.11 and later; uv is the repository's development and
release tool, not a requirement imposed on callers of the Python package.

CI runs Python tests, desktop/MCP integration tests, runtime-selection tests,
skill validation and a strict documentation build. Package builds run the
Python tests again on each native operating system.

## Build installers

On the target operating system and architecture:

```sh
cd desktop
npm ci
npm run bundle:python
npm run package -- --mac --arm64 --publish never
# Intel Mac: --mac --x64
# Windows:   --win --x64
```

The bundle script copies a complete uv-managed Python distribution, installs
locked desktop dependencies and the built CadKit wheel, then relocates it to
a path containing spaces and tests a real CAD scene. It does not ship a venv
whose interpreter points back to the CI machine. Electron includes this
runtime outside its application archive. Users can still choose a project
environment with `--python` for extra project dependencies.

The packaged app opens a writable copy of the example on its first launch.
Its MCP configuration uses the app executable with `--mcp`, so users do not
need to install Node separately.

Run the packaged smoke check before distributing:

```sh
npm run smoke:package -- release/mac-arm64/CadKit.app/Contents/MacOS/CadKit
# Intel Mac: release/mac/CadKit.app/Contents/MacOS/CadKit
# Windows: release/win-unpacked/CadKit.exe
```

## Publish a version

1. Update Python and desktop versions together; update `desktop/package-lock.json`
   and `uv.lock` with the package managers. Refresh any version-pinned examples.
2. Run `uv run python scripts/sync_skill.py` after changing documentation.
3. Merge the tested release changes into `main`.
4. Push a tag matching the version:

   ```sh
   git tag v0.2.0
   git push origin main v0.2.0
   ```

The Release workflow tests the code, builds all three native targets, launches
each packaged app, builds the wheel/sdist and skill archive, and validates the
complete asset set. Only then does it create a draft release, upload all assets
and SHA-256 checksums, and publish it. If an upload fails, the draft remains
unpublished; remove that incomplete draft before rerunning the publish job.
Do not move a published version tag to new code; release a new patch version.

Manual **Run workflow** builds downloadable Actions artifacts without creating
a release. Python distributions are attached to GitHub Releases; this workflow
does not publish to PyPI or npm.

Expected assets:

- `CadKit-VERSION-macos-arm64.dmg` and `.zip`
- `CadKit-VERSION-macos-x64.dmg` and `.zip`
- `CadKit-VERSION-windows-x64.exe`
- `cadkit-VERSION-py3-none-any.whl` and `cadkit-VERSION.tar.gz`
- `cadkit-skill-VERSION.zip` and `SHA256SUMS`

## Code signing

Without credentials, builds are unsigned or ad-hoc signed. macOS Gatekeeper
and Windows SmartScreen can warn or block launch. The installers do not disable
either protection. For public distribution without those warnings, configure
the repository's Actions secrets before building the release:

- macOS: `CSC_LINK`, `CSC_KEY_PASSWORD` (Developer ID certificate), `APPLE_ID`,
  `APPLE_APP_SPECIFIC_PASSWORD`, `APPLE_TEAM_ID` (notarization).
- Windows: `WIN_CSC_LINK`, `WIN_CSC_KEY_PASSWORD` for the signing certificate.

See [electron-builder code signing](https://www.electron.build/code-signing.html)
for certificate formats and alternative signing services. Certificate passwords
belong in Actions secrets, never in this repository. A signed build should be
downloaded and opened on a separate Mac/Windows machine before announcing it.

## Install scripts

GitHub Pages serves `install.sh` and `install.ps1` from the source scripts.
Both resolve a published GitHub Release, select the matching asset and verify
its checksum before installing. macOS installs to `~/Applications` without
sudo and preserves the previous app if replacement fails. Windows launches
the NSIS installation wizard. Neither script downloads a Python environment
on the user's machine.

To select a specific macOS version or location:

```sh
curl -fsSL https://aurkakoak.github.io/cadkit/install.sh | \
  CADKIT_VERSION=0.2.0 CADKIT_INSTALL_DIR="$HOME/Applications" sh
```

On Windows, set `$env:CADKIT_VERSION = '0.2.0'` before running the script.
The scripts require a published release; a draft or Actions artifact is not
available through the latest-release URL. Linux users can run from source;
Linux binary packages are not part of this initial release pipeline.

## Documentation and skill

The site consists of `site/` for the small static landing page, Material for
MkDocs at `/docs/`, and the two installer scripts. Build it with:

```sh
uv run --locked --only-group docs python scripts/build_site.py
```

The combined output is `build/site/`. The Pages workflow deploys this directory
when `main` changes. Configure **Settings → Pages → Source → GitHub Actions**
once in GitHub. The source URL is `https://aurkakoak.github.io/cadkit/`.

`npx skills` installs directly from GitHub; it has no npm publishing step for
individual skills. The committed `skill/` directory includes the instructions
and their reference files. Refresh those references with
`python scripts/sync_skill.py`; CI's `--check` rejects stale or broken content.
Test discovery without installing into an agent:

```sh
npx skills add ./skill --list
```

Publishing this repository makes `npx skills add aurkakoak/cadkit --skill cadkit`
available. The [skills.sh directory](https://skills.sh/docs) derives discovery
and rankings from CLI usage; a listing or ranking is not guaranteed by a push.
