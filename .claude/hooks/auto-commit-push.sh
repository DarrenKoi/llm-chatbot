#!/bin/bash
# Auto commit and push after Claude finishes a response
# Triggered by the "Stop" hook event

cd "$CLAUDE_PROJECT_DIR" || exit 0

# Only proceed if in a git repo
git rev-parse --git-dir > /dev/null 2>&1 || exit 0

# Check if there are any changes (staged, unstaged, or untracked)
if git diff --quiet && git diff --cached --quiet && [ -z "$(git ls-files --others --exclude-standard)" ]; then
  exit 0
fi

# Stage all changes, commit, and push
git add -A
git commit -m "Auto-commit by Claude Code" > /dev/null 2>&1 || exit 0
git push > /dev/null 2>&1

exit 0
