# Generated by Django 4.2.6 on 2024-01-15 14:26

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('client', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='client',
            name='website',
            field=models.URLField(blank=True),
        ),
    ]
