# 3D AI Studio API reference (UEFN-Ducky MCP)

Base URL used by the plugin: `https://api.3daistudio.com`  
Auth: Bearer key from Settings → 3D AI Studio.

Agents use **`studio3d_*` tools** — not curl/CLI.

## Async pattern

```
submit tool  →  { "task_id": "…", "status": "submitted" }
studio3d_status(task_id) until FINISHED | FAILED
studio3d_download(task_id)  and/or  studio3d_import_glb_to_blender(url_or_path)
```

Status values: `PENDING` | `IN_PROGRESS` | `FINISHED` | `FAILED`  
Asset types: `3D_MODEL`, `SCALED_3D_MODEL`, `EDITED_IMAGE`, `IMAGE`, `ARCHIVE`  
Poll ~every 10s; generation often takes 3–8 minutes. Result URLs expire ~24h.

## Credit balance

`studio3d_balance` → GET `/account/user/wallet/` → `{"balance": "150.00"}`

## Status / download

| Tool | Notes |
|------|-------|
| `studio3d_status(task_id, poll=false)` | One shot; `poll=true` waits until done |
| `studio3d_download(task_id, output_dir="")` | Requires FINISHED; default temp dir |

## 3D generation

| Tool | Endpoint (approx) | Credits |
|------|-------------------|---------|
| `studio3d_tencent_rapid(prompt\|image, enable_pbr)` | `/v1/3d-models/tencent/generate/rapid/` | ~35 (+PBR) |
| `studio3d_tencent_pro(...)` | `/v1/3d-models/tencent/generate/pro/` | ~60–100 |
| `studio3d_trellis(image, enable_pbr)` | `/v1/3d-models/trellis2/generate/` | ~10–50 |
| `studio3d_tripo(prompt\|image, version, enable_pbr)` | Tripo text/image-to-3d | ~0–120 |
| `studio3d_tripo_p1(prompt\|image)` | Tripo P1 | ~60–160 |

`image` may be a local path (auto base64), `data:` URI, or `http(s)` URL (TRELLIS prefers `image_url` for URLs).

Pro extras: `model` (default `3.0`), `face_count`, `generate_type` (`Normal`\|`Cartoon`\|`Sculpture`).

## Image generation

| Tool | Credits |
|------|---------|
| `studio3d_image_gemini3pro(prompt, count)` | ~10/image |
| `studio3d_image_gemini31flash(prompt, count)` | ~7/image |
| `studio3d_image_gemini25flash(prompt, count)` | ~5/image (max 4) |
| `studio3d_image_seedream(prompt)` | varies |

## Tools

| Tool | Credits |
|------|---------|
| `studio3d_convert(model_url, output_format)` | ~10 — format: `obj`\|`fbx`\|`stl`\|`ply` |
| `studio3d_render(model_url)` | ~5–20 |
| `studio3d_repair(model_url)` | ~60–90 |
| `studio3d_optimize(model_url)` | ~10 |
| `studio3d_bake_texture(high_poly_url, low_poly_url)` | ~5 |
| `studio3d_remove_bg(image)` | ~3–5 |
| `studio3d_image_enhance(image)` | ~15–20 |
| `studio3d_volume(model_url)` | ~20 (beta) |

## Miniature flow

`studio3d_miniature(image, preset, edition="default", scale="none", …)`  
Credits: ~200 (`fast`) / ~300 (`default`).

Useful presets: `v3_miniature_human_full_body`, `v4_miniature_general`, `miniature_human_bust`, `realistic_human_full_body`, …  
Scale: `none`, `h0` (1:87), `o`, `g`, `z`, `n`, `tt`, `1:NUMBER`, `custom` (+ `scale_height_cm`).

Results may include `EDITED_IMAGE`, `3D_MODEL`, `SCALED_3D_MODEL`, `ARCHIVE`.

## Blender handoff

`studio3d_import_glb_to_blender(url_or_path)` — downloads HTTP URLs to a temp file, then `bpy.ops.import_scene.gltf` via Blender MCP.

## Errors

| HTTP | Meaning |
|------|---------|
| 401 | Bad/expired/revoked key |
| 402 | Insufficient credits |
| 429 | Rate limited (default 3/min) |
| 400 | Validation failed |

Failed jobs refund credits automatically.
