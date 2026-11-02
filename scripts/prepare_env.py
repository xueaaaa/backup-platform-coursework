"""Generate local secrets once, without overwriting an existing .env."""
import secrets
import argparse
from pathlib import Path

root = Path(__file__).resolve().parent.parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=Path, default=root / '.env')
args = parser.parse_args()
destination = args.output
if destination.exists():
    raise SystemExit('.env already exists; kept unchanged.')
template = (root / '.env.example').read_text(encoding='utf-8')
for placeholder in ['replace-with-a-long-random-secret', 'replace-with-at-least-12-characters',
                    'replace-source-password', 'replace-restore-password',
                    'replace-and-save-this-encryption-passphrase']:
    template = template.replace(placeholder, secrets.token_urlsafe(40))
destination.write_text(template, encoding='utf-8', newline='\n')
destination.chmod(0o600)
print(f'Created {destination.name}. Admin login: admin. Read ADMIN_PASSWORD in that file locally.')
