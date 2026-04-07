"""로컬 워크플로 개발용 Flask 서버.

Production Flask 앱(port 5000)과 충돌하지 않도록 port 5001을 사용한다.
Dev runner 내부에서는 workflow state와 대화 이력을 각각 devtools 전용 로컬 경로로
분리하여 production 설정과 섞이지 않게 한다.

사용법:
    python -m devtools.workflow_runner.app
"""

import os
import sys
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가 (직접 실행 시 필요)
_project_root = Path(__file__).resolve().parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

_dev_root = Path(__file__).resolve().parent.parent / "var"
_dev_workflow_state_dir = _dev_root / "workflow_state"
_dev_conversation_dir = _dev_root / "conversation_history"

from flask import Flask  # noqa: E402

from devtools.workflow_runner.routes import dev_bp  # noqa: E402


def _configure_dev_runtime() -> None:
    from api import config, conversation_service
    from api.workflows import state_service

    config.WORKFLOW_STATE_DIR = _dev_workflow_state_dir
    config.CONVERSATION_BACKEND = "local"
    config.CONVERSATION_LOCAL_DIR = _dev_conversation_dir
    state_service.WORKFLOW_STATE_DIR = _dev_workflow_state_dir
    conversation_service._backend = None

    _dev_workflow_state_dir.mkdir(parents=True, exist_ok=True)
    _dev_conversation_dir.mkdir(parents=True, exist_ok=True)


def create_dev_app() -> Flask:
    """Dev workflow runner Flask 앱을 생성한다."""

    _configure_dev_runtime()
    template_dir = Path(__file__).resolve().parent / "templates"

    app = Flask(
        __name__,
        template_folder=str(template_dir),
    )

    app.register_blueprint(dev_bp)

    return app


def main() -> None:
    """Dev runner 서버를 시작한다."""

    port = int(os.environ.get("DEV_RUNNER_PORT", "5001"))
    app = create_dev_app()

    print("=== Dev Workflow Runner ===")
    print(f"http://localhost:{port}")
    print(f"State dir: {_dev_workflow_state_dir}")
    print(f"Conversation dir: {_dev_conversation_dir}")
    print()

    app.run(host="0.0.0.0", port=port, debug=True)


if __name__ == "__main__":
    main()
