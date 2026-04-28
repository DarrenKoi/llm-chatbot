import pytest

from devtools.scripts import new_workflow, promote


def test_new_workflow_scaffold_creates_matching_dev_mcp_module(tmp_path, monkeypatch):
    workflows_dir = tmp_path / "devtools" / "workflows"
    template_dir = workflows_dir / "_template"
    mcp_dir = tmp_path / "devtools" / "mcp_client"
    mcp_template_file = mcp_dir / "_template.py"

    template_dir.mkdir(parents=True)
    mcp_dir.mkdir(parents=True)

    (template_dir / "__init__.py").write_text(
        'WORKFLOW_ID = "__WORKFLOW_ID__"\nSTATE = "__STATE_CLASS__"\n',
        encoding="utf-8",
    )
    (template_dir / "lg_state.py").write_text(
        "class __STATE_CLASS__:\n    pass\n",
        encoding="utf-8",
    )
    (template_dir / "lg_graph.py").write_text(
        "from devtools.mcp_client.__WORKFLOW_ID__ import register_tools\n"
        "def build_lg_graph():\n"
        "    register_tools()\n"
        "    return {'workflow_id': '__WORKFLOW_ID__'}\n",
        encoding="utf-8",
    )
    mcp_template_file.write_text(
        'WORKFLOW_ID = "__WORKFLOW_ID__"\n',
        encoding="utf-8",
    )

    monkeypatch.setattr(new_workflow, "WORKFLOWS_DIR", workflows_dir)
    monkeypatch.setattr(new_workflow, "TEMPLATE_DIR", template_dir)
    monkeypatch.setattr(new_workflow, "MCP_DIR", mcp_dir)
    monkeypatch.setattr(new_workflow, "MCP_TEMPLATE_FILE", mcp_template_file)

    new_workflow.scaffold("sample_flow")

    scaffolded_dir = workflows_dir / "sample_flow"
    scaffolded_mcp = mcp_dir / "sample_flow.py"

    assert scaffolded_dir.exists()
    assert scaffolded_mcp.exists()
    assert 'WORKFLOW_ID = "sample_flow"' in (scaffolded_dir / "__init__.py").read_text(encoding="utf-8")
    assert 'STATE = "SampleFlowState"' in (scaffolded_dir / "__init__.py").read_text(encoding="utf-8")
    assert "from devtools.mcp_client.sample_flow import register_tools" in (scaffolded_dir / "lg_graph.py").read_text(
        encoding="utf-8"
    )
    assert 'WORKFLOW_ID = "sample_flow"' in scaffolded_mcp.read_text(encoding="utf-8")


def test_promote_moves_matching_dev_mcp_module_and_rewrites_imports(tmp_path, monkeypatch):
    project_root = tmp_path
    dev_workflows_dir = project_root / "devtools" / "workflows"
    dev_mcp_dir = project_root / "devtools" / "mcp_client"
    prod_workflows_dir = project_root / "api" / "workflows"
    prod_mcp_dir = project_root / "api" / "mcp_client"
    workflow_source = dev_workflows_dir / "sample_flow"
    workflow_source.mkdir(parents=True)
    dev_mcp_dir.mkdir(parents=True)

    (workflow_source / "__init__.py").write_text(
        "from devtools.mcp_client.sample_flow import register_tools\n",
        encoding="utf-8",
    )
    (workflow_source / "lg_graph.py").write_text("def build_lg_graph():\n    return {}\n", encoding="utf-8")
    (dev_mcp_dir / "sample_flow.py").write_text(
        'IMPORT_PATH = "devtools.mcp_client.sample_flow"\n',
        encoding="utf-8",
    )

    monkeypatch.setattr(promote, "PROJECT_ROOT", project_root)
    monkeypatch.setattr(promote, "DEV_WORKFLOWS_DIR", dev_workflows_dir)
    monkeypatch.setattr(promote, "DEV_MCP_DIR", dev_mcp_dir)
    monkeypatch.setattr(promote, "PROD_WORKFLOWS_DIR", prod_workflows_dir)
    monkeypatch.setattr(promote, "PROD_MCP_DIR", prod_mcp_dir)
    monkeypatch.setattr(
        promote,
        "_validate_promoted_workflow",
        lambda workflow_id: {"workflow_id": workflow_id, "build_lg_graph": object()},
    )

    promote.promote("sample_flow")

    workflow_target = prod_workflows_dir / "sample_flow"
    mcp_target = prod_mcp_dir / "sample_flow.py"

    assert workflow_target.exists()
    assert mcp_target.exists()
    assert not workflow_source.exists()
    assert not (dev_mcp_dir / "sample_flow.py").exists()
    assert "from api.mcp_client.sample_flow import register_tools" in (workflow_target / "__init__.py").read_text(
        encoding="utf-8"
    )
    assert 'IMPORT_PATH = "api.mcp_client.sample_flow"' in mcp_target.read_text(encoding="utf-8")


def test_promote_rolls_back_targets_when_validation_fails(tmp_path, monkeypatch):
    project_root = tmp_path
    dev_workflows_dir = project_root / "devtools" / "workflows"
    dev_mcp_dir = project_root / "devtools" / "mcp_client"
    prod_workflows_dir = project_root / "api" / "workflows"
    prod_mcp_dir = project_root / "api" / "mcp_client"

    workflow_source = dev_workflows_dir / "sample_flow"
    workflow_source.mkdir(parents=True)
    dev_mcp_dir.mkdir(parents=True)

    (workflow_source / "__init__.py").write_text(
        "from devtools.mcp_client.sample_flow import register_tools\n",
        encoding="utf-8",
    )
    (dev_mcp_dir / "sample_flow.py").write_text("def register_tools():\n    return None\n", encoding="utf-8")

    monkeypatch.setattr(promote, "PROJECT_ROOT", project_root)
    monkeypatch.setattr(promote, "DEV_WORKFLOWS_DIR", dev_workflows_dir)
    monkeypatch.setattr(promote, "DEV_MCP_DIR", dev_mcp_dir)
    monkeypatch.setattr(promote, "PROD_WORKFLOWS_DIR", prod_workflows_dir)
    monkeypatch.setattr(promote, "PROD_MCP_DIR", prod_mcp_dir)

    def _raise_validation_error(_workflow_id: str) -> dict[str, object]:
        raise RuntimeError("boom")

    monkeypatch.setattr(promote, "_validate_promoted_workflow", _raise_validation_error)

    with pytest.raises(SystemExit) as exc_info:
        promote.promote("sample_flow")

    assert exc_info.value.code == 1
    assert workflow_source.exists()
    assert (dev_mcp_dir / "sample_flow.py").exists()
    assert not (prod_workflows_dir / "sample_flow").exists()
    assert not (prod_mcp_dir / "sample_flow.py").exists()


def test_validate_promoted_workflow_imports_matching_mcp_module(tmp_path, monkeypatch):
    prod_mcp_dir = tmp_path / "api" / "mcp_client"
    prod_mcp_dir.mkdir(parents=True)
    (prod_mcp_dir / "sample_flow.py").write_text("REGISTERED = True\n", encoding="utf-8")

    monkeypatch.setattr(promote, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(promote, "PROD_MCP_DIR", prod_mcp_dir)

    imported_modules: list[str] = []

    class _WorkflowModule:
        @staticmethod
        def get_workflow_definition() -> dict[str, object]:
            return {"workflow_id": "sample_flow", "build_lg_graph": object()}

    def _fake_import_module(module_path: str):
        imported_modules.append(module_path)
        if module_path == "api.workflows.sample_flow":
            return _WorkflowModule()
        if module_path == "api.mcp_client.sample_flow":
            return object()
        raise AssertionError(module_path)

    monkeypatch.setattr(promote, "import_module", _fake_import_module)

    definition = promote._validate_promoted_workflow("sample_flow")

    assert definition["workflow_id"] == "sample_flow"
    assert imported_modules == ["api.mcp_client.sample_flow", "api.workflows.sample_flow"]
