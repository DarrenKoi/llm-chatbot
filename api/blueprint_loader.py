from collections.abc import Iterable
from importlib import import_module
from pathlib import Path
from types import ModuleType

from flask import Blueprint

_ROUTER_EXPORT_NAMES = ("bp", "blueprint", "router", "router_bp")


def discover_blueprints(package_name: str = "api", package_path: Path | None = None) -> list[Blueprint]:
    """Discover Flask blueprints from router modules inside a package tree."""
    package_root = _resolve_package_root(package_name, package_path)
    blueprints: list[Blueprint] = []

    for module_path in _iter_router_modules(package_root):
        module_name = _module_name_from_path(package_name, package_root, module_path)
        module = import_module(module_name)
        blueprints.extend(_extract_blueprints(module, module_name))

    return blueprints


def _resolve_package_root(package_name: str, package_path: Path | None) -> Path:
    if package_path is not None:
        return package_path.resolve()

    package = import_module(package_name)
    package_file = getattr(package, "__file__", None)
    if package_file is None:
        raise RuntimeError(f"Cannot resolve package root for {package_name!r}.")
    return Path(package_file).resolve().parent


def _iter_router_modules(package_root: Path) -> list[Path]:
    router_paths = [
        path
        for path in package_root.rglob("router*.py")
        if path.is_file() and (path.stem == "router" or path.stem.startswith("router_"))
    ]
    return sorted(router_paths, key=_router_sort_key)


def _router_sort_key(path: Path) -> tuple[str, int, str]:
    return (path.parent.as_posix(), 0 if path.stem == "router" else 1, path.name)


def _module_name_from_path(package_name: str, package_root: Path, module_path: Path) -> str:
    relative = module_path.relative_to(package_root).with_suffix("")
    return ".".join((package_name, *relative.parts))


def _extract_blueprints(module: ModuleType, module_name: str) -> list[Blueprint]:
    blueprints_attr = getattr(module, "blueprints", None)
    if blueprints_attr is not None:
        return _coerce_blueprints(blueprints_attr, module_name)

    for attr_name in _ROUTER_EXPORT_NAMES:
        candidate = getattr(module, attr_name, None)
        if isinstance(candidate, Blueprint):
            return [candidate]

    discovered = [
        value
        for value in module.__dict__.values()
        if isinstance(value, Blueprint)
    ]
    if discovered:
        return discovered

    raise RuntimeError(
        f"Router module {module_name!r} must export a Flask Blueprint via "
        "'bp', 'blueprint', 'router', 'router_bp', or 'blueprints'."
    )


def _coerce_blueprints(value: object, module_name: str) -> list[Blueprint]:
    if not isinstance(value, Iterable) or isinstance(value, (str, bytes)):
        raise RuntimeError(f"Router module {module_name!r} has a non-iterable 'blueprints' export.")

    blueprints = list(value)
    if not all(isinstance(item, Blueprint) for item in blueprints):
        raise RuntimeError(f"Router module {module_name!r} has non-Blueprint entries in 'blueprints'.")
    return blueprints
