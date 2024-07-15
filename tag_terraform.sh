#!/usr/bin/env bash

set -euo pipefail

if [ -n "$(git status -s)" ] && [ -z "${DIRTY_WORKTREE+x}" ]; then
  echo >&2 "Error: Dirty git working tree"
  exit 1
fi

if [ -z "${TAG_SUFFIX:-}" ]; then
  echo >&2 "Error: TAG_SUFFIX must be supplied"
  exit 1
fi

TERRAFORM_VERSIONS=(
  "1.6.0" "1.6.1" "1.6.2" "1.6.3" "1.6.4" "1.6.5" "1.6.6" "1.7.0" "1.7.1"
  "1.7.2" "1.7.3" "1.7.4" "1.7.5" "1.8.0" "1.8.1" "1.8.2" "1.8.3" "1.8.4"
)

git_tags=()
for v in "${TERRAFORM_VERSIONS[@]}"; do
  git_tags+=("${v}-${TAG_SUFFIX}")
done

echo >&2 "List of git tags:"
( IFS=$'\n'; column -x <<< "${git_tags[*]}"; )

echo >&2 "These tags will be applied to:"
git log -1 --pretty --oneline

read -p "Continue (y/n)? " CONT
if [ "${CONT}" != "y" ]; then
  echo >&2 "Info: Operation aborted"
fi

for t in "${git_tags[@]}"; do
  { git tag "${t}" && git push origin "${t}"; } || echo >&2 "Error: Tag '${t}' failed"
done
