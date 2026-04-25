#!/usr/bin/env bash
# Nuxt SPA를 빌드하고 산출물을 Flask 정적 디렉토리로 복사한다.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WEB_DIR="$REPO_ROOT/web"
TARGET_DIR="$REPO_ROOT/api/static/chat"

if [ ! -d "$WEB_DIR" ]; then
  echo "ERROR: $WEB_DIR not found" >&2
  exit 1
fi

cd "$WEB_DIR"
if [ ! -d node_modules ]; then
  npm install
fi
npm run build

mkdir -p "$TARGET_DIR"
# .gitkeep을 보존하기 위해 디렉토리 자체를 지우지 않고 내부만 정리한다.
find "$TARGET_DIR" -mindepth 1 ! -name '.gitkeep' -exec rm -rf {} +

cp -r "$WEB_DIR/.output/public/." "$TARGET_DIR/"

echo "Web chat SPA deployed to: $TARGET_DIR"
