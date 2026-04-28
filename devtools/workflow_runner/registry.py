"""dev runner 측 워크플로 발견 유틸 (mirror of api/workflows/registry.py).

이 파일은 ``api/workflows/registry.py``의 mirror 사본 중 ``discover_workflows`` 경로만
복제한 것이다. ``HARNESS.md``의 "api/ ↔ devtools/ 격리 정책"에 따라 두 파일을 같은
PR에서 함께 업데이트해야 한다.

api 측과의 차이:
- ``log_workflow_activity`` 호출 제거 (dev runner는 워크플로 등록 로깅이 필요 없음).
- ``tool_tags`` 정규화는 단순 ``tuple()``로 처리 (dev에서는 prod 구조 검증이 불필요).
- ``load_workflows`` / ``list_handoff_workflows`` / ``get_workflow``는 mirror하지 않음
  (dev runner는 ``discover_workflows`` 결과만 직접 캐싱한다).
"""

import logging
import pkgutil
from collections.abc import Callable, Iterable
from importlib import import_module
from pathlib import Path
from types import ModuleType
from typing import Any

log = logging.getLogger(__name__)

WorkflowDefinition = dict[str, Any]
WorkflowBuilder = Callable[[], WorkflowDefinition]


def discover_workflows(
    package_name: str = "devtools.workflows",
    package_path: Path | None = None,
) -> dict[str, WorkflowDefinition]:
    """워크플로 패키지를 스캔해 정의 목록을 반환한다."""

    package = import_module(package_name)
    package_paths = _resolve_package_paths(package, package_path)
    workflows: dict[str, WorkflowDefinition] = {}

    module_infos = sorted(
        pkgutil.iter_modules(package_paths, package_name + "."),
        key=lambda item: item.name,
    )

    for module_info in module_infos:
        short_name = module_info.name.rsplit(".", 1)[-1]
        if not module_info.ispkg or short_name.startswith("_"):
            continue

        module = import_module(module_info.name)
        definition = _extract_workflow_definition(module, short_name)
        if definition is None:
            continue

        workflow_id = definition["workflow_id"]
        if workflow_id in workflows:
            raise RuntimeError(f"중복 workflow_id가 발견되었습니다: {workflow_id}")
        workflows[workflow_id] = definition

    return workflows


def _resolve_package_paths(package: ModuleType, package_path: Path | None) -> list[str]:
    if package_path is not None:
        return [str(package_path.resolve())]

    package_paths = list(getattr(package, "__path__", []))
    if not package_paths:
        raise RuntimeError(f"워크플로 패키지 경로를 찾을 수 없습니다: {package.__name__}")
    return package_paths


def _extract_workflow_definition(
    module: ModuleType,
    default_workflow_id: str,
) -> WorkflowDefinition | None:
    definition_factory = getattr(module, "get_workflow_definition", None)
    if callable(definition_factory):
        raw_definition = definition_factory()
    else:
        raw_definition = getattr(module, "WORKFLOW_DEFINITION", None)

    if raw_definition is None:
        log.debug("워크플로 정의 export가 없어 건너뜁니다: %s", module.__name__)
        return None

    return _normalize_workflow_definition(
        raw_definition=raw_definition,
        default_workflow_id=default_workflow_id,
        module_name=module.__name__,
    )


def _normalize_workflow_definition(
    *,
    raw_definition: object,
    default_workflow_id: str,
    module_name: str,
) -> WorkflowDefinition:
    if not isinstance(raw_definition, dict):
        raise RuntimeError(f"워크플로 정의는 dict여야 합니다: {module_name}")

    definition = dict(raw_definition)
    definition["workflow_id"] = str(definition.get("workflow_id") or default_workflow_id)

    build_lg_graph = definition.get("build_lg_graph")
    if not callable(build_lg_graph):
        raise RuntimeError(f"워크플로 build_lg_graph가 필요합니다: {module_name}")

    definition.pop("state_cls", None)
    definition["handoff_keywords"] = _normalize_keywords(
        definition.get("handoff_keywords", ()),
        module_name=module_name,
    )
    definition["tool_tags"] = _normalize_tool_tags(definition.get("tool_tags", ()))
    return definition


def _normalize_keywords(keywords: object, *, module_name: str) -> tuple[str, ...]:
    if keywords in (None, ""):
        return ()
    if isinstance(keywords, (str, bytes)) or not isinstance(keywords, Iterable):
        raise RuntimeError(f"handoff_keywords는 문자열 iterable이어야 합니다: {module_name}")

    normalized: list[str] = []
    for keyword in keywords:
        value = str(keyword).strip().lower()
        if value:
            normalized.append(value)
    return tuple(normalized)


def _normalize_tool_tags(tool_tags: object) -> tuple[str, ...]:
    if tool_tags in (None, ""):
        return ()
    if isinstance(tool_tags, (str, bytes)) or not isinstance(tool_tags, Iterable):
        return ()
    return tuple(str(tag).strip() for tag in tool_tags if str(tag).strip())
