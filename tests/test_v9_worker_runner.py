"""Reproductions for worker identity and deterministic trial bookkeeping."""
import json
import subprocess
import sys
import uuid
from types import SimpleNamespace

from runner.trials import TrialRunner
from worker.faults import FaultManager
from worker.heartbeat import HeartbeatThread
from worker.lifecycle import LifecycleManager
from worker.ownership import OwnershipManager
from worker.sinks import SinkManager
from worker.workloads import ItemPreparer, WorkloadGenerator


def test_d9_one_incarnation_passed_to_all_managers():
    identity = uuid.uuid4()
    config = SimpleNamespace(trial_id='v9', worker_id='worker', stream_id='S1', condition='C3',
                             lease_secs=60, num_items=1, workload='ordered', prep_cpu_ms=0)
    managers = (LifecycleManager(None, config, identity),
                OwnershipManager(None, config, identity),
                SinkManager(None, None, config, identity),
                FaultManager(None, config, identity),
                WorkloadGenerator(None, config, identity),
                ItemPreparer(config, identity),
                HeartbeatThread(None, config, None, identity))
    assert {m.incarnation for m in managers} == {identity}


def test_d11_trial_id_and_seed_stable_across_python_processes(tmp_path):
    runner = TrialRunner(None, str(tmp_path), False, 1)
    cell = {'condition': 'C2', 'workload': 'ordered'}
    local = (runner._generate_trial_id('A', cell, 3), runner._trial_seed('A', cell, 3))
    code = ("import json; from runner.trials import TrialRunner; "
            "r=TrialRunner(None, '/tmp/v9-no-trials', False, 1); "
            "c={'condition':'C2','workload':'ordered'}; "
            "print(json.dumps([r._generate_trial_id('A',c,3),r._trial_seed('A',c,3)]))")
    remote = json.loads(subprocess.check_output([sys.executable, '-c', code], text=True))
    assert local == tuple(remote)
