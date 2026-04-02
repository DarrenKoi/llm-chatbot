import sys
from textwrap import dedent

from api.workflows.registry import discover_workflows


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
            from api.workflows.models import WorkflowState


            class AlphaState(WorkflowState):
                pass


            def build_graph():
                return {
                    "workflow_id": "alpha_flow",
                    "entry_node_id": "entry",
                    "nodes": {"entry": lambda _state, _message: None},
                }


            def get_workflow_definition():
                return {
                    "workflow_id": "alpha_flow",
                    "entry_node_id": "entry",
                    "build_graph": build_graph,
                    "state_cls": AlphaState,
                    "handoff_keywords": ("Alpha", "신규 업무"),
                }
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    (beta_dir / "__init__.py").write_text(
        dedent(
            """
            def build_graph():
                return {
                    "workflow_id": "beta_flow",
                    "entry_node_id": "start",
                    "nodes": {"start": lambda _state, _message: None},
                }


            WORKFLOW_DEFINITION = {
                "workflow_id": "beta_flow",
                "entry_node_id": "start",
                "build_graph": build_graph,
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
    assert workflows["alpha_flow"]["entry_node_id"] == "entry"
    assert workflows["alpha_flow"]["handoff_keywords"] == ("alpha", "신규 업무")
    assert workflows["beta_flow"]["entry_node_id"] == "start"


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
            def build_graph():
                return {
                    "workflow_id": "gamma_flow",
                    "entry_node_id": "entry",
                    "nodes": {"entry": lambda _state, _message: None},
                }


            WORKFLOW_DEFINITION = {
                "entry_node_id": "entry",
                "build_graph": build_graph,
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
