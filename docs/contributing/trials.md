# Local adoption trials

Build a release from the current CadKit files with a unique local version. The
builder needs uv and network/cache access to setuptools build
requirements. It excludes consumer geometry, node_modules, generated desktop
bundles, caches and prior trial reports.

```sh
python3 scripts/build_trial.py --label trial.1 --output releases/cadkit-trial.1
python3 releases/cadkit-trial.1/install.py verify
```

`skill/` is the maintained skill entrypoint and UI metadata. The builder packages
it under `skills/cadkit`; `scripts/sync_skill.py` assembles `agent-reference/`
and the desktop reference into `references/`. Run that sync before building.
Install from the assembled release, so copied
skills never depend on documentation outside their folder. Edit the agent sources
and rebuild under a new label; do not hand-edit generated skill references.

Before handing a release to a consumer agent:

1. Validate the packaged skill and its relative links.
2. Create an empty working directory and a fresh virtual environment with no
   system packages or editable CadKit install. Install the wheel and desktop
   extra through `install.py`; record `pip freeze` and actual import paths.
3. Copy and run the independent bracket example: describe, inspect, build,
   check, STEP assembly, render assets and a Blender smoke image when available.
4. Copy the desktop runtime with the installer, install its locked npm packages
   and run its build/Electron tests against that fresh Python. Label mock slicer
   evidence accurately. Verify the release still matches its manifest afterward.
5. Checkpoint the consumer's current work. Install the copied skill and start a
   fresh task/worktree from that checkpoint, with no inherited migration chat.

The migration brief should specify outcomes and allowed materials, not an
implementation. It should require the consumer's own baseline, parity evidence
and an adoption report. Give it the release path and normal setup instructions.
Reading the installed framework source is possible for an open-source consumer;
record when undocumented behavior makes that necessary.

Keep observer notes outside the release and consumer inputs. Record the bundle
hash, consumer baseline commit, exact initial prompt, fresh task ID, environment,
progress and any intervention. Monitor without sending implementation hints.
If a limitation requires a framework fix, record the failure, issue a new
release and mark the next attempt explicitly. Preserve the original evidence.
Claim success only for workflows verified, with pre-existing failures and
remaining limitations kept distinct.

Local skill discovery follows the standard [Codex repository skill layout](https://learn.chatgpt.com/docs/build-skills).
The provided installer is an authentication-free substitute for the local-path
installation supported by the [Skills CLI](https://github.com/vercel-labs/skills).
