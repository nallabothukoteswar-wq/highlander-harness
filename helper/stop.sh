#!/bin/sh
# stop.sh - Fallback script to stop worker (normally worker stops itself)
# Usage: kubectl exec -c helper <pod> -- /helper/stop.sh

PID=$(cat /shared/worker.pid)
if [ -n "$PID" ]; then
    kill -STOP "$PID"
    echo "Stopped worker PID: $PID"
else
    echo "No worker PID found"
    exit 1
fi
