"""dev 워크플로를 api/workflows/로 promotion(이동)하는 스크립트.

사용법:
    python -m devtools.scripts.promote my_workflow
"""

import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEV_WORKFLOWS_DIR = PROJECT_ROOT / "devtools" / "workflows"
PROD_WORKFLOWS_DIR = PROJECT_ROOT / "api" / "workflows"
DEV_STATE_DIR = PROJECT_ROOT / "devtools" / "var" / "workflow_state"


def promote(workflow_id: str) -> None:
    source = DEV_WORKFLOWS_DIR / workflow_id
    target = PROD_WORKFLOWS_DIR / workflow_id

    # 1. 존재 확인
    if not source.exists():
        print(f"오류: dev 워크플로를 찾을 수 없습니다: {source}")
        sys.exit(1)

    if target.exists():
        print(f"오류: 운영 경로에 이미 동일 이름이 존재합니다: {target}")
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

    # 3. 이동
    shutil.move(str(source), str(target))
    print(f"이동 완료: {source} -> {target}")

    # 4. Import 검증
    print("import 검증 중...")
    try:
        # sys.path에 프로젝트 루트가 있어야 함
        if str(PROJECT_ROOT) not in sys.path:
            sys.path.insert(0, str(PROJECT_ROOT))

        module_path = f"api.workflows.{workflow_id}"
        module = __import__(module_path, fromlist=["get_workflow_definition"])
        definition = module.get_workflow_definition()
        print(f"  workflow_id: {definition.get('workflow_id')}")
        print(f"  entry_node_id: {definition.get('entry_node_id')}")
        print("  import 검증 통과")
    except Exception as exc:
        print(f"  import 검증 실패: {exc}")
        print(f"  수동으로 확인하세요: {target}")

    # 5. Dev state 정리
    _cleanup_dev_state(workflow_id)

    print()
    print("다음 단계:")
    print(f"  1. pytest tests/ -v 로 전체 테스트를 실행하세요.")
    print(f"  2. git add api/workflows/{workflow_id}/ 로 변경사항을 스테이징하세요.")
    print(f"  3. 코드 리뷰 후 배포하세요.")


def _cleanup_dev_state(workflow_id: str) -> None:
    """dev 전용 state 파일을 정리한다."""

    if not DEV_STATE_DIR.exists():
        return

    cleaned = 0
    for state_file in DEV_STATE_DIR.glob("*.json"):
        try:
            import json
            data = json.loads(state_file.read_text(encoding="utf-8"))
            if data.get("workflow_id") == workflow_id:
                state_file.unlink()
                cleaned += 1
        except Exception:
            pass

    if cleaned:
        print(f"dev state {cleaned}개 정리 완료.")


def main() -> None:
    if len(sys.argv) != 2:
        print("사용법: python -m devtools.scripts.promote <workflow_id>")
        sys.exit(1)

    promote(sys.argv[1])


if __name__ == "__main__":
    main()
