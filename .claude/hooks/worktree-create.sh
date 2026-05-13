#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PROJECT_DIR=${CLAUDE_PROJECT_DIR:-$(CDPATH= cd -- "$SCRIPT_DIR/../.." && pwd)}
REPO_NAME=$(basename "$PROJECT_DIR")
WORKTREE_ROOT="${CLAUDE_WORKTREE_ROOT:-$HOME/.claude/worktrees}"

NAME=$(python3 -c 'import json, sys; print(json.load(sys.stdin).get("name", "agent-worktree"))')
SAFE_NAME=$(printf '%s' "$NAME" | tr -c 'A-Za-z0-9._-' '-')
WORKTREE_PATH="$WORKTREE_ROOT/$REPO_NAME-$SAFE_NAME"

if ! git -C "$PROJECT_DIR" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Project directory is not a git work tree: $PROJECT_DIR" >&2
  exit 1
fi

mkdir -p "$WORKTREE_ROOT"

if [ -e "$WORKTREE_PATH" ]; then
  echo "Worktree path already exists: $WORKTREE_PATH" >&2
  exit 1
fi

git -C "$PROJECT_DIR" worktree add --detach "$WORKTREE_PATH" HEAD >&2

printf '%s\n' "$WORKTREE_PATH"
