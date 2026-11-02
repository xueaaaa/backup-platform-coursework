import os
from django.contrib.auth.models import Group, Permission, User
from django.core.management.base import BaseCommand, CommandError
from console.models import Plan
from console.engine import sync_plan


class Command(BaseCommand):
    help = 'Создать роли, первого администратора и отключённое демонстрационное задание'

    def handle(self, *args, **options):
        reader, _ = Group.objects.get_or_create(name='Наблюдатели')
        reader.permissions.set(Permission.objects.filter(content_type__app_label='console', codename='view_plan'))
        operator, _ = Group.objects.get_or_create(name='Операторы')
        operator.permissions.set(Permission.objects.filter(content_type__app_label='console').exclude(codename='restore_plan'))
        username = os.environ.get('ADMIN_USERNAME', 'admin')
        if not User.objects.filter(username=username).exists():
            password = os.environ.get('ADMIN_PASSWORD', '')
            if len(password) < 12:
                raise CommandError('Задайте ADMIN_PASSWORD длиной не менее 12 символов')
            User.objects.create_superuser(username, '', password)
        if not Plan.objects.exists():
            Plan.objects.create(name='Учебная база PostgreSQL')
        for plan in Plan.objects.all():
            sync_plan(plan)
        self.stdout.write(self.style.SUCCESS('Роли и настройки готовы'))
