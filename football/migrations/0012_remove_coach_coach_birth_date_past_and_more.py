# Generated by Django 5.1.6 on 2025-02-11 12:01

import datetime
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('football', '0011_fixturecoach_fixturelineup_fixturelineupplayer_and_more'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='coach',
            name='coach_birth_date_past',
        ),
        migrations.AddConstraint(
            model_name='coach',
            constraint=models.CheckConstraint(condition=models.Q(('birth_date__lt', datetime.datetime(2025, 2, 11, 12, 1, 7, 504211, tzinfo=datetime.timezone.utc))), name='coach_birth_date_past'),
        ),
    ]
