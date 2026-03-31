"""
Process manager — spawns and controls pipeline subprocesses.
Two singleton instances are exported:
  process_manager    — Phase 1 (main.py)
  process_manager_p2 — Phase 2 (main_phase2.py)
"""

import json
import os
import queue
import signal
import subprocess
import sys
import threading
from collections import deque
from datetime import datetime
from pathlib import Path


class ProcessManager:
    VALID_STATES = ('idle', 'running', 'paused', 'stopping')

    def __init__(self, root: Path):
        self._root        = root
        self._lock        = threading.Lock()
        self._proc        = None
        self._state       = 'idle'
        self._started_at  = None
        self._exit_code   = None
        self._log_buffer  = deque(maxlen=500)
        self._listeners: list[queue.Queue] = []

    # ── Public state ──────────────────────────────────────────────────────────

    @property
    def state(self) -> str:
        with self._lock:
            self._sync_state()
            return self._state

    def status(self) -> dict:
        with self._lock:
            self._sync_state()
            elapsed = None
            if self._started_at and self._state != 'idle':
                elapsed = round((datetime.utcnow() - self._started_at).total_seconds())
            return {
                'state':      self._state,
                'pid':        self._proc.pid if self._proc else None,
                'started_at': self._started_at.isoformat() if self._started_at else None,
                'elapsed':    elapsed,
                'exit_code':  self._exit_code,
            }

    def get_buffer(self) -> list[str]:
        with self._lock:
            return list(self._log_buffer)

    # ── Controls ──────────────────────────────────────────────────────────────

    def start(
        self,
        config: dict | None = None,
        script: str = 'main.py',
        env_extra: dict | None = None,
    ) -> tuple[bool, str]:
        with self._lock:
            self._sync_state()
            if self._state != 'idle':
                return False, f'A run is already {self._state}'

            # Write run config override file if provided (phase 1 only)
            if config:
                config_path = self._root / 'outputs' / 'run_config.json'
                config_path.parent.mkdir(parents=True, exist_ok=True)
                config_path.write_text(json.dumps(config, indent=2))

            self._log_buffer.clear()
            self._started_at = datetime.utcnow()
            self._exit_code  = None

            env = os.environ.copy()
            env['PYTHONUNBUFFERED'] = '1'  # force line-buffered output
            if env_extra:
                env.update({k: str(v) for k, v in env_extra.items()})

            self._proc = subprocess.Popen(
                [sys.executable, script],
                cwd=str(self._root),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            self._state = 'running'

        # Start reader thread outside the lock
        threading.Thread(target=self._read_output, daemon=True).start()
        return True, self._proc.pid

    def stop(self) -> tuple[bool, str]:
        with self._lock:
            self._sync_state()
            if self._state == 'idle':
                return False, 'Nothing is running'
            if self._state == 'paused':
                # Must resume before it can handle SIGTERM
                try:
                    self._proc.send_signal(signal.SIGCONT)
                except ProcessLookupError:
                    pass
            self._state = 'stopping'
            proc = self._proc

        try:
            proc.terminate()
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        except ProcessLookupError:
            pass

        with self._lock:
            self._state = 'idle'
            self._proc  = None
        self._broadcast(None)  # signal end-of-stream to SSE clients
        return True, 'Stopped'

    def pause(self) -> tuple[bool, str]:
        with self._lock:
            self._sync_state()
            if self._state != 'running':
                return False, 'Run is not active'
            try:
                self._proc.send_signal(signal.SIGSTOP)
            except ProcessLookupError:
                return False, 'Process not found'
            self._state = 'paused'
        return True, 'Paused'

    def resume(self) -> tuple[bool, str]:
        with self._lock:
            self._sync_state()
            if self._state != 'paused':
                return False, 'Run is not paused'
            try:
                self._proc.send_signal(signal.SIGCONT)
            except ProcessLookupError:
                return False, 'Process not found'
            self._state = 'running'
        return True, 'Resumed'

    # ── SSE subscription ──────────────────────────────────────────────────────

    def subscribe(self, q: queue.Queue):
        with self._lock:
            self._listeners.append(q)

    def unsubscribe(self, q: queue.Queue):
        with self._lock:
            try:
                self._listeners.remove(q)
            except ValueError:
                pass

    # ── Internal ──────────────────────────────────────────────────────────────

    def _sync_state(self):
        """Check if the process has exited naturally. Must be called under lock."""
        if self._proc is not None and self._proc.poll() is not None:
            self._exit_code = self._proc.returncode
            self._state     = 'idle'
            self._proc      = None

    def _broadcast(self, item):
        """Send item to all SSE subscribers. None = end-of-stream sentinel."""
        with self._lock:
            for q in self._listeners:
                q.put(item)

    def _read_output(self):
        """Background thread: read subprocess stdout line by line."""
        try:
            for raw in self._proc.stdout:
                line = raw.rstrip('\n')
                with self._lock:
                    self._log_buffer.append(line)
                for q in list(self._listeners):
                    q.put(line)
        except Exception:
            pass
        finally:
            with self._lock:
                self._sync_state()
            self._broadcast(None)  # end-of-stream


# Singletons — imported by api.py
ROOT = Path(__file__).parent.parent
process_manager    = ProcessManager(ROOT)   # Phase 1
process_manager_p2 = ProcessManager(ROOT)   # Phase 2
