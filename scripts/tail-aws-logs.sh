APP_NAME="nash"
AWS_REGION="us-west-2"
ENV="${1:-dev}"

SERVICE_NAME="${APP_NAME}-${ENV}"
AWS_ACCOUNT_ID=$(aws sts get-caller-identity | jq -r '.Account')
SERVICE_ARN="$(aws apprunner list-services --region "${AWS_REGION}" \
  --query "ServiceSummaryList[?ServiceName=='${SERVICE_NAME}'].ServiceArn | [0]" --output text)"

SERVICE_ID="$(echo "${SERVICE_ARN}" | awk -F'/' '{print $NF}')"
LOG_GROUP="/aws/apprunner/${SERVICE_NAME}/${SERVICE_ID}/service"


echo "tailing ${LOG_GROUP}"
aws logs tail "${LOG_GROUP}" \
  --region "${AWS_REGION}" \
  --follow \
  --since 1m \
  --format short &
TAIL_PID=$!

LOG_GROUP="/aws/apprunner/${SERVICE_NAME}/${SERVICE_ID}/application"

echo "tailing ${LOG_GROUP}"
aws logs tail "${LOG_GROUP}" \
  --region "${AWS_REGION}" \
  --follow \
  --since 1m \
  --format short &
APP_TAIL_PID=$!


cleanup() {
  kill "${TAIL_PID}" 2>/dev/null || true
  kill "${APP_TAIL_PID}" 2>/dev/null || true
}
trap cleanup EXIT SIGINT SIGTERM 
wait