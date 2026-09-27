"""Persistent native caching must fail open and never accept stale geometry."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from zipfile import ZipFile, ZIP_STORED

import cadquery as cq
import pytest
import cadkit as ck
from cadkit.desktop import Session
from cadkit.geometry_cache import GeometryCache, _inventory


def project(builder=None, *, selection=None, dependencies=()):
    builder = builder or (lambda: cq.Solid.makeBox(2, 3, 4))
    assembly = ck.Assembly('fixture')
    part = ck.Part('block', builder, ck.FDM('PETG'))
    assembly.fix(assembly.add('left', part))
    assembly.fix(assembly.add('right', part), at=ck.Frame((10, 0, 0)))
    result = assembly.as_project()
    if selection is not None or dependencies:
        from types import SimpleNamespace
        result._variants = SimpleNamespace(dependencies=dependencies, describe=lambda _: {})
        result.variant_selection = selection or {}
    return result


@pytest.fixture
def inputs(tmp_path, monkeypatch):
    source = tmp_path/'source'
    source.mkdir()
    (source/'project.py').write_text('# fixture\n')
    monkeypatch.chdir(source)
    monkeypatch.setattr('cadkit.geometry_cache._source_roots', lambda: [str(source)])
    return source, tmp_path/'cache'


def run(inputs, model=None, *, runtime='runtime-1', max_bytes=1024**2):
    source, root = inputs
    cache = GeometryCache(root, roots=[source], runtime=runtime, max_bytes=max_bytes)
    model = project() if model is None else model
    cache.prepare('project:PROJECT', model)
    session = Session(model, geometry_cache=cache)
    scene = session.scene_for_transport()
    return cache, scene, session


def test_fresh_cache_reuses_native_bodies_and_retains_placement(inputs):
    calls = []
    def build():
        calls.append(1)
        return cq.Solid.makeBox(2, 3, 4)
    model = project(build)
    first, old, _ = run(inputs, model)
    assert first.stats['misses'] == first.stats['writes'] == 1
    second, new, session = run(inputs, model)
    assert calls == [1]
    assert second.stats['status'] == 'warm'
    assert second.stats['hits'] == 1 and second.stats['writes'] == 0
    for before, after in zip(old['components'], new['components']):
        assert {k:v for k,v in before.items() if k not in {'bounds', 'size', 'volume_mm3'}} == {
            k:v for k,v in after.items() if k not in {'bounds', 'size', 'volume_mm3'}}
        assert before['size'] == pytest.approx(after['size'], abs=1e-6)
        assert before['volume_mm3'] == pytest.approx(after['volume_mm3'])
        for lohi_before, lohi_after in zip(before['bounds'], after['bounds']):
            assert lohi_before == pytest.approx(lohi_after, abs=1e-6)
    left, right = session.models.values()
    assert left.Volume() == right.Volume() == pytest.approx(24)
    assert right.BoundingBox().xmin == pytest.approx(10)
    assert left.isValid() and right.isValid()
    assert new['revision'] != old['revision']
    assert second.stats['bytes_read'] > 0
    assert new['performance']['stages_seconds']['cache_read'] > 0
    assert len(list(inputs[1].glob('*.zip'))) == 1


@pytest.mark.parametrize('change', ['edit', 'add', 'delete', 'environment', 'runtime', 'variant', 'dependency'])
def test_inputs_invalidate_cache_by_content(inputs, monkeypatch, change):
    source, _ = inputs
    helper = source/'helper.py'
    helper.write_text('value = 1\n')
    dependency = source/'dimensions.json'
    dependency.write_text('{"diameter": 1}')
    model = project(selection={'base':'a'}, dependencies=[str(dependency)])
    run(inputs, model)
    runtime = 'runtime-1'
    if change == 'edit':
        stamp = helper.stat()
        helper.write_text('value = 2\n')
        os.utime(helper, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
    elif change == 'add':
        (source/'new_module.py').write_text('# new import candidate\n')
    elif change == 'delete':
        helper.unlink()
    elif change == 'environment':
        monkeypatch.setenv('CADKIT_TEST_DIMENSION', '20')
    elif change == 'runtime':
        runtime = 'runtime-2'
    elif change == 'variant':
        model = project(selection={'base':'b'}, dependencies=[str(dependency)])
    else:
        dependency.write_text('{"diameter": 2}')
    cache, _, _ = run(inputs, model, runtime=runtime)
    assert cache.stats['hits'] == 0
    assert cache.stats['misses'] == 1


def rewrite_archive(path, transform):
    with ZipFile(path) as archive:
        entries = {name:archive.read(name) for name in archive.namelist()}
    transform(entries)
    with ZipFile(path, 'w', compression=ZIP_STORED) as archive:
        for name, data in entries.items():
            archive.writestr(name, data)


@pytest.mark.parametrize('damage', ['zip', 'manifest', 'body', 'invalid_brep'])
def test_corrupt_cache_rebuilds_and_repairs(inputs, damage):
    first, _, _ = run(inputs)
    if damage == 'zip':
        first.path.write_bytes(b'not a zip')
    else:
        def corrupt(entries):
            if damage == 'manifest':
                entries['manifest.json'] = b'[]'
                return
            filename = next(n for n in entries if n.endswith('.brep'))
            entries[filename] = b'not a native shape'
            if damage == 'invalid_brep':
                manifest = json.loads(entries['manifest.json'])
                record = next(iter(manifest['bodies'].values()))
                record['bytes'] = len(entries[filename])
                record['sha256'] = hashlib.sha256(entries[filename]).hexdigest()
                entries['manifest.json'] = json.dumps(manifest).encode()
        rewrite_archive(first.path, corrupt)
    second, _, session = run(inputs)
    assert second.stats['hits'] == 0
    assert second.stats['misses'] == second.stats['corruptions'] == 1
    assert next(iter(session.models.values())).Volume() == pytest.approx(24)
    third, _, _ = run(inputs)
    assert third.stats['hits'] == 1


def test_failure_does_not_publish_partial_build_or_leak_cache_context(inputs):
    source, root = inputs
    assembly = ck.Assembly('broken')
    calls = []
    def good():
        calls.append(1)
        return cq.Solid.makeBox(1, 1, 1)
    def bad():
        raise ValueError('builder failed')
    a = ck.Part('good', good, ck.FDM('PETG'))
    assembly.fix(assembly.add(a))
    assembly.fix(assembly.add(ck.Part('bad', bad, ck.FDM('PETG'))))
    model = assembly.as_project()
    cache = GeometryCache(root, roots=[source], runtime='test')
    cache.prepare('project:PROJECT', model)
    with pytest.raises(ValueError, match='builder failed'):
        Session(model, geometry_cache=cache).scene()
    assert not list(root.glob('*.zip'))
    a.build()
    assert calls == [1, 1]


def test_changing_inputs_during_build_prevents_publication(inputs):
    source, root = inputs
    def build():
        (source/'project.py').write_text('# changed during build\n')
        return cq.Solid.makeBox(2, 3, 4)
    cache, _, _ = run(inputs, project(build))
    assert cache.stats['status'] == 'inputs_changed'
    assert not list(root.glob('*.zip'))


def test_unwritable_cache_and_small_budget_do_not_break_geometry(inputs):
    source, root = inputs
    root.write_text('a file cannot be a cache directory')
    cache, _, session = run(inputs)
    assert cache.stats['status'] == 'unavailable'
    assert next(iter(session.models.values())).Volume() == pytest.approx(24)
    root.unlink()
    cache, _, _ = run(inputs, max_bytes=1)
    assert cache.stats['status'] == 'unavailable'
    assert not list(root.glob('*.zip'))


def test_lru_budget_evicts_older_revisions(inputs, monkeypatch):
    first, _, _ = run(inputs)
    size = first.path.stat().st_size
    monkeypatch.setenv('CADKIT_TEST_REVISION', 'second')
    second, _, _ = run(inputs, max_bytes=int(size * 1.5))
    assert second.path.exists()
    assert not first.path.exists()
    assert sum(p.stat().st_size for p in inputs[1].glob('*.zip')) <= int(size * 1.5)


def test_dependency_directory_tracks_non_python_files_and_missing_inputs(inputs):
    source, root = inputs
    data = source/'data'
    data.mkdir()
    (data/'dimensions.txt').write_text('1')
    missing = source/'missing.json'
    first, _ = _inventory([source], [data, missing], root)
    (data/'dimensions.txt').write_text('2')
    second, _ = _inventory([source], [data, missing], root)
    assert first != second
    missing.write_text('{}')
    third, _ = _inventory([source], [data, missing], root)
    assert second != third


def test_native_cache_works_across_fresh_worker_processes(tmp_path):
    source = tmp_path/'project'
    source.mkdir()
    (source/'project.py').write_text('''
import cadquery as cq
import cadkit as ck
from pathlib import Path

def body():
    with Path('calls.txt').open('a') as log:
        log.write('built\\n')
    return cq.Solid.makeBox(2, 3, 4)
a = ck.Assembly('fixture')
a.fix(a.add(ck.Part('part', body, ck.FDM('PETG'))))
PROJECT = a.as_project()
''')
    env = {**os.environ, 'PYTHONPATH':str(Path(ck.__file__).parents[1]),
           'PYTHONDONTWRITEBYTECODE':'1', 'CADKIT_GEOMETRY_CACHE':'1',
           'CADKIT_GEOMETRY_CACHE_DIR':str(tmp_path/'cache')}
    scenes = []
    for _ in range(2):
        p = subprocess.run([sys.executable, '-m', 'cadkit.desktop', '--project', 'project:PROJECT'],
                           cwd=source, env=env, text=True, input='{"id":1,"method":"scene"}\n',
                           capture_output=True, timeout=30)
        assert p.returncode == 0, p.stderr
        result = next(json.loads(line) for line in p.stdout.splitlines() if json.loads(line).get('id') == 1)
        assert 'error' not in result, p.stderr
        scenes.append(result['result'])
    assert (source/'calls.txt').read_text() == 'built\n'
    assert scenes[0]['performance']['geometry_cache']['misses'] == 1
    assert scenes[1]['performance']['geometry_cache']['hits'] == 1
    assert scenes[0]['components'] == scenes[1]['components']


def test_partial_cache_repairs_only_damaged_body(inputs):
    assembly = ck.Assembly('two')
    calls = []
    def body(size):
        calls.append(size)
        return cq.Solid.makeBox(size, 2, 3)
    for index in (1, 2):
        assembly.fix(assembly.add(ck.Part(f'part{index}', lambda n=index: body(n), ck.FDM('PETG'))))
    model = assembly.as_project()
    first, _, _ = run(inputs, model)
    def corrupt(entries):
        filename = next(n for n in entries if n.endswith('.brep'))
        entries[filename] = b'corrupt'
    rewrite_archive(first.path, corrupt)
    second, _, _ = run(inputs, model)
    assert second.stats['status'] == 'partial'
    assert second.stats['hits'] == second.stats['misses'] == second.stats['writes'] == 1
    assert len(calls) == 3
    third, _, _ = run(inputs, model)
    assert third.stats['hits'] == 2
    assert len(calls) == 3


def test_input_edit_between_cache_start_and_project_import_is_not_cached(inputs):
    source, root = inputs
    cache = GeometryCache(root, roots=[source], runtime='test')
    (source/'project.py').write_text('# changed during project import\n')
    model = project()
    cache.prepare('project:PROJECT', model)
    Session(model, geometry_cache=cache).scene()
    assert cache.stats['status'] == 'inputs_changed'
    assert not list(root.glob('*.zip'))


def test_late_import_remains_an_input_when_cached_builder_is_skipped(tmp_path):
    source = tmp_path/'project'
    source.mkdir()
    external = tmp_path/'external'
    external.mkdir()
    helper = external/'dimensions.py'
    helper.write_text('WIDTH = 2\n')
    (source/'project.py').write_text(f'''
import cadquery as cq
import cadkit as ck
import sys

def body():
    sys.path.insert(0, {str(external)!r})
    import dimensions
    return cq.Solid.makeBox(dimensions.WIDTH, 3, 4)
a = ck.Assembly('fixture')
a.fix(a.add(ck.Part('part', body, ck.FDM('PETG'))))
PROJECT = a.as_project()
''')
    env = {**os.environ, 'PYTHONPATH':str(Path(ck.__file__).parents[1]),
           'PYTHONDONTWRITEBYTECODE':'1', 'CADKIT_GEOMETRY_CACHE':'1',
           'CADKIT_GEOMETRY_CACHE_DIR':str(tmp_path/'cache')}
    scenes = []
    for index in range(3):
        if index == 2:
            helper.write_text('WIDTH = 4\n')
        p = subprocess.run([sys.executable, '-m', 'cadkit.desktop', '--project', 'project:PROJECT'],
                           cwd=source, env=env, text=True, input='{"id":1,"method":"scene"}\n',
                           capture_output=True, timeout=30)
        assert p.returncode == 0, p.stderr
        messages = [json.loads(line) for line in p.stdout.splitlines()]
        result = next(m for m in messages if m.get('id') == 1)
        assert 'error' not in result, p.stderr
        scenes.append(result['result'])
        emitted = [m for m in messages if m.get('event') == 'inputs'][-1]
        assert str(helper) in emitted['paths']
        assert str(external) in emitted['source_roots']
    assert [s['performance']['geometry_cache']['hits'] for s in scenes] == [0, 1, 0]
    assert [s['components'][0]['volume_mm3'] for s in scenes] == pytest.approx([24, 24, 48])


def test_source_inventory_skips_archived_environments_but_tracks_explicit_import_roots(inputs):
    source, root = inputs
    environment = source/'.venv-old'
    environment.mkdir()
    (environment/'pyvenv.cfg').write_text('home = /somewhere\n')
    library = environment/'library'
    library.mkdir()
    hidden = library/'geometry.py'
    hidden.write_text('dimension = 1\n')
    cache_dir = source/'.cache'/'downloads'
    cache_dir.mkdir(parents=True)
    cached = cache_dir/'unrelated.py'
    cached.write_text('# not project source\n')
    ordinary, _ = _inventory([source], [], root)
    assert str(hidden) not in ordinary and str(cached) not in ordinary
    explicit, _ = _inventory([source, library], [], root)
    assert str(hidden) in explicit


def test_concurrent_writers_publish_complete_archives(inputs):
    source, root = inputs
    model = project()
    caches = [GeometryCache(root, roots=[source], runtime='runtime-1') for _ in range(2)]
    for cache in caches:
        cache.prepare('project:PROJECT', model)
        with cache.collect():
            model.get_assembly()
    assert len(list(root.glob('.pending-*'))) == 2
    for cache in caches:
        cache.finish()
    assert len(list(root.glob('*.zip'))) == 1
    warm, _, _ = run(inputs, model)
    assert warm.stats['hits'] == 1


def test_new_backdated_source_during_build_prevents_publication(inputs):
    source, root = inputs
    def build():
        path = source/'shadow.py'
        path.write_text('# new import candidate\n')
        os.utime(path, (1, 1))
        return cq.Solid.makeBox(2, 3, 4)
    cache, _, _ = run(inputs, project(build))
    assert cache.stats['status'] == 'inputs_changed'
    assert not list(root.glob('*.zip'))


def test_reduced_budget_evicts_existing_archives_even_when_new_body_cannot_fit(inputs):
    first, _, _ = run(inputs)
    assert first.path.exists()
    second, _, session = run(inputs, max_bytes=1)
    assert not first.path.exists()
    assert second.stats['status'] == 'unavailable'
    assert next(iter(session.models.values())).Volume() == pytest.approx(24)


def test_recent_abandoned_staging_files_count_toward_disk_budget(inputs):
    _, root = inputs
    root.mkdir()
    abandoned = root/'.pending-abandoned.zip'
    abandoned.write_bytes(b'x' * 20_000)
    cache, _, _ = run(inputs, max_bytes=10_000)
    assert not abandoned.exists()
    assert cache.stats['writes'] == 1
    assert cache.path.exists()
    assert sum(p.stat().st_size for p in root.glob('*.zip')) <= 10_000


def test_desktop_launch_tokens_do_not_invalidate_geometry(inputs, monkeypatch):
    monkeypatch.setenv('DESKTOP_STARTUP_ID', 'first-launch')
    monkeypatch.setenv('GIO_LAUNCHED_DESKTOP_FILE_PID', '123')
    run(inputs)
    monkeypatch.setenv('DESKTOP_STARTUP_ID', 'second-launch')
    monkeypatch.setenv('GIO_LAUNCHED_DESKTOP_FILE_PID', '456')
    cached, _, _ = run(inputs)
    assert cached.stats['hits'] == 1
