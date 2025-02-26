# Generated by Django 5.1.6 on 2025-02-25 11:39

import datetime
import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('football', '0020_remove_coach_coach_birth_date_past_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='FixtureH2H',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('update_by', models.CharField(default='manual', max_length=50)),
                ('update_at', models.DateTimeField(default=django.utils.timezone.now)),
            ],
        ),
        migrations.RemoveConstraint(
            model_name='coach',
            name='coach_birth_date_past',
        ),
        migrations.AddConstraint(
            model_name='coach',
            constraint=models.CheckConstraint(condition=models.Q(('birth_date__lt', datetime.datetime(2025, 2, 25, 11, 39, 26, 775727, tzinfo=datetime.timezone.utc))), name='coach_birth_date_past'),
        ),
        migrations.AddField(
            model_name='fixtureh2h',
            name='reference_fixture',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='h2h_references', to='football.fixture'),
        ),
        migrations.AddField(
            model_name='fixtureh2h',
            name='related_fixture',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='h2h_related', to='football.fixture'),
        ),
        migrations.AddIndex(
            model_name='fixtureh2h',
            index=models.Index(fields=['reference_fixture'], name='football_fi_referen_a535bd_idx'),
        ),
        migrations.AddIndex(
            model_name='fixtureh2h',
            index=models.Index(fields=['related_fixture'], name='football_fi_related_908c3e_idx'),
        ),
        migrations.AlterUniqueTogether(
            name='fixtureh2h',
            unique_together={('reference_fixture', 'related_fixture')},
        ),
    ]
