from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.db import connection
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import engine
from .forms import PlanForm
from .models import Operation, Plan


def health(request):
    with connection.cursor() as cursor:
        cursor.execute('SELECT 1')
    return HttpResponse('ok', content_type='text/plain')


@login_required
@permission_required('console.view_plan', raise_exception=True)
def dashboard(request):
    plans = Plan.objects.all()
    return render(request, 'dashboard.html', {
        'plans': plans, 'total': plans.count(), 'enabled': plans.filter(enabled=True).count(),
        'recent': Operation.objects.select_related('plan')[:8],
    })


@login_required
@permission_required('console.view_plan', raise_exception=True)
def plan_detail(request, pk):
    plan = get_object_or_404(Plan, pk=pk)
    archive_list, archive_error = [], ''
    try:
        archive_list = engine.archives(plan)
    except engine.EngineError as exc:
        archive_error = str(exc)
    return render(request, 'detail.html', {
        'plan': plan, 'archives': archive_list, 'archive_error': archive_error,
        'operations': plan.operations.all()[:20], 'scheduled_log': engine.scheduled_log(plan),
    })


@login_required
def edit_plan(request, pk=None):
    permission = 'console.change_plan' if pk else 'console.add_plan'
    if not request.user.has_perm(permission):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied
    plan = get_object_or_404(Plan, pk=pk) if pk else None
    form = PlanForm(request.POST or None, instance=plan)
    if request.method == 'POST' and form.is_valid():
        saved = form.save()
        try:
            engine.sync_plan(saved)
        except (OSError, engine.EngineError):
            # Stop advertising a schedule when publishing its configuration failed.
            saved.enabled = False
            saved.save(update_fields=['enabled'])
            (engine.settings.BACKUP_CRON_DIR / f'plan-{saved.pk}').unlink(missing_ok=True)
            messages.error(request, 'Настройки сохранены, но публикация конфигурации не удалась. Расписание отключено; проверьте права на тома.')
        else:
            messages.success(request, 'Задание сохранено. Расписание применяется системным cron.')
        return redirect('plan-detail', pk=saved.pk)
    return render(request, 'form.html', {'form': form, 'plan': plan})


@login_required
@permission_required('console.delete_plan', raise_exception=True)
def delete_plan(request, pk):
    plan = get_object_or_404(Plan, pk=pk)
    if request.method == 'POST':
        engine.remove_plan_files(plan)
        plan.delete()
        messages.success(request, 'Задание удалено, расписание отключено. Архивы сохранены на диске.')
        return redirect('dashboard')
    return render(request, 'delete.html', {'plan': plan})


@login_required
@require_POST
def plan_action(request, pk):
    from django.core.exceptions import PermissionDenied
    action = request.POST.get('action', '')
    if action not in ['init', 'backup', 'check', 'restore']:
        return HttpResponseBadRequest('Неизвестная операция')
    permission = 'console.restore_plan' if action == 'restore' else 'console.operate_plan'
    if not request.user.has_perm(permission):
        raise PermissionDenied
    if action == 'restore' and request.POST.get('confirmation') != 'ВОССТАНОВИТЬ':
        return HttpResponseBadRequest('Подтвердите замену данных тестовой БД словом ВОССТАНОВИТЬ')
    plan = get_object_or_404(Plan, pk=pk)
    operation = Operation.objects.create(plan=plan, action=action, user=request.user.get_username())
    try:
        engine.sync_plan(plan)
        operation.output = engine.execute(plan, action, request.POST.get('archive', 'latest'))
        operation.success = True
        messages.success(request, 'Операция выполнена. Результат добавлен в журнал.')
    except (engine.EngineError, OSError) as exc:
        operation.output = engine.redact(str(exc))
        messages.error(request, 'Операция не выполнена. Подробности в журнале.')
    finally:
        operation.finished_at = timezone.now()
        operation.save()
    return redirect('plan-detail', pk=pk)
