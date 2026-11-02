from django.contrib import admin
from .models import Plan, Operation

admin.site.register(Plan)


@admin.register(Operation)
class OperationAdmin(admin.ModelAdmin):
    list_display = ['plan', 'action', 'user', 'started_at', 'success']
    readonly_fields = ['plan', 'action', 'user', 'started_at', 'finished_at', 'success', 'output']

    def has_add_permission(self, request):
        return False
