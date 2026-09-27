"""Desktop-only, revision-scoped native geometry cache.

Builders must depend on source, environment, variants and declared input files.
This deliberately invalidates the whole project when any tracked input changes;
it does not infer dependencies of arbitrary Python closures.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from hashlib import sha256
from importlib import metadata
from io import BytesIO
import json
import math
import os
from pathlib import Path
import platform
import stat
import sys
import tempfile
import time
from zipfile import BadZipFile, ZipFile, ZIP_STORED

import cadquery as cq
from .performance import measure

_active = ContextVar("cadkit_geometry_cache", default=None)
_FORMAT = 1
_IGNORED = {".git", ".cadkit", ".cache", ".venv", "venv", "node_modules", "__pycache__", "build", "dist"}
_INACTIVE = {"unavailable", "inputs_changed", "unsupported"}
_LAUNCH_ENV = {"DESKTOP_STARTUP_ID", "XDG_ACTIVATION_TOKEN", "GIO_LAUNCHED_DESKTOP_FILE_PID",
               "SYSTEMD_EXEC_PID", "INVOCATION_ID", "JOURNAL_STREAM", "XDG_SESSION_ID"}


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _digest(value):
    return sha256(_json(value)).hexdigest()


def cached_body(key, build):
    cache = _active.get()
    return build() if cache is None else cache.body(key, build)


def _runtime():
    # RECORD identifies wheel contents, including native libraries and data.
    # Editable source is additionally covered by the source inventory below.
    packages = sorted((d.metadata.get("Name", ""), d.version,
                       sha256((d.read_text("RECORD") or "").encode()).hexdigest())
                      for d in metadata.distributions())
    return _digest([sys.version, sys.executable, sys.prefix, platform.platform(), packages])


def _source_roots():
    prefixes = (Path(sys.prefix).resolve(), Path(sys.base_prefix).resolve())
    def local(path):
        return not any(path.is_relative_to(prefix) for prefix in prefixes)
    roots = {Path.cwd().resolve()}
    for entry in sys.path:
        path = Path(entry or os.curdir).resolve()
        if path.is_dir() and local(path):
            roots.add(path)
    for module in tuple(sys.modules.values()):
        filename = getattr(module, "__file__", None)
        if not filename or not filename.endswith(".py"):
            continue
        path = Path(filename).resolve()
        if not local(path):
            continue
        directory = path.parent
        while (directory.parent / "__init__.py").is_file():
            directory = directory.parent
        roots.add(directory)
    # Keep explicitly imported/search-path roots even inside ignored directories.
    # A parent inventory skips caches/venvs, but an actual external import still
    # needs tracking at its own package root.
    return sorted(str(p) for p in roots)


def _inventory(roots, dependencies, cache_root):
    """Content hashes, including missing paths and directory membership."""
    files = {}
    newest = 0
    def visit(path, sources=False):
        nonlocal newest
        # Retain the authored path as well as symlink targets in the fingerprint.
        path = Path(path).absolute()
        if path == cache_root or path.is_relative_to(cache_root):
            return
        if not path.exists():
            files[str(path)] = None
            return
        if path.is_dir():
            files[str(path)] = "directory:" + str(path.resolve())
            for directory, dirs, names in os.walk(path):
                dirs[:] = sorted(d for d in dirs if (not sources or d not in _IGNORED)
                                 and (not sources or not (Path(directory)/d/"pyvenv.cfg").is_file())
                                 and not (Path(directory)/d).is_relative_to(cache_root))
                for name in sorted(names):
                    if not sources or name.endswith(".py"):
                        visit(Path(directory)/name)
                # os.walk does not follow directory links. Record the target and
                # hash its contents separately, with a cycle guard.
                for name in tuple(dirs):
                    child = Path(directory)/name
                    if child.is_symlink():
                        dirs.remove(name)
                        target = child.resolve()
                        files[str(child)] = "link:" + str(target)
                        if str(target) not in files:
                            visit(target, sources)
            return
        before = path.stat()
        if not stat.S_ISREG(before.st_mode):
            raise ValueError("Cache inputs must be regular files")
        data = path.read_bytes()
        after = path.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise ValueError("Input changed while hashing")
        newest = max(newest, after.st_mtime_ns)
        files[str(path)] = [str(path.resolve()), sha256(data).hexdigest()]
    for root in roots:
        visit(root, sources=True)
    for dependency in dependencies:
        visit(dependency)
    return files, newest


class GeometryCache:
    """One worker's cache transaction. Only successful scenes are published."""
    def __init__(self, root, *, max_bytes=512 * 1024**2, roots=None, runtime=None):
        self.root = Path(root).resolve()
        self.max_bytes = max_bytes
        self.started_ns = time.time_ns()
        self.roots = _source_roots() if roots is None else [str(Path(p).absolute()) for p in roots]
        self.initial_roots = list(self.roots)
        self.runtime = _runtime() if runtime is None else runtime
        self.dependencies = []
        self.reader = None
        self.writer = None
        self.temporary = None
        self.records = {}
        self.previous = {}
        self.path = None
        self.stats = {"status": "cold", "hits": 0, "misses": 0, "writes": 0,
                      "uncacheable": 0, "corruptions": 0, "bytes_read": 0, "bytes_written": 0}
        try:
            self.initial, _ = _inventory(self.roots, [], self.root)
        except Exception:
            self.initial = {}
            self.stats["status"] = "unavailable"

    @classmethod
    def for_worker(cls):
        if os.environ.get("CADKIT_GEOMETRY_CACHE", "1") == "0":
            return None
        directory = os.environ.get("CADKIT_GEOMETRY_CACHE_DIR")
        if not directory:
            if sys.platform == "darwin":
                base = Path.home()/"Library"/"Caches"
            elif sys.platform == "win32":
                base = Path(os.environ.get("LOCALAPPDATA", Path.home()/"AppData"/"Local"))
            else:
                base = Path(os.environ.get("XDG_CACHE_HOME", Path.home()/".cache"))
            directory = base/"cadkit"/"geometry"
        try:
            budget = int(os.environ.get("CADKIT_GEOMETRY_CACHE_MAX_MB", "512"))
            if budget <= 0:
                return None
            return cls(directory, max_bytes=budget * 1024**2)
        except Exception:
            return None

    def prepare(self, reference, project):
        from .design.assembly import Project
        if type(project) is not Project:
            self.stats["status"] = "unsupported"
        if self.stats["status"] in _INACTIVE:
            return
        try:
            # Enforce a reduced budget even if this build cannot fit in it.
            self._prune()
            description = project.describe()
            self.dependencies = [str(Path(p).absolute()) for p in description.get("dependencies", ())]
            self.roots = sorted(set(self.roots + _source_roots()))
            context = [str(Path.cwd().resolve()), reference, description,
                       self.runtime, _digest({k: v for k, v in os.environ.items() if k not in _LAUNCH_ENV}), _FORMAT]
            self.path = self.root/(_digest(context) + ".zip")
            if self.path.exists():
                try:
                    self.reader = ZipFile(self.path)
                    if self.reader.getinfo("manifest.json").file_size > 8 * 1024**2:
                        raise ValueError("Oversized cache manifest")
                    manifest = json.loads(self.reader.read("manifest.json"))
                    if (manifest["format"] != _FORMAT or not isinstance(manifest["bodies"], dict)
                            or not isinstance(manifest["inputs"], dict)
                            or not isinstance(manifest["roots"], list)
                            or any(not isinstance(p, str) or not Path(p).is_absolute() for p in manifest["roots"])):
                        raise ValueError("Cache format changed")
                    self.roots = sorted(set(self.roots + manifest["roots"]))
                    self.previous = manifest["bodies"]
                except (OSError, ValueError, KeyError, TypeError, BadZipFile):
                    self.stats["corruptions"] += 1
                    manifest = None
            else:
                manifest = None
            initial_now, _ = _inventory(self.initial_roots, [], self.root)
            self.inputs, newest = _inventory(self.roots, self.dependencies, self.root)
            # Sources already imported at prepare time must describe the same
            # input revision observed before project import.
            if initial_now != self.initial or newest > self.started_ns:
                self.stats["status"] = "inputs_changed"
                self.previous = {}
                return
            if manifest is None or manifest["inputs"] != self.inputs:
                self.previous = {}
            if self.previous:
                os.utime(self.path, None)
        except Exception:
            self.stats["status"] = "unavailable"
            self.previous = {}

    @contextmanager
    def collect(self):
        token = _active.set(self)
        try:
            yield
        finally:
            _active.reset(token)

    def watched_paths(self):
        # Lazy imports need watching even when a hit skips their builders.
        return sorted(set(self.dependencies + [p for p, v in getattr(self, "inputs", {}).items()
                                               if isinstance(v, list) and p.endswith(".py")]))

    def body(self, key, build):
        if self.stats["status"] in _INACTIVE or self.path is None:
            return build()
        record = self.previous.get(key)
        model = None
        if record is not None:
            try:
                with measure("cache_read", key):
                    filename = sha256(key.encode()).hexdigest() + ".brep"
                    info = self.reader.getinfo(filename)
                    if info.file_size != record["bytes"] or info.file_size > self.max_bytes:
                        raise ValueError("Invalid cached body size")
                    data = self.reader.read(filename)
                    if sha256(data).hexdigest() != record["sha256"]:
                        raise ValueError("Cached body checksum changed")
                    model = cq.Shape.importBrep(BytesIO(data))
                    volume = model.Volume()
                    if (not model.isValid() or record["solids"] < 1 or len(model.Solids()) != record["solids"]
                            or not math.isfinite(volume)
                            or not math.isclose(volume, record["volume"], rel_tol=1e-10, abs_tol=1e-6)):
                        raise ValueError("Invalid cached native solid")
                self.stats["hits"] += 1
                self.stats["bytes_read"] += len(data)
                self.records[key] = record
                return model
            except Exception:
                # Importing damaged native data can raise several OCP exception
                # types. Cache failures must not replace the real builder error.
                self.stats["corruptions"] += 1
                model = None
        if model is None:
            self.stats["misses"] += 1
            model = build()
        self._store(key, model)
        return model

    def _store(self, key, model):
        if not isinstance(model, cq.Shape):
            self.stats["uncacheable"] += 1
            return
        try:
            with measure("cache_write", key):
                data = BytesIO()
                if not model.exportBrep(data):
                    raise ValueError("Native export failed")
                data = data.getvalue()
                if self.stats["bytes_written"] + len(data) > self.max_bytes:
                    self.stats["status"] = "unavailable"
                    return
                if self.writer is None:
                    self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
                    fd, self.temporary = tempfile.mkstemp(prefix=".pending-", suffix=".zip", dir=self.root)
                    os.close(fd)
                    self.writer = ZipFile(self.temporary, "w", compression=ZIP_STORED)
                filename = sha256(key.encode()).hexdigest() + ".brep"
                self.writer.writestr(filename, data)
                self.records[key] = {"bytes": len(data), "sha256": sha256(data).hexdigest(),
                                     "volume": model.Volume(), "solids": len(model.Solids())}
                self.stats["writes"] += 1
                self.stats["bytes_written"] += len(data)
        except Exception:
            self.stats["status"] = "unavailable"

    def finish(self):
        try:
            if self.stats["status"] in _INACTIVE or self.path is None:
                return
            with measure("cache_commit"):
                current, _ = _inventory(self.roots, self.dependencies, self.root)
                roots = sorted(set(self.roots + _source_roots()))
                inputs, newest = _inventory(roots, self.dependencies, self.root)
                if current != self.inputs or newest > self.started_ns:
                    self.stats["status"] = "inputs_changed"
                    return
                self.roots, self.inputs = roots, inputs
                if self.writer is not None:
                    # A partial miss repairs the archive atomically. Reuse bytes
                    # already validated from hits, without exporting solids again.
                    written = set(self.writer.namelist())
                    for key, record in self.records.items():
                        filename = sha256(key.encode()).hexdigest() + ".brep"
                        if filename not in written:
                            data = self.reader.read(filename)
                            if sha256(data).hexdigest() != record["sha256"]:
                                raise ValueError("Cache changed during repair")
                            self.writer.writestr(filename, data)
                    manifest = {"format": _FORMAT, "roots": roots, "inputs": inputs, "bodies": self.records}
                    self.writer.writestr("manifest.json", _json(manifest))
                    self.writer.close()
                    self.writer = None
                    if self.reader is not None:
                        self.reader.close()
                        self.reader = None
                    if Path(self.temporary).stat().st_size > self.max_bytes:
                        self.stats["status"] = "unavailable"
                        return
                    os.replace(self.temporary, self.path)
                    self.temporary = None
                self._prune()
                self.stats["status"] = "warm" if self.stats["hits"] and not self.stats["misses"] else (
                    "partial" if self.stats["hits"] else "cold")
        except Exception:
            self.stats["status"] = "unavailable"
        finally:
            self.close()

    def _prune(self):
        files = []
        for path in self.root.glob("*.zip"):
            try:
                stat = path.stat()
                if path.name.startswith(".pending-"):
                    if time.time() - stat.st_mtime > 86400:
                        path.unlink(missing_ok=True)
                    else:
                        # Cancelled workers can leave recent staging files.
                        # Count these against the budget too. Evicting a live
                        # staging file only makes that writer skip publication.
                        files.append((stat.st_mtime_ns, stat.st_size, path))
                    continue
                if len(path.stem) == 64 and all(c in "0123456789abcdef" for c in path.stem):
                    files.append((stat.st_mtime_ns, stat.st_size, path))
            except OSError:
                continue
        total = sum(size for _, size, _ in files)
        for _, size, path in sorted(files):
            if total <= self.max_bytes:
                break
            try:
                path.unlink(missing_ok=True)
                total -= size
            except OSError:
                continue

    def close(self):
        for archive in (self.reader, self.writer):
            if archive is not None:
                try:
                    archive.close()
                except (OSError, ValueError):
                    pass
        self.reader = self.writer = None
        if self.temporary is not None:
            try:
                Path(self.temporary).unlink(missing_ok=True)
            except OSError:
                pass
            self.temporary = None
