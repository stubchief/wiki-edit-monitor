#!/usr/bin/env bash
# Run once before the first terraform apply.
# Creates a Yandex Cloud service account for Terraform and saves its key.
#
# Requires: yc CLI authenticated with your personal account
#   https://cloud.yandex.ru/docs/cli/quickstart

set -e

ENV_FILE="$(dirname "$0")/../.env"
KEY_PATH="$(dirname "$0")/terraform/key.json"
SA_NAME="terraform-sa"

if [ ! -f "$ENV_FILE" ]; then
    echo "Error: .env not found at $ENV_FILE"
    echo "Copy .env.template to .env and fill in TF_VAR_folder_id."
    exit 1
fi

source "$ENV_FILE"

if [ -z "${TF_VAR_folder_id:-}" ]; then
    echo "Error: TF_VAR_folder_id is not set in .env"
    echo "Run 'yc config list' to find your folder id."
    exit 1
fi

echo "Using folder_id: $TF_VAR_folder_id"

echo "Creating service account '$SA_NAME'..."
yc iam service-account create --name "$SA_NAME" --folder-id "$TF_VAR_folder_id" || true

echo "Granting 'editor' role..."
yc resource-manager folder add-access-binding \
    --id "$TF_VAR_folder_id" \
    --role editor \
    --service-account-name "$SA_NAME"

echo "Creating authorized key..."
yc iam key create \
    --service-account-name "$SA_NAME" \
    --output "$KEY_PATH"

echo ""
echo "Done. Key saved to $KEY_PATH (already in .gitignore)."
echo ""
echo "Next steps:"
echo "  Create Object Storage bucket 'wiki-edit-monitor-tfstate' in Yandex Cloud console"
echo "  Add TF_VAR_folder_id, TF_VAR_ssh_public_key_path to .env"
echo "  export \$(cat .env | xargs)"
echo "  cd deploy/terraform && terraform init && terraform apply"