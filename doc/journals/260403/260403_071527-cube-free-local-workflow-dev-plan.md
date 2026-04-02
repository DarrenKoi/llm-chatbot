## 1. 진행 사항

- 현재 저장소 구조를 검토했다. `doc/project_structure.md`, `doc/project_structure_api.md`, `doc/guideline/workflow_추가_가이드.md`를 읽고 `api/cube/`와 `api/workflows/`의 책임 분리를 확인했다.
- `rg -n "Cube|cube|workflow" api tests doc -g '!doc/journals/**'`로 Cube 연동 지점과 workflow 실행 지점을 확인했다.
- 사용자 우려를 정리했다. 현재 workflow 개발이 `Cube -> queue -> worker -> orchestrator -> workflow` 흐름에 묶여 있어, 동료가 로컬에서 workflow만 빠르게 개발하거나 검증하기 어렵다는 점이 핵심이다.
- 해결 방향을 정리했다. 새 저장소를 만드는 대신 현재 저장소 안에서 Cube를 transport adapter로 더 얇게 두고, 로컬 개발용 ingress를 추가해 workflow를 동일한 orchestrator로 실행하는 구조가 적절하다고 판단했다.
- 제안한 구조는 아래와 같다.

```text
api/
  cube/                 # 운영용 transport adapter 유지
  workflows/            # 업무 로직 유지
  devtools/
    workflow_runner/    # 로컬 개발 전용 진입점
      router.py         # HTTP/CLI 입력 수신
      schemas.py        # 로컬 요청/응답 모델
      service.py        # orchestrator 호출 어댑터
      fixtures.py       # 샘플 user/channel/session 생성
```

- 제안한 개발 흐름은 다음과 같다.

```text
로컬 개발자 입력
-> dev workflow runner
-> api/workflows/orchestrator.handle_message()
-> workflow 실행
-> 로컬 JSON/HTML 응답 확인

운영 Cube 입력
-> api/cube/router.py
-> queue/worker
-> api/workflows/orchestrator.handle_message()
-> Cube 응답 전송
```

- 핵심 원칙도 함께 정리했다.
  - workflow 코드는 `api/workflows/` 아래에서 Cube를 직접 알지 않게 유지한다.
  - Cube 특화 payload 파싱, reply 전송, queue 처리는 `api/cube/`에만 둔다.
  - 로컬 개발용 진입점은 같은 state 모델과 orchestrator를 재사용해 운영과 동일한 로직을 타게 한다.
  - 필요하면 `tests/test_*workflow.py`와 별도로 수동 점검용 `/dev/workflows/<workflow_id>` 엔드포인트 또는 CLI runner를 둔다.

## 2. 수정 내용

- 새 저널 파일을 생성했다.
  - `doc/journals/260403/260403_071527-cube-free-local-workflow-dev-plan.md`
- 코드 변경은 없고, 사용자 우려와 권장 구조를 문서로 정리했다.
- 제안한 구체 해법은 다음과 같다.
  - 별도 폴더에서 workflow 로직을 새로 복제하지 않는다.
  - 기존 `api/workflows/`를 단일 소스로 유지한다.
  - `api/devtools/workflow_runner/` 같은 로컬 전용 adapter 계층을 추가한다.
  - 동료는 로컬에서 이 runner로 workflow를 개발하고, 배포 후에는 기존 Cube 경로가 같은 orchestrator를 사용한다.
  - 이렇게 하면 로컬 개발 경험은 빨라지고, 운영 배포 시 경로만 Cube로 바뀌며 업무 로직은 동일하게 유지된다.

## 3. 다음 단계

- `api/devtools/workflow_runner/` 패키지를 실제로 추가한다.
- 로컬 개발용 입력 계약을 정한다. 우선 `user_id`, `channel_id`, `message`, `workflow_id` 정도만 받는 단순 스키마로 시작하는 것이 적절하다.
- Flask dev endpoint(`/dev/workflows/<workflow_id>`) 또는 CLI runner 중 하나를 먼저 구현한다.
- `api/workflows/orchestrator.py`가 Cube 모델에 과하게 묶여 있다면, 공통 입력 모델로 한 번 더 분리한다.
- 로컬 runner 기준의 pytest를 추가해 "Cube 없이도 workflow 검증 가능" 상태를 만든다.
- 팀 가이드 문서(`doc/guideline/workflow_추가_가이드.md`)에 "로컬 workflow 개발 방법" 섹션을 추가한다.

## 4. 메모리 업데이트

변경 없음
