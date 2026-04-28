"""로컬 워크플로 개발용 Flask 서버.

Production Flask 앱(port 5000)과 충돌하지 않도록 port 5001을 사용한다.
Dev runner는 자체 conversation_history 모듈로 대화 이력을 저장하므로 운영 설정을
건드리지 않는다.

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

from flask import Flask  # noqa: E402

from devtools.workflow_runner import conversation_history as _dev_history  # noqa: E402
from devtools.workflow_runner.routes import dev_bp  # noqa: E402


def create_dev_app() -> Flask:
    """Dev workflow runner Flask 앱을 생성한다."""

    _dev_history._ensure_dir()
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
    print(f"Conversation dir: {_dev_history._HISTORY_DIR}")
    print()

    app.run(host="0.0.0.0", port=port, debug=True)


if __name__ == "__main__":
    main()
