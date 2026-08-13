---
name: studio3d-api
description: "3D AI Studio via UEFN-Ducky MCP — text/image-to-3D, image gen, miniature flow, mesh tools, credit balance. Async: submit → task_id → poll → download/import to Blender."
license: Ducky Source-Available License v1.0
metadata:
  label: 3D AI Studio
  version: 6
  author: UEFN-Ducky
  copyright: Copyright 2026 UEFN-Ducky
  allow_redistribute: false
  managed_by: uefn-ducky
  source_plugin_id: studio3d
---

# 3D AI Studio — generate via MCP

You call **`studio3d_*` tools** on the shared `uefn-ducky` MCP. Do **not** run CLI scripts or read a `.env` file.

API key lives in **Settings → 3D AI Studio** (encrypted on device). This is the **studio3d** Store plugin — independent of the Blender plugin.

## Prerequisites

1. Plugin **studio3d** installed + enabled (Settings → Store).
2. Tools opted in for this chat.
3. User has pasted a 3D AI Studio API key (https://www.3daistudio.com/Platform/API#api-keys).
4. For scene import: Blender open with BlenderMCP addon listening on `localhost:9876` (Blender Store plugin deploys the addon).

## Core pattern (all jobs are async)

1. Submit → JSON with `task_id`
2. `studio3d_status(task_id)` or `studio3d_status(task_id, poll=true)` until `FINISHED` / `FAILED`
3. `studio3d_download(task_id)` and/or `studio3d_import_glb_to_blender(url_or_path)`

Generation tools accept `wait=true` to poll + download in one call (can take several minutes). Prefer submit + poll when the user may want progress updates.

Result asset URLs expire in ~24 hours — download promptly. Default rate limit: **3 requests/minute**.

## Tools

| Tool | When |
|------|------|
| `studio3d_balance` | Credit check before expensive jobs |
| `studio3d_status` | Poll task (`poll=true` to block until done) |
| `studio3d_download` | Save FINISHED assets to disk |
| `studio3d_tencent_rapid` | Fast text/image→3D (~35 cr) |
| `studio3d_tencent_pro` | Higher quality (~60–100 cr) |
| `studio3d_trellis` | TRELLIS.2 image→3D only (~10–50 cr) |
| `studio3d_tripo` | Tripo v3.0/v3.1 text or image (~0–120 cr) |
| `studio3d_tripo_p1` | Tripo P1 premium (~60–160 cr) |
| `studio3d_image_gemini3pro` | Image gen (~10 cr/image) |
| `studio3d_image_gemini31flash` | Image gen (~7 cr/image) |
| `studio3d_image_gemini25flash` | Image gen (~5 cr/image) |
| `studio3d_image_seedream` | SeeDream v5 Lite |
| `studio3d_convert` | GLB → obj/fbx/stl/ply (~10 cr) |
| `studio3d_render` | Render model (~5–20 cr) |
| `studio3d_repair` | Mesh repair / print prep (~60–90 cr) |
| `studio3d_optimize` | Compress GLB (~10 cr) |
| `studio3d_bake_texture` | High→low poly bake (~5 cr) |
| `studio3d_remove_bg` | Background removal (~3–5 cr) |
| `studio3d_image_enhance` | Upscale/enhance (~15–20 cr) |
| `studio3d_volume` | Volume estimates (~20 cr, beta) |
| `studio3d_miniature` | Photo → figurine (~200–300 cr) |
| `studio3d_import_glb_to_blender` | Land a GLB URL/path into Blender |

Details: [references/api_reference.md](references/api_reference.md), [references/examples.md](references/examples.md), [references/setup.md](references/setup.md).

## Typical UEFN path

1. `studio3d_balance`
2. **`ducky_ask_user`** — yes/no spend with ~credit estimate (never chat-only)
3. On approve: generate (`studio3d_tripo` / `studio3d_tencent_rapid` / …) with `confirm_spend=true`, `wait=true` **or** poll
4. `studio3d_import_glb_to_blender` with a `3D_MODEL` asset URL
5. Continue with **blender** Store plugin skill (inspect / clean / export)

## Overlap with Hyper3D / Hunyuan (Blender addon)

Those use keys inside Blender MCP prefs (`blender_generate_hyper3d_*` / `blender_generate_hunyuan3d_*`) and require the **blender** plugin. Prefer **3D AI Studio** for Tripo, TRELLIS, miniature, image tools, and credit-based workflows.

## HARD RULES — CREDITS (non-negotiable)

Paid `studio3d_*` create tools **refuse** unless `confirm_spend=true`. Free: balance, status, download, import. Settings → **Test** verifies the API key. 3D AI Studio has no free community Discover library — for free existing meshes prefer **meshy** `meshy_discover_search` when that plugin is available; otherwise do not invent spend.

**100% of paid spends:** call `ducky_ask_user` first. Never ask only in chat text. Never set `confirm_spend=true` without a modal approve on that spend.

1. Call `studio3d_balance` before proposing work.
2. Call **`ducky_ask_user`** with a required yes/no question that includes the **~credit estimate** (tool docstring / CREDIT GATE) and what job will run — miniature/P1/repair are expensive. Example options: Spend / Cancel. Do not ask spend approval in plain chat.
3. Only if they select Spend (or clear free-text yes): retry the same tool with `confirm_spend=true`.
4. Never invent approval. Silence, skipped_all, Cancel, or vague interest = do **not** spend.
5. Never chain extra paid jobs without a new `ducky_ask_user` OK.
6. One modal OK covers one stated job (or a short list you named in that question) — not unlimited follow-ups.

## Don'ts

- Don't invent task status — poll tools.
- Don't tell the user to install `requests` or set `.env`.
- Don't ask spend approval only in chat — always `ducky_ask_user`.
- Don't call paid tools with `confirm_spend=true` unless `ducky_ask_user` just approved that spend.
