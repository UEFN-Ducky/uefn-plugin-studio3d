"""3D AI Studio API — HTTP client + MCP tools (standalone Store plugin).

Calls https://api.3daistudio.com with a Bearer key from DPAPI credentials
(secret key ``3d_ai_studio_api_key``). Stdlib only (urllib).
"""

from __future__ import annotations

import base64
import json
import logging
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

log = logging.getLogger("uefn.plugin.studio3d")

SECRET_KEY = "3d_ai_studio_api_key"
BASE_URL = "https://api.3daistudio.com"
DEFAULT_TIMEOUT = 60
INTENT = r"\b(3daistudio|3d\s*ai\s*studio|tripo|trellis|miniature|studio3d)\b"


def _api_key() -> str:
    from backend.agent.secrets import get_key

    return (get_key(SECRET_KEY) or "").strip()


def encode_image(path: str) -> str:
    """Local image path → data URI."""
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"image not found: {path}")
    mime = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }.get(p.suffix.lower(), "image/jpeg")
    return f"data:{mime};base64,{base64.b64encode(p.read_bytes()).decode()}"


def resolve_image(image: str) -> str:
    """Pass through http(s)/data URIs; encode local paths."""
    s = (image or "").strip()
    if not s:
        return ""
    if s.startswith(("http://", "https://", "data:")):
        return s
    return encode_image(s)


def auth_header(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def parse_status_payload(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize a status JSON body (used by tools + self-check)."""
    status = str(raw.get("status") or "")
    progress = raw.get("progress", 0)
    results = raw.get("results") if isinstance(raw.get("results"), list) else []
    assets = []
    for item in results:
        if not isinstance(item, dict):
            continue
        url = item.get("asset")
        if url:
            assets.append(
                {
                    "asset": url,
                    "asset_type": item.get("asset_type"),
                    "metadata": item.get("metadata"),
                }
            )
    return {
        "status": status,
        "progress": progress,
        "failure_reason": raw.get("failure_reason"),
        "results": assets,
        "finished": status == "FINISHED",
        "failed": status == "FAILED",
    }


class Studio3dError(Exception):
    def __init__(self, message: str, *, status: int | None = None, detail: Any = None):
        super().__init__(message)
        self.status = status
        self.detail = detail


class Studio3dClient:
    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str = BASE_URL,
        timeout: int = DEFAULT_TIMEOUT,
    ):
        key = (api_key if api_key is not None else _api_key()).strip()
        if not key:
            raise Studio3dError(
                "3D AI Studio API key not set. Paste it in Settings → 3D AI Studio."
            )
        self.api_key = key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        data = None
        headers = auth_header(self.api_key)
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = resp.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as exc:
            detail_body = ""
            try:
                detail_body = exc.read().decode("utf-8", "replace")
            except Exception:
                pass
            detail: Any = detail_body
            try:
                detail = json.loads(detail_body) if detail_body else {}
            except (ValueError, TypeError):
                pass
            msg = _http_error_message(exc.code, detail)
            raise Studio3dError(msg, status=exc.code, detail=detail) from exc
        except urllib.error.URLError as exc:
            raise Studio3dError(f"3D AI Studio network error: {exc.reason}") from exc
        if not body.strip():
            return {}
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError as exc:
            raise Studio3dError(f"3D AI Studio returned non-JSON: {body[:200]}") from exc
        if not isinstance(parsed, dict):
            raise Studio3dError(f"3D AI Studio unexpected response type: {type(parsed).__name__}")
        return parsed

    def get(self, path: str) -> dict[str, Any]:
        return self._request("GET", path)

    def post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", path, payload)

    def balance(self) -> dict[str, Any]:
        return self.get("/account/user/wallet/")

    def status(self, task_id: str) -> dict[str, Any]:
        return parse_status_payload(self.get(f"/v1/generation-request/{task_id}/status/"))

    def wait(
        self,
        task_id: str,
        *,
        poll_interval: int = 10,
        max_attempts: int = 120,
    ) -> dict[str, Any]:
        for _ in range(max_attempts):
            result = self.status(task_id)
            if result["finished"] or result["failed"]:
                return result
            time.sleep(max(1, poll_interval))
        raise Studio3dError(
            f"Task {task_id} did not finish within {max_attempts * poll_interval}s"
        )

    def download_url(self, url: str, dest: Path) -> Path:
        dest.parent.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            dest.write_bytes(resp.read())
        return dest

    def download_results(self, status_result: dict[str, Any], output_dir: str | Path) -> list[str]:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        paths: list[str] = []
        for item in status_result.get("results") or []:
            url = item.get("asset") if isinstance(item, dict) else None
            if not url:
                continue
            name = str(url).split("/")[-1].split("?")[0] or "asset.bin"
            dest = out / name
            self.download_url(str(url), dest)
            paths.append(str(dest))
        return paths

    def submit_task(self, path: str, payload: dict[str, Any]) -> str:
        r = self.post(path, payload)
        task_id = r.get("task_id")
        if not task_id:
            raise Studio3dError(f"No task_id in response: {r}")
        return str(task_id)


def _http_error_message(code: int, detail: Any) -> str:
    snippet = ""
    if isinstance(detail, dict):
        snippet = str(
            detail.get("detail")
            or detail.get("message")
            or detail.get("code")
            or detail
        )[:240]
    elif detail:
        snippet = str(detail)[:240]
    if code == 401:
        return (
            "3D AI Studio rejected the API key (401). "
            "Re-check Settings → 3D AI Studio."
            + (f" ({snippet})" if snippet else "")
        )
    if code == 402:
        return "3D AI Studio: insufficient credits (402). Purchase credits on 3daistudio.com."
    if code == 429:
        return "3D AI Studio rate limited (429). Default is 3 req/min — wait and retry."
    return f"3D AI Studio error {code}" + (f": {snippet}" if snippet else "")


def _dumps(obj: Any) -> str:
    return json.dumps(obj, indent=2, default=str)

def format_balance_detail(balance_payload: dict[str, Any]) -> str:
    """Human line for Settings → Test."""
    if not isinstance(balance_payload, dict):
        return "Connected"
    for key in ("credits", "balance", "credit_balance", "available_credits", "remaining"):
        if balance_payload.get(key) is not None:
            return f"Connected — {balance_payload[key]} credits"
    for nest in ("wallet", "data", "result"):
        inner = balance_payload.get(nest)
        if isinstance(inner, dict):
            detail = format_balance_detail(inner)
            if detail != "Connected":
                return detail
    return "Connected"


def test_api_key(api_key: str = "") -> dict[str, Any]:
    """Settings → Test: GET wallet with a draft or saved key."""
    key = (api_key or "").strip()
    if not key:
        return {"ok": False, "detail": "Paste a 3D AI Studio API key first"}
    try:
        return {"ok": True, "detail": format_balance_detail(Studio3dClient(api_key=key).balance())}
    except Studio3dError as exc:
        return {"ok": False, "detail": str(exc)}


def credit_gate(confirm_spend: bool, estimated_credits: int, label: str) -> str | None:
    """Hard spend lock — paid jobs need confirm_spend=true after ducky_ask_user OK."""
    if int(estimated_credits or 0) <= 0:
        return None
    if confirm_spend:
        return None
    return (
        f"Error: CREDIT GATE — {label} costs ~{estimated_credits} credits. "
        "1) Call studio3d_balance. "
        "2) Call ducky_ask_user with a yes/no spend question (include the ~credit estimate) — "
        "never ask only in chat text. "
        "3) Only if they approve: retry with confirm_spend=true. Do not invent approval."
    )




def _default_download_dir(task_id: str) -> Path:
    return Path(tempfile.gettempdir()) / "uefn-ducky-studio3d" / task_id


def _maybe_wait_download(
    client: Studio3dClient,
    task_id: str,
    *,
    wait: bool,
    output_dir: str,
) -> str:
    payload: dict[str, Any] = {"task_id": task_id, "status": "submitted"}
    if not wait:
        return _dumps(payload)
    result = client.wait(task_id)
    payload.update(result)
    if result.get("finished"):
        dest = output_dir.strip() or str(_default_download_dir(task_id))
        payload["downloaded"] = client.download_results(result, dest)
        payload["output_dir"] = dest
    return _dumps(payload)


def register_tools(api: Any) -> None:
    """Register studio3d_* tools on the shared MCP server."""

    def _client() -> Studio3dClient:
        return Studio3dClient()

    if hasattr(api, "register_secret_test"):
        api.register_secret_test(SECRET_KEY, test_api_key)

    @api.tool(name="studio3d_balance", intent=INTENT)
    def studio3d_balance() -> str:
        """Check 3D AI Studio credit balance."""
        try:
            return _dumps(_client().balance())
        except Studio3dError as exc:
            return f"Error: {exc}"

    @api.tool(name="studio3d_status", intent=INTENT)
    def studio3d_status(task_id: str, poll: bool = False, poll_interval: int = 10) -> str:
        """Poll a 3D AI Studio task. Set poll=true to wait until FINISHED/FAILED."""
        try:
            client = _client()
            if poll:
                return _dumps(client.wait(task_id, poll_interval=max(1, int(poll_interval or 10))))
            return _dumps(client.status(task_id))
        except Studio3dError as exc:
            return f"Error: {exc}"

    @api.tool(name="studio3d_download", intent=INTENT)
    def studio3d_download(task_id: str, output_dir: str = "") -> str:
        """Download assets for a FINISHED task to output_dir (default temp folder)."""
        try:
            client = _client()
            result = client.status(task_id)
            if not result.get("finished"):
                return _dumps(
                    {
                        "error": f"Task is {result.get('status')}, not FINISHED",
                        **result,
                    }
                )
            dest = output_dir.strip() or str(_default_download_dir(task_id))
            paths = client.download_results(result, dest)
            return _dumps({"downloaded": paths, "output_dir": dest, **result})
        except Studio3dError as exc:
            return f"Error: {exc}"

    @api.tool(name="studio3d_tencent_rapid", intent=INTENT)
    def studio3d_tencent_rapid(
        prompt: str = "",
        image: str = "",
        enable_pbr: bool = False,
        confirm_spend: bool = False,
        wait: bool = False,
        output_dir: str = "",
    ) -> str:
        """Tencent Hunyuan Rapid text/image-to-3D (~35 credits). Provide prompt or image."""
        try:
            blocked = credit_gate(confirm_spend, 35, "tencent_rapid")
            if blocked:
                return blocked
            client = _client()
            payload: dict[str, Any] = {"enable_pbr": bool(enable_pbr)}
            img = resolve_image(image) if image else ""
            if img:
                payload["image"] = img
            elif prompt.strip():
                payload["prompt"] = prompt.strip()
            else:
                return "Error: provide prompt or image"
            task_id = client.submit_task("/v1/3d-models/tencent/generate/rapid/", payload)
            return _maybe_wait_download(client, task_id, wait=wait, output_dir=output_dir)
        except (Studio3dError, FileNotFoundError, OSError) as exc:
            return f"Error: {exc}"

    @api.tool(name="studio3d_tencent_pro", intent=INTENT)
    def studio3d_tencent_pro(
        prompt: str = "",
        image: str = "",
        model: str = "3.0",
        enable_pbr: bool = False,
        face_count: int = 0,
        generate_type: str = "",
        confirm_spend: bool = False,
        wait: bool = False,
        output_dir: str = "",
    ) -> str:
        """Tencent Hunyuan Pro text/image-to-3D (~60–100 credits). generate_type: Normal|Cartoon|Sculpture."""
        try:
            blocked = credit_gate(confirm_spend, 80, "tencent_pro")
            if blocked:
                return blocked
            client = _client()
            payload: dict[str, Any] = {
                "model": model or "3.0",
                "enable_pbr": bool(enable_pbr),
            }
            img = resolve_image(image) if image else ""
            if img:
                payload["image"] = img
            elif prompt.strip():
                payload["prompt"] = prompt.strip()
            else:
                return "Error: provide prompt or image"
            if face_count:
                payload["face_count"] = int(face_count)
            if generate_type.strip():
                payload["generate_type"] = generate_type.strip()
            task_id = client.submit_task("/v1/3d-models/tencent/generate/pro/", payload)
            return _maybe_wait_download(client, task_id, wait=wait, output_dir=output_dir)
        except (Studio3dError, FileNotFoundError, OSError) as exc:
            return f"Error: {exc}"

    @api.tool(name="studio3d_trellis", intent=INTENT)
    def studio3d_trellis(
        image: str,
        enable_pbr: bool = False,
        confirm_spend: bool = False,
        wait: bool = False,
        output_dir: str = "",
    ) -> str:
        """TRELLIS.2 image-to-3D only (~10–50 credits). image: local path or URL."""
        try:
            blocked = credit_gate(confirm_spend, 30, "trellis")
            if blocked:
                return blocked
            client = _client()
            payload: dict[str, Any] = {"enable_pbr": bool(enable_pbr)}
            raw = (image or "").strip()
            if raw.startswith(("http://", "https://")):
                payload["image_url"] = raw
            else:
                payload["image"] = resolve_image(raw)
            task_id = client.submit_task("/v1/3d-models/trellis2/generate/", payload)
            return _maybe_wait_download(client, task_id, wait=wait, output_dir=output_dir)
        except (Studio3dError, FileNotFoundError, OSError) as exc:
            return f"Error: {exc}"

    @api.tool(name="studio3d_tripo", intent=INTENT)
    def studio3d_tripo(
        prompt: str = "",
        image: str = "",
        version: str = "v3.1",
        enable_pbr: bool = False,
        confirm_spend: bool = False,
        wait: bool = False,
        output_dir: str = "",
    ) -> str:
        """Tripo v3.0/v3.1 text or image-to-3D (~0–120 credits)."""
        try:
            blocked = credit_gate(confirm_spend, 60, "tripo")
            if blocked:
                return blocked
            client = _client()
            payload: dict[str, Any] = {
                "version": version or "v3.1",
                "enable_pbr": bool(enable_pbr),
            }
            img = resolve_image(image) if image else ""
            if img:
                payload["image"] = img
                path = "/v1/3d-models/tripo/image-to-3d/"
            elif prompt.strip():
                payload["prompt"] = prompt.strip()
                path = "/v1/3d-models/tripo/text-to-3d/"
            else:
                return "Error: provide prompt or image"
            task_id = client.submit_task(path, payload)
            return _maybe_wait_download(client, task_id, wait=wait, output_dir=output_dir)
        except (Studio3dError, FileNotFoundError, OSError) as exc:
            return f"Error: {exc}"

    @api.tool(name="studio3d_tripo_p1", intent=INTENT)
    def studio3d_tripo_p1(
        prompt: str = "",
        image: str = "",
        confirm_spend: bool = False,
        wait: bool = False,
        output_dir: str = "",
    ) -> str:
        """Tripo P1 premium text/image-to-3D (~60–160 credits)."""
        try:
            blocked = credit_gate(confirm_spend, 100, "tripo_p1")
            if blocked:
                return blocked
            client = _client()
            payload: dict[str, Any] = {}
            img = resolve_image(image) if image else ""
            if img:
                payload["image"] = img
                path = "/v1/3d-models/tripo/image-to-3d/p1/"
            elif prompt.strip():
                payload["prompt"] = prompt.strip()
                path = "/v1/3d-models/tripo/text-to-3d/p1/"
            else:
                return "Error: provide prompt or image"
            task_id = client.submit_task(path, payload)
            return _maybe_wait_download(client, task_id, wait=wait, output_dir=output_dir)
        except (Studio3dError, FileNotFoundError, OSError) as exc:
            return f"Error: {exc}"

    def _image_gen(
        endpoint: str,
        prompt: str,
        count: int,
        wait: bool,
        output_dir: str,
        *,
        confirm_spend: bool = False,
        estimated_credits: int = 10,
        label: str = "image_gen",
    ) -> str:
        try:
            blocked = credit_gate(confirm_spend, estimated_credits * max(1, int(count or 1)), label)
            if blocked:
                return blocked
            client = _client()
            if not prompt.strip():
                return "Error: prompt is required"
            payload: dict[str, Any] = {"prompt": prompt.strip()}
            if count and count != 1:
                payload["count"] = int(count)
            task_id = client.submit_task(endpoint, payload)
            return _maybe_wait_download(client, task_id, wait=wait, output_dir=output_dir)
        except Studio3dError as exc:
            return f"Error: {exc}"

    @api.tool(name="studio3d_image_gemini3pro", intent=INTENT)
    def studio3d_image_gemini3pro(
        prompt: str, count: int = 1, confirm_spend: bool = False, wait: bool = False, output_dir: str = ""
    ) -> str:
        """Gemini 3 Pro image generation (~10 credits/image)."""
        return _image_gen(
            "/v1/images/gemini/3/pro/generate/", prompt, count, wait, output_dir,
            confirm_spend=confirm_spend, estimated_credits=10, label="gemini3pro",
        )

    @api.tool(name="studio3d_image_gemini31flash", intent=INTENT)
    def studio3d_image_gemini31flash(
        prompt: str, count: int = 1, confirm_spend: bool = False, wait: bool = False, output_dir: str = ""
    ) -> str:
        """Gemini 3.1 Flash image generation (~7 credits/image)."""
        return _image_gen(
            "/v1/images/gemini/3.1/flash/generate/", prompt, count, wait, output_dir,
            confirm_spend=confirm_spend, estimated_credits=7, label="gemini31flash",
        )

    @api.tool(name="studio3d_image_gemini25flash", intent=INTENT)
    def studio3d_image_gemini25flash(
        prompt: str, count: int = 1, confirm_spend: bool = False, wait: bool = False, output_dir: str = ""
    ) -> str:
        """Gemini 2.5 Flash image generation (~5 credits/image, max 4)."""
        return _image_gen(
            "/v1/images/gemini/2.5/flash/generate/", prompt, count, wait, output_dir,
            confirm_spend=confirm_spend, estimated_credits=5, label="gemini25flash",
        )

    @api.tool(name="studio3d_image_seedream", intent=INTENT)
    def studio3d_image_seedream(
        prompt: str, confirm_spend: bool = False, wait: bool = False, output_dir: str = ""
    ) -> str:
        """SeeDream v5 Lite image generation."""
        return _image_gen(
            "/v1/images/seedream/v5/lite/generate/", prompt, 1, wait, output_dir,
            confirm_spend=confirm_spend, estimated_credits=10, label="seedream",
        )

    @api.tool(name="studio3d_convert", intent=INTENT)
    def studio3d_convert(
        model_url: str,
        output_format: str,
        confirm_spend: bool = False,
        wait: bool = False,
        output_dir: str = "",
    ) -> str:
        """Convert GLB to obj|fbx|stl|ply (~10 credits)."""
        try:
            blocked = credit_gate(confirm_spend, 10, "convert")
            if blocked:
                return blocked
            client = _client()
            fmt = (output_format or "").strip().lower()
            if fmt not in {"obj", "fbx", "stl", "ply"}:
                return "Error: output_format must be obj, fbx, stl, or ply"
            task_id = client.submit_task(
                "/v1/tools/convert/",
                {"model_url": model_url.strip(), "output_format": fmt},
            )
            return _maybe_wait_download(client, task_id, wait=wait, output_dir=output_dir)
        except Studio3dError as exc:
            return f"Error: {exc}"

    @api.tool(name="studio3d_render", intent=INTENT)
    def studio3d_render(model_url: str, confirm_spend: bool = False,
        wait: bool = False, output_dir: str = "") -> str:
        """Render a 3D model to image/video (~5–20 credits)."""
        try:
            blocked = credit_gate(confirm_spend, 15, "render")
            if blocked:
                return blocked
            client = _client()
            task_id = client.submit_task(
                "/v1/tools/render/", {"model_url": model_url.strip()}
            )
            return _maybe_wait_download(client, task_id, wait=wait, output_dir=output_dir)
        except Studio3dError as exc:
            return f"Error: {exc}"

    @api.tool(name="studio3d_repair", intent=INTENT)
    def studio3d_repair(model_url: str, confirm_spend: bool = False,
        wait: bool = False, output_dir: str = "") -> str:
        """Repair mesh / 3D-print prep (~60–90 credits)."""
        try:
            blocked = credit_gate(confirm_spend, 75, "repair")
            if blocked:
                return blocked
            client = _client()
            task_id = client.submit_task(
                "/v1/tools/repair/", {"model_url": model_url.strip()}
            )
            return _maybe_wait_download(client, task_id, wait=wait, output_dir=output_dir)
        except Studio3dError as exc:
            return f"Error: {exc}"

    @api.tool(name="studio3d_optimize", intent=INTENT)
    def studio3d_optimize(model_url: str, confirm_spend: bool = False,
        wait: bool = False, output_dir: str = "") -> str:
        """Compress/optimize a GLB (~10 credits)."""
        try:
            blocked = credit_gate(confirm_spend, 10, "optimize")
            if blocked:
                return blocked
            client = _client()
            task_id = client.submit_task(
                "/v1/tools/optimize/", {"model_url": model_url.strip()}
            )
            return _maybe_wait_download(client, task_id, wait=wait, output_dir=output_dir)
        except Studio3dError as exc:
            return f"Error: {exc}"

    @api.tool(name="studio3d_bake_texture", intent=INTENT)
    def studio3d_bake_texture(
        high_poly_url: str,
        low_poly_url: str,
        confirm_spend: bool = False,
        wait: bool = False,
        output_dir: str = "",
    ) -> str:
        """Bake textures from high-poly to low-poly (~5 credits)."""
        try:
            blocked = credit_gate(confirm_spend, 5, "bake_texture")
            if blocked:
                return blocked
            client = _client()
            task_id = client.submit_task(
                "/v1/tools/bake-texture/",
                {
                    "high_poly_model_url": high_poly_url.strip(),
                    "low_poly_model_url": low_poly_url.strip(),
                },
            )
            return _maybe_wait_download(client, task_id, wait=wait, output_dir=output_dir)
        except Studio3dError as exc:
            return f"Error: {exc}"

    @api.tool(name="studio3d_remove_bg", intent=INTENT)
    def studio3d_remove_bg(image: str, confirm_spend: bool = False,
        wait: bool = False, output_dir: str = "") -> str:
        """Remove image background (~3–5 credits). image: local path or data URI."""
        try:
            blocked = credit_gate(confirm_spend, 5, "remove_bg")
            if blocked:
                return blocked
            client = _client()
            task_id = client.submit_task(
                "/v1/tools/remove-bg/", {"image": resolve_image(image)}
            )
            return _maybe_wait_download(client, task_id, wait=wait, output_dir=output_dir)
        except (Studio3dError, FileNotFoundError, OSError) as exc:
            return f"Error: {exc}"

    @api.tool(name="studio3d_image_enhance", intent=INTENT)
    def studio3d_image_enhance(
        image: str, confirm_spend: bool = False, wait: bool = False, output_dir: str = ""
    ) -> str:
        """Upscale/enhance an image (~15–20 credits)."""
        try:
            blocked = credit_gate(confirm_spend, 20, "image_enhance")
            if blocked:
                return blocked
            client = _client()
            task_id = client.submit_task(
                "/v1/tools/image-enhance/", {"image": resolve_image(image)}
            )
            return _maybe_wait_download(client, task_id, wait=wait, output_dir=output_dir)
        except (Studio3dError, FileNotFoundError, OSError) as exc:
            return f"Error: {exc}"

    @api.tool(name="studio3d_volume", intent=INTENT)
    def studio3d_volume(model_url: str, confirm_spend: bool = False,
        wait: bool = False, output_dir: str = "") -> str:
        """Calculate volume / material estimates (~20 credits, beta)."""
        try:
            blocked = credit_gate(confirm_spend, 20, "volume")
            if blocked:
                return blocked
            client = _client()
            task_id = client.submit_task(
                "/v1/tools/calculate-volume/", {"model_url": model_url.strip()}
            )
            return _maybe_wait_download(client, task_id, wait=wait, output_dir=output_dir)
        except Studio3dError as exc:
            return f"Error: {exc}"

    @api.tool(name="studio3d_miniature", intent=INTENT)
    def studio3d_miniature(
        image: str,
        preset: str,
        edition: str = "default",
        scale: str = "none",
        scale_height_cm: float = 0.0,
        face_count: int = 0,
        two_d_engine: str = "",
        three_d_engine: str = "",
        confirm_spend: bool = False,
        wait: bool = False,
        output_dir: str = "",
    ) -> str:
        """Photo → 3D-printable miniature (~200–300 credits). See skill for presets."""
        try:
            blocked = credit_gate(confirm_spend, 250, "miniature")
            if blocked:
                return blocked
            client = _client()
            payload: dict[str, Any] = {
                "image": resolve_image(image),
                "preset": preset.strip(),
                "edition": edition.strip() or "default",
            }
            sc = (scale or "none").strip()
            if sc and sc != "none":
                payload["scale"] = sc
            if scale_height_cm:
                payload["scale_height_cm"] = float(scale_height_cm)
            if face_count:
                payload["face_count"] = int(face_count)
            if two_d_engine.strip():
                payload["2d_engine"] = two_d_engine.strip()
            if three_d_engine.strip():
                payload["3d_engine"] = three_d_engine.strip()
            task_id = client.submit_task("/v1/flow/miniature/", payload)
            return _maybe_wait_download(client, task_id, wait=wait, output_dir=output_dir)
        except (Studio3dError, FileNotFoundError, OSError) as exc:
            return f"Error: {exc}"

    @api.tool(name="studio3d_import_glb_to_blender", intent=INTENT)
    def studio3d_import_glb_to_blender(url_or_path: str) -> str:
        """Download a GLB (if URL) and import it into the connected Blender scene."""
        try:
            src = (url_or_path or "").strip()
            if not src:
                return "Error: url_or_path is required"
            if src.startswith(("http://", "https://")):
                name = src.split("/")[-1].split("?")[0] or "model.glb"
                if not name.lower().endswith((".glb", ".gltf")):
                    name = f"{name}.glb"
                dest = Path(tempfile.gettempdir()) / "uefn-ducky-studio3d" / "imports" / name
                Studio3dClient().download_url(src, dest)
                local = str(dest.resolve())
            else:
                local = str(Path(src).expanduser().resolve())
                if not Path(local).is_file():
                    return f"Error: file not found: {local}"
            # Escape for embedding in Blender Python string
            escaped = local.replace("\\", "\\\\").replace("'", "\\'")
            code = (
                "import bpy\n"
                f"bpy.ops.import_scene.gltf(filepath=r'{escaped}')\n"
                "'imported'\n"
            )
            from .blender_import import execute_code

            result = execute_code(code)
            return _dumps({"ok": True, "path": local, "blender": result})
        except (Studio3dError, OSError, ConnectionError) as exc:
            return f"Error importing to Blender: {exc}"
        except Exception as exc:
            return f"Error importing to Blender: {exc}"

    api.log("studio3d tools registered")
