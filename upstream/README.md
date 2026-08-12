# Character upstream references

HearthGhost tracks selected upstream projects as references without making them runtime authorities.

## Sources

- **AIRI** (`moeru-ai/airi`, MIT): reference for VRM loading, animation, gaze, blink, expression, lip sync, and future motion/gesture ideas.
- **PNGAL** (`1mm-module/PNGAL`, Apache-2.0): reference or asset-generation source for 2D idle motion, eye/mouth animation, sprite timing, face variants, and a future 2D renderer pipeline.

The reviewed baseline SHAs and watched paths live in `character-sources.json`.

## Boundary

HearthGhost owns its semantic character contract. Upstream-specific APIs must stay behind adapters or renderer implementations. Natural-language behavior such as `raise_left_hand`, `wave_right`, `turn_right`, or `bow` should become HearthGhost semantic actions first and only then be mapped to VRM animation, procedural bone motion, or a 2D sprite implementation.

Do not let an LLM emit unrestricted bone transforms or renderer-specific commands. The LLM may propose a typed semantic action; HearthGhost validates it and the character controller executes only known actions.

## Update flow

`.github/workflows/upstream-character-watch.yml` runs once per day and can also be started manually. It compares each reviewed baseline with the current upstream branch and filters the changed files through the manifest's watch globs.

When a relevant change appears, the workflow creates or refreshes a GitHub Issue containing:

- the reviewed baseline and current upstream SHA;
- the upstream compare link;
- the relevant changed files;
- the HearthGhost review focus;
- the upstream license and integration policy.

The workflow never copies, merges, or executes upstream source code.

Review useful changes manually, adapt them behind HearthGhost's renderer/semantic boundary, preserve required attribution, run the normal CI suite, and only then update `baselineSha` in `character-sources.json` to the reviewed upstream commit.

## Local maintenance

Validate the manifest without network access:

```bash
python tools/upstream_watch.py validate
```

Scan the current upstream branches and write a machine-readable report:

```bash
GITHUB_TOKEN=... python tools/upstream_watch.py scan --output upstream-report.json
```

`GITHUB_TOKEN` is optional for public repositories but recommended to avoid anonymous API rate limits. Do not store it in the manifest or commit it to Git.
