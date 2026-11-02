import json
import os
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth.models import Permission, User
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from . import engine
from .forms import PlanForm
from .models import Operation, Plan


class PanelTests(TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.override = override_settings(**{
            f'BACKUP_{name}_DIR': root / name.lower()
            for name in ['CONFIG', 'CRON', 'LOG', 'REPOSITORY', 'LOCK']
        })
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.addCleanup(self.temp.cleanup)
        self.admin = User.objects.create_superuser('admin', '', 'a-strong-test-password')
        self.reader = User.objects.create_user('reader', password='a-strong-test-password')
        self.reader.user_permissions.add(Permission.objects.get(codename='view_plan'))
        self.plan = Plan.objects.create(name='Учебная база')
        engine.sync_plan(self.plan)

    def test_anonymous_redirects_to_login(self):
        self.assertRedirects(self.client.get('/'), '/login/?next=/', fetch_redirect_response=False)

    def test_login_and_dashboard_render(self):
        self.assertTrue(self.client.login(username='admin', password='a-strong-test-password'))
        self.assertContains(self.client.get('/'), 'Учебная база')

    def test_reader_cannot_create_edit_delete_or_operate(self):
        self.client.force_login(self.reader)
        for url, data in [('/plans/new/', {}), (f'/plans/{self.plan.pk}/edit/', {}),
                          (f'/plans/{self.plan.pk}/delete/', {}),
                          (f'/plans/{self.plan.pk}/action/', {'action': 'backup'}),
                          (f'/plans/{self.plan.pk}/action/', {'action': 'restore', 'confirmation': 'ВОССТАНОВИТЬ'})]:
            with self.subTest(url=url, data=data):
                self.assertEqual(self.client.post(url, data).status_code, 403)
        self.assertEqual(Operation.objects.count(), 0)

    def test_create_update_delete_keeps_archives(self):
        self.client.force_login(self.admin)
        response = self.client.post('/plans/new/', {'name': 'Новый план', 'schedule': '0 * * * *', 'keep_daily': 3, 'keep_weekly': 1})
        self.assertEqual(response.status_code, 302)
        plan = Plan.objects.get(name='Новый план')
        repository = engine.repository_path(plan)
        repository.mkdir()
        (repository / 'config').write_text('borg repository')
        self.client.post(f'/plans/{plan.pk}/edit/', {'name': 'Изменённый', 'schedule': '*/5 * * * *', 'keep_daily': 3, 'keep_weekly': 1, 'enabled': 'on'})
        plan.refresh_from_db()
        self.assertTrue(plan.enabled)
        cron = engine.settings.BACKUP_CRON_DIR / f'plan-{plan.pk}'
        self.assertTrue(cron.exists())
        self.client.post(f'/plans/{plan.pk}/delete/')
        self.assertFalse(cron.exists())
        self.assertTrue(repository.exists())

    def test_cannot_schedule_before_initialization(self):
        form = PlanForm({'name': 'Bad', 'schedule': '0 * * * *', 'keep_daily': 7, 'keep_weekly': 1, 'enabled': 'on'})
        self.assertFalse(form.is_valid())
        self.assertIn('enabled', form.errors)

    def test_cannot_inject_cron_expression(self):
        form = PlanForm({'name': 'Bad', 'schedule': '* * * * *; touch /tmp/injected', 'keep_daily': 7, 'keep_weekly': 1})
        self.assertFalse(form.is_valid())
        self.assertIn('schedule', form.errors)

    def test_restore_requires_confirmation(self):
        self.client.force_login(self.admin)
        with patch('console.engine.execute') as execute:
            response = self.client.post(f'/plans/{self.plan.pk}/action/', {'action': 'restore'})
        self.assertEqual(response.status_code, 400)
        execute.assert_not_called()

    def test_csrf_required_for_operations(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin)
        response = client.post(f'/plans/{self.plan.pk}/action/', {'action': 'backup'})
        self.assertEqual(response.status_code, 403)

    def test_get_cannot_run_backup(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(f'/plans/{self.plan.pk}/action/').status_code, 405)

    @patch('console.engine.execute', return_value='Created archive')
    def test_success_is_recorded(self, execute):
        self.client.force_login(self.admin)
        self.client.post(f'/plans/{self.plan.pk}/action/', {'action': 'backup'})
        operation = Operation.objects.get()
        self.assertTrue(operation.success)
        self.assertEqual(operation.user, 'admin')
        self.assertIsNotNone(operation.finished_at)

    @patch.dict(os.environ, {'SOURCE_DB_PASSWORD': 'top-secret-value'})
    @patch('console.engine.execute', side_effect=engine.EngineError('failed top-secret-value'))
    def test_failure_is_recorded_without_secret(self, execute):
        self.client.force_login(self.admin)
        self.client.post(f'/plans/{self.plan.pk}/action/', {'action': 'backup'})
        operation = Operation.objects.get()
        self.assertFalse(operation.success)
        self.assertNotIn('top-secret-value', operation.output)

    @patch('console.engine.archives', return_value=[{'name': '<script>alert(1)</script>', 'id': 'a' * 64, 'time': '2026-10-30'}])
    def test_details_escape_archive_names(self, archives):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('plan-detail', args=[self.plan.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, '<script>')
        self.assertContains(response, '&lt;script&gt;')

    def test_configuration_uses_ready_database_hook_and_separate_restore_host(self):
        config = engine.configuration(self.plan)
        source = config['postgresql_databases'][0]
        self.assertEqual(source['hostname'], 'source-db')
        self.assertEqual(source['restore_hostname'], 'restore-db')
        self.assertEqual(source['format'], 'custom')
        self.assertEqual(source['password'], '${SOURCE_DB_PASSWORD}')
        self.assertNotIn('before_backup', config)

    def test_configuration_validates_against_borgmatic_schema(self):
        import borgmatic.config.validate
        parsed, paths, logs = borgmatic.config.validate.parse_configuration(
            str(engine.config_path(self.plan)), borgmatic.config.validate.schema_filename(), resolve_env=False,
        )
        self.assertEqual(parsed['postgresql_databases'][0]['restore_hostname'], 'restore-db')

    def test_generated_commands_are_supported_by_pinned_borgmatic(self):
        from borgmatic.commands.arguments import parse_arguments
        for action in ['init', 'backup', 'check', 'archives', 'restore']:
            with self.subTest(action=action):
                parsed = parse_arguments(*engine.command(self.plan, action)[1:])
                self.assertTrue(parsed)

    def test_restore_does_not_accept_arbitrary_command_or_destination(self):
        for invalid in ['--hostname=source-db', '; rm -rf /', '../../repo', 'latest\nwhoami']:
            with self.subTest(archive=invalid), self.assertRaises(engine.EngineError):
                engine.command(self.plan, 'restore', invalid)
        self.assertNotIn('source-db', engine.command(self.plan, 'restore'))
        args = engine.command(self.plan, 'restore')
        self.assertEqual(args[args.index('--original-port') + 1], '5432')
        self.assertNotIn('--port', args)

    @patch('console.engine.subprocess.run')
    def test_lock_conflict_is_not_reported_as_success(self, run):
        run.return_value = subprocess.CompletedProcess([], 75, '', '')
        with self.assertRaisesMessage(engine.EngineError, 'уже выполняется'):
            engine.execute(self.plan, 'backup')
        args = run.call_args.args[0]
        self.assertIn('flock', args)
        self.assertIn('timeout', args)
        self.assertFalse(run.call_args.kwargs.get('shell', False))

    @patch('console.engine.subprocess.run')
    def test_archives_parse_real_borgmatic_json_shape(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, json.dumps([{'archives': [{'id': 'a' * 64, 'name': 'test'}]}]), '')
        self.assertEqual(engine.archives(self.plan)[0]['name'], 'test')

    def test_disabling_plan_removes_cron(self):
        self.plan.enabled = True
        engine.sync_plan(self.plan)
        cron = engine.settings.BACKUP_CRON_DIR / f'plan-{self.plan.pk}'
        self.assertTrue(cron.read_text().endswith('\n'))
        self.plan.enabled = False
        engine.sync_plan(self.plan)
        self.assertFalse(cron.exists())
