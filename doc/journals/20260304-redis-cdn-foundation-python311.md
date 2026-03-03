# 2026-03-04 작업 저널

## 1. 진행 사항
- Redis 서버 2대 정보를 환경설정에 반영하고, 대화 이력 저장에서 primary/secondary 순차 연결을 구현했다.
  - primary: `10.156.133.129:10108`
  - secondary: `10.156.133.126:10121`
- `api/config.py`에서 환경 파일 로딩 규칙을 정리했다.
  - 업무 환경: `.env` 우선
  - 홈 코딩/기본값: `.env.example` 폴백
- CDN 기초 기능을 신규 구축했다.
  - 엔드포인트: `POST /api/v1/cdn/upload`, `GET /cdn/images/<image_id>`
  - 업로드 방식: `multipart/form-data`의 `file` 필드
  - 저장 방식: 이미지 파일 저장 + 메타데이터 저장(Redis 또는 in-memory 폴백)
- PVC 루트 경로 정책을 반영했다.
  - 기본 PVC 루트: `/project/workSpace/pvc/download`
  - 기본 CDN 저장 경로: `/project/workSpace/pvc/download/cdn/images`
  - `platform.system()` + `pathlib.Path` 기반으로 cross-platform 처리
- 테스트를 보강하고 실행했다.
  - `pytest tests/test_conversation_service.py -v` 통과
  - `pytest tests/test_index.py -v` 통과
  - `pytest tests/ -v` 최종 `29 passed`
- 프로젝트 런타임 기준을 Python 3.11로 고정했다.
  - `.python-version`, `runtime.txt`, `README.md` 업데이트

## 2. 수정 내용
- 변경 파일
  - `.env.example`: Redis/CDN/PVC 관련 환경변수 추가 및 기본값 반영
  - `api/config.py`: `.env` 우선 로딩, `.env.example` 폴백, `WORKSPACE_ROOT`/`PVC_ROOT`/CDN 설정 추가
  - `api/services/conversation_service.py`: Redis primary->fallback 연결 시도 및 ping 검증 추가
  - `tests/test_conversation_service.py`: fallback 동작 테스트 추가 및 기존 테스트 패치 보강
  - `api/routes.py`: CDN 업로드/다운로드 라우트 추가
  - `api/services/cdn/__init__.py`: CDN 서비스 export
  - `api/services/cdn/cdn_service.py`: 이미지 저장/조회, 메타데이터 백엔드(Redis/in-memory) 구현
  - `tests/test_index.py`: CDN 업로드/조회/예외 케이스 테스트 추가
  - `.python-version`: Python 3.11 지정
  - `runtime.txt`: `python-3.11.11` 지정
  - `README.md`: Python 3.11 기준 실행 방법 문서화
  - `.gitignore`: `*.log.*` 패턴 추가

## 3. 다음 단계
- `create_chart` 도구가 생성하는 이미지도 CDN 서비스(`cdn_service`)를 통해 저장/URL 발급하도록 통합한다.
- CDN 업로드 API에 인증(예: 내부 토큰/서명)과 요청 제한을 추가한다.
- CDN 파일 정리 정책(TTL 기반 삭제, orphan 파일 정리)을 스케줄러에 추가한다.
- Linux 배포 환경에서 `/project/workSpace/pvc/download` 쓰기 권한 및 실제 URL(`CDN_BASE_URL`)을 운영 도메인으로 검증한다.

## 4. 메모리 업데이트
- `MEMORY.md` 신규 생성 및 업데이트 완료.
- 반영 내용: Python 3.11 기준, 환경 로딩 규칙, Redis 이중화 규칙, CDN 엔드포인트/저장 경로 규칙.
