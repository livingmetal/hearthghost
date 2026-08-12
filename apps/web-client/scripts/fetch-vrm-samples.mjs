import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, isAbsolute, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const MAX_ASSET_BYTES = 40 * 1024 * 1024;
const MODEL_A = Object.freeze({
  name: "AvatarSample_Y.vrm",
  environmentVariable: "HEARTHGHOST_MODEL_A_PATH",
  outputPath: "models/AvatarSample_Y.vrm",
  expectedBytes: 16_935_148,
  sha256: "48af6bf879cadbc4e17431543f795010c9ca2bf31c3ca5e0b450c87b05545c11",
});
const ASSETS = Object.freeze([
  Object.freeze({
    name: "AvatarSample_C.vrm",
    repository: "hirokazuniimoto/virtual-avatar-sdk",
    commit: "114d4336e0ac36bf9c2297b0a93ad7604b13704b",
    sourcePath: "assets/avatars/AvatarSample_C.vrm",
    outputPath: "models/AvatarSample_C.vrm",
    blobSha: "4513c2989150c6bd5040f8a3e1b89631efef9a87",
  }),
  Object.freeze({
    name: "airi-idle-loop.vrma",
    repository: "moeru-ai/airi",
    commit: "b6011381bc34a6b85ad669363513cb1a2eea6438",
    sourcePath: "packages/stage-ui-three/src/assets/vrm/animations/idle_loop.vrma",
    outputPath: "animations/airi-idle-loop.vrma",
    blobSha: "26b28f4e4227c48eecdd29d25e3dc6f4c6ac3844",
  }),
]);

const scriptDir = dirname(fileURLToPath(import.meta.url));
const publicDir = resolve(scriptDir, "..", "public");

function gitBlobSha(bytes) {
  const header = Buffer.from(`blob ${bytes.length}\0`, "utf8");
  return createHash("sha1").update(header).update(bytes).digest("hex");
}

function sha256(bytes) {
  return createHash("sha256").update(bytes).digest("hex");
}

function validateModelA(bytes) {
  if (bytes.length !== MODEL_A.expectedBytes || bytes.length > MAX_ASSET_BYTES) {
    throw new Error(`${MODEL_A.name}: unexpected asset size ${bytes.length}`);
  }
  if (bytes.subarray(0, 4).toString("ascii") !== "glTF" || bytes.readUInt32LE(4) !== 2) {
    throw new Error(`${MODEL_A.name}: expected a glTF 2.0/VRM container`);
  }
  const observed = sha256(bytes);
  if (observed !== MODEL_A.sha256) {
    throw new Error(`${MODEL_A.name}: SHA-256 mismatch (${observed})`);
  }
  return observed;
}

async function prepareModelA() {
  const output = resolve(publicDir, MODEL_A.outputPath);
  const configuredPath = process.env[MODEL_A.environmentVariable]?.trim() ?? "";
  let bytes;
  let sourceLabel;

  if (configuredPath !== "") {
    const source = isAbsolute(configuredPath) ? configuredPath : resolve(process.cwd(), configuredPath);
    bytes = await readFile(source);
    sourceLabel = source;
  } else {
    try {
      bytes = await readFile(output);
      sourceLabel = output;
    } catch {
      throw new Error(
        `${MODEL_A.name}: place the tracked model at ${output} `
        + `or set ${MODEL_A.environmentVariable} to a local override path`,
      );
    }
  }

  const observed = validateModelA(bytes);
  await mkdir(dirname(output), { recursive: true });
  await writeFile(output, bytes, { mode: 0o644 });
  console.log(`${MODEL_A.name}: ${bytes.length} bytes / sha256 ${observed} / source ${sourceLabel}`);
}

async function fetchAsset(asset) {
  const url = `https://raw.githubusercontent.com/${asset.repository}/${asset.commit}/${asset.sourcePath}`;
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 30_000);
  try {
    const response = await fetch(url, {
      redirect: "error",
      signal: controller.signal,
      headers: { "User-Agent": "HearthGhost-Presentation-Build/1" },
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
    const output = resolve(publicDir, asset.outputPath);
    await mkdir(dirname(output), { recursive: true });
    await writeFile(output, bytes, { mode: 0o644 });
    console.log(`${asset.name}: ${bytes.length} bytes / git-blob ${observed}`);
  } finally {
    clearTimeout(timeout);
  }
}

await prepareModelA();
for (const asset of ASSETS) {
  await fetchAsset(asset);
}
