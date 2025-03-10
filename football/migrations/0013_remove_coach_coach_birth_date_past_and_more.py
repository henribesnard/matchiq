# Generated by Django 5.1.6 on 2025-02-11 12:19

import datetime
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('football', '0012_remove_coach_coach_birth_date_past_and_more'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='coach',
            name='coach_birth_date_past',
        ),
        migrations.AlterField(
            model_name='fixturelineupplayer',
            name='position',
            field=models.CharField(choices=[('GK', 'Goalkeeper'), ('DF', 'Defender'), ('MF', 'Midfielder'), ('FW', 'Forward')], max_length=2),
        ),
        migrations.AddConstraint(
            model_name='coach',
            constraint=models.CheckConstraint(condition=models.Q(('birth_date__lt', datetime.datetime(2025, 2, 11, 12, 19, 50, 473567, tzinfo=datetime.timezone.utc))), name='coach_birth_date_past'),
        ),
    ]
