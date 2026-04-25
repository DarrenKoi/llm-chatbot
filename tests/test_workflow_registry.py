import json
import logging
import sys
from textwrap import dedent

from api import config
from api.logging_service import get_workflow_logger
from api.workflows import registry
from api.workflows.registry import discover_workflows, load_workflows


def _remove_tagged_handlers(logger: logging.Logger) -> None:
    handlers = list(logger.handlers)
    for handler in handlers:
        if getattr(handler, "_chatbot_handler_tag", "").startswith("chatbot."):
            logger.removeHandler(handler)
            handler.close()


def _reset_logger_state() -> None:
    from api.logging_service import service as logger_service

    logger_service._setup_done = False
    _remove_tagged_handlers(logging.getLogger())
    _remove_tagged_handlers(logging.getLogger("activity"))

    manager = logging.root.manager
    for name, logger_obj in manager.loggerDict.items():
        if isinstance(logger_obj, logging.Logger) and name.startswith("workflow."):
            _remove_tagged_handlers(logger_obj)


def _flush_handlers(logger: logging.Logger) -> None:
    for handler in logger.handlers:
        handler.flush()


def test_discover_workflows_loads_package_definitions(tmp_path):
    package_root = tmp_path / "samplepkg"
    workflows_dir = package_root / "workflows"
    alpha_dir = workflows_dir / "alpha_flow"
    beta_dir = workflows_dir / "beta_flow"
    helper_dir = workflows_dir / "helper_utils"

    alpha_dir.mkdir(parents=True)
    beta_dir.mkdir(parents=True)
    helper_dir.mkdir(parents=True)

    (package_root / "__init__.py").write_text("", encoding="utf-8")
    (workflows_dir / "__init__.py").write_text("", encoding="utf-8")
    (helper_dir / "__init__.py").write_text('"""not a workflow package."""\n', encoding="utf-8")

    (alpha_dir / "__init__.py").write_text(
        dedent(
            """
            def build_lg_graph():
                return None


            def get_workflow_definition():
                return {
                    "workflow_id": "alpha_flow",
                    "build_lg_graph": build_lg_graph,
                    "handoff_keywords": ("Alpha", "신규 업무"),
                    "tool_tags": (" Translation ", "LANGUAGE", "translation"),
                }
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    (beta_dir / "__init__.py").write_text(
        dedent(
            """
            def build_lg_graph():
                return None


            WORKFLOW_DEFINITION = {
                "workflow_id": "beta_flow",
                "build_lg_graph": build_lg_graph,
            }
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    sys.path.insert(0, str(tmp_path))
    try:
        workflows = discover_workflows(package_name="samplepkg.workflows")
    finally:
        sys.path.remove(str(tmp_path))
        for module_name in list(sys.modules):
            if module_name == "samplepkg" or module_name.startswith("samplepkg."):
                sys.modules.pop(module_name, None)

    assert sorted(workflows) == ["alpha_flow", "beta_flow"]
    assert workflows["alpha_flow"]["handoff_keywords"] == ("alpha", "신규 업무")
    assert workflows["alpha_flow"]["tool_tags"] == ("translation", "language")


def test_discover_workflows_uses_package_name_as_default_workflow_id(tmp_path):
    package_root = tmp_path / "samplepkg2"
    workflows_dir = package_root / "workflows"
    gamma_dir = workflows_dir / "gamma_flow"

    gamma_dir.mkdir(parents=True)

    (package_root / "__init__.py").write_text("", encoding="utf-8")
    (workflows_dir / "__init__.py").write_text("", encoding="utf-8")
    (gamma_dir / "__init__.py").write_text(
        dedent(
            """
            def build_lg_graph():
                return None


            WORKFLOW_DEFINITION = {
                "build_lg_graph": build_lg_graph,
            }
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    sys.path.insert(0, str(tmp_path))
    try:
        workflows = discover_workflows(package_name="samplepkg2.workflows")
    finally:
        sys.path.remove(str(tmp_path))
        for module_name in list(sys.modules):
            if module_name == "samplepkg2" or module_name.startswith("samplepkg2."):
                sys.modules.pop(module_name, None)

    assert "gamma_flow" in workflows
    assert workflows["gamma_flow"]["workflow_id"] == "gamma_flow"


def test_load_workflows_bootstraps_workflow_logs(tmp_path, monkeypatch):
    package_root = tmp_path / "samplepkg3"
    workflows_dir = package_root / "workflows"
    alpha_dir = workflows_dir / "alpha_flow"

    alpha_dir.mkdir(parents=True)

    (package_root / "__init__.py").write_text("", encoding="utf-8")
    (workflows_dir / "__init__.py").write_text("", encoding="utf-8")
    (alpha_dir / "__init__.py").write_text(
        dedent(
            """
            def build_lg_graph():
                return None


            WORKFLOW_DEFINITION = {
                "workflow_id": "alpha_flow",
                "build_lg_graph": build_lg_graph,
                "handoff_keywords": ("Alpha",),
                "tool_tags": ("translation", "language"),
            }
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(config, "LOG_DIR", tmp_path / "logs")
    monkeypatch.setattr(config, "LOG_TIMEZONE", "Asia/Seoul")
    monkeypatch.setattr(config, "LOG_RETENTION_DAYS", 7)
    _reset_logger_state()

    sys.path.insert(0, str(tmp_path))
    try:
        workflows = load_workflows(force_reload=True, package_name="samplepkg3.workflows")
        workflow_logger = get_workflow_logger("alpha_flow")
        _flush_handlers(workflow_logger)
    finally:
        registry._WORKFLOWS = None
        sys.path.remove(str(tmp_path))
        for module_name in list(sys.modules):
            if module_name == "samplepkg3" or module_name.startswith("samplepkg3."):
                sys.modules.pop(module_name, None)

    assert "alpha_flow" in workflows
    workflow_log_file = config.LOG_DIR / "workflows" / "alpha_flow" / "events.jsonl"
    assert workflow_log_file.exists()
    payload = json.loads(workflow_log_file.read_text(encoding="utf-8").splitlines()[0])
    assert payload["event"] == "workflow_registered"
    assert payload["workflow_id"] == "alpha_flow"
    assert payload["handoff_keywords"] == ["alpha"]
    assert payload["tool_tags"] == ["translation", "language"]
