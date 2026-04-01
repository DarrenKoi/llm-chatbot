# Project Structure

이 문서는 `llm_chatbot` 프로젝트의 파일 구조를 빠르게 파악하기 위한 목차 문서다.

## 한눈에 보는 구조

```text
llm_chatbot/
├── index.py
├── scheduler_worker.py
├── cube_worker.py
├── requirements.txt
├── wsgi.ini
├── README.md
├── api/
├── tests/
├── doc/
├── scripts/
├── logs/
└── var/
```

## 문서 구성

- [`project_structure_api.md`](./project_structure_api.md): `api/` 패키지 상세 구조
- [`project_structure_supporting_files.md`](./project_structure_supporting_files.md): 진입점, 테스트, 문서, 스크립트, 로그/상태 디렉터리 정리

## 빠른 요약

- `index.py`: 로컬 Flask 앱 실행 진입점
- `scheduler_worker.py`: APScheduler 전용 워커 진입점
- `cube_worker.py`: Cube 큐 소비 워커 진입점
- `api/`: 실제 애플리케이션 로직이 모여 있는 핵심 패키지
- `tests/`: `pytest` 기반 테스트
- `doc/`: 설계 문서와 작업 기록
- `scripts/`: 보조 스크립트
- `logs/`, `var/`: 런타임 로그와 상태 저장소

## 구조 이해 순서 추천

처음 코드를 읽을 때는 아래 순서가 가장 효율적이다.

1. `README.md`
2. `index.py`
3. `api/__init__.py`
4. `api/blueprint_loader.py`
5. `api/cube/` 또는 `api/workflows/`
6. 관련 테스트 파일 (`tests/`)

## 요약

이 프로젝트는 Flask 웹앱, 별도 스케줄러 워커, Cube 큐 워커, 그리고 워크플로우 기반 대화 처리 계층으로 구성된다. 실제 기능 분석의 중심은 `api/` 아래에 있다.
