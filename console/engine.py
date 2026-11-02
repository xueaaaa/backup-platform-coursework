"""Adapter to existing Borg/borgmatic CLIs; contains no backup implementation."""
import json
import os
import re
import subprocess
from pathlib import Path

import yaml
from django.conf import settings


class EngineError(Exception):
    pass


def config_path(plan):
    return settings.BACKUP_CONFIG_DIR / f'plan-{plan.pk}.yaml'


def repository_path(plan):
    return settings.BACKUP_REPOSITORY_DIR / f'plan-{plan.pk}'


def prepare_directories():
    for directory in [settings.BACKUP_CONFIG_DIR, settings.BACKUP_CRON_DIR, settings.BACKUP_LOG_DIR,
                      settings.BACKUP_REPOSITORY_DIR, settings.BACKUP_LOCK_DIR]:
        directory.mkdir(parents=True, exist_ok=True)


def atomic_write(path, content, mode=0o600):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(content, encoding='utf-8', newline='\n')
    temporary.chmod(mode)
    temporary.replace(path)


def configuration(plan):
    return {
        'repositories': [{'path': str(repository_path(plan))}],
        'source_directories': [],
        'encryption_passphrase': '${BORG_PASSPHRASE}',
        'archive_name_format': f'plan-{plan.pk}-{{now:%Y-%m-%dT%H:%M:%S.%f}}',
        'keep_daily': plan.keep_daily,
        'keep_weekly': plan.keep_weekly,
        'checks': [{'name': 'repository', 'frequency': '1 day'}],
        'postgresql_databases': [{
            'name': 'coursework', 'hostname': 'source-db', 'port': 5432,
            'username': 'backup', 'password': '${SOURCE_DB_PASSWORD}', 'format': 'custom',
            'restore_hostname': 'restore-db', 'restore_port': 5432,
            'restore_username': 'backup', 'restore_password': '${RESTORE_DB_PASSWORD}',
        }],
    }


def sync_plan(plan):
    prepare_directories()
    atomic_write(config_path(plan), yaml.safe_dump(configuration(plan), allow_unicode=True))
    cron_path = settings.BACKUP_CRON_DIR / f'plan-{plan.pk}'
    if plan.enabled:
        # All shell fragments are constants or server-generated integer identifiers.
        # No user-supplied command, path, database name, or cron expression is accepted.
        if plan.schedule not in dict(plan.SCHEDULES):
            raise EngineError('Недопустимое расписание')
        atomic_write(cron_path, cron_entry(plan), 0o644)
    else:
        cron_path.unlink(missing_ok=True)


def cron_entry(plan):
    # Paths are fixed Linux container paths. Debian cron requires a final newline.
    return (
        'SHELL=/bin/sh\nPATH=/usr/local/bin:/usr/bin:/bin\n'
        f'{plan.schedule} root /usr/local/bin/run-backup {plan.pk}'
        f' >> /logs/plan-{plan.pk}.log 2>&1\n'
    )


def remove_plan_files(plan):
    (settings.BACKUP_CRON_DIR / f'plan-{plan.pk}').unlink(missing_ok=True)
    config_path(plan).unlink(missing_ok=True)
    # Archive data and logs are deliberately retained for recovery.


def redact(text):
    for key in ['SOURCE_DB_PASSWORD', 'RESTORE_DB_PASSWORD', 'BORG_PASSPHRASE']:
        secret = os.environ.get(key)
        if secret:
            text = text.replace(secret, '[скрыто]')
    return text


def command(plan, action, archive='latest'):
    base = ['borgmatic', '-c', str(config_path(plan))]
    actions = {
        'init': ['repo-create', '--encryption', 'repokey-blake2'],
        'backup': ['create', 'prune', 'compact'],
        'check': ['check', '--force'],
        'archives': ['repo-list', '--json'],
    }
    if action == 'restore':
        if archive != 'latest' and not re.fullmatch(r'[a-f0-9]{64}', archive):
            raise EngineError('Недопустимый идентификатор архива')
        # Destination comes exclusively from restore_* config, never from a request.
        # borgmatic 1.9.14 matches a configured dump port against --original-port.
        # This selects the source dump; restore_port/restore_hostname set its destination.
        return base + ['restore', '--archive', archive, '--database', 'coursework',
                       '--original-port', '5432']
    if action not in actions:
        raise EngineError('Неизвестная операция')
    return base + actions[action]


def execute(plan, action, archive='latest'):
    prepare_directories()
    args = command(plan, action, archive)
    # Manual and cron operations use exactly the same cross-process lock.
    args = ['timeout', '--kill-after=5s', str(settings.BACKUP_TIMEOUT),
            'flock', '-n', '-E', '75', str(settings.BACKUP_LOCK_DIR / f'plan-{plan.pk}')] + args
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=settings.BACKUP_TIMEOUT + 15,
                                encoding='utf-8', errors='replace', check=False)
    except FileNotFoundError as exc:
        raise EngineError('Borgmatic доступен в Docker-стенде. Запустите проект через Docker Compose.') from exc
    except subprocess.TimeoutExpired as exc:
        raise EngineError('Превышено время ожидания. Проверьте состояние процессов и журнал перед повторным запуском.') from exc
    output = redact(result.stdout + '\n' + result.stderr).strip()
    if result.returncode == 75:
        raise EngineError('Для этого задания уже выполняется другая операция.')
    if result.returncode != 0:
        raise EngineError(output[-12000:] or f'Команда завершилась с кодом {result.returncode}')
    return result.stdout if action == 'archives' else output[-12000:]


def archives(plan):
    try:
        return json.loads(execute(plan, 'archives'))[0]['archives']
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise EngineError('Неожиданный ответ borgmatic при чтении архивов') from exc


def scheduled_log(plan):
    path = settings.BACKUP_LOG_DIR / f'plan-{plan.pk}.log'
    if not path.exists():
        return 'Планировщик пока не записал журнал.'
    with path.open('rb') as stream:
        stream.seek(max(0, path.stat().st_size - 16000))
        return redact(stream.read().decode('utf-8', errors='replace'))
