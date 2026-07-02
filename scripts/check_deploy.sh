#!/usr/bin/env bash
# 배포 후 주요 JSON 파일 HTTP 200 + 최신 날짜 확인
set -euo pipefail

BASE="${1:-https://soc-intelligence.pages.dev}"
TODAY=$(date -u +%Y-%m-%d)
FAIL=0
TMP=$(mktemp)

check() {
  local path="$1"
  local url="$BASE/$path"
  local status
  status=$(curl -s -o "$TMP" -w "%{http_code}" --max-time 15 "$url")
  if [ "$status" != "200" ]; then
    echo "FAIL  HTTP $status — $url"
    FAIL=1
    return
  fi
  if grep -q "$TODAY" "$TMP" 2>/dev/null; then
    echo "OK    $url ($TODAY 확인)"
  else
    echo "WARN  $url — 오늘 날짜 미포함 (데이터 갱신 여부 수동 확인)"
  fi
}

check "data/refined/company_summaries.json"
check "data/refined/foundry/tsmc.json"
check "data/refined/mobile_ap/apple.json"
check "data/refined/hpc_datacenter/nvidia.json"

rm -f "$TMP"

if [ $FAIL -ne 0 ]; then
  echo "배포 검증 실패 — 위 FAIL 항목 확인"
  exit 1
fi
echo "배포 검증 완료 → $BASE"
