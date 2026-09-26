// Whole-build cache. Each entry owns native geometry as well as its scene.
// Source generations and UI activations are deliberately independent.
export class BuildCache {
  constructor({ create, activate, busy, failed, capacity = 3 }) {
    Object.assign(this, { create, activate, busy, failed, capacity });
    this.generation = 0;
    this.request = 0;
    this.entries = new Map();
    this.jobs = new Map();
    this.workers = new Set();
    this.queue = Promise.resolve();
    this.closed = false;
    this.warmAttempts = new Set();
  }
  key(selection) {
    return JSON.stringify(
      Object.entries(selection).sort(([a], [b]) => a.localeCompare(b)),
    );
  }
  invalidate() {
    this.generation++;
    this.request++;
    this.entries.clear();
    for (const worker of this.workers) {
      if (worker === this.active?.worker) continue;
      if (worker.built) worker.retire();
      else worker.close();
    }
    this.jobs.clear();
    this.warmAttempts.clear();
  }
  async warm(selection) {
    const key = this.key(selection);
    if (
      this.closed ||
      this.entries.has(key) ||
      this.jobs.has(key) ||
      this.warmAttempts.has(key) ||
      this.entries.size >= this.capacity
    )
      return;
    this.warmAttempts.add(key);
    const generation = this.generation,
      request = this.request;
    const job = this.queue
      .catch(() => {})
      .then(async () => {
        if (
          this.closed ||
          generation !== this.generation ||
          (request !== this.request && this.wanted !== key) ||
          (this.entries.size >= this.capacity && request === this.request)
        )
          return;
        const worker = this.create(selection, { background: true });
        this.workers.add(worker);
        const pending = { key, worker };
        this.background = pending;
        try {
          const scene = await worker.call("scene");
          if (this.closed || generation !== this.generation || worker.closed)
            throw new Error("Build superseded");
          worker.built = true;
          const entry = { worker, scene, selection };
          this.entries.set(
            this.key(scene.project?.variant_selection ?? selection),
            entry,
          );
          return entry;
        } catch (error) {
          worker.retire();
          throw error;
        } finally {
          if (this.background === pending) this.background = undefined;
        }
      });
    this.jobs.set(key, job);
    this.queue = job;
    try {
      await job;
    } catch {
      /* Speculation must never change the visible build status. */
    } finally {
      if (this.jobs.get(key) === job) this.jobs.delete(key);
      for (const worker of this.workers)
        if (worker.closed) this.workers.delete(worker);
    }
  }
  prewarm() {
    if (this.warming) return this.warming;
    const task = this.prewarmChoices();
    this.warming = task;
    const done = () => {
      if (this.warming === task) this.warming = undefined;
    };
    task.then(done, done);
    return task;
  }
  async prewarmChoices() {
    const entry = this.active,
      request = this.request;
    if (!entry) return;
    const selected = entry.scene.project?.variant_selection ?? entry.selection;
    let attempts = 0;
    for (const [key, choice] of Object.entries(
      entry.scene.project?.variants ?? {},
    )) {
      for (const option of choice.options) {
        if (
          request !== this.request ||
          this.closed ||
          this.entries.size >= this.capacity
        )
          return;
        const candidate = { ...selected, [key]: option };
        const candidateKey = this.key(candidate);
        if (
          this.entries.has(candidateKey) ||
          this.warmAttempts.has(candidateKey)
        )
          continue;
        if (++attempts >= this.capacity) return;
        await this.warm(candidate);
      }
    }
  }
  async select(selection) {
    if (this.closed) throw new Error("Project session changed");
    const generation = this.generation;
    const request = ++this.request;
    const key = this.key(selection);
    // Foreground work wins. Reuse the requested speculative build; cancel any
    // other one so a slow alternative cannot delay an explicit selection.
    if (this.background && this.background.key !== key) {
      this.background.worker.close();
      this.jobs.delete(this.background.key);
    }
    this.wanted = key;
    const current = () =>
      !this.closed &&
      generation === this.generation &&
      request === this.request;
    let entry = this.entries.get(key);
    const cached = Boolean(entry && !entry.worker.closed);
    if (entry?.worker.closed) {
      this.entries.delete(key);
      entry = undefined;
    }
    this.busy(selection, cached);
    try {
      if (!entry) {
        let job = this.jobs.get(key);
        if (!job) {
          job = this.queue
            .catch(() => {})
            .then(async () => {
              if (
                this.closed ||
                generation !== this.generation ||
                this.wanted !== key
              )
                throw new Error("Build superseded");
              const worker = this.create(selection, { background: false });
              this.workers.add(worker);
              try {
                const scene = await worker.call("scene");
                if (this.closed || generation !== this.generation)
                  throw new Error("Build superseded");
                worker.built = true;
                const built = { worker, scene, selection };
                this.entries.set(
                  this.key(scene.project?.variant_selection ?? selection),
                  built,
                );
                return built;
              } catch (error) {
                worker.retire();
                throw error;
              }
            });
          this.jobs.set(key, job);
          this.queue = job;
          // Register both handlers to avoid a detached rejected finally promise.
          const remove = () => {
            if (this.jobs.get(key) === job) this.jobs.delete(key);
          };
          job.then(remove, remove);
        }
        entry = await job;
      }
      if (!current()) throw new Error("Build superseded");
      const previous = this.active;
      this.active = entry;
      const resolvedKey = this.key(
        entry.scene.project?.variant_selection ?? selection,
      );
      this.entries.delete(resolvedKey);
      this.entries.set(resolvedKey, entry);
      if (previous && ![...this.entries.values()].includes(previous))
        previous.worker.retire();
      return await this.activate(entry, cached);
    } catch (error) {
      if (current()) this.failed(error);
      throw error;
    } finally {
      for (const [oldKey, old] of this.entries) {
        if (this.entries.size <= this.capacity) break;
        if (old === this.active) continue;
        this.entries.delete(oldKey);
        old.worker.retire();
      }
      for (const worker of this.workers)
        if (worker.closed) this.workers.delete(worker);
    }
  }
  close() {
    this.closed = true;
    this.request++;
    for (const worker of this.workers) worker.close();
    this.workers.clear();
    this.entries.clear();
  }
}
