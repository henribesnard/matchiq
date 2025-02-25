# Generated by Django 5.1.6 on 2025-02-08 20:09

import datetime
import django.core.validators
import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('football', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Bookmaker',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('external_id', models.IntegerField(db_index=True, unique=True)),
                ('name', models.CharField(max_length=100)),
                ('logo_url', models.URLField(blank=True, null=True)),
                ('is_active', models.BooleanField(default=True)),
                ('priority', models.SmallIntegerField(default=0)),
                ('update_by', models.CharField(default='manual', max_length=50)),
                ('update_at', models.DateTimeField(default=django.utils.timezone.now)),
            ],
        ),
        migrations.CreateModel(
            name='Odds',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('value', models.DecimalField(decimal_places=2, max_digits=7, validators=[django.core.validators.MinValueValidator(1.01)])),
                ('is_main', models.BooleanField(default=False)),
                ('probability', models.DecimalField(decimal_places=2, max_digits=5, null=True)),
                ('status', models.CharField(choices=[('active', 'Active'), ('suspended', 'Suspended'), ('settled', 'Settled'), ('cancelled', 'Cancelled')], default='active', max_length=20)),
                ('last_update', models.DateTimeField(auto_now=True)),
                ('update_by', models.CharField(default='manual', max_length=50)),
                ('update_at', models.DateTimeField(default=django.utils.timezone.now)),
            ],
        ),
        migrations.CreateModel(
            name='OddsHistory',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('old_value', models.DecimalField(decimal_places=2, max_digits=7)),
                ('new_value', models.DecimalField(decimal_places=2, max_digits=7)),
                ('change_time', models.DateTimeField(auto_now_add=True)),
                ('movement', models.CharField(choices=[('up', 'Up'), ('down', 'Down'), ('stable', 'Stable')], max_length=10)),
            ],
        ),
        migrations.CreateModel(
            name='OddsType',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('external_id', models.IntegerField(db_index=True, unique=True)),
                ('name', models.CharField(max_length=100)),
                ('key', models.CharField(db_index=True, max_length=50)),
                ('description', models.TextField(blank=True, null=True)),
                ('category', models.CharField(choices=[('main', 'Main'), ('goals', 'Goals'), ('halves', 'Halves'), ('specials', 'Specials')], db_index=True, max_length=50)),
                ('display_order', models.SmallIntegerField(default=0)),
            ],
        ),
        migrations.CreateModel(
            name='OddsValue',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('name', models.CharField(db_index=True, max_length=100)),
                ('key', models.CharField(max_length=50)),
                ('display_order', models.SmallIntegerField(default=0)),
            ],
        ),
        migrations.RemoveConstraint(
            model_name='coach',
            name='coach_birth_date_past',
        ),
        migrations.AddConstraint(
            model_name='coach',
            constraint=models.CheckConstraint(condition=models.Q(('birth_date__lt', datetime.datetime(2025, 2, 8, 20, 9, 28, 387867, tzinfo=datetime.timezone.utc))), name='coach_birth_date_past'),
        ),
        migrations.AddIndex(
            model_name='bookmaker',
            index=models.Index(fields=['name'], name='football_bo_name_6efa85_idx'),
        ),
        migrations.AddIndex(
            model_name='bookmaker',
            index=models.Index(fields=['is_active', 'priority'], name='football_bo_is_acti_ba71c4_idx'),
        ),
        migrations.AddField(
            model_name='odds',
            name='bookmaker',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='football.bookmaker'),
        ),
        migrations.AddField(
            model_name='odds',
            name='fixture',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='football.fixture'),
        ),
        migrations.AddField(
            model_name='oddshistory',
            name='odds',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='football.odds'),
        ),
        migrations.AddIndex(
            model_name='oddstype',
            index=models.Index(fields=['category', 'display_order'], name='football_od_categor_069411_idx'),
        ),
        migrations.AddField(
            model_name='odds',
            name='odds_type',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='football.oddstype'),
        ),
        migrations.AddField(
            model_name='oddsvalue',
            name='odds_type',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='football.oddstype'),
        ),
        migrations.AddField(
            model_name='odds',
            name='odds_value',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='football.oddsvalue'),
        ),
        migrations.AddIndex(
            model_name='oddshistory',
            index=models.Index(fields=['odds', 'change_time'], name='football_od_odds_id_c37716_idx'),
        ),
        migrations.AddIndex(
            model_name='oddsvalue',
            index=models.Index(fields=['odds_type', 'display_order'], name='football_od_odds_ty_f21cb6_idx'),
        ),
        migrations.AlterUniqueTogether(
            name='oddsvalue',
            unique_together={('odds_type', 'key')},
        ),
        migrations.AddIndex(
            model_name='odds',
            index=models.Index(fields=['fixture', 'bookmaker', 'odds_type'], name='football_od_fixture_59f36a_idx'),
        ),
        migrations.AddIndex(
            model_name='odds',
            index=models.Index(fields=['fixture', 'status'], name='football_od_fixture_25ea69_idx'),
        ),
        migrations.AddIndex(
            model_name='odds',
            index=models.Index(fields=['last_update'], name='football_od_last_up_b67594_idx'),
        ),
        migrations.AddConstraint(
            model_name='odds',
            constraint=models.UniqueConstraint(fields=('fixture', 'bookmaker', 'odds_type', 'odds_value'), name='unique_odds'),
        ),
    ]
