#!/bin/sh
# verify_stopped.sh - Verify that worker is in stopped state (State: T)
# Usage: kubectl exec -c helper <pod> -- /helper/verify_stopped.sh

PID=$(cat /shared/worker.pid)
if [ -n "$PID" ]; then
    # Poll /proc/<pid>/status for State: T
    TIMEOUT=2
    ELAPSED=0
    while [ $ELAPSED -lt $TIMEOUT ]; do
        if grep -q "State:\s*T" /proc/$PID/status 2>/dev/null; then
            echo "Worker PID $PID is in stopped state"
            exit 0
        fi
        sleep 0.1
        ELAPSED=$((ELAPSED + 1))
    done
    echo "Worker PID $PID is not in stopped state after $TIMEOUT seconds"
    exit 1
else
    echo "No worker PID found"
    exit 1
fi
