from collections.abc import Iterable
from importlib import import_module
from pathlib import Path
from types import ModuleType

from flask import Blueprint

_ROUTER_EXPORT_NAMES = ("bp", "blueprint", "router", "router_bp")


def discover_blueprints(package_name: str = "api", package_path: Path | None = None) -> list[Blueprint]:
    """패키지 트리에서 router*.py 모듈을 자동 탐색하여 Flask Blueprint 목록을 반환한다.

    새 라우터를 추가할 때 수동 등록 없이 파일만 생성하면 자동으로 앱에 등록된다.
    """
    package_root = _resolve_package_root(package_name, package_path)
    blueprints: list[Blueprint] = []

    for module_path in _iter_router_modules(package_root):
        module_name = _module_name_from_path(package_name, package_root, module_path)
        module = import_module(module_name)
        blueprints.extend(_extract_blueprints(module, module_name))

    return blueprints


def _resolve_package_root(package_name: str, package_path: Path | None) -> Path:
    """패키지 이름 또는 경로로부터 패키지 루트 디렉토리를 반환한다."""
    if package_path is not None:
        return package_path.resolve()

    package = import_module(package_name)
    package_file = getattr(package, "__file__", None)
    if package_file is None:
        raise RuntimeError(f"Cannot resolve package root for {package_name!r}.")
    return Path(package_file).resolve().parent


def _iter_router_modules(package_root: Path) -> list[Path]:
    """패키지 루트 하위에서 router*.py 파일을 재귀적으로 탐색하여 정렬된 목록으로 반환한다."""
    router_paths = [
        path
        for path in package_root.rglob("router*.py")
        if path.is_file() and (path.stem == "router" or path.stem.startswith("router_"))
    ]
    return sorted(router_paths, key=_router_sort_key)


def _router_sort_key(path: Path) -> tuple[str, int, str]:
    """router.py가 router_*.py보다 먼저 로드되도록 정렬 키를 반환한다."""
    return (path.parent.as_posix(), 0 if path.stem == "router" else 1, path.name)


def _module_name_from_path(package_name: str, package_root: Path, module_path: Path) -> str:
    """파일 경로를 Python 모듈 경로 문자열(예: api.cube.router)로 변환한다."""
    relative = module_path.relative_to(package_root).with_suffix("")
    return ".".join((package_name, *relative.parts))


def _extract_blueprints(module: ModuleType, module_name: str) -> list[Blueprint]:
    """모듈에서 Blueprint 객체를 추출한다.

    우선순위: blueprints 속성 → 표준 이름(bp/blueprint/router 등) → 모듈 내 Blueprint 전체 탐색.
    Blueprint를 찾지 못하면 RuntimeError를 발생시킨다.
    """
    blueprints_attr = getattr(module, "blueprints", None)
    if blueprints_attr is not None:
        return _coerce_blueprints(blueprints_attr, module_name)

    for attr_name in _ROUTER_EXPORT_NAMES:
        candidate = getattr(module, attr_name, None)
        if isinstance(candidate, Blueprint):
            return [candidate]

    discovered = [value for value in module.__dict__.values() if isinstance(value, Blueprint)]
    if discovered:
        return discovered

    raise RuntimeError(
        f"Router module {module_name!r} must export a Flask Blueprint via "
        "'bp', 'blueprint', 'router', 'router_bp', or 'blueprints'."
    )


def _coerce_blueprints(value: object, module_name: str) -> list[Blueprint]:
    """blueprints 속성 값을 Blueprint 리스트로 변환하고 타입을 검증한다."""
    if not isinstance(value, Iterable) or isinstance(value, (str, bytes)):
        raise RuntimeError(f"Router module {module_name!r} has a non-iterable 'blueprints' export.")

    blueprints = list(value)
    if not all(isinstance(item, Blueprint) for item in blueprints):
        raise RuntimeError(f"Router module {module_name!r} has non-Blueprint entries in 'blueprints'.")
    return blueprints
