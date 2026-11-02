from django import forms
from .models import Plan


class PlanForm(forms.ModelForm):
    def clean_enabled(self):
        enabled = self.cleaned_data['enabled']
        if enabled:
            from .engine import repository_path
            if not self.instance.pk or not (repository_path(self.instance) / 'config').exists():
                raise forms.ValidationError('Сначала сохраните задание и инициализируйте хранилище, затем включите расписание.')
        return enabled

    class Meta:
        model = Plan
        fields = ['name', 'schedule', 'keep_daily', 'keep_weekly', 'enabled']
