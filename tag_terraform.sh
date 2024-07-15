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
  "1.0.0" "1.0.1"  "1.0.2"  "1.0.3" "1.0.4" "1.0.5" "1.0.6"  "1.0.7" "1.0.8"
  "1.0.9" "1.0.10" "1.0.11" "1.1.0" "1.1.1" "1.1.2" "1.1.3"  "1.1.4" "1.1.5"
  "1.1.6" "1.1.7"  "1.1.8"  "1.1.9" "1.2.0" "1.2.1" "1.2.2"  "1.2.3" "1.2.4"
  "1.2.5" "1.2.6"  "1.2.7"  "1.2.8" "1.2.9" "1.3.0" "1.3.1"  "1.3.2" "1.3.3"
  "1.3.4" "1.3.5"  "1.3.6"  "1.3.7" "1.3.8" "1.3.9" "1.3.10" "1.4.0" "1.4.1"
  "1.4.2" "1.4.3"  "1.4.4"  "1.4.5" "1.4.6" "1.4.7" "1.5.0"  "1.5.1" "1.5.2"
  "1.5.3" "1.5.4"  "1.5.5"  "1.5.6" "1.5.7" 
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
