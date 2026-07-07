#!/usr/bin/env bash
set -euo pipefail

CLICKHOUSE_PASSWORD="${CLICKHOUSE_PASSWORD:-secret}"

ch_query() {
  kubectl exec -it -n clickhouse chi-clickhouse-clickhouse-0-0-0 -- \
    clickhouse-client --password "$CLICKHOUSE_PASSWORD" \
    --query "$1" 2>/dev/null
}

snapshot() {
  echo "pods:"
  kubectl get pods -n default --no-headers | awk '{print "  "$1, $3, "restarts="$4}'
  echo "agg_edits: $(ch_query 'SELECT count(), max(tick_start) FROM agg_edits')"
}

wait_for_running() {
  echo "Waiting for consumer to be Running..."
  for i in $(seq 1 30); do
    status=$(kubectl get pods -n default --no-headers | grep consumer-consumer | awk '{print $3}' | head -1)
    if [ "$status" = "Running" ]; then
      echo "Consumer is Running."
      return 0
    fi
    sleep 5
  done
  echo "Warning: consumer did not reach Running state in time."
}

run_pod_kill() {
  echo "======================================"
  echo "SCENARIO 1: pod-kill"
  echo "Kills the consumer pod. Kubernetes restarts it automatically."
  echo "Consumer resumes from last checkpoint in ClickHouse."
  echo "======================================"

  echo ""
  echo "[before]"
  snapshot

  echo ""
  echo "Applying pod-kill chaos..."
  kubectl apply -f chaos/pod-kill.yaml

  sleep 5
  echo ""
  echo "[during — pod killed]"
  snapshot

  sleep 30
  echo ""
  echo "[after — pod restarted]"
  snapshot

  kubectl delete -f chaos/pod-kill.yaml --ignore-not-found
  echo ""
}

run_network_partition() {
  echo "======================================"
  echo "SCENARIO 2: network-partition"
  echo "Cuts network between consumer and ClickHouse."
  echo "Consumer crashes on failed INSERT -> CrashLoopBackOff."
  echo "After chaos removed -> rollout restart -> data resumes."
  echo "======================================"

  echo ""
  echo "[before]"
  snapshot

  echo ""
  echo "Applying network-partition chaos..."
  kubectl apply -f chaos/network-partition.yaml

  sleep 30
  echo ""
  echo "[during — network cut, data frozen]"
  snapshot

  sleep 150  # 2.5 minutes total — enough to see CrashLoopBackOff
  echo ""
  echo "[during — CrashLoopBackOff in progress]"
  snapshot

  echo ""
  echo "Removing network-partition chaos..."
  kubectl delete -f chaos/network-partition.yaml --ignore-not-found

  echo ""
  echo "Restarting consumer to reset CrashLoopBackOff backoff..."
  kubectl rollout restart deployment consumer-consumer -n default

  wait_for_running

  sleep 30
  echo ""
  echo "[after — data resumed]"
  snapshot
}

echo "Wiki Edit Monitor — Chaos Engineering Demo"
echo "$(date)"
echo ""

case "${1:-all}" in
  pod-kill)
    run_pod_kill
    ;;
  network-partition)
    run_network_partition
    ;;
  all)
    run_pod_kill
    run_network_partition
    ;;
  *)
    echo "Usage: $0 [pod-kill|network-partition|all]"
    exit 1
    ;;
esac

echo ""
echo "Done."