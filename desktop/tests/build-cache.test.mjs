import test from "node:test";
import assert from "node:assert/strict";
import { BuildCache } from "../electron/build-cache.mjs";
const deferred = () => {
  let resolve, reject;
  const promise = new Promise((a, b) => {
    resolve = a;
    reject = b;
  });
  return { promise, resolve, reject };
};
function fixture(capacity = 3) {
  const workers = [],
    shown = [],
    errors = [];
  const cache = new BuildCache({
    capacity,
    create(selection) {
      const result = deferred();
      const worker = {
        selection,
        result,
        closed: false,
        call: () => result.promise,
        retire() {
          this.closed = true;
        },
        close() {
          this.closed = true;
          result.reject(new Error("stopped"));
        },
      };
      workers.push(worker);
      return worker;
    },
    activate: (entry, cached) => {
      shown.push(entry);
      return { entry, cached };
    },
    busy() {},
    failed(e) {
      errors.push(e.message);
    },
  });
  const tick = () => new Promise((resolve) => setImmediate(resolve));
  const finish = (index, selection = workers[index].selection) =>
    workers[index].result.resolve({
      project: { variant_selection: selection },
    });
  return { cache, workers, shown, errors, tick, finish };
}
test("A/B/A restores worker and canonical defaults; eviction is bounded", async () => {
  const f = fixture(2);
  let task = f.cache.select({});
  await f.tick();
  f.finish(0, { base: "a" });
  await task;
  task = f.cache.select({ base: "b" });
  await f.tick();
  f.finish(1);
  await task;
  const restored = await f.cache.select({ base: "a" });
  assert.equal(restored.cached, true);
  assert.equal(restored.entry.worker, f.workers[0]);
  task = f.cache.select({ base: "c" });
  await f.tick();
  f.finish(2);
  await task;
  assert.equal(f.workers[1].closed, true);
  assert.equal(f.workers[0].closed, false);
  f.cache.close();
  assert.ok(f.workers.every((w) => w.closed));
});
test("late builds never replace the latest selection, but remain reusable", async () => {
  const f = fixture();
  let a = f.cache.select({ base: "a" });
  await f.tick();
  f.finish(0);
  await a;
  const b = f.cache.select({ base: "b" });
  const rejected = assert.rejects(b, /superseded/);
  await f.tick();
  await f.cache.select({ base: "a" });
  f.finish(1);
  await rejected;
  assert.equal(f.shown.at(-1).worker, f.workers[0]);
  assert.equal((await f.cache.select({ base: "b" })).cached, true);
});
test("source invalidation cancels builds, retains last good view, and rebuilds", async () => {
  const f = fixture();
  let a = f.cache.select({ base: "a" });
  await f.tick();
  f.finish(0);
  await a;
  const b = f.cache.select({ base: "b" });
  const rejected = assert.rejects(b, /stopped|superseded/);
  await f.tick();
  f.cache.invalidate();
  await rejected;
  assert.equal(f.workers[0].closed, false);
  assert.equal(f.workers[1].closed, true);
  a = f.cache.select({ base: "a" });
  await f.tick();
  f.finish(2);
  assert.equal((await a).cached, false);
  assert.equal(f.workers[0].closed, true);
});
test("failed alternative preserves active geometry and is retried", async () => {
  const f = fixture();
  let a = f.cache.select({ base: "a" });
  await f.tick();
  f.finish(0);
  await a;
  const b = f.cache.select({ base: "b" });
  const failed = assert.rejects(b, /bad/);
  await f.tick();
  f.workers[1].result.reject(new Error("bad"));
  await failed;
  assert.equal(f.cache.active.worker, f.workers[0]);
  assert.equal(f.workers[0].closed, false);
  const retry = f.cache.select({ base: "b" });
  await f.tick();
  f.finish(2);
  assert.equal((await retry).cached, false);
});

test("warming stays silent and reuses the worker without activation", async () => {
  const f = fixture();
  const a = f.cache.select({ base: "a" });
  await f.tick();
  f.finish(0);
  await a;
  const revision = f.cache.request;
  const warm = f.cache.warm({ base: "b" });
  await f.tick();
  f.finish(1);
  await warm;
  assert.equal(f.cache.request, revision);
  assert.equal(f.shown.length, 1);
  assert.equal((await f.cache.select({ base: "b" })).cached, true);
  assert.equal(f.workers.length, 2);
});
test("foreground selection promotes an in-flight or queued warm build", async () => {
  for (const queued of [true, false]) {
    const f = fixture();
    const warm = f.cache.warm({ base: "b" });
    if (!queued) await f.tick();
    const selected = f.cache.select({ base: "b" });
    await f.tick();
    f.finish(0);
    await Promise.all([warm, selected]);
    assert.equal(f.workers.length, 1);
    assert.equal(f.shown.length, 1);
    f.cache.close();
  }
});
test("foreground preempts another warm build; speculative failures are silent", async () => {
  const f = fixture();
  const warm = f.cache.warm({ base: "b" });
  await f.tick();
  const a = f.cache.select({ base: "a" });
  await f.tick();
  f.finish(1);
  await Promise.all([warm, a]);
  assert.equal(f.workers[0].closed, true);
  assert.deepEqual(f.errors, []);
  const failed = f.cache.warm({ base: "broken" });
  await f.tick();
  f.workers[2].result.reject(new Error("bad alternative"));
  await failed;
  assert.deepEqual(f.errors, []);
  assert.equal(f.shown.at(-1).worker, f.workers[1]);
});
test("source invalidation cancels warming and speculative entries never evict history", async () => {
  const f = fixture(2);
  const a = f.cache.select({ base: "a" });
  await f.tick();
  f.finish(0);
  await a;
  const warm = f.cache.warm({ base: "b" });
  await f.tick();
  f.cache.invalidate();
  await warm;
  assert.equal(f.workers[1].closed, true);
  assert.equal(f.cache.entries.size, 0);
  const b = f.cache.select({ base: "b" });
  await f.tick();
  f.finish(2);
  await b;
  const c = f.cache.warm({ base: "c" });
  await f.tick();
  f.finish(3);
  await c;
  await f.cache.warm({ base: "d" });
  assert.equal(f.workers.length, 4);
  f.cache.close();
});

test("a promoted queued warm build can replace a full cache", async () => {
  const f = fixture(2);
  const a = f.cache.select({ base: "a" });
  await f.tick();
  f.finish(0);
  await a;
  const c = f.cache.select({ base: "c" });
  const superseded = assert.rejects(c, /superseded/);
  await f.tick();
  const warm = f.cache.warm({ base: "b" });
  const b = f.cache.select({ base: "b" });
  f.finish(1);
  await f.tick();
  f.finish(2);
  await Promise.all([warm, b, superseded]);
  assert.equal(f.cache.active.worker, f.workers[2]);
  assert.equal(f.cache.entries.size, 2);
  f.cache.close();
});
