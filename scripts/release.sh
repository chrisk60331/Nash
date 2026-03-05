#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PKG="$ROOT/package.json"
CONFIG="$ROOT/packages/data-provider/src/config.ts"

# Read current version from root package.json (e.g. 2.0.0)
current=$(node -p "require('$PKG').version")
IFS='.' read -r major minor patch <<< "$current"

echo "Current version: v${major}.${minor}.${patch}"
echo ""
echo "Bump type:"
echo "  1) patch  (v${major}.${minor}.$((patch + 1)))"
echo "  2) minor  (v${major}.$((minor + 1)).0)"
echo "  3) major  (v$((major + 1)).0.0)"
read -rp "Choose [1/2/3]: " bump_choice

case "$bump_choice" in
  1) patch=$((patch + 1)) ;;
  2) minor=$((minor + 1)); patch=0 ;;
  3) major=$((major + 1)); minor=0; patch=0 ;;
  *) echo "Invalid choice"; exit 1 ;;
esac

new_version="${major}.${minor}.${patch}"
tag="v${new_version}"

echo ""
read -rp "Release message: " message

if [ -z "$message" ]; then
  echo "Message cannot be empty"; exit 1
fi

echo ""
echo "--- Release Plan ---"
echo "  Version: $tag"
echo "  Message: $message"
echo "--------------------"
read -rp "Proceed? [y/N]: " confirm
if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
  echo "Aborted."; exit 0
fi

# Update package.json (version without "v" prefix)
sed -i '' "s/\"version\": \"${current}\"/\"version\": \"${new_version}\"/" "$PKG"

# Update Constants.VERSION in data-provider config (with "v" prefix)
sed -i '' "s/VERSION = 'v[^']*'/VERSION = '${tag}'/" "$CONFIG"

echo "Updated version to ${tag} in:"
echo "  $PKG"
echo "  $CONFIG"

cd "$ROOT"
git add -A
git commit -m "${tag} ${message}"
git tag -a "$tag" -m "$message"
git push
git push --tags
if command -v gh &>/dev/null; then
  gh release create "$tag" --title "$tag" --notes "$message"
else
  echo "gh not found; skipping GitHub release creation."
fi

echo ""
echo "Released ${tag}"
