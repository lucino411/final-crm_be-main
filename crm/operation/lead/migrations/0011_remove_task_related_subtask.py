# Generated by Django 4.2.6 on 2024-01-03 16:34

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('lead', '0010_remove_task_actual_completion_date_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='task',
            name='related_subtask',
        ),
    ]
