#!/bin/bash
# Auto push after Claude finishes a response
# Triggered by the "Stop" hook event
#
# Does NOT auto-commit — use /commit or /review-and-push skills instead
# for meaningful commit messages with full context.

cd "$CLAUDE_PROJECT_DIR" || exit 0

# Only proceed if in a git repo with a configured remote
git rev-parse --git-dir > /dev/null 2>&1 || exit 0
[ -n "$(git remote)" ] || exit 0

# Push any unpushed commits. If the branch has no upstream yet, fall back to a
# plain push so first-push workflows still publish the branch.
if git rev-parse --abbrev-ref --symbolic-full-name '@{u}' > /dev/null 2>&1; then
  UNPUSHED=$(git log --oneline @{u}..HEAD 2>/dev/null | wc -l | tr -d ' ')
  if [ "$UNPUSHED" -gt 0 ]; then
    git push > /dev/null 2>&1
  fi
else
  git push > /dev/null 2>&1
fi

# Warn if there are uncommitted changes
if ! git diff --quiet || ! git diff --cached --quiet || [ -n "$(git ls-files --others --exclude-standard)" ]; then
  echo '{"systemMessage":"⚠️ 커밋되지 않은 변경사항이 있습니다. /commit 또는 /review-and-push 를 사용하세요."}'
fi

exit 0
