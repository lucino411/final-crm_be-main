# Generated by Django 4.2.6 on 2024-01-08 23:47

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('lead', '0015_alter_leadtask_name'),
    ]

    operations = [
        migrations.AlterField(
            model_name='leadtask',
            name='name',
            field=models.CharField(max_length=200),
        ),
    ]