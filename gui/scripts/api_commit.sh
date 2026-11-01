#!/usr/bin/env bash
# Commit local files to a GitHub branch through the API, so GitHub signs the
# commit ("Verified") without any signing key on this machine or runner.
#
# Usage (from the repo root): gui/scripts/api_commit.sh <branch> <expected-head-sha> <message> <file>...
# Prints the new commit sha. Fails if <branch> no longer points at <expected-head-sha>.
set -euo pipefail

[[ $# -ge 4 ]] || { echo "usage: api_commit.sh <branch> <expected-head-sha> <message> <file>..." >&2; exit 2; }
repo="$(gh repo view --json nameWithOwner -q .nameWithOwner)"

payload="$(python3 -I - "$repo" "$@" <<'EOF'
import base64, json, sys
repo, branch, head, message, *files = sys.argv[1:]
query = """mutation($input: CreateCommitOnBranchInput!) {
  createCommitOnBranch(input: $input) { commit { oid } }
}"""
additions = [
    {"path": f, "contents": base64.b64encode(open(f, "rb").read()).decode()} for f in files
]
print(json.dumps({"query": query, "variables": {"input": {
    "branch": {"repositoryNameWithOwner": repo, "branchName": branch},
    "expectedHeadOid": head,
    "message": {"headline": message},
    "fileChanges": {"additions": additions},
}}}))
EOF
)"

oid="$(gh api graphql --input - -q '.data.createCommitOnBranch.commit.oid' <<< "$payload")"
[[ -n "$oid" ]] || { echo "error: GitHub did not return a commit" >&2; exit 1; }
echo "$oid"
