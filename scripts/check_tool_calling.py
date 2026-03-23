"""
LLM Function Calling 지원 여부 검증 스크립트

사용법:
    # .env 파일의 기본 모델로 테스트
    python scripts/check_tool_calling.py

    # 특정 모델 지정
    python scripts/check_tool_calling.py --model Kimi-K2.5

    # 여러 모델 동시 테스트
    python scripts/check_tool_calling.py --model Kimi-K2.5 --model Qwen3 --model gpt-oss-120b

    # BASE_URL과 API_KEY 직접 지정
    python scripts/check_tool_calling.py --base-url http://localhost:8000 --api-key sk-xxx --model Kimi-K2.5
"""

import argparse
import json
import sys
from pathlib import Path

import httpx

# 프로젝트 루트를 path에 추가하여 api.config 사용 가능하게
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# 테스트용 도구 정의
TEST_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "도시의 현재 날씨를 조회합니다",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "날씨를 조회할 도시 이름",
                    }
                },
                "required": ["city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_documents",
            "description": "사내 문서를 키워드로 검색합니다",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "검색 키워드",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "최대 결과 수",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        },
    },
]

# LLM이 도구를 호출하도록 유도하는 테스트 메시지
TEST_MESSAGE = "서울 날씨 알려줘"


def check_model(base_url: str, model: str, api_key: str, timeout: int) -> dict:
    """단일 모델의 function calling 지원 여부를 테스트한다."""
    url = f"{base_url.rstrip('/')}/chat/completions"

    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": TEST_MESSAGE}],
        "tools": TEST_TOOLS,
    }

    result = {
        "model": model,
        "supported": False,
        "tool_calls": None,
        "finish_reason": None,
        "content": None,
        "error": None,
        "raw_response": None,
    }

    try:
        response = httpx.post(url, json=payload, headers=headers, timeout=timeout)
        response.raise_for_status()
        data = response.json()
        result["raw_response"] = data

        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})
        finish_reason = choice.get("finish_reason", "")

        result["finish_reason"] = finish_reason
        result["content"] = message.get("content")
        result["tool_calls"] = message.get("tool_calls")

        # tool_calls가 있으면 지원 확인
        if message.get("tool_calls"):
            result["supported"] = True

    except httpx.HTTPStatusError as exc:
        result["error"] = f"HTTP {exc.response.status_code}: {exc.response.text[:200]}"
    except httpx.RequestError as exc:
        result["error"] = f"연결 실패: {exc}"
    except (json.JSONDecodeError, KeyError, IndexError) as exc:
        result["error"] = f"응답 파싱 실패: {exc}"

    return result


def print_result(result: dict) -> None:
    """테스트 결과를 출력한다."""
    model = result["model"]
    print(f"\n{'=' * 60}")
    print(f"모델: {model}")
    print(f"{'=' * 60}")

    if result["error"]:
        print(f"  상태: 오류")
        print(f"  오류: {result['error']}")
        return

    if result["supported"]:
        print(f"  상태: Function Calling 지원 확인")
        print(f"  finish_reason: {result['finish_reason']}")
        print(f"  tool_calls:")
        for tc in result["tool_calls"]:
            fn = tc.get("function", {})
            print(f"    - {fn.get('name', '?')}({fn.get('arguments', '{}')})")
    else:
        print(f"  상태: Function Calling 미지원 (또는 도구 호출 안 함)")
        print(f"  finish_reason: {result['finish_reason']}")
        if result["content"]:
            preview = result["content"][:150]
            print(f"  응답 내용: {preview}{'...' if len(result['content']) > 150 else ''}")


def main():
    parser = argparse.ArgumentParser(
        description="LLM Function Calling 지원 여부 검증",
    )
    parser.add_argument(
        "--model",
        action="append",
        dest="models",
        help="테스트할 모델 이름 (여러 번 지정 가능)",
    )
    parser.add_argument(
        "--base-url",
        help="LLM API 기본 URL (미지정 시 .env의 LLM_BASE_URL 사용)",
    )
    parser.add_argument(
        "--api-key",
        help="API 키 (미지정 시 .env의 LLM_API_KEY 사용)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="요청 타임아웃 (초, 기본값: 30)",
    )
    parser.add_argument(
        "--raw",
        action="store_true",
        help="원본 API 응답 JSON도 함께 출력",
    )

    args = parser.parse_args()

    # 설정 로드: CLI 인자 우선, 없으면 .env에서
    try:
        from api import config

        base_url = args.base_url or config.LLM_BASE_URL
        api_key = args.api_key if args.api_key is not None else config.LLM_API_KEY
        default_model = config.LLM_MODEL
    except Exception:
        base_url = args.base_url or ""
        api_key = args.api_key or ""
        default_model = ""

    if not base_url:
        print("오류: --base-url을 지정하거나 .env에 LLM_BASE_URL을 설정하세요.")
        sys.exit(1)

    models = args.models or ([default_model] if default_model else [])
    if not models:
        print("오류: --model을 지정하거나 .env에 LLM_MODEL을 설정하세요.")
        sys.exit(1)

    print(f"테스트 대상 URL: {base_url}")
    print(f"테스트 메시지: \"{TEST_MESSAGE}\"")
    print(f"제공 도구: {', '.join(t['function']['name'] for t in TEST_TOOLS)}")
    print(f"테스트 모델 수: {len(models)}")

    results = []
    for model in models:
        result = check_model(base_url, model, api_key, args.timeout)
        results.append(result)
        print_result(result)

        if args.raw and result["raw_response"]:
            print(f"\n  [원본 응답]")
            print(f"  {json.dumps(result['raw_response'], ensure_ascii=False, indent=2)}")

    # 요약
    print(f"\n{'=' * 60}")
    print("요약")
    print(f"{'=' * 60}")
    for r in results:
        status = "지원" if r["supported"] else ("오류" if r["error"] else "미지원")
        icon = {"지원": "[O]", "미지원": "[X]", "오류": "[!]"}[status]
        print(f"  {icon} {r['model']}: {status}")


if __name__ == "__main__":
    main()
