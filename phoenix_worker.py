"""uWSGI에 부착되는 Phoenix 관측성 서버 진입점."""

import os
import shutil
import sys
import tempfile
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
OFFICE_WORKSPACE_ROOT = Path("/project/workSpace")
DEFAULT_DATA_DIRECTORY_NAME = "phoenix-data"
DEFAULT_DATABASE_FILE_NAME = "phoenix.db"


def load_environment() -> None:
    """Phoenix CLI도 앱과 같은 루트 `.env`를 사용하도록 로드한다."""

    env_path = BASE_DIR / ".env"
    if not env_path.exists():
        return

    override = os.environ.get("DOTENV_OVERRIDE", "true").lower() in ("true", "1", "yes")
    load_dotenv(env_path, override=override)


def resolve_working_directory() -> Path:
    """Phoenix SQLite와 서버 데이터를 보존할 경로를 반환한다."""

    configured = os.environ.get("PHOENIX_WORKING_DIR", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()

    if OFFICE_WORKSPACE_ROOT.exists():
        return OFFICE_WORKSPACE_ROOT / DEFAULT_DATA_DIRECTORY_NAME
    return BASE_DIR / "var" / DEFAULT_DATA_DIRECTORY_NAME


def prepare_sqlite_storage() -> Path:
    """저장 경로를 만들고 쓰기 가능 여부를 실제로 확인한다.

    SQLite 파일과 schema migration은 Phoenix server가 처음 기동할 때
    자동으로 생성한다. 이 함수는 부모 디렉터리와 안정적인 DB URL만
    준비한다.
    """

    working_directory = resolve_working_directory()
    if working_directory.exists() and not working_directory.is_dir():
        raise RuntimeError(f"Phoenix working path is not a directory: {working_directory}")

    try:
        working_directory.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(prefix=".phoenix-write-test-", dir=working_directory):
            pass
    except OSError as exc:
        raise RuntimeError(f"Phoenix working directory is not writable: {working_directory}") from exc

    os.environ["PHOENIX_WORKING_DIR"] = str(working_directory)
    os.environ.setdefault(
        "PHOENIX_SQL_DATABASE_URL",
        f"sqlite:///{working_directory / DEFAULT_DATABASE_FILE_NAME}",
    )
    return working_directory


def resolve_phoenix_executable() -> Path:
    """Phoenix CLI 경로를 명시적 설정, 현재 venv, PATH 순으로 찾는다."""

    configured = os.environ.get("PHOENIX_EXECUTABLE", "").strip()
    if configured:
        configured_path = Path(configured).expanduser()
        if configured_path.is_file() and os.access(configured_path, os.X_OK):
            return configured_path.resolve()
        resolved = shutil.which(configured)
        if resolved:
            return Path(resolved).resolve()
        raise RuntimeError(f"PHOENIX_EXECUTABLE is not executable: {configured}")

    current_venv_candidate = Path(sys.executable).with_name("phoenix")
    if current_venv_candidate.is_file() and os.access(current_venv_candidate, os.X_OK):
        return current_venv_candidate.resolve()

    resolved = shutil.which("phoenix")
    if resolved:
        return Path(resolved).resolve()

    raise RuntimeError("Phoenix CLI was not found. Install arize-phoenix or set PHOENIX_EXECUTABLE.")


def main() -> int:
    """SQLite 저장소를 준비하고 현재 daemon process를 Phoenix로 교체한다."""

    load_environment()
    working_directory = prepare_sqlite_storage()
    executable = resolve_phoenix_executable()

    print(
        f"Starting Phoenix server: executable={executable} working_dir={working_directory}",
        flush=True,
    )
    os.execv(str(executable), [str(executable), "serve"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
