#!/usr/bin/env bash
set -euo pipefail

if ! git_root=$(git rev-parse --show-toplevel 2>/dev/null); then
  echo "Error: not inside a Git repository" >&2
  exit 1
fi

cd "$git_root"

tracked_ignored=()
while IFS= read -r -d '' file; do
  tracked_ignored+=("$file")
done < <(git ls-files -ci --exclude-standard -z)

if [[ ${#tracked_ignored[@]} -eq 0 ]]; then
  echo "No tracked files match current ignore rules."
  exit 0
fi

echo "Tracked files matched by ignore rules:"
for file in "${tracked_ignored[@]}"; do
  printf '  %s\n' "$file"
done

auto_confirm=${1:-}
if [[ "$auto_confirm" != "-y" && "$auto_confirm" != "--yes" ]]; then
  read -r -p "Remove these files from the Git index? [y/N] " reply
  case "$reply" in
    y|Y|yes|YES) ;;
    *)
      echo "Aborted."
      exit 0
      ;;
  esac
fi

# Remove the files from the index while leaving them on disk.
git rm -r --cached -- "${tracked_ignored[@]}"

echo "Done. Run 'git status' to review the changes."
