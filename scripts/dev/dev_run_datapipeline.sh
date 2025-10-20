#!/usr/bin/env bash
set -euo pipefail

# Development runner for DataPipeline component
# - loads .env.local if present
# - activates DataPipeline/.venv if present
# - executes given command (or drops to a shell)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
ENV_FILE="$REPO_ROOT/.env.local"
VENV_PATH="$REPO_ROOT/DataPipeline/.venv"

if [ -f "$ENV_FILE" ]; then
    echo "Loading environment from: $ENV_FILE"
    set -a
    # shellcheck disable=SC1090
    . "$ENV_FILE"
    set +a
fi

if [ -d "$VENV_PATH" ]; then
    echo "Activating venv: $VENV_PATH"
    # shellcheck disable=SC1091
    source "$VENV_PATH/bin/activate"
else
    echo "Warning: venv not found at $VENV_PATH. Proceeding without venv activation."
fi

if [ $# -gt 0 ]; then
    echo "Executing in DataPipeline venv: $*"
    exec "$@"
else
    echo "No command provided. Starting interactive shell in DataPipeline venv (if activated)."
    exec bash
fi


