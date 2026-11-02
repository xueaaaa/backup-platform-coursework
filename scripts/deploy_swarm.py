"""Deploy on the data/manager node and verify a real two-node backup application."""
import json
import argparse
import os
import subprocess
import time
from pathlib import Path

STACK = 'coursework-backup-cloud'
ROOT = Path(__file__).resolve().parent.parent


def docker(*args):
    return subprocess.check_output(['docker', *args], text=True, cwd=ROOT).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lab', action='store_true', help='Publish within the isolated nested manager only')
    args = parser.parse_args()
    for name in ('PANEL_IMAGE', 'ENGINE_IMAGE'):
        if not os.environ.get(name):
            raise SystemExit(f'Set {name} to the immutable release image tag')
    info = json.loads(docker('info', '--format', '{{json .Swarm}}'))
    if not info.get('ControlAvailable'):
        raise SystemExit('Run on a Swarm manager')
    ids = docker('node', 'ls', '-q').splitlines()
    nodes = json.loads(docker('node', 'inspect', *ids))
    ready = [n for n in nodes if n['Status']['State'] == 'ready'
             and n['Spec']['Availability'] == 'active']
    data = [n for n in ready if n['Spec'].get('Labels', {}).get('backup.data') == 'true']
    restore = [n for n in ready if n['Spec'].get('Labels', {}).get('backup.restore') == 'true']
    if len(data) != 1 or data[0]['ID'] != info['NodeID']:
        raise SystemExit('Exactly this manager must be labelled backup.data=true')
    if len(restore) != 1 or restore[0]['ID'] == data[0]['ID']:
        raise SystemExit('Label exactly one other ready/active node backup.restore=true')
    files = ['-c', 'stack.yaml']
    if args.lab:
        files += ['-c', 'deploy/lab/stack.override.yaml']
    docker('stack', 'deploy', '--with-registry-auth', '--resolve-image', 'always', *files, STACK)
    deadline = time.monotonic() + 900
    expected = {f'{STACK}_{s}' for s in ('panel', 'scheduler', 'source-db', 'restore-db', 'proxy')}
    while time.monotonic() < deadline:
        services = docker('stack', 'services', STACK, '--format', '{{.Name}} {{.Replicas}}')
        rows = dict(line.split() for line in services.splitlines())
        if set(rows) == expected and all(value == '1/1' for value in rows.values()):
            service_state = json.loads(docker('service', 'inspect', *sorted(expected)))
            updates = [s.get('UpdateStatus', {}).get('State') for s in service_state]
            if any(s and s.startswith(('pause', 'rollback')) for s in updates):
                raise SystemExit('Service update failed or rolled back; inspect docker service ps')
            if not all(s in (None, 'completed') for s in updates):
                time.sleep(5)
                continue
            panel_ids = docker('ps', '-q', '--filter', f'label=com.docker.swarm.service.name={STACK}_panel').splitlines()
            if len(panel_ids) == 1:
                panel = panel_ids[0]
                state = json.loads(docker('inspect', panel))[0]['State']
                if state.get('Health', {}).get('Status') == 'healthy':
                    break
        time.sleep(5)
    else:
        print(docker('stack', 'ps', STACK, '--no-trunc'))
        raise SystemExit('Services did not converge within 900 seconds')
    print(services, flush=True)
    # Uses the source and restore services across the overlay network, never mocks.
    # docker exec does not inherit exports made by the container entrypoint.
    subprocess.run(['docker', 'exec', panel, 'sh', '-c',
                    '. /usr/local/bin/load-secrets; exec python manage.py smoke_backup'],
                   check=True, timeout=300)
    proxy_id = docker('ps', '-q', '--filter', f'label=com.docker.swarm.service.name={STACK}_proxy')
    proxy = json.loads(docker('inspect', proxy_id))[0]
    address = next(n['IPAddress'] for name, n in proxy['NetworkSettings']['Networks'].items()
                   if name.endswith('_backup-net'))
    print(f'PASS: two distinct Swarm nodes, five services and real backup/restore. Proxy internal IP: {address}')
    destination = '127.0.0.1:18081' if args.lab else f'{address}:80'
    print(f'Access from your computer: ssh -N -L 8081:{destination} USER@MANAGER')


if __name__ == '__main__':
    main()
