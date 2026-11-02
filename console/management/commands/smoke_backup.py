"""Real integration check; executed inside the Docker panel, never mocked."""
import os
import subprocess

from django.core.management.base import BaseCommand, CommandError
from console import engine
from console.models import Plan


def read_demo_rows(host, password):
    env = os.environ.copy()
    env['PGPASSWORD'] = password
    result = subprocess.run([
        'psql', '-X', '-A', '-t', '-v', 'ON_ERROR_STOP=1', '-h', host,
        '-U', 'backup', '-d', 'coursework', '-c',
        "SELECT coalesce(jsonb_agg(to_jsonb(p) ORDER BY id), '[]'::jsonb) FROM projects p",
    ], env=env, capture_output=True, text=True, check=True, timeout=20)
    return result.stdout.strip()


class Command(BaseCommand):
    help = 'Создать реальную копию, восстановить только restore-db и сравнить тестовые записи'

    def handle(self, *args, **options):
        plan = Plan.objects.first()
        if plan is None:
            raise CommandError('Сначала выполните bootstrap')
        engine.sync_plan(plan)
        try:
            if not (engine.repository_path(plan) / 'config').exists():
                engine.execute(plan, 'init')
            before = read_demo_rows('source-db', os.environ['SOURCE_DB_PASSWORD'])
            engine.execute(plan, 'backup')
            if not engine.archives(plan):
                raise CommandError('Архив не появился')
            engine.execute(plan, 'check')
            engine.execute(plan, 'restore')
            restored = read_demo_rows('restore-db', os.environ['RESTORE_DB_PASSWORD'])
            after = read_demo_rows('source-db', os.environ['SOURCE_DB_PASSWORD'])
            if before != restored or before != after:
                raise CommandError('Содержимое БД не совпало после восстановления')
        except (engine.EngineError, subprocess.SubprocessError) as exc:
            raise CommandError(engine.redact(str(exc))) from exc
        self.stdout.write(self.style.SUCCESS('PASS: архив создан, проверен и восстановлен; тестовые записи совпадают; исходная БД не изменена.'))
