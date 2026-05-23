#!/bin/bash
set -e
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PUBLIC_DIR="$REPO_ROOT/public/apps"
NGINX_DIR="/var/www/pocketmint/apps"

sudo mkdir -p "$NGINX_DIR"

for zip in "$PUBLIC_DIR"/*.zip; do
    name=$(basename "$zip")
    echo "Deploying $name..."
    sudo cp "$zip" "$NGINX_DIR/$name"
done

echo "All apps deployed to $NGINX_DIR"
