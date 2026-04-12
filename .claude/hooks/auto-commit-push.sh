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

# Push any unpushed commits. If the branch has no upstream yet, set one up
# with -u so first-push workflows still publish the branch.
if git rev-parse --abbrev-ref --symbolic-full-name '@{u}' > /dev/null 2>&1; then
  UNPUSHED=$(git rev-list --count '@{u}..HEAD' 2>/dev/null)
  if [ "${UNPUSHED:-0}" -gt 0 ]; then
    git push > /dev/null 2>&1
  fi
else
  git push -u origin HEAD > /dev/null 2>&1
fi

exit 0
