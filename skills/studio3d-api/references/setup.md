# Setup — 3D AI Studio in UEFN-Ducky

## Prerequisites

- UEFN-Ducky with the **studio3d** Store plugin installed and enabled
- A 3D AI Studio account + API key

## Configure the API key

1. Open https://www.3daistudio.com/Platform/API#api-keys and create a key (shown once — store it).
2. In UEFN-Ducky: **Settings → 3D AI Studio → API key**
3. Paste the key → **Test**. Stored encrypted (DPAPI) as `3d_ai_studio_api_key`.

No `.env`, no `pip install`, no CLI client. Paid tools need `ducky_ask_user` (panel yes/no with credit estimate) then `confirm_spend=true` — never chat-only approval.

## Verify

Hit **Test** in Settings, or ask the agent:

```
studio3d_balance
```

Success returns JSON like `{"balance": "150.00"}`.

| Symptom | Fix |
|---------|-----|
| Key not set | Paste key in Settings → 3D AI Studio |
| 401 | Key invalid/expired/revoked — create a new key |
| 402 | Buy credits on 3daistudio.com |
| 429 | Wait; default limit is 3 req/min |

## Blender import (optional)

`studio3d_*` generation does **not** require Blender. Importing does:

1. Blender open, BlenderMCP addon enabled on `localhost:9876`
2. `studio3d_import_glb_to_blender(url_or_path)`

The Blender Store plugin deploys the addon; it does not need to be enabled for the socket if the addon is already running.

## Token security

- Never commit keys or put them in the plugin zip
- Rotate keys in the 3D AI Studio dashboard if leaked
- Failed jobs refund credits automatically
