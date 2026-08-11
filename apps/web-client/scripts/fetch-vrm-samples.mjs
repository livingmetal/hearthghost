import { createHash } from "node:crypto";
import { mkdir, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const SOURCE_COMMIT = "114d4336e0ac36bf9c2297b0a93ad7604b13704b";
const MAX_ASSET_BYTES = 40 * 1024 * 1024;
const ASSETS = Object.freeze([
  Object.freeze({
    name: "AvatarSample_A.vrm",
    blobSha: "2ab43eef01826a3f93ab92e4174473efd473ae98",
  }),
  Object.freeze({
    name: "AvatarSample_C.vrm",
    blobSha: "4513c2989150c6bd5040f8a3e1b89631efef9a87",
  }),
]);

const scriptDir = dirname(fileURLToPath(import.meta.url));
const outputDir = resolve(scriptDir, "..", "public", "models");

function gitBlobSha(bytes) {
  const header = Buffer.from(`blob ${bytes.length}\0`, "utf8");
  return createHash("sha1").update(header).update(bytes).digest("hex");
}

async function fetchAsset(asset) {
  const url = `https://raw.githubusercontent.com/hirokazuniimoto/virtual-avatar-sdk/${SOURCE_COMMIT}/assets/avatars/${asset.name}`;
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 30_000);
  try {
    const response = await fetch(url, {
      redirect: "error",
      signal: controller.signal,
      headers: { "User-Agent": "HearthGhost-VRM-Build/1" },
    });
    if (!response.ok) {
      throw new Error(`${asset.name}: source returned HTTP ${response.status}`);
    }
    const declaredLength = Number(response.headers.get("content-length") ?? "0");
    if (Number.isFinite(declaredLength) && declaredLength > MAX_ASSET_BYTES) {
      throw new Error(`${asset.name}: declared asset size exceeds limit`);
    }
    const bytes = Buffer.from(await response.arrayBuffer());
    if (bytes.length === 0 || bytes.length > MAX_ASSET_BYTES) {
      throw new Error(`${asset.name}: asset size is invalid`);
    }
    const observed = gitBlobSha(bytes);
    if (observed !== asset.blobSha) {
      throw new Error(`${asset.name}: Git blob identity mismatch (${observed})`);
    }
    await writeFile(resolve(outputDir, asset.name), bytes, { mode: 0o644 });
    console.log(`${asset.name}: ${bytes.length} bytes / git-blob ${observed}`);
  } finally {
    clearTimeout(timeout);
  }
}

await mkdir(outputDir, { recursive: true });
for (const asset of ASSETS) {
  await fetchAsset(asset);
}
