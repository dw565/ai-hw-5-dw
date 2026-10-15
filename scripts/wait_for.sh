#!/bin/bash
# Helpers for driving a full run: wait until the team is idle, or until no request awaits approval.
# Usage: scripts/wait_for.sh idle | approvals
API=http://localhost:8000/api
case "$1" in
  idle)
    sleep 4
    until [ "$(curl -s $API/health | python3 -c 'import json,sys;print(json.load(sys.stdin)["busy"])')" = "False" ]; do sleep 3; done ;;
  approvals)
    until [ "$(curl -s $API/payments?status=pending_approval | python3 -c 'import json,sys;print(len(json.load(sys.stdin)))')" = "0" ]; do sleep 3; done ;;
esac
echo "--- tickets"; curl -s $API/tickets | python3 -c 'import json,sys;[print(t["id"],t["status"]) for t in json.load(sys.stdin)]'
echo "--- requests"; curl -s $API/payments | python3 -c 'import json,sys;[print(p["id"],p["kind"],p["amount"],p["status"],p["ticket_id"],p["decided_by"]) for p in json.load(sys.stdin)]'
echo "--- cash"; curl -s $API/cash; echo
