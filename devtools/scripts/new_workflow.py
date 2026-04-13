"""새 워크플로를 _template에서 scaffold하는 스크립트.

사용법:
    python -m devtools.scripts.new_workflow my_new_workflow
"""

import re
import shutil
import sys
from pathlib import Path

DEVTOOLS_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = DEVTOOLS_ROOT / "workflows" / "_template"
WORKFLOWS_DIR = DEVTOOLS_ROOT / "workflows"
MCP_TEMPLATE_FILE = DEVTOOLS_ROOT / "mcp" / "_template.py"
MCP_DIR = DEVTOOLS_ROOT / "mcp"

WORKFLOW_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


def _to_class_name(workflow_id: str) -> str:
    """snake_case workflow_id를 PascalCase 클래스 이름으로 변환한다."""

    return "".join(part.capitalize() for part in workflow_id.split("_")) + "State"


def scaffold(workflow_id: str) -> None:
    if not WORKFLOW_ID_PATTERN.match(workflow_id):
        print(f"오류: workflow_id는 소문자, 숫자, 밑줄만 허용됩니다: {workflow_id}")
        sys.exit(1)

    target_dir = WORKFLOWS_DIR / workflow_id
    if target_dir.exists():
        print(f"오류: 이미 존재하는 워크플로입니다: {target_dir}")
        sys.exit(1)

    if not TEMPLATE_DIR.exists():
        print(f"오류: 템플릿 디렉토리를 찾을 수 없습니다: {TEMPLATE_DIR}")
        sys.exit(1)

    if not MCP_TEMPLATE_FILE.exists():
        print(f"오류: MCP 템플릿 파일을 찾을 수 없습니다: {MCP_TEMPLATE_FILE}")
        sys.exit(1)

    state_class = _to_class_name(workflow_id)

    shutil.copytree(TEMPLATE_DIR, target_dir)

    for py_file in target_dir.glob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        content = content.replace("__WORKFLOW_ID__", workflow_id)
        content = content.replace("__STATE_CLASS__", state_class)
        py_file.write_text(content, encoding="utf-8")

    target_mcp_file = MCP_DIR / f"{workflow_id}.py"
    target_mcp_file.parent.mkdir(parents=True, exist_ok=True)

    if target_mcp_file.exists():
        print(f"오류: 이미 존재하는 dev MCP 모듈입니다: {target_mcp_file}")
        shutil.rmtree(target_dir, ignore_errors=True)
        sys.exit(1)

    mcp_content = MCP_TEMPLATE_FILE.read_text(encoding="utf-8")
    mcp_content = mcp_content.replace("__WORKFLOW_ID__", workflow_id)
    target_mcp_file.write_text(mcp_content, encoding="utf-8")

    print(f"워크플로를 생성했습니다: {target_dir}")
    print(f"dev MCP 모듈을 생성했습니다: {target_mcp_file}")
    print()
    print("다음 단계:")
    print(f"  1. {target_dir / 'lg_state.py'} 에서 LangGraph 상태 필드를 정의하세요.")
    print(f"  2. {target_dir / 'lg_graph.py'} 에서 노드와 StateGraph를 구현하세요.")
    print(f"  3. {target_mcp_file} 에서 MCP 도구 등록 함수를 구현하세요.")
    print("  5. python -m devtools.workflow_runner.app 으로 실행 후 테스트하세요.")
    print(f"  6. 완료 후 python -m devtools.scripts.promote {workflow_id} 로 운영 반영하세요.")


def main() -> None:
    if len(sys.argv) != 2:
        print("사용법: python -m devtools.scripts.new_workflow <workflow_id>")
        sys.exit(1)

    scaffold(sys.argv[1])


if __name__ == "__main__":
    main()
