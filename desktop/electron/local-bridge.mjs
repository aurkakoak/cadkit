// Private, authenticated local IPC. The MCP stdio process attaches to this
// already-running app; it never launches another CAD session or exposes HTTP.
import net from "node:net";
import os from "node:os";
import path from "node:path";
import { createHash, randomBytes, timingSafeEqual } from "node:crypto";
import {
  mkdir,
  lstat,
  readFile,
  writeFile,
  unlink,
  realpath,
  chmod,
} from "node:fs/promises";

export async function connectionFile(projectDir, reference) {
  const root = path.join(
    os.tmpdir(),
    `cadkit-${process.getuid?.() ?? os.userInfo().username}`,
  );
  await mkdir(root, { recursive: true, mode: 0o700 });
  const stat = await lstat(root);
  if (
    !stat.isDirectory() ||
    stat.isSymbolicLink() ||
    (process.getuid && (stat.uid !== process.getuid() || stat.mode & 0o077))
  )
    throw new Error(
      "CadKit IPC directory must be owned by this user with permissions 0700",
    );
  const key = createHash("sha256")
    .update(`${await realpath(projectDir)}\0${reference}`)
    .digest("hex")
    .slice(0, 24);
  return path.join(root, `${key}.json`);
}

export async function callApp(file, method, params = {}) {
  let config;
  try {
    config = JSON.parse(await readFile(file, "utf8"));
  } catch {
    throw new Error(
      "CadKit app is not running for this project. Open it first with the same --project-dir and --project.",
    );
  }
  return new Promise((resolve, reject) => {
    const socket = net.createConnection(config.socket);
    let body = "";
    socket.setTimeout(300000, () =>
      socket.destroy(new Error("CadKit request timed out")),
    );
    socket.on("connect", () =>
      socket.write(
        JSON.stringify({ token: config.token, method, params }) + "\n",
      ),
    );
    socket.on("data", (chunk) => {
      body += chunk;
      if (body.length > 32 * 1024 * 1024)
        return socket.destroy(new Error("CadKit response too large"));
      if (!body.includes("\n")) return;
      try {
        const response = JSON.parse(body.slice(0, body.indexOf("\n")));
        response.error
          ? reject(new Error(response.error))
          : resolve(response.result);
      } catch (error) {
        reject(error);
      }
      socket.end();
    });
    socket.on("error", reject);
    socket.on("end", () => {
      if (!body.includes("\n")) reject(new Error("CadKit app disconnected"));
    });
  });
}

export async function startBridge(projectDir, reference, execute) {
  const file = await connectionFile(projectDir, reference);
  const token = randomBytes(32).toString("hex");
  const socketPath =
    process.platform === "win32"
      ? `\\\\.\\pipe\\cadkit-${randomBytes(16).toString("hex")}`
      : file.replace(/\.json$/, ".sock");
  // Never unlink a live app's socket. Stale discovery is only removed after
  // an OS-level connection refusal, not after an application error or timeout.
  if (process.platform !== "win32") {
    await new Promise((resolve, reject) => {
      const probe = net.createConnection(socketPath);
      probe.on("connect", () => {
        probe.destroy();
        reject(new Error("CadKit is already open for this project"));
      });
      probe.on("error", (e) =>
        ["ENOENT", "ECONNREFUSED"].includes(e.code) ? resolve() : reject(e),
      );
    });
    await unlink(socketPath).catch((e) => {
      if (e.code !== "ENOENT") throw e;
    });
  }
  const sockets = new Set();
  const server = net.createServer((socket) => {
    sockets.add(socket);
    socket.on("close", () => sockets.delete(socket));
    socket.on("error", () => {});
    socket.setTimeout(300000, () => socket.destroy());
    let body = "",
      handled = false;
    socket.on("data", async (chunk) => {
      if (handled) return;
      body += chunk;
      if (body.length > 256000) return socket.destroy();
      if (!body.includes("\n")) return;
      handled = true;
      try {
        const request = JSON.parse(body.slice(0, body.indexOf("\n")));
        const supplied = Buffer.from(String(request.token ?? ""));
        const expected = Buffer.from(token);
        if (
          supplied.length !== expected.length ||
          !timingSafeEqual(supplied, expected)
        )
          throw new Error("Unauthorized");
        const result = await execute(request.method, request.params);
        socket.end(JSON.stringify({ result }) + "\n");
      } catch (error) {
        socket.end(JSON.stringify({ error: error.message }) + "\n");
      }
    });
  });
  await new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(socketPath, resolve);
  });
  if (process.platform !== "win32") await chmod(socketPath, 0o600);
  await unlink(file).catch((e) => {
    if (e.code !== "ENOENT") throw e;
  });
  await writeFile(
    file,
    JSON.stringify({ socket: socketPath, token, pid: process.pid }),
    { mode: 0o600, flag: "wx" },
  );
  return {
    file,
    async close() {
      for (const socket of sockets) socket.destroy();
      await new Promise((resolve) => server.close(resolve));
      await unlink(file).catch(() => {});
    },
  };
}
