#!/bin/sh
# kill.sh - Kill worker and bracket the kill with database markers
# Usage: kubectl exec -c helper <pod> -- /helper/kill.sh

PID=$(cat /shared/worker.pid)
if [ -n "$PID" ]; then
    # Record before marker
    PGPASSWORD=worker_password psql -h postgres -U worker_rw -d highlander -c \
        "INSERT INTO ctl.kill_markers (trial_id, worker_id, incarnation, marker_type, at) \
         VALUES ((SELECT trial_id FROM ctl.trials ORDER BY started_at DESC LIMIT 1), \
                 '$(hostname)', \
                 (SELECT incarnation FROM ctl.incarnations WHERE worker_id = '$(hostname)' ORDER BY started_at DESC LIMIT 1), \
                 'before', clock_timestamp());"

    # Kill worker
    kill -KILL "$PID"
    echo "Killed worker PID: $PID"

    # Record after marker
    PGPASSWORD=worker_password psql -h postgres -U worker_rw -d highlander -c \
        "INSERT INTO ctl.kill_markers (trial_id, worker_id, incarnation, marker_type, at) \
         VALUES ((SELECT trial_id FROM ctl.trials ORDER BY started_at DESC LIMIT 1), \
                 '$(hostname)', \
                 (SELECT incarnation FROM ctl.incarnations WHERE worker_id = '$(hostname)' ORDER BY started_at DESC LIMIT 1), \
                 'after', clock_timestamp());"
else
    echo "No worker PID found"
    exit 1
fi
