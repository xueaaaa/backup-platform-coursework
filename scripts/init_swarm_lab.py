"""Initialise two independent nested Docker Engines, without changing the host's Swarm mode."""
import os
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COMPOSE = ['docker', 'compose', '-f', 'deploy/lab/compose.yaml']


def run(*args, capture=True):
    return subprocess.run(args, check=True, text=True, capture_output=capture,
                          cwd=ROOT, timeout=900)


def main():
    if os.environ.get('DOCKER_HOST'):
        raise SystemExit('Unset DOCKER_HOST: initialise the lab using the outer host Docker Engine')
    run(*COMPOSE, 'up', '-d', capture=False)
    for node in ('manager', 'worker'):
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            result = subprocess.run([*COMPOSE, 'exec', '-T', node, 'docker', 'info'],
                                    cwd=ROOT, capture_output=True)
            if result.returncode == 0:
                break
            time.sleep(3)
        else:
            raise SystemExit(f'{node} Docker Engine did not start')
    def inner(node, *args):
        return run(*COMPOSE, 'exec', '-T', node, 'docker', *args).stdout.strip()
    if inner('manager', 'info', '--format', '{{.Swarm.LocalNodeState}}') == 'inactive':
        inner('manager', 'swarm', 'init', '--advertise-addr', 'eth0')
    if inner('worker', 'info', '--format', '{{.Swarm.LocalNodeState}}') == 'inactive':
        # Do not print join tokens.
        token = inner('manager', 'swarm', 'join-token', '-q', 'worker')
        try:
            inner('worker', 'swarm', 'join', '--token', token, '--advertise-addr', 'eth0', 'manager:2377')
        except subprocess.CalledProcessError:
            raise SystemExit('Worker join failed; check the private lab network') from None
    manager_id = inner('manager', 'info', '--format', '{{.Swarm.NodeID}}')
    worker_id = inner('worker', 'info', '--format', '{{.Swarm.NodeID}}')
    if manager_id == worker_id:
        raise SystemExit('Manager and worker must be separate Docker Engines')
    inner('manager', 'node', 'update', '--label-add', 'backup.data=true', manager_id)
    inner('manager', 'node', 'update', '--label-add', 'backup.restore=true', worker_id)
    print(inner('manager', 'node', 'ls'))
    print('Lab ready. Use DOCKER_HOST=tcp://127.0.0.1:23750 for stack operations.')


if __name__ == '__main__':
    main()
