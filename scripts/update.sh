#!/bin/bash

# Navigate to project directory (where this script is located's parent)
# Assuming scripts/update.sh -> project_root/scripts/update.sh
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "Updating Magic 8-Ball from: $PROJECT_ROOT"
cd "$PROJECT_ROOT" || exit 1

# Stash any local changes to avoid conflicts
if [[ -n $(git status -s) ]]; then
    echo "Stashing local changes..."
    git stash
fi

# Pull latest changes
echo "Pulling latest code..."
git pull

# Ensure scripts are executable
chmod +x scripts/*.sh

echo "Update complete! You can close this window."
read -p "Press Enter to exit..."
