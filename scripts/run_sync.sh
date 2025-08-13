#!/usr/bin/env bash
# /scripts/run_sync.sh

# 외부에서 session 없이 호출할 수 있는 internal endpoint
URL="https://your-domain.com/internal/orders-sync?sync_token=${SYNC_TOKEN}"
curl -s "$URL" > /dev/null 2>&1
