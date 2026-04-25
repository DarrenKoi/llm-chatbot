"""/chat 경로에서 Nuxt 빌드 산출물(api/static/chat)을 서빙하는 Blueprint.

`api/static/chat/index.html`을 SPA 진입점으로 하고, 알 수 없는 하위 경로는
모두 동일 index.html로 떨어뜨려 Vue Router가 client-side 라우팅을 처리하도록 한다.
빌드 산출물은 .gitignore 대상이며, 실제 파일은 배포 단계에서 주입된다.
"""

from pathlib import Path

from flask import Blueprint, abort, send_from_directory

_STATIC_ROOT = Path(__file__).resolve().parent.parent / "static" / "chat"
_NUXT_ASSET_DIR = _STATIC_ROOT / "_nuxt"

bp = Blueprint("web_frontend", __name__)


@bp.route("/chat", methods=["GET"])
@bp.route("/chat/", methods=["GET"])
def chat_index():
    return _serve_spa_entry()


@bp.route("/chat/_nuxt/<path:asset_path>", methods=["GET"])
def chat_nuxt_asset(asset_path: str):
    """Nuxt 빌드가 만들어내는 _nuxt/ 자산을 서빙한다."""
    if not _NUXT_ASSET_DIR.exists():
        abort(404)
    return send_from_directory(_NUXT_ASSET_DIR, asset_path)


@bp.route("/chat/<path:rest>", methods=["GET"])
def chat_spa_fallback(rest: str):
    """SPA fallback — 정적 파일이 있으면 그대로, 없으면 index.html."""
    candidate = _STATIC_ROOT / rest
    if candidate.is_file():
        return send_from_directory(_STATIC_ROOT, rest)
    return _serve_spa_entry()


def _serve_spa_entry():
    index_file = _STATIC_ROOT / "index.html"
    if not index_file.is_file():
        abort(503, description="Web chat SPA build is not deployed.")
    return send_from_directory(_STATIC_ROOT, "index.html")
