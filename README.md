# 3D AI Studio

3D AI Studio API — text/image-to-3D, image generation, miniature flow, and mesh tools (Tripo, TRELLIS, Tencent, convert/repair/optimize). Optional import into a running Blender session.

Desktop plugin for [UEFN-Ducky](https://github.com/UEFN-Ducky/UEFN-Ducky) (`studio3d`).
Install or update from **Settings → Store** in the app — do not install from a zip by hand.

## Build

```bash
py scripts/build_zip.py
```

Writes `deploy/studio3d-1.0.12.ducky-plugin.zip` (scripts/ and deploy/ are not packed).

## Secrets

Never commit tokens or keys. The app stores `3d_ai_studio_api_key` locally (DPAPI), not in this package.
