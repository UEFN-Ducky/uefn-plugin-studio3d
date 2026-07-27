"""3D AI Studio — Store desktop plugin (API tools on shared uefn-ducky MCP)."""

from __future__ import annotations

import logging

from . import studio3d

log = logging.getLogger("uefn.plugin.studio3d")
PLUGIN_ID = "studio3d"


def register(api) -> None:
    studio3d.register_tools(api)
    api.log("studio3d tools registered")
