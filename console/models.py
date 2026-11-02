from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Plan(models.Model):
    SCHEDULES = [('*/5 * * * *', 'Каждые 5 минут'), ('0 * * * *', 'Каждый час'), ('0 2 * * *', 'Ежедневно в 02:00')]
    name = models.CharField('Название', max_length=100)
    schedule = models.CharField('Расписание (Europe/Moscow)', max_length=30, choices=SCHEDULES, default='0 2 * * *')
    keep_daily = models.PositiveSmallIntegerField('Хранить ежедневных копий', default=7, validators=[MinValueValidator(1), MaxValueValidator(365)])
    keep_weekly = models.PositiveSmallIntegerField('Хранить еженедельных копий', default=4, validators=[MinValueValidator(0), MaxValueValidator(52)])
    enabled = models.BooleanField('Автоматическое копирование', default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        permissions = [('operate_plan', 'Может запускать копирование и проверку'), ('restore_plan', 'Может восстанавливать тестовую БД')]

    def __str__(self):
        return self.name


class Operation(models.Model):
    plan = models.ForeignKey(Plan, on_delete=models.CASCADE, related_name='operations')
    action = models.CharField(max_length=30)
    user = models.CharField(max_length=150)
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True)
    success = models.BooleanField(default=False)
    output = models.TextField(blank=True)

    class Meta:
        ordering = ['-started_at']
