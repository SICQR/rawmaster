#!/usr/bin/env bash
# RAWMASTER - HuggingFace Spaces deploy script
# Usage: ./scripts/deploy_spaces.sh
# Requires: huggingface-cli logged in (huggingface-cli login)
set -euo pipefail

REPO_ID="smashd/rawmaster"
SPACES_DIR="$(cd "$(dirname "$0")/../spaces" && pwd)"

echo "RAWMASTER - deploying to HuggingFace Spaces"
echo "   Repo : $REPO_ID"
echo "   From : $SPACES_DIR"
echo ""

if ! command -v huggingface-cli &>/dev/null; then
  echo "huggingface-cli not found"
  echo "   pip install huggingface_hub[cli]"
  exit 1
fi

if ! huggingface-cli whoami &>/dev/null; then
  echo "Not logged in to HuggingFace."
  echo "   Run: huggingface-cli login"
  exit 1
fi

HF_USER=$(huggingface-cli whoami 2>/dev/null | head -1)
echo "Logged in as: $HF_USER"

python3 - <<EOF
from huggingface_hub import HfApi, create_repo

api = HfApi()
repo_id = "$REPO_ID"

try:
    api.repo_info(repo_id=repo_id, repo_type="space")
    print(f"Space already exists: https://huggingface.co/spaces/{repo_id}")
except Exception:
    print(f"Creating Space: {repo_id}")
    create_repo(repo_id=repo_id, repo_type="space", space_sdk="gradio", private=False)
    print(f"Space created: https://huggingface.co/spaces/{repo_id}")
EOF

echo "Uploading $SPACES_DIR to $REPO_ID ..."

python3 - <<EOF
from huggingface_hub import HfApi
import subprocess, datetime

api = HfApi()
api.upload_folder(
    folder_path="$SPACES_DIR",
    repo_id="$REPO_ID",
    repo_type="space",
    commit_message=f"Deploy RAWMASTER demo {datetime.date.today()}",
    ignore_patterns=["__pycache__", "*.pyc", ".DS_Store", ".env"],
)
print(f"Done! Live at: https://huggingface.co/spaces/$REPO_ID")
EOF