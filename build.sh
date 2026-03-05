#!/usr/bin/env bash
# =============================================================================
# Nash 2.0 — Full build pipeline
#
#   1. Terraform apply (ECR)
#   2. ECR login
#   3-5. Build, tag, push Docker image
#   6. Terraform apply (full)
#   7-8. Deploy to App Runner
#
# Usage:
#   ./build.sh              # defaults to dev-latest
#   ./build.sh staging      # tags as staging-latest
#   ./build.sh prod v1.2.3  # tags as prod-v1.2.3
#
# Env vars:
#   SKIP_TERRAFORM=1   — skip terraform apply
# =============================================================================
set -euo pipefail

APP_NAME="nash"
AWS_REGION="us-west-2"
AWS_ACCOUNT_ID=$(aws sts get-caller-identity | jq -r '.Account')
ECR_URL="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
TF_DIR="$(cd "$(dirname "$0")/terraform" && pwd)"

ENV="${1:-dev}"
TAG="${2:-latest}"
IMAGE_TAG="${ENV}-${TAG}"

STEPS=8

echo "──────────────────────────────────────────────"
echo "  Nash 2.0 (Python)"
echo "  Env:    ${ENV}"
echo "  Tag:    ${IMAGE_TAG}"
echo "  ECR:    ${ECR_URL}"
echo "──────────────────────────────────────────────"

# ── 1. Terraform apply (ECR) ────────────────────────────────────────────
if [[ "${SKIP_TERRAFORM:-0}" != "1" ]]; then
  TFVARS_FILE="${TF_DIR}/terraform.tfvars"
  if [ ! -f "${TFVARS_FILE}" ]; then
    echo "ERROR: ${TFVARS_FILE} not found"
    exit 1
  fi
  echo "[1/${STEPS}] Terraform bootstrap + ECR..."
  cd "${TF_DIR}/bootstrap" && terraform init -input=false && terraform apply -auto-approve && cd ..
  terraform init -input=false && terraform apply -target=module.ecr -auto-approve && cd ..
else
  echo "[1/${STEPS}] Skipping terraform (SKIP_TERRAFORM=1)"
fi

# ── 2. ECR login ────────────────────────────────────────────────────────
echo "[2/${STEPS}] Logging into ECR..."
aws ecr get-login-password --region "${AWS_REGION}" --profile personal \
  | docker login --username AWS --password-stdin "${ECR_URL}"

# ── 3-5. Docker build, tag, push ────────────────────────────────────────
echo "[3/${STEPS}] Building Docker image..."
docker buildx build --platform linux/amd64 -t "${APP_NAME}" .

echo "[4/${STEPS}] Tagging ${APP_NAME}:${IMAGE_TAG}..."
docker tag "${APP_NAME}:latest" "${ECR_URL}/${APP_NAME}:${IMAGE_TAG}"

echo "[5/${STEPS}] Pushing image..."
aws ecr get-login-password --region "${AWS_REGION}" | docker login --username AWS --password-stdin "${ECR_URL}"
docker push "${ECR_URL}/${APP_NAME}:${IMAGE_TAG}"
echo "  Pushed ${ECR_URL}/${APP_NAME}:${IMAGE_TAG}"

# ── 6. Terraform apply (full) ──────────────────────────────────────────
echo "[6/${STEPS}] Running terraform apply (env: ${ENV})..."
terraform -chdir="${TF_DIR}" init -input=false
terraform -chdir="${TF_DIR}" apply -auto-approve
echo ""

# ── 7-8. Deploy to App Runner ──────────────────────────────────────────
SERVICE_NAME="${APP_NAME}-${ENV}"

echo "[7/${STEPS}] Looking up App Runner service (${SERVICE_NAME})..."
SERVICE_ARN="$(aws apprunner list-services --region "${AWS_REGION}" \
  --query "ServiceSummaryList[?ServiceName=='${SERVICE_NAME}'].ServiceArn | [0]" --output text)"

echo "[8/${STEPS}] Starting App Runner deployment..."
aws apprunner start-deployment --service-arn "${SERVICE_ARN}" --region "${AWS_REGION}"

echo "Deployment started"
aws apprunner describe-service --service-arn "${SERVICE_ARN}" --region "${AWS_REGION}" | jq -r '.Service.Status'

while [ "$(aws apprunner describe-service --service-arn "${SERVICE_ARN}" --region "${AWS_REGION}" | jq -r '.Service.Status')" = "OPERATION_IN_PROGRESS" ]; do
    echo "Waiting for deployment to complete..."
    sleep 10
done

echo ""
echo "Deployment completed"
