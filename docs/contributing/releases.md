# Releases

CadKit uses one version in `pyproject.toml` and `desktop/package.json`. The
release workflow checks both against a `vMAJOR.MINOR.PATCH` tag. The current
release targets are macOS Apple Silicon and Intel, plus Linux x64 and arm64.

## Development

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and Node 24:

```sh
uv sync --locked --extra desktop
uv run pytest tests -q
cd desktop
npm ci
npm run setup
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
Python tests again on each native operating system and architecture.

## Build installers

On the target operating system and architecture:

```sh
cd desktop
npm ci
npm run bundle:python
npm run package -- --mac --arm64 --publish never
# Intel Mac: --mac --x64
# Linux: --linux --x64 or --linux --arm64
```

The bundle script copies a complete uv-managed Python distribution, installs
locked desktop dependencies and the built CadKit wheel, then relocates it to
a path containing spaces and tests a real CAD scene. It does not ship a venv
whose interpreter points back to the CI machine. Electron includes this
runtime outside its application archive. Users can still choose a project
environment with `--python` for extra project dependencies.

Packaging checks the bundled platform, architecture and CadKit version against
the desktop build. If they differ, run `npm run bundle:python` before packaging.

The packaged app opens Projects when launched without a project. Users choose an
existing folder or create a writable starter or bracket example. The packaged
smoke test explicitly opens a bracket copy to verify the worker and renderer.
MCP configuration uses the app executable with `--mcp`, so users do not need to
install Node separately.

Run the packaged smoke check before distributing:

```sh
npm run smoke:package -- release/mac-arm64/CadKit.app/Contents/MacOS/CadKit
# Intel Mac: release/mac/CadKit.app/Contents/MacOS/CadKit
# Linux x64: release/linux-unpacked/cadkit-desktop
# Linux arm64: release/linux-arm64-unpacked/cadkit-desktop
```

## Publish a version

1. Update Python and desktop versions together; update `desktop/package-lock.json`
   and `uv.lock` with the package managers. Refresh any version-pinned examples.
2. Run `uv run python scripts/sync_skill.py` after changing `agent-reference/`
   or the desktop README. Build the human docs separately with `scripts/build_site.py`.
3. Merge the tested release changes into `main`.
4. Push a tag matching the version:

   ```sh
   git tag v0.5.3
   git push origin main v0.5.3
   ```

The Release workflow tests the code, builds all four native targets, launches
each packaged app, builds the wheel/sdist and skill archive, and validates the
complete asset set. Only then does it create a draft release, upload all assets
and SHA-256 checksums, and publish it. If an upload fails, the draft remains
unpublished; remove that incomplete draft before rerunning the publish job.
Do not move a published version tag to new code; release a new patch version.

Manual **Run workflow** builds downloadable Actions artifacts by default. Select
**Publish this version after all native builds pass** to create a new version
tag and release from the tested commit after every build passes. This option
rejects an existing version tag; use the tag-triggered workflow or a new version
instead. Python distributions are attached to GitHub Releases; this workflow
does not publish to PyPI or npm.

Expected assets:

- `CadKit-VERSION-macos-arm64.dmg` and `.zip`
- `CadKit-VERSION-macos-x64.dmg` and `.zip`
- `CadKit-VERSION-linux-x64.tar.gz` and `CadKit-VERSION-linux-arm64.tar.gz`
- `cadkit-VERSION-py3-none-any.whl` and `cadkit-VERSION.tar.gz`
- `cadkit-skill-VERSION.zip` and `SHA256SUMS`

## Code signing

Without credentials, macOS builds are unsigned or ad-hoc signed. Gatekeeper
can warn or block launch. The installer preserves this protection.
For public distribution without those warnings, configure
the repository's Actions secrets before building the release:

- `CSC_LINK`, `CSC_KEY_PASSWORD` (Developer ID certificate).
- `APPLE_ID`, `APPLE_APP_SPECIFIC_PASSWORD`, `APPLE_TEAM_ID` (notarization).

See [electron-builder code signing](https://www.electron.build/code-signing.html)
for certificate formats and alternative signing services. Certificate passwords
belong in Actions secrets, never in this repository. A signed build should be
downloaded and opened on a separate Mac before announcing it.

## Install script

GitHub Pages serves `install.sh` from the source script. It resolves a published
GitHub Release, selects the matching operating system and architecture, and
verifies the asset's checksum before installing without sudo. The app includes
its Python environment.

On macOS, it installs to `~/Applications` and preserves the previous app if
replacement fails. On Linux, it installs the native `.tar.gz` bundle to
`~/.local/share/cadkit`, creates the `~/.local/bin/cadkit-desktop` launcher and
adds `~/.local/share/applications/cadkit.desktop` to the app menu.

To select a specific macOS version or location:

```sh
curl -fsSL https://aurkakoak.github.io/cadkit/install.sh | \
  CADKIT_VERSION=0.5.3 CADKIT_INSTALL_DIR="$HOME/Applications" sh
```

The script requires a published release; a draft or Actions artifact is not
available through the latest-release URL.

## Documentation and skill

The site consists of `site/` for the small static landing page, Material for
MkDocs at `/docs/`, and the macOS/Linux installer script. Build it with:

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
