"""Self-check for 3D AI Studio helpers (no live API calls)."""

from __future__ import annotations

import base64
import tempfile
from pathlib import Path

try:
    from .studio3d import (
        auth_header,
        credit_gate,
        encode_image,
        format_balance_detail,
        parse_status_payload,
        resolve_image,
        test_api_key as check_api_key,
    )
except ImportError:
    from studio3d import (
        auth_header,
        credit_gate,
        encode_image,
        format_balance_detail,
        parse_status_payload,
        resolve_image,
        test_api_key as check_api_key,
    )


def test_auth_header_bearer() -> None:
    h = auth_header("test-key-123")
    assert h["Authorization"] == "Bearer test-key-123"
    assert h["Content-Type"] == "application/json"


def test_parse_status_finished() -> None:
    parsed = parse_status_payload(
        {
            "status": "FINISHED",
            "progress": 100,
            "failure_reason": None,
            "results": [
                {
                    "asset": "https://storage.3daistudio.com/assets/model.glb",
                    "asset_type": "3D_MODEL",
                    "metadata": None,
                }
            ],
        }
    )
    assert parsed["finished"] is True
    assert parsed["failed"] is False
    assert len(parsed["results"]) == 1
    assert parsed["results"][0]["asset"].endswith("model.glb")


def test_parse_status_pending() -> None:
    parsed = parse_status_payload({"status": "PENDING", "progress": 0, "results": []})
    assert parsed["finished"] is False
    assert parsed["failed"] is False


def test_encode_and_resolve_image() -> None:
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "x.png"
        # minimal 1x1 PNG
        png = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
        )
        p.write_bytes(png)
        uri = encode_image(str(p))
        assert uri.startswith("data:image/png;base64,")
        assert resolve_image(str(p)).startswith("data:image/png;")
        assert resolve_image("https://example.com/a.png") == "https://example.com/a.png"
        assert resolve_image(uri) == uri


def test_credit_gate() -> None:
    msg = credit_gate(False, 35, "tripo") or ""
    assert "CREDIT GATE" in msg
    assert "ducky_ask_user" in msg
    assert credit_gate(True, 35, "tripo") is None
    assert credit_gate(False, 0, "free") is None


def test_format_balance_and_empty_key() -> None:
    assert "42" in format_balance_detail({"credits": 42})
    assert check_api_key("")["ok"] is False


if __name__ == "__main__":
    test_auth_header_bearer()
    test_parse_status_finished()
    test_parse_status_pending()
    test_encode_and_resolve_image()
    test_credit_gate()
    test_format_balance_and_empty_key()
    print("studio3d self-check ok")
