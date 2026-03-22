#!/usr/bin/env bash
# Combines all version-bump steps from auto-bump-version.yml into one script:
#   1. Determine bump type from PR title ([major], [minor], or patch default)
#   2. Compute new semantic version
#   3. Update VERSION file and utils/pyproject.toml
#   4. Git commit + push to develop
#   5. Write step summary
#
# Required env vars (must be set in workflow step env:):
#   PR_TITLE  — from github.event.pull_request.title
#   PR_NUMBER — from github.event.pull_request.number
#
# Note: git push works because actions/checkout is called with
#   token: ${{ secrets.GITHUB_TOKEN }} which configures the remote auth.
set -euo pipefail

echo "PR title: ${PR_TITLE}"

# ── Determine bump type ───────────────────────────────────────────────────────
if echo "${PR_TITLE}" | grep -qi '\[major\]'; then
  BUMP="major"
elif echo "${PR_TITLE}" | grep -qi '\[minor\]'; then
  BUMP="minor"
else
  BUMP="patch"
fi

# ── Compute new version ───────────────────────────────────────────────────────
CURRENT=$(cat VERSION | tr -d '[:space:]')
MAJOR=$(echo "$CURRENT" | cut -d. -f1)
MINOR=$(echo "$CURRENT" | cut -d. -f2)
PATCH=$(echo "$CURRENT" | cut -d. -f3)

case "$BUMP" in
  major) MAJOR=$((MAJOR + 1)); MINOR=0; PATCH=0 ;;
  minor) MINOR=$((MINOR + 1)); PATCH=0 ;;
  patch) PATCH=$((PATCH + 1)) ;;
esac

NEW_VERSION="${MAJOR}.${MINOR}.${PATCH}"
echo "Bumping ${CURRENT} → ${NEW_VERSION} (${BUMP})"

# ── Update files ──────────────────────────────────────────────────────────────
echo "${NEW_VERSION}" > VERSION
sed -i -E "s/^(version[[:space:]]*=[[:space:]]*[\"'])[^\"']+([\"'])/\1${NEW_VERSION}\2/" utils/pyproject.toml
echo "pyproject.toml version updated to ${NEW_VERSION}"

# ── Commit and push ───────────────────────────────────────────────────────────
git config user.name  "github-actions[bot]"
git config user.email "github-actions[bot]@users.noreply.github.com"
git add VERSION utils/pyproject.toml

if git diff --cached --quiet; then
  echo "Nothing to commit — version files unchanged."
  exit 0
fi

git commit -m "ci: bump version ${CURRENT} → ${NEW_VERSION} [${BUMP}]"
git push origin develop

# ── Step summary ──────────────────────────────────────────────────────────────
cat >> "${GITHUB_STEP_SUMMARY}" << EOF
## Version Bumped
| Field | Value |
|-------|-------|
| Previous | \`${CURRENT}\` |
| New      | \`${NEW_VERSION}\` |
| Type     | \`${BUMP}\` |
| PR       | #${PR_NUMBER} — ${PR_TITLE} |
EOF
