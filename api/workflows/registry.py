"""워크플로 패키지를 동적으로 발견하고 정의를 조회한다."""

import logging
import pkgutil
from collections.abc import Callable, Iterable
from importlib import import_module
from pathlib import Path
from types import ModuleType
from typing import Any

from api.utils.logger import log_workflow_activity
from api.workflows.models import WorkflowState

log = logging.getLogger(__name__)

WorkflowDefinition = dict[str, Any]
WorkflowBuilder = Callable[[], WorkflowDefinition]

_WORKFLOWS: dict[str, WorkflowDefinition] | None = None


def discover_workflows(
    package_name: str = "api.workflows",
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


def load_workflows(
    *,
    force_reload: bool = False,
    package_name: str = "api.workflows",
    package_path: Path | None = None,
) -> dict[str, WorkflowDefinition]:
    """워크플로 정의 캐시를 로드한다."""

    global _WORKFLOWS

    if force_reload or _WORKFLOWS is None:
        _WORKFLOWS = discover_workflows(package_name=package_name, package_path=package_path)
        _bootstrap_workflow_logging(_WORKFLOWS)

    return _WORKFLOWS


def list_workflow_ids() -> list[str]:
    """등록된 모든 workflow_id 목록을 반환한다."""

    return sorted(load_workflows().keys())


def list_handoff_workflows() -> list[WorkflowDefinition]:
    """start_chat에서 handoff 가능한 워크플로 정의만 반환한다."""

    return [definition for definition in load_workflows().values() if definition.get("handoff_keywords")]


def get_workflow(workflow_id: str) -> WorkflowDefinition:
    """등록된 workflow graph / entrypoint를 반환한다."""

    try:
        return load_workflows()[workflow_id]
    except KeyError as exc:
        raise KeyError(f"등록되지 않은 workflow_id입니다: {workflow_id}") from exc


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

    build_graph = definition.get("build_graph")
    if not callable(build_graph):
        raise RuntimeError(f"워크플로 build_graph가 필요합니다: {module_name}")

    entry_node_id = definition.get("entry_node_id")
    if not isinstance(entry_node_id, str) or not entry_node_id:
        raise RuntimeError(f"워크플로 entry_node_id가 필요합니다: {module_name}")

    definition["state_cls"] = _normalize_state_cls(definition.get("state_cls"), module_name)
    definition["handoff_keywords"] = _normalize_keywords(
        definition.get("handoff_keywords", ()),
        module_name=module_name,
    )
    definition["tool_tags"] = _normalize_tags(
        definition.get("tool_tags", ()),
        field_name="tool_tags",
        module_name=module_name,
    )
    return definition


def _normalize_state_cls(candidate: object, module_name: str) -> type[WorkflowState]:
    if candidate is None:
        return WorkflowState
    if isinstance(candidate, type) and issubclass(candidate, WorkflowState):
        return candidate
    raise RuntimeError(f"워크플로 state_cls는 WorkflowState 하위 클래스여야 합니다: {module_name}")


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


def _normalize_tags(raw_tags: object, *, field_name: str, module_name: str) -> tuple[str, ...]:
    if raw_tags in (None, ""):
        return ()
    if isinstance(raw_tags, str):
        candidates = [raw_tags]
    elif isinstance(raw_tags, Iterable):
        candidates = raw_tags
    else:
        raise RuntimeError(f"{field_name}는 문자열 iterable이어야 합니다: {module_name}")

    normalized: list[str] = []
    seen: set[str] = set()
    for tag in candidates:
        value = str(tag).strip().lower()
        if not value or value in seen:
            continue
        normalized.append(value)
        seen.add(value)
    return tuple(normalized)


def _bootstrap_workflow_logging(workflows: dict[str, WorkflowDefinition]) -> None:
    """Prime per-workflow structured logging for newly discovered workflow packages."""

    for workflow_id, definition in workflows.items():
        state_cls = definition.get("state_cls", WorkflowState)
        log_workflow_activity(
            workflow_id,
            "workflow_registered",
            entry_node_id=definition["entry_node_id"],
            state_class=getattr(state_cls, "__name__", str(state_cls)),
            handoff_keywords=list(definition.get("handoff_keywords", ())),
            tool_tags=list(definition.get("tool_tags", ())),
        )
