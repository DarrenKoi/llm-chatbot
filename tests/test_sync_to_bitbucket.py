from pathlib import Path

from scripts.sync_to_bitbucket import copy_entry, is_excluded_by_path, normalize_entry_path


def test_is_excluded_by_path_matches_nested_directories():
    exclude_paths = [
        normalize_entry_path("api/mcp/"),
        normalize_entry_path("api/workflows/"),
    ]

    assert is_excluded_by_path(Path("api/mcp/client.py"), exclude_paths)
    assert is_excluded_by_path(Path("api/workflows/start_chat/graph.py"), exclude_paths)
    assert not is_excluded_by_path(Path("api/cube/service.py"), exclude_paths)


def test_copy_entry_skips_excluded_directories(tmp_path):
    src = tmp_path / "src"
    dst = tmp_path / "dst"

    (src / "api" / "cube").mkdir(parents=True)
    (src / "api" / "mcp").mkdir(parents=True)
    (src / "api" / "workflows").mkdir(parents=True)
    dst.mkdir()

    (src / "api" / "cube" / "service.py").write_text("cube = True\n", encoding="utf-8")
    (src / "api" / "mcp" / "client.py").write_text("mcp = True\n", encoding="utf-8")
    (src / "api" / "workflows" / "graph.py").write_text("workflow = True\n", encoding="utf-8")

    copied = copy_entry(
        src=src,
        dst=dst,
        entry="api/",
        dry_run=False,
        exclude_paths=[
            normalize_entry_path("api/mcp/"),
            normalize_entry_path("api/workflows/"),
        ],
    )

    assert copied == 1
    assert (dst / "api" / "cube" / "service.py").exists()
    assert not (dst / "api" / "mcp" / "client.py").exists()
    assert not (dst / "api" / "workflows" / "graph.py").exists()
