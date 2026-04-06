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
    "Windows": Path("F:/itc-1stop-solution-llm"),
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
]

# ──────────────────────────────────────────────
# 동기화 전 대상 폴더에서 삭제할 경로 목록
# 소스에서 삭제된 파일이 대상에 남는 것을 방지
# ──────────────────────────────────────────────
CLEAN_BEFORE_SYNC = [
    "api/",
]

EXCLUDE_PATTERNS = [
    "__pycache__",
    "*.pyc",
]

DEFAULT_EXCLUDE_PATHS = [
    "api/mcp/",
    "api/workflows/",
]


def normalize_entry_path(entry: str) -> Path:
    """슬래시 유무와 상관없이 비교 가능한 상대 경로로 정규화한다."""
    return Path(entry.rstrip("/"))


def is_excluded_by_pattern(path: Path) -> bool:
    """파일명/확장자 기반 제외 패턴에 해당하는지 확인"""
    for pattern in EXCLUDE_PATTERNS:
        if pattern.startswith("*"):
            if path.suffix == pattern[1:]:
                return True
        elif path.name == pattern or pattern in path.parts:
            return True
    return False


def is_excluded_by_path(relative_path: Path, exclude_paths: list[Path]) -> bool:
    """상대 경로가 제외 대상 하위인지 확인"""
    for excluded in exclude_paths:
        if relative_path == excluded or excluded in relative_path.parents:
            return True
    return False


def should_exclude(path: Path, relative_path: Path, exclude_paths: list[Path]) -> bool:
    """제외 패턴 또는 제외 경로에 해당하는지 확인"""
    return is_excluded_by_pattern(path) or is_excluded_by_path(relative_path, exclude_paths)


def copy_entry(src: Path, dst: Path, entry: str, dry_run: bool, exclude_paths: list[Path]) -> int:
    """단일 항목을 복사하고 복사된 파일 수를 반환한다."""
    normalized_entry = normalize_entry_path(entry)
    src_path = src / normalized_entry
    dst_path = dst / normalized_entry
    count = 0

    if not src_path.exists():
        print(f"  [건너뜀] {entry} (존재하지 않음)")
        return 0

    if src_path.is_dir():
        for file in src_path.rglob("*"):
            rel = file.relative_to(src)
            if file.is_dir() or should_exclude(file, rel, exclude_paths):
                continue
            target = dst / rel
            count += 1
            if dry_run:
                print(f"  [복사 예정] {rel}")
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(file, target)
    else:
        if should_exclude(src_path, normalized_entry, exclude_paths):
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
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="PATH",
        help="추가로 제외할 상대 경로 (예: api/profile/). 여러 번 지정 가능",
    )
    parser.add_argument(
        "--no-default-excludes",
        action="store_true",
        help="기본 제외 경로(api/mcp/, api/workflows/) 없이 전체 동기화",
    )
    args = parser.parse_args()

    dst = args.dst or DEFAULT_DST.get(platform.system(), PROJECT_ROOT.parent / "llm_chatbot_share")
    exclude_entries = [] if args.no_default_excludes else list(DEFAULT_EXCLUDE_PATHS)
    exclude_entries.extend(args.exclude)
    exclude_paths = [normalize_entry_path(entry) for entry in exclude_entries]

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
    if exclude_paths:
        print("제외 경로:")
        for entry in exclude_paths:
            print(f"  - {entry}")
    else:
        print("제외 경로: 없음")
    print()

    # 지정된 경로 정리
    for entry in CLEAN_BEFORE_SYNC:
        target = dst / entry.rstrip("/")
        if target.exists():
            if args.dry_run:
                print(f"  [삭제 예정] {entry}")
            else:
                shutil.rmtree(target) if target.is_dir() else target.unlink()
                print(f"  [삭제 완료] {entry}")

    # 파일 복사 (기존 파일 덮어쓰기, 수동 추가 파일은 유지)
    total = 0
    for entry in INCLUDE:
        total += copy_entry(PROJECT_ROOT, dst, entry, args.dry_run, exclude_paths)

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
