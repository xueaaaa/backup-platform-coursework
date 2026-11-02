"""Create immutable Docker Swarm secrets from a server-local env file, without printing values."""
import argparse
import subprocess
from pathlib import Path

KEYS = ('DJANGO_SECRET_KEY', 'ADMIN_PASSWORD', 'SOURCE_DB_PASSWORD',
        'RESTORE_DB_PASSWORD', 'BORG_PASSPHRASE')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('env_file', type=Path)
    args = parser.parse_args()
    values = dict(line.split('=', 1) for line in args.env_file.read_text(encoding='utf-8-sig').splitlines()
                  if line.strip() and not line.lstrip().startswith('#') and '=' in line)
    for key in KEYS:
        value = values.get(key, '')
        if len(value) < 12 or value.startswith('replace-'):
            raise SystemExit(f'Missing or placeholder value: {key}')
    for key in KEYS:
        name = f'coursework-{key}'
        existing = subprocess.run(['docker', 'secret', 'inspect', name],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if existing.returncode == 0:
            print(f'Kept existing secret: {name}')
            continue
        subprocess.run(['docker', 'secret', 'create', name, '-'],
                       input=values[key].encode(), check=True, stdout=subprocess.DEVNULL)
        print(f'Created secret: {name}')


if __name__ == '__main__':
    main()
