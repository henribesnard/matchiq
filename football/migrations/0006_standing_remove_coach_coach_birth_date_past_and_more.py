# Generated by Django 5.1.6 on 2025-02-09 11:32

import datetime
import django.core.validators
import django.db.models.deletion
import django.db.models.expressions
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('football', '0005_remove_coach_coach_birth_date_past_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='Standing',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('rank', models.PositiveSmallIntegerField(validators=[django.core.validators.MinValueValidator(1)])),
                ('points', models.PositiveSmallIntegerField(default=0)),
                ('goals_diff', models.SmallIntegerField(default=0)),
                ('form', models.CharField(blank=True, max_length=10, null=True)),
                ('status', models.CharField(blank=True, max_length=20, null=True)),
                ('description', models.CharField(blank=True, max_length=100, null=True)),
                ('played', models.PositiveSmallIntegerField(default=0)),
                ('won', models.PositiveSmallIntegerField(default=0)),
                ('drawn', models.PositiveSmallIntegerField(default=0)),
                ('lost', models.PositiveSmallIntegerField(default=0)),
                ('goals_for', models.PositiveSmallIntegerField(default=0)),
                ('goals_against', models.PositiveSmallIntegerField(default=0)),
                ('home_played', models.PositiveSmallIntegerField(default=0)),
                ('home_won', models.PositiveSmallIntegerField(default=0)),
                ('home_drawn', models.PositiveSmallIntegerField(default=0)),
                ('home_lost', models.PositiveSmallIntegerField(default=0)),
                ('home_goals_for', models.PositiveSmallIntegerField(default=0)),
                ('home_goals_against', models.PositiveSmallIntegerField(default=0)),
                ('away_played', models.PositiveSmallIntegerField(default=0)),
                ('away_won', models.PositiveSmallIntegerField(default=0)),
                ('away_drawn', models.PositiveSmallIntegerField(default=0)),
                ('away_lost', models.PositiveSmallIntegerField(default=0)),
                ('away_goals_for', models.PositiveSmallIntegerField(default=0)),
                ('away_goals_against', models.PositiveSmallIntegerField(default=0)),
                ('update_by', models.CharField(default='manual', max_length=50)),
                ('update_at', models.DateTimeField(default=django.utils.timezone.now)),
            ],
        ),
        migrations.RemoveConstraint(
            model_name='coach',
            name='coach_birth_date_past',
        ),
        migrations.AddField(
            model_name='oddshistory',
            name='update_at',
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
        migrations.AddField(
            model_name='oddshistory',
            name='update_by',
            field=models.CharField(default='manual', max_length=50),
        ),
        migrations.AddField(
            model_name='oddstype',
            name='update_at',
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
        migrations.AddField(
            model_name='oddstype',
            name='update_by',
            field=models.CharField(default='manual', max_length=50),
        ),
        migrations.AddField(
            model_name='oddsvalue',
            name='update_at',
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
        migrations.AddField(
            model_name='oddsvalue',
            name='update_by',
            field=models.CharField(default='manual', max_length=50),
        ),
        migrations.AddField(
            model_name='playerstatistics',
            name='update_at',
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
        migrations.AddField(
            model_name='playerstatistics',
            name='update_by',
            field=models.CharField(default='manual', max_length=50),
        ),
        migrations.AddConstraint(
            model_name='coach',
            constraint=models.CheckConstraint(condition=models.Q(('birth_date__lt', datetime.datetime(2025, 2, 9, 11, 32, 31, 551907, tzinfo=datetime.timezone.utc))), name='coach_birth_date_past'),
        ),
        migrations.AddField(
            model_name='standing',
            name='season',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='football.season'),
        ),
        migrations.AddField(
            model_name='standing',
            name='team',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='football.team'),
        ),
        migrations.AddIndex(
            model_name='standing',
            index=models.Index(fields=['season', 'team'], name='football_st_season__61594b_idx'),
        ),
        migrations.AddIndex(
            model_name='standing',
            index=models.Index(fields=['season', 'rank'], name='football_st_season__edd21a_idx'),
        ),
        migrations.AddIndex(
            model_name='standing',
            index=models.Index(fields=['season', 'points'], name='football_st_season__dfbbd8_idx'),
        ),
        migrations.AddIndex(
            model_name='standing',
            index=models.Index(fields=['update_at'], name='football_st_update__8692b7_idx'),
        ),
        migrations.AddConstraint(
            model_name='standing',
            constraint=models.UniqueConstraint(fields=('season', 'team'), name='unique_team_season_standing'),
        ),
        migrations.AddConstraint(
            model_name='standing',
            constraint=models.CheckConstraint(condition=models.Q(('played', django.db.models.expressions.CombinedExpression(django.db.models.expressions.CombinedExpression(models.F('won'), '+', models.F('drawn')), '+', models.F('lost')))), name='total_matches_check'),
        ),
        migrations.AddConstraint(
            model_name='standing',
            constraint=models.CheckConstraint(condition=models.Q(('home_played', django.db.models.expressions.CombinedExpression(django.db.models.expressions.CombinedExpression(models.F('home_won'), '+', models.F('home_drawn')), '+', models.F('home_lost')))), name='home_matches_check'),
        ),
        migrations.AddConstraint(
            model_name='standing',
            constraint=models.CheckConstraint(condition=models.Q(('away_played', django.db.models.expressions.CombinedExpression(django.db.models.expressions.CombinedExpression(models.F('away_won'), '+', models.F('away_drawn')), '+', models.F('away_lost')))), name='away_matches_check'),
        ),
        migrations.AddConstraint(
            model_name='standing',
            constraint=models.CheckConstraint(condition=models.Q(('played', django.db.models.expressions.CombinedExpression(models.F('home_played'), '+', models.F('away_played')))), name='total_vs_home_away_matches_check'),
        ),
        migrations.AddConstraint(
            model_name='standing',
            constraint=models.CheckConstraint(condition=models.Q(('goals_for', django.db.models.expressions.CombinedExpression(models.F('home_goals_for'), '+', models.F('away_goals_for')))), name='total_vs_home_away_goals_for_check'),
        ),
        migrations.AddConstraint(
            model_name='standing',
            constraint=models.CheckConstraint(condition=models.Q(('goals_against', django.db.models.expressions.CombinedExpression(models.F('home_goals_against'), '+', models.F('away_goals_against')))), name='total_vs_home_away_goals_against_check'),
        ),
    ]
