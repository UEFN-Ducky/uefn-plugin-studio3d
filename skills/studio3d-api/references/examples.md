# 3D AI Studio — MCP workflow examples

All examples use `studio3d_*` tools on the `uefn-ducky` MCP server.
Paid jobs need **`ducky_ask_user`** first, then `confirm_spend=true` — without
that the credit gate refuses the call.

## 1. Check balance

```
studio3d_balance
```

## 2. Quick text → 3D → Blender

```
# after ducky_ask_user approve:
studio3d_tencent_rapid(prompt="a wooden chair with armrests", enable_pbr=true, confirm_spend=true, wait=true)
# → task_id, then downloaded GLB paths when wait=true

studio3d_import_glb_to_blender(url_or_path="<asset URL or local .glb path>")
```

Or without wait:

```
studio3d_tripo(prompt="a fantasy crate", version="v3.1", enable_pbr=true, confirm_spend=true)
studio3d_status(task_id="…", poll=true)
studio3d_download(task_id="…")
studio3d_import_glb_to_blender(url_or_path="https://storage.3daistudio.com/assets/….glb")
```

## 3. Miniature figurine from photo

```
studio3d_miniature(
  image="C:/path/to/portrait.jpg",
  preset="v3_miniature_human_full_body",
  edition="default",
  scale="h0",
  confirm_spend=true,
  wait=true
)
```

## 4. Image → 3D (TRELLIS)

```
studio3d_trellis(image="C:/path/to/product.png", enable_pbr=true, confirm_spend=true, wait=true)
```

## 5. Image gen → 3D pipeline

```
studio3d_image_gemini31flash(
  prompt="a sleek modern chair, white background, product photo",
  confirm_spend=true,
  wait=true
)
# take downloaded image path:
studio3d_trellis(image="<downloaded image path>", enable_pbr=true, confirm_spend=true, wait=true)
studio3d_import_glb_to_blender(url_or_path="<glb>")
```

## 6. Generate → repair → convert

```
studio3d_tencent_rapid(prompt="a ceramic vase", enable_pbr=true, confirm_spend=true, wait=true)
# use result asset URL:
studio3d_repair(model_url="https://storage.3daistudio.com/assets/model.glb", confirm_spend=true, wait=true)
studio3d_convert(model_url="<repaired asset URL>", output_format="stl", confirm_spend=true, wait=true)
```

## 7. Remove background before 3D

```
studio3d_remove_bg(image="C:/path/to/product.jpg", confirm_spend=true, wait=true)
studio3d_trellis(image="<cleaned png path>", enable_pbr=true, confirm_spend=true, wait=true)
```

## Status values

| Status | Meaning |
|--------|---------|
| `PENDING` | Queued |
| `IN_PROGRESS` | Running |
| `FINISHED` | Done — download / import |
| `FAILED` | Failed — credits refunded |

## Credit cheat sheet

| Operation | Credits |
|-----------|---------|
| Tencent Rapid | ~35 |
| Tencent Pro | ~60–100 |
| TRELLIS.2 | ~10–50 |
| Tripo v3 | ~0–120 |
| Tripo P1 | ~60–160 |
| Gemini images | ~5–10 / image |
| Miniature | ~200–300 |
| Convert / Optimize | ~10 |
| Repair | ~60–90 |
| Remove BG | ~3–5 |
