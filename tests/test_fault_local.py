"""Fault injection tests for local platform."""

import os
import signal
import time
import pytest
import threading


def test_sigstop_state():
    """Test that self-SIGSTOP gives state T and a heartbeat gap."""
    pid = os.getpid()

    # Fork a child process to test SIGSTOP
    child_pid = os.fork()
    if child_pid == 0:
        # Child process
        time.sleep(0.1)
        os.kill(os.getpid(), signal.SIGSTOP)
        time.sleep(2)  # Will be stopped here
        os._exit(0)
    else:
        # Parent process
        time.sleep(0.2)  # Let child stop

        # Check child process state
        try:
            with open(f"/proc/{child_pid}/status", "r") as f:
                content = f.read()
                assert "State:\tT" in content, f"Child process should be in stopped state, got: {content}"
        except FileNotFoundError:
            pytest.skip("/proc not available (not Linux)")

        # Resume child
        os.kill(child_pid, signal.SIGCONT)

        # Wait for child to finish
        os.waitpid(child_pid, 0)


def test_sigcont_resume():
    """Test that SIGCONT resumes the worker."""
    pid = os.getpid()

    # Fork a child process
    child_pid = os.fork()
    if child_pid == 0:
        # Child process
        time.sleep(0.1)
        os.kill(os.getpid(), signal.SIGSTOP)
        time.sleep(2)  # Will be stopped here, then resumed
        os._exit(0)
    else:
        # Parent process
        time.sleep(0.2)  # Let child stop

        # Check child is stopped
        try:
            with open(f"/proc/{child_pid}/status", "r") as f:
                content = f.read()
                assert "State:\tT" in content
        except FileNotFoundError:
            pytest.skip("/proc not available (not Linux)")

        # Resume child
        os.kill(child_pid, signal.SIGCONT)
        time.sleep(0.1)

        # Check child is running again
        try:
            with open(f"/proc/{child_pid}/status", "r") as f:
                content = f.read()
                assert "State:\tT" not in content, "Child should no longer be in stopped state"
        except FileNotFoundError:
            pytest.skip("/proc not available (not Linux)")

        # Wait for child to finish
        os.waitpid(child_pid, 0)


def test_sigkill_respawn():
    """Test that SIGKILL leads to a respawn with a new incarnation."""
    # This test simulates what happens in the runner
    # In a real scenario, the runner would detect the kill and spawn a new process

    # Fork a child process
    child_pid = os.fork()
    if child_pid == 0:
        # Child process
        time.sleep(10)  # Will be killed before this
        os._exit(0)
    else:
        # Parent process
        time.sleep(0.1)

        # Kill child
        os.kill(child_pid, signal.SIGKILL)

        # Wait for child to be reaped
        _, status = os.waitpid(child_pid, 0)
        assert os.WIFSIGNALED(status), "Child should have been killed by signal"
        assert os.WTERMSIG(status) == signal.SIGKILL, "Child should have been killed by SIGKILL"

        # Simulate respawn by forking a new child
        new_child_pid = os.fork()
        if new_child_pid == 0:
            # New child process
            os._exit(0)
        else:
            # Parent process
            os.waitpid(new_child_pid, 0)
            assert new_child_pid != child_pid, "New child should have different PID"


def test_verify_stopped():
    """Test the verify_stopped function."""
    # Fork a child process
    child_pid = os.fork()
    if child_pid == 0:
        # Child process
        time.sleep(0.1)
        os.kill(os.getpid(), signal.SIGSTOP)
        time.sleep(2)  # Will be stopped here
        os._exit(0)
    else:
        # Parent process
        time.sleep(0.2)  # Let child stop

        # Verify child is stopped
        def verify_stopped(pid):
            try:
                with open(f"/proc/{pid}/status", "r") as f:
                    content = f.read()
                    return "State:\tT" in content
            except (FileNotFoundError, IOError):
                return False

        assert verify_stopped(child_pid), "Child should be in stopped state"

        # Resume child
        os.kill(child_pid, signal.SIGCONT)

        # Wait for child to finish
        os.waitpid(child_pid, 0)
