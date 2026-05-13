#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PROJECT_DIR=${CLAUDE_PROJECT_DIR:-$(CDPATH= cd -- "$SCRIPT_DIR/../.." && pwd)}

WORKTREE_PATH=$(python3 -c 'import json, sys; print(json.load(sys.stdin).get("worktree_path", ""))')

if [ -z "$WORKTREE_PATH" ]; then
  echo "Missing worktree_path" >&2
  exit 1
fi

git -C "$PROJECT_DIR" worktree remove "$WORKTREE_PATH" >&2
