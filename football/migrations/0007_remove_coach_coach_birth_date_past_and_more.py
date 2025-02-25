# Generated by Django 5.1.6 on 2025-02-09 11:51

import datetime
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('football', '0006_standing_remove_coach_coach_birth_date_past_and_more'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='coach',
            name='coach_birth_date_past',
        ),
        migrations.AddField(
            model_name='fixturestatus',
            name='description',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddConstraint(
            model_name='coach',
            constraint=models.CheckConstraint(condition=models.Q(('birth_date__lt', datetime.datetime(2025, 2, 9, 11, 51, 3, 444264, tzinfo=datetime.timezone.utc))), name='coach_birth_date_past'),
        ),
    ]
