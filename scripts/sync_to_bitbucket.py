"""
Bitbucket 공유용 코드 동기화 스크립트

GitHub 전체 저장소에서 동료와 공유할 파일만 선별하여
별도의 Bitbucket 로컬 저장소로 복사합니다.

사용법:
    python scripts/sync_to_bitbucket.py                          # 기본 경로 사용
    python scripts/sync_to_bitbucket.py --dst C:/work/share_repo # 대상 경로 지정
    python scripts/sync_to_bitbucket.py --dry-run                # 실제 복사 없이 미리보기
"""

import argparse
import platform
import shutil
import sys
from pathlib import Path

# 프로젝트 루트 (이 스크립트의 상위 디렉토리)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ──────────────────────────────────────────────
# 대상 경로 설정 (OS별 하드코딩)
# --dst 인자 없이 실행하면 이 경로를 사용합니다.
# ──────────────────────────────────────────────
DEFAULT_DST = {
    "Windows": Path("C:/work/llm_chatbot_share"),
    "Darwin": PROJECT_ROOT.parent / "llm_chatbot_share",
}

# ──────────────────────────────────────────────
# 공유할 파일/폴더 목록
# - 폴더는 "/" 로 끝남 (하위 전체 복사)
# - 파일은 그대로 지정
# ──────────────────────────────────────────────
INCLUDE = [
    # 애플리케이션 패키지
    "api/",
    # 엔트리포인트
    "index.py",
    "cube_worker.py",
    "scheduler_worker.py",
    # 설정/배포
    "wsgi.ini",
    "requirements.txt",
    ".env.example",
    ".gitignore",
    # 템플릿
    "api/templates/",
]

# api/ 내에서 제외할 항목 (Claude 개인 설정 등은 루트에만 있으므로 별도 제외 불필요)
EXCLUDE_PATTERNS = [
    "__pycache__",
    "*.pyc",
]


def should_exclude(path: Path) -> bool:
    """제외 패턴에 해당하는지 확인"""
    for pattern in EXCLUDE_PATTERNS:
        if pattern.startswith("*"):
            if path.suffix == pattern[1:]:
                return True
        elif path.name == pattern or pattern in path.parts:
            return True
    return False


def copy_entry(src: Path, dst: Path, entry: str, dry_run: bool) -> int:
    """단일 항목을 복사하고 복사된 파일 수를 반환한다."""
    src_path = src / entry.rstrip("/")
    dst_path = dst / entry.rstrip("/")
    count = 0

    if not src_path.exists():
        print(f"  [건너뜀] {entry} (존재하지 않음)")
        return 0

    if src_path.is_dir():
        for file in src_path.rglob("*"):
            if file.is_dir() or should_exclude(file):
                continue
            rel = file.relative_to(src)
            target = dst / rel
            count += 1
            if dry_run:
                print(f"  [복사 예정] {rel}")
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(file, target)
    else:
        if should_exclude(src_path):
            return 0
        count = 1
        if dry_run:
            print(f"  [복사 예정] {entry}")
        else:
            dst_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_path, dst_path)

    return count


def main():
    parser = argparse.ArgumentParser(
        description="Bitbucket 공유용 코드 동기화",
    )
    parser.add_argument(
        "--dst",
        type=Path,
        help="Bitbucket 로컬 저장소 경로 (기본: 프로젝트 루트 옆의 llm_chatbot_share/)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="실제 복사 없이 대상 파일만 확인",
    )
    args = parser.parse_args()

    dst = args.dst or DEFAULT_DST.get(platform.system(), PROJECT_ROOT.parent / "llm_chatbot_share")

    if not dst.exists():
        print(f"오류: 대상 디렉토리가 존재하지 않습니다: {dst}")
        print(f"먼저 Bitbucket 저장소를 clone하세요:")
        print(f"  git clone <bitbucket-url> {dst}")
        sys.exit(1)

    if not (dst / ".git").exists():
        print(f"경고: {dst} 에 .git 폴더가 없습니다. Git 저장소가 아닙니다.")
        sys.exit(1)

    print(f"소스: {PROJECT_ROOT}")
    print(f"대상: {dst}")
    print(f"모드: {'미리보기 (dry-run)' if args.dry_run else '실제 복사'}")
    print()

    # 파일 복사 (기존 파일 덮어쓰기, 수동 추가 파일은 유지)
    total = 0
    for entry in INCLUDE:
        total += copy_entry(PROJECT_ROOT, dst, entry, args.dry_run)

    print(f"\n총 {total}개 파일 {'복사 예정' if args.dry_run else '복사 완료'}")

    if not args.dry_run:
        print(f"\n다음 단계:")
        print(f"  cd {dst}")
        print(f"  git add -A")
        print(f"  git status")
        print(f"  git commit -m \"코드 동기화\"")
        print(f"  git push")


if __name__ == "__main__":
    main()
