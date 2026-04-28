"""Compatibility aliases for the former api.mcp package.

The MCP runtime moved to ``api.mcp_runtime``. Keep this package so persisted
workflow state and older workflow modules that import ``api.mcp.*`` continue to
load while deployments drain old checkpoints.
"""

import sys
from importlib import import_module

_runtime = import_module("api.mcp_runtime")
_runtime_public_api = tuple(getattr(_runtime, "__all__", ()))

for _name in _runtime_public_api:
    globals()[_name] = getattr(_runtime, _name)

_SUBMODULE_NAMES = (
    "client",
    "errors",
    "executor",
    "local_tools",
    "models",
    "registry",
    "tool_selector",
)

for _submodule_name in _SUBMODULE_NAMES:
    _submodule = import_module(f"api.mcp_runtime.{_submodule_name}")
    globals()[_submodule_name] = _submodule
    sys.modules[f"{__name__}.{_submodule_name}"] = _submodule

__all__ = [*_runtime_public_api, *_SUBMODULE_NAMES]
