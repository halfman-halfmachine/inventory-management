#!/bin/bash

# PostToolUse hook for Edit/Write: formats the edited frontend file with Prettier
#
# Claude Code passes hook data as JSON on stdin (there is no $CLAUDE_FILE_PATH
# variable), so the file path comes from .tool_input.file_path

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

# Only format files Prettier should own: the Vue client's source
case "$FILE_PATH" in
  "$CLAUDE_PROJECT_DIR"/client/src/*.vue|"$CLAUDE_PROJECT_DIR"/client/src/*.js|"$CLAUDE_PROJECT_DIR"/client/src/*.css) ;;
  *) exit 0 ;;
esac

PRETTIER="$CLAUDE_PROJECT_DIR/client/node_modules/.bin/prettier"

# Skip quietly if dependencies aren't installed yet, rather than letting npx
# download Prettier on every edit
[ -x "$PRETTIER" ] || exit 0

# Run from client/ so Prettier picks up client/.prettierrc.json.
# Never block the edit: a formatting failure only gets reported to Claude
cd "$CLAUDE_PROJECT_DIR/client" && "$PRETTIER" --write --log-level warn "$FILE_PATH" >&2 || true
exit 0
