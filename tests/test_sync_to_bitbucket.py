from pathlib import Path

import pytest

from scripts import sync_to_bitbucket
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


def test_main_copies_devtools_directory(tmp_path, monkeypatch, capsys):
    project_root = tmp_path / "project"
    destination = tmp_path / "share_repo"

    (project_root / "api").mkdir(parents=True)
    (project_root / "devtools" / "scripts").mkdir(parents=True)
    (destination / ".git").mkdir(parents=True)

    (project_root / "api" / "__init__.py").write_text("", encoding="utf-8")
    (project_root / "devtools" / "scripts" / "promote.py").write_text(
        "print('sync')\n",
        encoding="utf-8",
    )
    (project_root / "index.py").write_text("app = None\n", encoding="utf-8")
    (project_root / "cube_worker.py").write_text("cube = None\n", encoding="utf-8")
    (project_root / "scheduler_worker.py").write_text("scheduler = None\n", encoding="utf-8")

    monkeypatch.setattr(sync_to_bitbucket, "PROJECT_ROOT", project_root)
    monkeypatch.setattr(sync_to_bitbucket.platform, "system", lambda: "TestOS")
    monkeypatch.setattr(
        sync_to_bitbucket,
        "DEFAULT_DST",
        {"TestOS": destination},
    )
    monkeypatch.setattr("sys.argv", ["sync_to_bitbucket.py"])

    sync_to_bitbucket.main()

    captured = capsys.readouterr()
    assert "총 5개 파일 복사 완료" in captured.out
    assert (destination / "devtools" / "scripts" / "promote.py").exists()


def test_main_rejects_destination_argument(monkeypatch):
    monkeypatch.setattr("sys.argv", ["sync_to_bitbucket.py", "--dst", "C:/work/share_repo"])

    with pytest.raises(SystemExit) as exc_info:
        sync_to_bitbucket.main()

    assert exc_info.value.code == 2


def test_main_preserves_default_clean_paths_without_overwriting(tmp_path, monkeypatch):
    project_root = tmp_path / "project"
    destination = tmp_path / "share_repo"

    (project_root / "api" / "cube").mkdir(parents=True)
    (project_root / "api" / "mcp").mkdir(parents=True)
    (destination / ".git").mkdir(parents=True)
    (destination / "api" / "cube").mkdir(parents=True)
    (destination / "api" / "mcp").mkdir(parents=True)

    (project_root / "api" / "cube" / "service.py").write_text("cube = True\n", encoding="utf-8")
    (project_root / "api" / "mcp" / "client.py").write_text("source mcp\n", encoding="utf-8")
    (project_root / "index.py").write_text("app = None\n", encoding="utf-8")
    (project_root / "cube_worker.py").write_text("cube = None\n", encoding="utf-8")
    (project_root / "scheduler_worker.py").write_text("scheduler = None\n", encoding="utf-8")
    (destination / "api" / "cube" / "old.py").write_text("old = True\n", encoding="utf-8")
    (destination / "api" / "mcp" / "client.py").write_text("custom mcp\n", encoding="utf-8")
    (destination / "api" / "mcp" / "custom_only.py").write_text("custom only\n", encoding="utf-8")

    monkeypatch.setattr(sync_to_bitbucket, "PROJECT_ROOT", project_root)
    monkeypatch.setattr(sync_to_bitbucket.platform, "system", lambda: "TestOS")
    monkeypatch.setattr(sync_to_bitbucket, "DEFAULT_DST", {"TestOS": destination})
    monkeypatch.setattr("sys.argv", ["sync_to_bitbucket.py"])

    sync_to_bitbucket.main()

    assert not (destination / "api" / "cube" / "old.py").exists()
    assert (destination / "api" / "cube" / "service.py").read_text(encoding="utf-8") == "cube = True\n"
    assert (destination / "api" / "mcp" / "client.py").read_text(encoding="utf-8") == "custom mcp\n"
    assert (destination / "api" / "mcp" / "custom_only.py").read_text(encoding="utf-8") == "custom only\n"
