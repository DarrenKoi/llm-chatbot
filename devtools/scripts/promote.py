"""dev 워크플로를 api/workflows/로 promotion(이동)하는 스크립트.

사용법:
    python -m devtools.scripts.promote my_workflow
"""

import re
import shutil
import sys
from importlib import import_module
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEV_WORKFLOWS_DIR = PROJECT_ROOT / "devtools" / "workflows"
DEV_MCP_DIR = PROJECT_ROOT / "devtools" / "mcp"
PROD_WORKFLOWS_DIR = PROJECT_ROOT / "api" / "workflows"
PROD_MCP_DIR = PROJECT_ROOT / "api" / "mcp"

WORKFLOW_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


def promote(workflow_id: str) -> None:
    # 0. Path traversal 방지
    if not WORKFLOW_ID_PATTERN.match(workflow_id):
        print(f"오류: workflow_id는 소문자, 숫자, 밑줄만 허용됩니다: {workflow_id}")
        sys.exit(1)

    source = DEV_WORKFLOWS_DIR / workflow_id
    target = PROD_WORKFLOWS_DIR / workflow_id
    mcp_source = _resolve_dev_mcp_source(workflow_id)
    mcp_target = _resolve_prod_mcp_target(mcp_source) if mcp_source else None

    # 1. 존재 확인
    if not source.exists():
        print(f"오류: dev 워크플로를 찾을 수 없습니다: {source}")
        sys.exit(1)

    if target.exists():
        print(f"오류: 운영 경로에 이미 동일 이름이 존재합니다: {target}")
        sys.exit(1)

    if mcp_target and mcp_target.exists():
        print(f"오류: 운영 MCP 경로에 이미 동일 이름이 존재합니다: {mcp_target}")
        sys.exit(1)

    # 2. 절대 import 잔존 검사 (상대 import 규칙 위반)
    absolute_pattern = f"devtools.workflows.{workflow_id}"
    violations: list[tuple[Path, int, str]] = []
    for py_file in source.glob("*.py"):
        for line_no, line in enumerate(py_file.read_text(encoding="utf-8").splitlines(), 1):
            if absolute_pattern in line:
                violations.append((py_file, line_no, line.strip()))

    if violations:
        print("경고: 절대 import가 발견되었습니다. promotion 후 import 오류가 발생할 수 있습니다.")
        for path, line_no, line in violations:
            print(f"  {path.name}:{line_no}  {line}")
        print()
        answer = input("그래도 진행할까요? (y/N): ").strip().lower()
        if answer != "y":
            print("취소됨.")
            sys.exit(0)

    # 3. 복사 후 검증 (실패 시 롤백)
    _copy_path(source, target)
    print(f"복사 완료: {source} -> {target}")

    if mcp_source and mcp_target:
        _copy_path(mcp_source, mcp_target)
        print(f"MCP 복사 완료: {mcp_source} -> {mcp_target}")

    _rewrite_import_prefix(target, old_prefix="devtools.mcp.", new_prefix="api.mcp.")
    if mcp_target:
        _rewrite_import_prefix(mcp_target, old_prefix="devtools.mcp.", new_prefix="api.mcp.")

    # 4. Import 검증
    print("import 검증 중...")
    try:
        definition = _validate_promoted_workflow(workflow_id)
        print(f"  workflow_id: {definition.get('workflow_id')}")
        print(f"  build_lg_graph: {callable(definition.get('build_lg_graph'))}")
        print("  import 검증 통과")
    except Exception as exc:
        # 검증 실패 시 롤백
        _remove_path(target)
        if mcp_target:
            _remove_path(mcp_target)
        print(f"  import 검증 실패: {exc}")
        print("  promotion을 롤백했습니다. dev 워크플로를 수정 후 다시 시도하세요.")
        sys.exit(1)

    # 5. 검증 통과 후 dev 소스 삭제
    _remove_path(source)
    print(f"dev 소스 삭제 완료: {source}")
    if mcp_source:
        _remove_path(mcp_source)
        print(f"dev MCP 삭제 완료: {mcp_source}")

    print()
    print("다음 단계:")
    print("  1. pytest tests/ -v 로 전체 테스트를 실행하세요.")
    print(f"  2. git add api/workflows/{workflow_id}/ api/mcp/{workflow_id}* 로 변경사항을 스테이징하세요.")
    print("  3. 코드 리뷰 후 배포하세요.")


def _resolve_dev_mcp_source(workflow_id: str) -> Path | None:
    file_candidate = DEV_MCP_DIR / f"{workflow_id}.py"
    dir_candidate = DEV_MCP_DIR / workflow_id
    matches = [candidate for candidate in (file_candidate, dir_candidate) if candidate.exists()]

    if len(matches) > 1:
        print(f"오류: dev MCP 소스가 파일/패키지 형태로 동시에 존재합니다: {workflow_id}")
        sys.exit(1)

    return matches[0] if matches else None


def _resolve_prod_mcp_target(source: Path) -> Path:
    return PROD_MCP_DIR / source.name


def _copy_path(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        shutil.copytree(str(source), str(target))
        return

    shutil.copy2(str(source), str(target))


def _remove_path(target: Path) -> None:
    if not target.exists():
        return
    if target.is_dir():
        shutil.rmtree(str(target), ignore_errors=True)
        return
    target.unlink()


def _rewrite_import_prefix(path: Path, *, old_prefix: str, new_prefix: str) -> None:
    if path.is_dir():
        py_files = path.rglob("*.py")
    elif path.suffix == ".py":
        py_files = [path]
    else:
        return

    for py_file in py_files:
        content = py_file.read_text(encoding="utf-8")
        updated = content.replace(old_prefix, new_prefix)
        if updated != content:
            py_file.write_text(updated, encoding="utf-8")


def _validate_promoted_workflow(workflow_id: str) -> dict[str, object]:
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

    workflow_module_path = f"api.workflows.{workflow_id}"
    mcp_module_path = f"api.mcp.{workflow_id}"
    _invalidate_import_cache(workflow_module_path)
    _invalidate_import_cache(mcp_module_path)

    if _resolve_prod_mcp_target_for_validation(workflow_id).exists():
        import_module(mcp_module_path)

    module = import_module(workflow_module_path)
    return module.get_workflow_definition()


def _invalidate_import_cache(module_path: str) -> None:
    sys.modules.pop(module_path, None)
    prefix = module_path + "."
    for loaded_module in [name for name in sys.modules if name.startswith(prefix)]:
        sys.modules.pop(loaded_module, None)


def _resolve_prod_mcp_target_for_validation(workflow_id: str) -> Path:
    file_candidate = PROD_MCP_DIR / f"{workflow_id}.py"
    dir_candidate = PROD_MCP_DIR / workflow_id
    if file_candidate.exists():
        return file_candidate
    return dir_candidate


def main() -> None:
    if len(sys.argv) != 2:
        print("사용법: python -m devtools.scripts.promote <workflow_id>")
        sys.exit(1)

    promote(sys.argv[1])


if __name__ == "__main__":
    main()
