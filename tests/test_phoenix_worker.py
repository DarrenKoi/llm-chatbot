import os

import pytest

import phoenix_worker


def test_prepare_sqlite_storage_creates_directory_and_database_url(tmp_path, monkeypatch):
    working_directory = tmp_path / "phoenix" / "data"
    monkeypatch.setenv("PHOENIX_WORKING_DIR", str(working_directory))
    monkeypatch.delenv("PHOENIX_SQL_DATABASE_URL", raising=False)

    resolved = phoenix_worker.prepare_sqlite_storage()

    assert resolved == working_directory
    assert working_directory.is_dir()
    assert os.environ["PHOENIX_WORKING_DIR"] == str(working_directory)
    assert os.environ["PHOENIX_SQL_DATABASE_URL"] == f"sqlite:///{working_directory / 'phoenix.db'}"
    assert not (working_directory / "phoenix.db").exists()


def test_prepare_sqlite_storage_preserves_explicit_database_url(tmp_path, monkeypatch):
    working_directory = tmp_path / "phoenix"
    database_url = "postgresql://phoenix.example.internal/phoenix"
    monkeypatch.setenv("PHOENIX_WORKING_DIR", str(working_directory))
    monkeypatch.setenv("PHOENIX_SQL_DATABASE_URL", database_url)

    phoenix_worker.prepare_sqlite_storage()

    assert os.environ["PHOENIX_SQL_DATABASE_URL"] == database_url


def test_prepare_sqlite_storage_rejects_file_path(tmp_path, monkeypatch):
    working_path = tmp_path / "not-a-directory"
    working_path.write_text("occupied", encoding="utf-8")
    monkeypatch.setenv("PHOENIX_WORKING_DIR", str(working_path))

    with pytest.raises(RuntimeError, match="not a directory"):
        phoenix_worker.prepare_sqlite_storage()


def test_resolve_phoenix_executable_uses_explicit_path(tmp_path, monkeypatch):
    executable = tmp_path / "phoenix"
    executable.write_text("#!/bin/sh\n", encoding="utf-8")
    executable.chmod(0o755)
    monkeypatch.setenv("PHOENIX_EXECUTABLE", str(executable))

    assert phoenix_worker.resolve_phoenix_executable() == executable.resolve()


def test_resolve_phoenix_executable_rejects_invalid_explicit_path(tmp_path, monkeypatch):
    monkeypatch.setenv("PHOENIX_EXECUTABLE", str(tmp_path / "missing-phoenix"))
    monkeypatch.setattr(phoenix_worker.shutil, "which", lambda _command: None)

    with pytest.raises(RuntimeError, match="PHOENIX_EXECUTABLE is not executable"):
        phoenix_worker.resolve_phoenix_executable()


def test_main_executes_phoenix_serve(tmp_path, monkeypatch):
    working_directory = tmp_path / "data"
    executable = tmp_path / "phoenix"
    executable.write_text("#!/bin/sh\n", encoding="utf-8")
    executable.chmod(0o755)

    monkeypatch.setattr(phoenix_worker, "load_environment", lambda: None)
    monkeypatch.setenv("PHOENIX_WORKING_DIR", str(working_directory))
    monkeypatch.setenv("PHOENIX_EXECUTABLE", str(executable))
    calls: list[tuple[str, list[str]]] = []
    monkeypatch.setattr(phoenix_worker.os, "execv", lambda path, args: calls.append((path, args)))

    assert phoenix_worker.main() == 0
    assert calls == [(str(executable.resolve()), [str(executable.resolve()), "serve"])]
