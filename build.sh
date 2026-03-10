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
docker tag "${APP_NAME}:latest" "${ECR_URL}/${APP_NAME}-${ENV}:${IMAGE_TAG}"

echo "[5/${STEPS}] Pushing image..."
aws ecr get-login-password --region "${AWS_REGION}" | docker login --username AWS --password-stdin "${ECR_URL}"
docker push "${ECR_URL}/${APP_NAME}-${ENV}:${IMAGE_TAG}"
echo "  Pushed ${ECR_URL}/${APP_NAME}-${ENV}:${IMAGE_TAG}"

if [[ "${SKIP_TERRAFORM:-0}" != "1" ]]; then
# ── 6. Terraform apply (full) ──────────────────────────────────────────
echo "[6/${STEPS}] Running terraform apply (env: ${ENV})..."
  terraform -chdir="${TF_DIR}" init -input=false
  terraform -chdir="${TF_DIR}" plan
  read -p "Apply changes? (y/n): " apply
  if [[ "${apply}" == "y" ]]; then
    terraform -chdir="${TF_DIR}" apply -auto-approve
  fi
  echo ""
fi

# ── 7-8. Deploy to App Runner ──────────────────────────────────────────

SERVICE_NAME="${APP_NAME}-${ENV}"

echo "[7/${STEPS}] Looking up App Runner service (${SERVICE_NAME})..."
SERVICE_ARN="$(aws apprunner list-services --region "${AWS_REGION}" \
  --query "ServiceSummaryList[?ServiceName=='${SERVICE_NAME}'].ServiceArn | [0]" --output text)"

echo "[8/${STEPS}] Starting App Runner deployment..."
aws apprunner start-deployment --service-arn "${SERVICE_ARN}" --region "${AWS_REGION}"

# Derive the CloudWatch log group from the service ARN:
# arn:aws:apprunner:region:account:service/name/service-id
SERVICE_ID="$(echo "${SERVICE_ARN}" | awk -F'/' '{print $NF}')"
LOG_GROUP="/aws/apprunner/${SERVICE_NAME}/${SERVICE_ID}/service"

echo "Deployment started — tailing ${LOG_GROUP}"
aws logs tail "${LOG_GROUP}" \
  --region "${AWS_REGION}" \
  --follow \
  --since 1m \
  --format short &
TAIL_PID=$!

LOG_GROUP="/aws/apprunner/${SERVICE_NAME}/${SERVICE_ID}/application"

echo "Deployment started — tailing ${LOG_GROUP}"
aws logs tail "${LOG_GROUP}" \
  --region "${AWS_REGION}" \
  --follow \
  --since 1m \
  --format short &
APP_TAIL_PID=$!

while [ "$(aws apprunner describe-service --service-arn "${SERVICE_ARN}" --region "${AWS_REGION}" | jq -r '.Service.Status')" = "OPERATION_IN_PROGRESS" ]; do
    sleep 10
done


STATUS="$(aws apprunner describe-service --service-arn "${SERVICE_ARN}" --region "${AWS_REGION}" | jq -r '.Service.Status')"
echo ""
echo "Deployment completed — status: ${STATUS}"

cleanup() {
  kill "${TAIL_PID}" 2>/dev/null || true
  kill "${APP_TAIL_PID}" 2>/dev/null || true
}
trap cleanup EXIT SIGINT SIGTERM 