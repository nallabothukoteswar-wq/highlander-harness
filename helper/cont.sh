#!/bin/sh
# cont.sh - Resume worker and record fault marker
# Usage: kubectl exec -c helper <pod> -- /helper/cont.sh

PID=$(cat /shared/worker.pid)
if [ -n "$PID" ]; then
    # Record fault marker using database clock
    PGPASSWORD=worker_password psql -h postgres -U worker_rw -d highlander -c \
        "INSERT INTO ctl.fault_markers (trial_id, worker_id, incarnation, marker_type, at) \
         VALUES ((SELECT trial_id FROM ctl.trials ORDER BY started_at DESC LIMIT 1), \
                 '$(hostname)', \
                 (SELECT incarnation FROM ctl.incarnations WHERE worker_id = '$(hostname)' ORDER BY started_at DESC LIMIT 1), \
                 'cont', clock_timestamp());"

    # Resume worker
    kill -CONT "$PID"
    echo "Resumed worker PID: $PID"
else
    echo "No worker PID found"
    exit 1
fi
