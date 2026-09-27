# Connection and build recovery

Treat failed MCP use as an error to diagnose. Correct the cause, then retry;
repeating the same failing call adds no evidence. A tool listing proves only
server startup. A successful `get_state` with the intended project/reference and
a ready build confirms the live connection.

Run `cadkit doctor` in the consumer's configured Python environment for runtime,
import and executable diagnostics. It does **not** test the live app. A source
desktop runtime also provides this client using its existing Node dependencies:

```sh
node /resolved/cadkit/desktop/electron/mcp-client.mjs \
  --project-dir /resolved/consumer --project my_cad.project:PROJECT doctor
```

Resolve these paths from the consumer configuration. The client also accepts
`tools`, or `TOOL 'JSON_ARGUMENTS'`; `screenshot` requires `--output /path/image.png`.
Older or packaged runtimes may instead provide a consumer helper or the app's
plug configuration.

| Failure | Remedy |
| --- | --- |
| Tools unregistered | Use the documented helper or standard client. Use the app's plug configuration for a persistent connection; a helper needs no global settings change. |
| Helper fails resolving Python/packages before MCP starts | Check the selected runtime paths and Python with the consumer's resolver/doctor. Use the standard client from that runtime to avoid incidental dependency sync. Repair missing dependencies through [setup](install.md), without implicitly substituting a registry package or stale trial. |
| App absent, `ENOENT`, connection refused | Check the exact directory, worktree and import reference. Launch that target with the consumer command, wait for its build, then retry. A different open project does not satisfy the connection. |
| `EPERM`, `EACCES`, socket access denied | Use the host's permission mechanism for local app/socket access. Keep IPC permissions private; do not delete a live socket. |
| Build running, failed or unavailable | Read the build error and selected worker Python. Fix routine source/import/runtime errors within scope and wait for a successful build. A failed rebuild can leave old geometry visible. |
| Unknown tool or stale revision | Refresh tool schemas or state and re-resolve IDs. New source tools require the matching app/server restart; use supported tools for intentionally older runtimes. |

When user action is needed, give the actual error, what you tried and the exact
launch command, setting or permission required. Keep independent work moving,
but identify outstanding visual verification. Never invent selection or claim
in-app review after a connection failure.
