# Desktop performance

The desktop records wall-clock timings for every successful build. Read
`performance` from MCP `get_state` (or `cadkit://state`). In renderer DevTools,
`(await window.cadkit.load()).scene.performance` returns the same diagnostics.
No profiler, external service or additional UI is required.

## Reading a build

| Field | Boundary |
| --- | --- |
| `worker_ready_seconds` | Python spawn through imports, project construction and initial dependency discovery |
| `worker_seconds` | Python spawn through scene receipt and JSON parsing in Electron |
| `stages_seconds.project_load` | Import the project's module and resolve its selected variant |
| `stages_seconds.cache_prepare` | Fingerprint runtime, source and declared inputs; open a matching native cache |
| `stages_seconds.cache_read`, `cache_write` | Restore/check native bodies or serialize newly built bodies |
| `stages_seconds.cache_commit` | Recheck inputs and atomically publish/maintain the cache |
| `stages_seconds.assembly` | Build installed geometry, hardware and resolved relationships |
| `stages_seconds.geometry` | Build each distinct Part/Purchased definition used in the assembly |
| `stages_seconds.feature` | Apply and validate named manufacturing features |
| `stages_seconds.boolean_prepare` | Partition a manufacturing feature's body and cutters once using OCCT |
| `stages_seconds.boolean_check_sites` | Select and measure each cutter's exact material intersection from that partition |
| `stages_seconds.boolean_finish` | Select the cut result, clean it and validate material removal |
| `stages_seconds.hardware` | Build distinct hardware specifications |
| `stages_seconds.convert` | Convert native instances into the tessellator's hierarchy |
| `stages_seconds.tessellate` | Tessellate unique native shapes, retaining instance placements |
| `stages_seconds.bounds`, `volume` | Native component measurements |
| `stages_seconds.describe`, `mechanics` | Project and mechanical metadata |
| `stages_seconds.scene` | Entire scene request, including the tessellator import |
| `stages_seconds.encode` | Pack shared meshes into the viewer's binary-buffer transport format |
| `serialize_seconds`, `parse_seconds` | Worker JSON encoding and host decoding |
| `response_bytes` | Encoded scene response, including its newline |
| `peak_rss_bytes` | Peak Python worker resident memory through serialization; null if unavailable |
| `activation_seconds` | Scene activation in Electron through the viewport's ready acknowledgement |
| `clone_seconds`, `decode_seconds`, `render_seconds` | Renderer clone, binary buffer decoding, and synchronous viewer construction |
| `viewport_seconds` | View setup through two animation frames; an opportunity to paint, not a GPU fence |
| `viewport_cached` | Whether this activation reused an existing prepared viewport |
| `geometry_cache` | Native disk-cache status, body hits/misses/writes, skipped representations, corruption recovery and byte counts |

Times are seconds. **Stages are inclusive and overlap:** boolean stages belong
to features, features belong to geometry, geometry and hardware belong to
assembly, and assembly belongs to the scene. Do not add every stage together.
`operations` lists named geometry,
feature, hardware and measurement timings, slowest first. Reused part definitions
are built once; their geometry time is attributed to their first installed path.
Legacy project callbacks are covered by `assembly` but may have no per-definition
timings. `unique_native_shapes` counts tessellator instances, which can include
several solids within one component.

Cached variant activations retain the original worker's build measurements and
receive fresh viewport/activation timings. Worker memory excludes Electron,
GPU allocations and other cached workers. A cached switch differs from opening
a project in a fresh process.

## Reproducible worker benchmark

Run from the CadKit checkout with the project's Python environment. This script
uses fresh workers sequentially, discards scene buffers after measurement and
records the phase breakdown without launching the UI:

```sh
PYTHONPATH="$PWD/src:$PWD/../brewer/model/cadquery/src" \
  .venv/bin/python scripts/benchmark_desktop.py \
  --python "$PWD/../brewer/model/.venv/bin/python" \
  --project-dir ../brewer/model \
  --project brewer_cad.project:PROJECT \
  --runs 3 --output build/brewer-performance.json
```

Create the output directory first. `--variant base=hybrid` selects an alternative.
The report is saved after each completed run. Native disk caching is disabled
by default in this benchmark so its runs continue to measure cold geometry.
Pass `--cache-dir build/geometry-benchmark-cache` to enable it: an empty directory
gives one cold run followed by warm runs. Compare the individual cache statuses
and timings; a median mixing cold and warm runs describes neither case well.
Use medians within each case and retain individual
runs; first-run file-system caches, background activity and kernel scheduling
affect results. The script's `parse_seconds` uses Python's JSON decoder, while
the application's field uses Electron's decoder. `worker_seconds` excludes
application launch, project discovery and the viewport.

`--threads N` sets `CADKIT_OCCT_THREADS=N` for the worker. The desktop honors the
same environment variable through CadQuery's supported `setThreads()` API,
before loading project code. When unset, OCCT keeps its upstream default.
Compare several values on the actual model before choosing one: more threads
can increase overhead for many small booleans. This setting applies only to
desktop worker processes; importing CadKit does not change the host's thread pool.

For a full UI measurement, read `performance` after `viewport_seconds` appears.
Use a separate desktop user-data directory (`CADKIT_USER_DATA`) for experiments.
Avoid concurrent CAD benchmarks; they obscure both timing and memory results.

## Persistent native geometry

Desktop workers cache finished local Part/Purchased bodies from declarative
`Assembly.as_project()` projects. This is enabled by default. A cache hit restores
the native BRep, verifies its checksum, validity, solid count and volume, and then
performs normal assembly placement and tessellation. The worker reconstructs
metadata, mechanics and generated hardware from the loaded project. Measurements
use the restored native geometry; fabrication builders and ordinary CLI/Python
calls retain their existing behavior.

The cache conservatively invalidates the **whole project revision** on changes
to Python source contents or membership, declared dependency files/directories,
project metadata/variants, environment, interpreter or installed distribution
versions/records. Desktop activation tokens and process/session launch identifiers
are excluded from the environment fingerprint; geometry must not depend on them.
Source from external and lazy imports is tracked, including
when a warm build skips the import. Content hashes detect edits even when a
file's size and timestamp are unchanged. Input changes during a build prevent
publishing its cache. There is no per-part incremental dependency inference yet.

Geometry builders must be deterministic functions of those inputs. Declare
additional data files through `Variants(..., dependencies=(...))`. Clocks, random
values, network responses and undeclared file reads cannot be invalidated
reliably; disable caching for projects that require them. Native caching does
not skip project imports. Mesh bodies and legacy/custom project callbacks build
normally without being persisted.

The desktop stores archives under its user-data directory at `cache/geometry`;
direct `python -m cadkit.desktop` workers use the platform's user cache directory.
Nothing is written to the CAD project by default. Archives contain BRep data and
JSON, never pickled Python objects. Successful builds replace archives atomically.
Damaged entries are rebuilt, unavailable storage falls back to normal builds,
and least recently used archives are evicted against a shared 512 MiB budget.

| Environment setting | Behavior |
| --- | --- |
| `CADKIT_GEOMETRY_CACHE=0` | Disable native disk caching |
| `CADKIT_GEOMETRY_CACHE_DIR=/path` | Override the cache directory |
| `CADKIT_GEOMETRY_CACHE_MAX_MB=512` | Set the disk budget; zero disables caching |

Deleting the cache directory forces a cold rebuild. No manufacturing checks or
mesh quality settings are relaxed. `performance.geometry_cache` distinguishes
`cold`, `warm`, `partial`, `disabled`, `unsupported`, `unavailable` and
`inputs_changed`. `hits`/`misses` count distinct requested bodies, while `writes`
counts newly serialized bodies; a fully warm build writes none. Byte counts are
native payload sizes and exclude archive/manifest overhead.

### Brewer cache benchmark

With the implementation enabled, one cold worker took **26.905 s**; three
subsequent fresh workers took **6.418, 6.511 and 6.706 s** (warm median
**6.511 s**, approximately **4.1× faster** than that cold run). Each warm run
restored all **52** distinct native bodies, rebuilt generated hardware, and
produced the same 146-component scene at the existing tessellation settings.
These are complete worker round trips **including Python startup and scene
transfer/parsing**, unlike the earlier prototype's timing boundary below.

Source/runtime validation takes about 0.2 s. Project source inventories exclude
download caches and archived virtual environments, while explicitly imported
external packages remain tracked. This matters for workspaces containing old
environments: indiscriminately scanning Brewer's archived runtimes added several
seconds to every cache lookup during development.

Validation includes cache invalidation, corrupt/partial archive recovery,
concurrent publication, interrupted builds, disk limits, fresh-process restore,
and lazy-import tracking. An Electron integration test reopens the application,
verifies that its geometry builder did not run again, then edits a skipped lazy
import and verifies that the rebuilt native dimensions change. Variant failure
and rebuild tests also pass. The cache remains conservative across source edits;
these results do not measure per-part incremental rebuilding.

## Brewer investigation — 26 September 2026

Measured on Linux aarch64 (Asahi), 10 logical CPUs, Python 3.12.14,
CadQuery 2.8.0 / cadquery-ocp 7.9.3.1.1, ocp-tessellate 3.5.0 and
three-cad-viewer 5.0.4. Brewer commit `03e5bcc`, default `base=printed`,
146 installed native components. The original worker was taken from CadKit
`0c22f2a`; the first-pass worker includes the transport and instrumentation
changes below. The subsequent kernel improvement is measured separately.
Each sample starts a new Python process; OS file caches are not flushed.
Benchmarks ran sequentially. These are worker timings, not whole-app launch times.

| Configuration | Three runs (seconds) | Median | Scene response |
| --- | --- | --- | --- |
| Original, upstream 10-thread pool | 34.574, 32.322, 32.604 | 32.604 s | 37.74 MB |
| First pass, upstream 10-thread pool | 30.753, 31.052, 31.405 | 31.052 s | 12.43 MB |
| First pass, `CADKIT_OCCT_THREADS=1` | 25.833, 25.820, 26.090 | 25.833 s | 12.43 MB |

The first-pass default changes reduced worker time by **4.8%** in this benchmark.
Tuning this model to one OCCT thread reduced it by **20.8%** against the original.
The scene response is **67% smaller**. Hardware, selection IDs, tessellation
tolerances, native measurement geometry and manufacturing checks are retained.

In that first pass, with the default thread pool, median assembly construction
accounts for 27.11 s of the 31.05 s worker time. Tessellation takes 2.15 s, startup to worker readiness
1.27 s, mesh packing 0.014 s, JSON serialization 0.028 s, and Python JSON decoding
0.057 s. Metadata costs little. These separately calculated medians need not add
up to the median total, and the overlapping stages must not be summed.

Before the kernel improvement, the main gear took about 9.9 s to build. Its
`carrier-stack`, `rotor-mount` and `center-bore` features accounted for about
8.8 s of that time. The z cladding takes
about 3.1 s, the rotor 1.9 s and the outer housing 1.2 s. This identifies native
feature construction and validation as the main remaining cost, rather than
Python protocol handling. An exploratory wall-clock profile of the original
build counted 802 boolean operations and 213 shape-validity checks. Validation
was retained; reducing this work requires more than removing redundant UI calls.

The implemented changes are:

- Convert native components as one group so the existing upstream tessellator
  recognizes 71 unique shapes across the 146 installed components.
- Send each mesh once using the viewer's existing instanced, base64-buffer
  format, instead of expanded JSON number arrays. Only display data uses
  float32/uint32, matching the viewer's previous conversion; native CAD stays
  unchanged. Partial edge/vertex records remain supported inline.
- Query component bounds after tessellation, reuse them for scene bounds,
  and avoid a second set of native bounding-box calls.
- Record build phases, named geometry/features, serialization, viewport timing,
  thread count and worker peak resident memory. Expose optional thread tuning
  through the upstream CadQuery API, without a fork or global import-time patch.

The first-pass worker's median peak resident memory was approximately 690 MiB
with ten threads and 641 MiB with one. This is not a measurement of the whole
application or a diagnosis of an OOM: Electron, the GPU, other applications and
up to three retained variant workers have separate memory costs.

Thread tuning is deliberately **not a universal new default**. A single comparison
on the 39-component turbofan example took 27.93 s with ten threads and 44.97 s
with one; its geometry construction and tessellation benefited from parallelism.
The four-component shaft-support example took 1.21 s and 1.17 s respectively.
These smaller samples support keeping an explicit override rather than assuming
one thread count is optimal for every project.

### Sharing boolean work

A second implementation improves cold builds by sharing the intersection work
inside each manufacturing feature. Previously, each cutter ran a separate exact
intersection against the body to verify material removal, followed by another
boolean operation to cut all the tools. Complex bodies were processed repeatedly.

`_cut` now uses the existing upstream
[OCCT cells builder](https://occt3d.com/dev/doc/refman/html/class_b_o_p_algo___cells_builder.html)
through OCP. It partitions the body and cutters once, selects cells common to
the body and each cutter for the same volume checks, then selects body cells
outside every cutter for the final result. Overlapping cutters are checked against the original
body, preserving counterbore and duplicate-site semantics. Non-destructive mode
preserves reusable input geometry. Output validity, positive material removal,
feature ordering and tessellation quality remain checked as before. No CadQuery
fork or runtime monkey patch is required.

Three fresh default-thread workers took **25.641, 25.785 and 25.461 s** (median
**25.641 s**). This is **17.4% faster** than the first optimization's 31.052 s,
and **21.4% faster** than the original 32.604 s. These are complete worker
round trips, with the same 146 components and 12.43 MB response. The separate
gear-only experiment fell from 10.40 s to 6.79 s; its result retained the same
volume, 1,821 faces and native validity.

All **52 Brewer Part/Purchased bodies** were compared with BRep files captured
before this change. Every result was valid and retained its volume, solid count,
face count and bounds; exact booleans found **zero added or missing material**
in either direction. The targeted suite passed **109 tests**, including new
overlapping/nested/duplicate cutter, compound-body, split-solid, tangent-site and
whole-body-removal cases. This is stronger evidence than matching mesh appearance
or total volume alone.

Combining the shared boolean work with the optional one-thread setting took
**21.534, 21.758 and 21.388 s** (median **21.534 s**, **34.0% faster** than the
original default worker). The upstream default still remains unchanged.
Median peak worker RSS was 689 MiB with ten threads and 641 MiB with one.
This changes computation time, without materially reducing worker memory.
A turbofan smoke benchmark took 26.83 s, versus the earlier 27.93 s sample with
the same upstream thread default; this single comparison found no regression,
but is not a statistical performance claim for that project.

### Persistent native geometry: measured feasibility

A fixed-revision prototype wrote the 52 distinct Part/Purchased bodies from
Brewer to native BRep files, then restored them in separate fresh processes.
The files total **6.12 MB**, and export itself took **0.147 s**. Restore included
file hash checks, native shape validity, solid presence, volume and face-count
comparisons. Generated hardware was still rebuilt and the entire scene was still
tessellated at normal quality.

Project load through packed scene generation took **4.810, 4.994 and 5.011 s**,
with body restoration and checks taking about **1.1 s** instead of roughly 26 s
of part construction. The capture run took 30.374 s. These prototype timings
**exclude Python/CadQuery startup and transport to Electron**; they are not
five-second application-launch measurements. Peak worker RSS remained about
676–679 MiB: this demonstrates a latency improvement, not a memory solution.

These were the initial prototype measurements. The persistent native cache
described above now implements revision invalidation, corruption recovery,
atomic publication and bounded storage. Incremental dependency tracking and
persistent display meshes remain separate work.

The next architectural steps, in order, are:

1. Extend native caching to display meshes for unchanged project revisions,
   avoiding repeated tessellation as well as native construction.
2. Track dependencies per body/feature so editing a bracket reuses an unchanged
   gear. Arbitrary Python closures and module globals make a callable's name or
   `repr` insufficient as a cache key. Use explicit build inputs/dependencies or
   conservative invalidation where dependencies cannot be established.
3. Present saved display geometry while native geometry becomes available, and
   rebuild independent missing parts with a bounded worker pool. Parallelism
   needs a memory budget; the measured single-worker RSS rules out casually
   starting a worker for every CPU on a large project.

Caching cannot accelerate the first computation of new geometry. Sharing kernel
work already improves that case; bounded parallel builds and more efficient
feature construction are further options. The measurements do not show an
unavoidable rendering ceiling imposed by CadQuery.

### Viewport check

An isolated Electron launch using its normal graphics backend rendered all 146
Brewer components without renderer errors. Launch to ready was 33.09 s, of which
31.74 s was the Python worker round trip. Activation to ready took 0.94 s;
within that, view setup through two animation frames took 0.48 s, including
0.009 s cloning, 0.043 s decoding and 0.240 s constructing the viewer. This
confirms that native geometry dominates on this machine's normal graphics path.

A separate forced-SwiftShader run took about 19 s to reach viewport readiness
and timed out capturing a screenshot. Its CPU-side decode/render construction
was still below 0.3 s. That software-rendering result is not used for the normal
desktop performance conclusion; it demonstrates why worker and viewport timings
need separate measurements.
