#!/usr/bin/env bash
# wait_eni_release.sh — Aguarda liberação de ENIs gerenciadas pelo ECS/Lambda
# que bloqueiam o destroy do VPC (DependencyViolation em security groups).
#
# Funcionamento:
#   1. Lista ENIs com status "in-use" nos security groups do VPC alvo
#   2. Solicita desanexação das ENIs gerenciadas por ECS/Lambda (se houver)
#   3. Aguarda até que todas sejam liberadas (status "available" ou ausentes)
#   4. Se o timeout for atingido, lista as ENIs remanescentes para diagnóstico
#
# Uso:
#   bash scripts/ci/wait_eni_release.sh
#
# Env vars:
#   VPC_NAME_TAG    — tag Name do VPC (default: dm-chain-explorer-prd)
#   AWS_REGION      — região AWS (default: sa-east-1)
#   ENI_TIMEOUT     — timeout em segundos (default: 300)
set -euo pipefail

VPC_NAME_TAG="${VPC_NAME_TAG:-dm-chain-explorer-prd}"
AWS_REGION="${AWS_REGION:-sa-east-1}"
ENI_TIMEOUT="${ENI_TIMEOUT:-300}"
POLL_INTERVAL=15

echo "==> Waiting for ENI release (vpc=${VPC_NAME_TAG}, timeout=${ENI_TIMEOUT}s)"

# Obter VPC ID pelo nome
VPC_ID=$(aws ec2 describe-vpcs \
  --region "$AWS_REGION" \
  --filters "Name=tag:Name,Values=${VPC_NAME_TAG}" \
  --query 'Vpcs[0].VpcId' \
  --output text 2>/dev/null || echo "")

if [ -z "$VPC_ID" ] || [ "$VPC_ID" = "None" ]; then
  echo "  ✅ VPC '${VPC_NAME_TAG}' not found — already destroyed or doesn't exist."
  exit 0
fi

echo "  VPC ID: ${VPC_ID}"

# Detectar ENIs gerenciadas pelo ECS/Lambda (descrições reconhecidas)
_list_blocking_enis() {
  aws ec2 describe-network-interfaces \
    --region "$AWS_REGION" \
    --filters \
      "Name=vpc-id,Values=${VPC_ID}" \
      "Name=status,Values=in-use" \
    --query 'NetworkInterfaces[*].[NetworkInterfaceId,Description,InterfaceType,Attachment.AttachmentId]' \
    --output text 2>/dev/null || echo ""
}

BLOCKING=$(_list_blocking_enis)

if [ -z "$BLOCKING" ]; then
  echo "  ✅ No in-use ENIs found in VPC ${VPC_ID}."
  exit 0
fi

echo "  Found in-use ENIs:"
echo "$BLOCKING" | while read -r eni_id desc itype attach_id; do
  echo "    ${eni_id} | type=${itype} | ${desc:-<no description>}"
done

# Tentar desanexar ENIs Lambda (type=lambda) — ECS managed ENIs se auto-liberam
echo ""
echo "  Attempting to detach Lambda-managed ENIs..."
echo "$BLOCKING" | while read -r eni_id desc itype attach_id; do
  if echo "${desc:-}" | grep -qi "AWS Lambda"; then
    echo "    Detaching Lambda ENI ${eni_id} (attachment=${attach_id})..."
    aws ec2 detach-network-interface \
      --region "$AWS_REGION" \
      --attachment-id "$attach_id" \
      --force 2>/dev/null \
      && echo "    ✅ Detach requested for ${eni_id}" \
      || echo "    ⚠️  Could not detach ${eni_id} (may be already releasing)"
  fi
done

# Aguardar liberação
echo ""
echo "  Waiting for all ENIs to be released (poll every ${POLL_INTERVAL}s)..."
DEADLINE=$(( $(date +%s) + ENI_TIMEOUT ))
ATTEMPT=0

while [ "$(date +%s)" -lt "$DEADLINE" ]; do
  ATTEMPT=$((ATTEMPT + 1))
  REMAINING=$(_list_blocking_enis)
  COUNT=$(echo "$REMAINING" | grep -c '[a-z]' 2>/dev/null || echo "0")

  if [ "${COUNT:-0}" -eq 0 ] || [ -z "$REMAINING" ]; then
    echo "  ✅ All ENIs released after ${ATTEMPT} poll(s)."
    exit 0
  fi

  ELAPSED=$(( $(date +%s) - (DEADLINE - ENI_TIMEOUT) ))
  echo "  [${ELAPSED}s] ${COUNT} ENI(s) still in-use, waiting..."
  sleep "$POLL_INTERVAL"
done

# Timeout
echo ""
echo "  ❌ Timeout (${ENI_TIMEOUT}s) — remaining in-use ENIs:"
_list_blocking_enis | while read -r eni_id desc itype attach_id; do
  echo "    ${eni_id} | type=${itype} | ${desc:-<no description>}"
  echo "    Force detach: aws ec2 detach-network-interface --region ${AWS_REGION} --attachment-id ${attach_id} --force"
done
echo ""
echo "  Proceeding with terraform destroy anyway — it may fail with DependencyViolation."
exit 0
