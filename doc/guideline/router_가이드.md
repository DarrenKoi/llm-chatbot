# Router 시스템 가이드

## 목적

이 프로젝트는 Flask Blueprint를 수동으로 `import`해서 등록하지 않습니다.
대신 `api` 패키지 아래에서 `router.py`, `router_v1.py`, `router_v2.py` 같은 규칙의 파일을 자동 탐색해서 등록합니다.

즉, 새로운 API 라우트를 추가할 때는 앱 초기화 코드를 수정하지 않고, 정해진 이름으로 Router 파일만 만들면 됩니다.

## 적용 위치

- 자동 등록 시작점: `api/__init__.py`
- 탐색 로직: `api/blueprint_loader.py`

앱이 시작되면 `discover_blueprints()`가 실행되고, `api/` 아래의 Router 모듈들을 찾아 Flask Blueprint를 등록합니다.

## 파일명 규칙

자동 등록 대상은 아래 형식만 허용합니다.

- `router.py`
- `router_<version>.py`

예시:

- `api/cdn/router.py`
- `api/chat/router_v1.py`
- `api/chat/router_v2.py`

자동 등록되지 않는 예시:

- `routes.py`
- `api_router.py`
- `router-helper.py`
- `my_router.py`

핵심 규칙은 파일명이 반드시 `router`로 시작하고, 정확히 `router.py` 또는 `router_*.py` 형태여야 한다는 점입니다.

## 권장 구조

서비스별로 폴더를 나누고, 그 안에 Router 파일을 두는 방식을 권장합니다.

예시:

```text
api/
  cdn/
    __init__.py
    cdn_service.py
    router.py
  chat/
    __init__.py
    chat_service.py
    router_v1.py
    router_v2.py
```

이 구조를 쓰면 라우팅 코드와 서비스 로직이 자연스럽게 같은 영역에 모입니다.

## Blueprint export 규칙

가장 권장하는 방식은 `bp` 변수로 Blueprint를 export하는 것입니다.

예시:

```python
from flask import Blueprint, jsonify

bp = Blueprint("chat_v1", __name__)


@bp.route("/api/v1/chat/health", methods=["GET"])
def chat_health():
    return jsonify({"ok": True})
```

현재 자동 로더는 아래 export 이름도 지원합니다.

- `bp`
- `blueprint`
- `router`
- `router_bp`
- `blueprints`

하지만 팀 내 일관성을 위해 가능하면 `bp`만 사용하는 것을 권장합니다.

## 여러 Blueprint가 필요한 경우

한 파일에서 여러 Blueprint를 등록해야 하면 `blueprints` 리스트를 export할 수 있습니다.

예시:

```python
from flask import Blueprint

admin_bp = Blueprint("admin", __name__)
public_bp = Blueprint("public", __name__)

blueprints = [admin_bp, public_bp]
```

다만 관리 복잡도가 올라가므로, 특별한 이유가 없다면 Router 파일 하나당 Blueprint 하나를 권장합니다.

## 버전 관리 방식

버전이 하나뿐이면 `router.py`를 사용하면 됩니다.

예시:

- `api/cdn/router.py`

같은 도메인에서 API 버전이 늘어나면 아래처럼 확장할 수 있습니다.

- `router_v1.py`
- `router_v2.py`

예시:

```text
api/chat/router_v1.py
api/chat/router_v2.py
```

이때 URL path는 파일명이 아니라 Blueprint 내부의 `@bp.route(...)`에서 직접 결정합니다.

예시:

```python
@bp.route("/api/v1/chat/send", methods=["POST"])
```

```python
@bp.route("/api/v2/chat/send", methods=["POST"])
```

즉, `router_v2.py`라고 해서 자동으로 `/v2/`가 붙는 것은 아닙니다. URL version은 반드시 route path에서 명시해야 합니다.

## 등록 순서

자동 로더는 같은 폴더 안에서 아래 순서로 정렬합니다.

1. `router.py`
2. `router_*.py`

그 다음 파일명 기준으로 정렬합니다.

대부분의 경우 순서에 의존하지 않아야 하지만, 등록 순서를 이해해야 할 때는 이 규칙을 기준으로 보면 됩니다.

## 새 Router 추가 절차

1. 필요한 도메인 폴더를 만든다.
2. `router.py` 또는 `router_v1.py` 같은 이름으로 파일을 만든다.
3. `bp = Blueprint(...)`를 정의한다.
4. `@bp.route(...)`로 endpoint를 추가한다.
5. 앱 시작 코드에 별도 등록 코드를 추가하지 않는다.
6. 테스트를 작성하고 `pytest tests/ -v`로 검증한다.

## 예시

아래는 새 버전 Router를 추가하는 최소 예시입니다.

```python
from flask import Blueprint, jsonify

bp = Blueprint("chat_v2", __name__)


@bp.route("/api/v2/chat/ping", methods=["GET"])
def ping():
    return jsonify({"message": "pong"})
```

파일 위치 예시:

```text
api/chat/router_v2.py
```

이 파일을 저장하면 앱 시작 시 자동으로 탐색 및 등록됩니다.

## 주의사항

- `router.py` 또는 `router_*.py` 외의 이름은 자동 등록되지 않습니다.
- Blueprint를 export하지 않으면 앱 시작 시 오류가 납니다.
- URL version은 파일명이 아니라 route path에서 직접 관리해야 합니다.
- 수동 `app.register_blueprint(...)`를 추가하지 않는 것이 현재 규약입니다.
- 특별한 이유가 없다면 export 이름은 `bp`로 통일하는 것이 좋습니다.

## 현재 적용 예시

현재 CDN 라우트는 아래 파일을 사용합니다.

- `api/cdn/router.py`

이 파일은 자동 탐색되어 앱에 등록됩니다.
