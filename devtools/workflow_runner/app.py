"""로컬 워크플로 개발용 Flask 서버.

Production Flask 앱(port 5000)과 충돌하지 않도록 port 5001을 사용한다.
api.* import 전에 WORKFLOW_STATE_DIR을 devtools/var/workflow_state로 설정하여
production 상태와 완전히 분리한다.

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

# api.* import 전에 dev 전용 상태 디렉토리 설정
os.environ.setdefault(
    "WORKFLOW_STATE_DIR",
    str(Path(__file__).resolve().parent.parent / "var" / "workflow_state"),
)

from flask import Flask  # noqa: E402

from devtools.workflow_runner.routes import dev_bp  # noqa: E402


def create_dev_app() -> Flask:
    """Dev workflow runner Flask 앱을 생성한다."""

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
    print(f"State dir: {os.environ.get('WORKFLOW_STATE_DIR')}")
    print()

    app.run(host="0.0.0.0", port=port, debug=True)


if __name__ == "__main__":
    main()
