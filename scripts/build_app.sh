#!/usr/bin/env zsh
# build_app.sh — Self-configuring CameraGrid standalone app builder.
#
# After copying this project folder to any Mac running macOS 26+ or 27+,
# run this script and it will:
#   1. Install uv if missing
#   2. Sync runtime dependencies
#   3. Build the standalone CameraGrid.app
#   4. Copy the result to output/CameraGrid.app
#
# Usage:
#   chmod +x scripts/build_app.sh
#   ./scripts/build_app.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "📦 Project root: $PROJECT_ROOT"

if ! command -v uv &>/dev/null; then
    echo "🔧 uv not found. Installing..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
    if ! command -v uv &>/dev/null; then
        echo "❌ uv installation failed. Install manually from https://docs.astral.sh/uv/"
        exit 1
    fi
fi

echo "✅ uv $(uv --version)"

cd "$PROJECT_ROOT"

echo "🔄 Syncing dependencies..."
uv sync

echo "🧹 Cleaning previous build artifacts..."
rm -rf "$PROJECT_ROOT/build" "$PROJECT_ROOT/dist" "$PROJECT_ROOT/output/CameraGrid.app"

echo "🚀 Building CameraGrid.app..."
uv run --with pyinstaller --with pyinstaller-hooks-contrib \
    pyinstaller --clean --noconfirm scripts/CameraGrid.spec

if [ -d "$PROJECT_ROOT/dist/CameraGrid.app" ]; then
    echo "📋 Copying to output/CameraGrid.app..."
    rm -rf "$PROJECT_ROOT/output/CameraGrid.app"
    cp -R "$PROJECT_ROOT/dist/CameraGrid.app" "$PROJECT_ROOT/output/"
    echo "✅ Done! App is at: $PROJECT_ROOT/output/CameraGrid.app"
else
    echo "⚠️  Build completed but dist/CameraGrid.app not found."
    exit 1
fi
