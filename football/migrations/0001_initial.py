# Generated by Django 5.1.6 on 2025-02-08 18:59

import datetime
import django.core.validators
import django.db.models.deletion
import django.db.models.expressions
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Country',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('external_id', models.IntegerField(blank=True, db_index=True, null=True)),
                ('name', models.CharField(db_index=True, max_length=100, unique=True)),
                ('code', models.CharField(blank=True, db_index=True, max_length=3, null=True, validators=[django.core.validators.RegexValidator('^[A-Z]{2,3}$')])),
                ('flag_url', models.URLField(blank=True, null=True)),
                ('update_by', models.CharField(default='manual', max_length=50)),
                ('update_at', models.DateTimeField(default=django.utils.timezone.now)),
            ],
        ),
        migrations.CreateModel(
            name='Coach',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('external_id', models.IntegerField(db_index=True, unique=True)),
                ('name', models.CharField(db_index=True, max_length=255)),
                ('firstname', models.CharField(blank=True, max_length=100, null=True)),
                ('lastname', models.CharField(blank=True, max_length=100, null=True)),
                ('birth_date', models.DateField(blank=True, null=True)),
                ('photo_url', models.URLField(blank=True, null=True)),
                ('career_matches', models.PositiveIntegerField(default=0)),
                ('career_wins', models.PositiveIntegerField(default=0)),
                ('career_draws', models.PositiveIntegerField(default=0)),
                ('career_losses', models.PositiveIntegerField(default=0)),
                ('update_by', models.CharField(default='manual', max_length=50)),
                ('update_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('nationality', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='coaches', to='football.country')),
            ],
        ),
        migrations.CreateModel(
            name='FixtureStatus',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('short_code', models.CharField(help_text='Ex: FT, HT, NS', max_length=10, unique=True)),
                ('long_description', models.CharField(help_text='Ex: Match Finished, Half Time', max_length=100)),
                ('status_type', models.CharField(choices=[('scheduled', 'Scheduled'), ('in_play', 'In Play'), ('finished', 'Finished'), ('cancelled', 'Cancelled'), ('postponed', 'Postponed')], db_index=True, max_length=20)),
            ],
            options={
                'verbose_name_plural': 'Fixture Statuses',
                'indexes': [models.Index(fields=['short_code', 'status_type'], name='football_fi_short_c_4311b4_idx')],
            },
        ),
        migrations.CreateModel(
            name='League',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('external_id', models.IntegerField(db_index=True, unique=True)),
                ('name', models.CharField(db_index=True, max_length=255)),
                ('type', models.CharField(choices=[('League', 'League'), ('Cup', 'Cup'), ('Other', 'Other')], max_length=50)),
                ('logo_url', models.URLField(blank=True, null=True)),
                ('update_by', models.CharField(default='manual', max_length=50)),
                ('update_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('country', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='football.country')),
            ],
        ),
        migrations.CreateModel(
            name='Fixture',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('external_id', models.IntegerField(db_index=True, unique=True)),
                ('round', models.CharField(blank=True, max_length=100, null=True)),
                ('date', models.DateTimeField(db_index=True)),
                ('referee', models.CharField(blank=True, max_length=100, null=True)),
                ('elapsed_time', models.SmallIntegerField(blank=True, null=True)),
                ('timezone', models.CharField(default='UTC', max_length=50)),
                ('home_score', models.SmallIntegerField(default=0)),
                ('away_score', models.SmallIntegerField(default=0)),
                ('is_finished', models.BooleanField(default=False)),
                ('update_by', models.CharField(default='manual', max_length=50)),
                ('update_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('status', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='football.fixturestatus')),
                ('league', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='football.league')),
            ],
        ),
        migrations.CreateModel(
            name='Player',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('external_id', models.IntegerField(db_index=True, unique=True)),
                ('name', models.CharField(db_index=True, max_length=255)),
                ('firstname', models.CharField(blank=True, max_length=100, null=True)),
                ('lastname', models.CharField(blank=True, max_length=100, null=True)),
                ('birth_date', models.DateField(blank=True, null=True)),
                ('height', models.PositiveSmallIntegerField(blank=True, null=True, validators=[django.core.validators.MinValueValidator(120), django.core.validators.MaxValueValidator(250)])),
                ('weight', models.PositiveSmallIntegerField(blank=True, null=True, validators=[django.core.validators.MinValueValidator(30), django.core.validators.MaxValueValidator(150)])),
                ('position', models.CharField(choices=[('GK', 'Goalkeeper'), ('DF', 'Defender'), ('MF', 'Midfielder'), ('FW', 'Forward')], max_length=2)),
                ('number', models.PositiveSmallIntegerField(blank=True, null=True, validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(99)])),
                ('injured', models.BooleanField(default=False)),
                ('photo_url', models.URLField(blank=True, null=True)),
                ('season_goals', models.PositiveIntegerField(default=0)),
                ('season_assists', models.PositiveIntegerField(default=0)),
                ('season_yellow_cards', models.PositiveSmallIntegerField(default=0)),
                ('season_red_cards', models.PositiveSmallIntegerField(default=0)),
                ('total_appearances', models.PositiveIntegerField(default=0)),
                ('update_by', models.CharField(default='manual', max_length=50)),
                ('update_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('nationality', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='players', to='football.country')),
            ],
        ),
        migrations.CreateModel(
            name='PlayerInjury',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('type', models.CharField(max_length=100)),
                ('severity', models.CharField(choices=[('minor', 'Minor'), ('moderate', 'Moderate'), ('severe', 'Severe'), ('season_ending', 'Season Ending')], max_length=20)),
                ('status', models.CharField(choices=[('recovering', 'Recovering'), ('training', 'Back in Training'), ('available', 'Available for Selection'), ('doubtful', 'Doubtful')], max_length=20)),
                ('start_date', models.DateField(db_index=True)),
                ('end_date', models.DateField(blank=True, null=True)),
                ('expected_return_date', models.DateField(blank=True, null=True)),
                ('recovery_time', models.PositiveSmallIntegerField(blank=True, null=True, validators=[django.core.validators.MaxValueValidator(365)])),
                ('update_by', models.CharField(default='manual', max_length=50)),
                ('update_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('fixture', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='football.fixture')),
                ('player', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='injuries', to='football.player')),
            ],
        ),
        migrations.CreateModel(
            name='Season',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('external_id', models.IntegerField(blank=True, db_index=True, null=True)),
                ('year', models.PositiveSmallIntegerField(db_index=True, validators=[django.core.validators.MinValueValidator(1800), django.core.validators.MaxValueValidator(2100)])),
                ('start_date', models.DateField()),
                ('end_date', models.DateField()),
                ('is_current', models.BooleanField(default=False)),
                ('update_by', models.CharField(default='manual', max_length=50)),
                ('update_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('league', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='football.league')),
            ],
        ),
        migrations.AddField(
            model_name='fixture',
            name='season',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='football.season'),
        ),
        migrations.CreateModel(
            name='Team',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('external_id', models.IntegerField(db_index=True, unique=True)),
                ('name', models.CharField(db_index=True, max_length=255)),
                ('code', models.CharField(blank=True, db_index=True, max_length=5, null=True)),
                ('founded', models.PositiveSmallIntegerField(blank=True, null=True, validators=[django.core.validators.MinValueValidator(1800), django.core.validators.MaxValueValidator(2100)])),
                ('is_national', models.BooleanField(default=False)),
                ('logo_url', models.URLField(blank=True, null=True)),
                ('total_matches', models.PositiveIntegerField(default=0)),
                ('total_wins', models.PositiveIntegerField(default=0)),
                ('total_draws', models.PositiveIntegerField(default=0)),
                ('total_losses', models.PositiveIntegerField(default=0)),
                ('total_goals_scored', models.PositiveIntegerField(default=0)),
                ('total_goals_conceded', models.PositiveIntegerField(default=0)),
                ('update_by', models.CharField(default='manual', max_length=50)),
                ('update_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('country', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='football.country')),
            ],
        ),
        migrations.CreateModel(
            name='PlayerStatistics',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('minutes_played', models.PositiveSmallIntegerField(blank=True, null=True, validators=[django.core.validators.MaxValueValidator(150)])),
                ('goals', models.PositiveSmallIntegerField(default=0)),
                ('assists', models.PositiveSmallIntegerField(default=0)),
                ('shots_total', models.PositiveSmallIntegerField(default=0)),
                ('shots_on_target', models.PositiveSmallIntegerField(default=0)),
                ('passes', models.PositiveSmallIntegerField(default=0)),
                ('key_passes', models.PositiveSmallIntegerField(default=0)),
                ('pass_accuracy', models.DecimalField(decimal_places=2, max_digits=5, null=True, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(100)])),
                ('tackles', models.PositiveSmallIntegerField(default=0)),
                ('interceptions', models.PositiveSmallIntegerField(default=0)),
                ('duels_total', models.PositiveSmallIntegerField(default=0)),
                ('duels_won', models.PositiveSmallIntegerField(default=0)),
                ('dribbles_success', models.PositiveSmallIntegerField(default=0)),
                ('fouls_committed', models.PositiveSmallIntegerField(default=0)),
                ('fouls_drawn', models.PositiveSmallIntegerField(default=0)),
                ('yellow_cards', models.PositiveSmallIntegerField(default=0)),
                ('red_cards', models.PositiveSmallIntegerField(default=0)),
                ('rating', models.DecimalField(decimal_places=1, max_digits=3, null=True, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(10)])),
                ('is_substitute', models.BooleanField(default=False)),
                ('fixture', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='football.fixture')),
                ('player', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='football.player')),
                ('team', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='football.team')),
            ],
        ),
        migrations.AddField(
            model_name='player',
            name='team',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='players', to='football.team'),
        ),
        migrations.CreateModel(
            name='FixtureStatistic',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('stat_type', models.CharField(choices=[('possession', 'Ball Possession'), ('shots', 'Total Shots'), ('shots_on_target', 'Shots on Target'), ('corners', 'Corner Kicks'), ('fouls', 'Fouls'), ('offsides', 'Offsides')], max_length=50)),
                ('value', models.DecimalField(decimal_places=2, max_digits=5, validators=[django.core.validators.MinValueValidator(0)])),
                ('update_by', models.CharField(default='manual', max_length=50)),
                ('update_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('fixture', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='football.fixture')),
                ('team', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='football.team')),
            ],
        ),
        migrations.CreateModel(
            name='FixtureScore',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('halftime', models.SmallIntegerField(blank=True, null=True)),
                ('fulltime', models.SmallIntegerField(blank=True, null=True)),
                ('extratime', models.SmallIntegerField(blank=True, null=True)),
                ('penalty', models.SmallIntegerField(blank=True, null=True)),
                ('update_by', models.CharField(default='manual', max_length=50)),
                ('update_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('fixture', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='football.fixture')),
                ('team', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='football.team')),
            ],
        ),
        migrations.CreateModel(
            name='FixtureEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('time_elapsed', models.SmallIntegerField(validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(150)])),
                ('event_type', models.CharField(choices=[('Goal', 'Goal'), ('Card', 'Card'), ('Substitution', 'Substitution'), ('VAR', 'VAR'), ('Injury', 'Injury'), ('Other', 'Other')], db_index=True, max_length=50)),
                ('detail', models.CharField(max_length=100)),
                ('comments', models.TextField(blank=True, null=True)),
                ('update_by', models.CharField(default='manual', max_length=50)),
                ('update_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('fixture', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='football.fixture')),
                ('assist', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='assists', to='football.player')),
                ('player', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='events', to='football.player')),
                ('team', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='football.team')),
            ],
        ),
        migrations.AddField(
            model_name='fixture',
            name='away_team',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='away_fixtures', to='football.team'),
        ),
        migrations.AddField(
            model_name='fixture',
            name='home_team',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='home_fixtures', to='football.team'),
        ),
        migrations.CreateModel(
            name='CoachCareer',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('role', models.CharField(choices=[('head_coach', 'Head Coach'), ('assistant', 'Assistant Coach'), ('youth_coach', 'Youth Team Coach'), ('interim', 'Interim Manager')], max_length=20)),
                ('start_date', models.DateField(db_index=True)),
                ('end_date', models.DateField(blank=True, null=True)),
                ('matches', models.PositiveIntegerField(default=0)),
                ('wins', models.PositiveIntegerField(default=0)),
                ('draws', models.PositiveIntegerField(default=0)),
                ('losses', models.PositiveIntegerField(default=0)),
                ('update_by', models.CharField(default='manual', max_length=50)),
                ('update_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('coach', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='career_entries', to='football.coach')),
                ('team', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='coach_history', to='football.team')),
            ],
        ),
        migrations.AddField(
            model_name='coach',
            name='team',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='current_coach', to='football.team'),
        ),
        migrations.CreateModel(
            name='UpdateLog',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('table_name', models.CharField(db_index=True, max_length=100)),
                ('record_id', models.IntegerField(db_index=True)),
                ('update_type', models.CharField(choices=[('create', 'Create'), ('update', 'Update'), ('delete', 'Delete'), ('bulk_update', 'Bulk Update'), ('bulk_create', 'Bulk Create')], db_index=True, max_length=20)),
                ('update_by', models.CharField(db_index=True, max_length=50)),
                ('update_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ('old_data', models.JSONField(blank=True, null=True)),
                ('new_data', models.JSONField(blank=True, null=True)),
                ('description', models.TextField(blank=True, null=True)),
                ('is_success', models.BooleanField(default=True)),
                ('error_message', models.TextField(blank=True, null=True)),
            ],
            options={
                'indexes': [models.Index(fields=['table_name', 'record_id'], name='football_up_table_n_fea2fa_idx'), models.Index(fields=['update_at', 'update_type'], name='football_up_update__da39a7_idx')],
            },
        ),
        migrations.CreateModel(
            name='Venue',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('external_id', models.IntegerField(db_index=True, unique=True)),
                ('name', models.CharField(db_index=True, max_length=255)),
                ('address', models.CharField(blank=True, max_length=255, null=True)),
                ('city', models.CharField(db_index=True, max_length=100)),
                ('capacity', models.PositiveIntegerField(blank=True, null=True)),
                ('surface', models.CharField(blank=True, max_length=50, null=True)),
                ('image_url', models.URLField(blank=True, null=True)),
                ('update_by', models.CharField(default='manual', max_length=50)),
                ('update_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('country', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='football.country')),
            ],
        ),
        migrations.AddField(
            model_name='team',
            name='venue',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='football.venue'),
        ),
        migrations.AddField(
            model_name='fixture',
            name='venue',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='football.venue'),
        ),
        migrations.AddIndex(
            model_name='league',
            index=models.Index(fields=['name', 'country'], name='football_le_name_3feb86_idx'),
        ),
        migrations.AddIndex(
            model_name='playerinjury',
            index=models.Index(fields=['player', 'start_date'], name='football_pl_player__265ca5_idx'),
        ),
        migrations.AddIndex(
            model_name='playerinjury',
            index=models.Index(fields=['status', 'end_date'], name='football_pl_status_9cbe51_idx'),
        ),
        migrations.AddConstraint(
            model_name='playerinjury',
            constraint=models.CheckConstraint(condition=models.Q(('end_date__gt', models.F('start_date')), ('end_date__isnull', True), _connector='OR'), name='injury_end_date_after_start'),
        ),
        migrations.AddIndex(
            model_name='season',
            index=models.Index(fields=['league', 'year'], name='football_se_league__ae88f4_idx'),
        ),
        migrations.AddIndex(
            model_name='season',
            index=models.Index(fields=['is_current'], name='football_se_is_curr_3d2a9c_idx'),
        ),
        migrations.AddConstraint(
            model_name='season',
            constraint=models.CheckConstraint(condition=models.Q(('end_date__gt', models.F('start_date'))), name='end_date_after_start_date'),
        ),
        migrations.AddIndex(
            model_name='playerstatistics',
            index=models.Index(fields=['player', 'fixture'], name='football_pl_player__51b0be_idx'),
        ),
        migrations.AddIndex(
            model_name='playerstatistics',
            index=models.Index(fields=['rating'], name='football_pl_rating_377dd7_idx'),
        ),
        migrations.AddIndex(
            model_name='playerstatistics',
            index=models.Index(fields=['goals'], name='football_pl_goals_2d1016_idx'),
        ),
        migrations.AddIndex(
            model_name='playerstatistics',
            index=models.Index(fields=['assists'], name='football_pl_assists_1ad5bd_idx'),
        ),
        migrations.AddConstraint(
            model_name='playerstatistics',
            constraint=models.UniqueConstraint(fields=('player', 'fixture'), name='unique_player_fixture_stats'),
        ),
        migrations.AddConstraint(
            model_name='playerstatistics',
            constraint=models.CheckConstraint(condition=models.Q(('shots_on_target__lte', models.F('shots_total'))), name='shots_on_target_lte_total'),
        ),
        migrations.AddConstraint(
            model_name='playerstatistics',
            constraint=models.CheckConstraint(condition=models.Q(('duels_won__lte', models.F('duels_total'))), name='duels_won_lte_total'),
        ),
        migrations.AddIndex(
            model_name='player',
            index=models.Index(fields=['name', 'team'], name='football_pl_name_3b9a20_idx'),
        ),
        migrations.AddIndex(
            model_name='player',
            index=models.Index(fields=['position', 'team'], name='football_pl_positio_07cc12_idx'),
        ),
        migrations.AddIndex(
            model_name='player',
            index=models.Index(fields=['injured'], name='football_pl_injured_5d129d_idx'),
        ),
        migrations.AddIndex(
            model_name='fixturestatistic',
            index=models.Index(fields=['fixture', 'team', 'stat_type'], name='football_fi_fixture_dc6db7_idx'),
        ),
        migrations.AddConstraint(
            model_name='fixturestatistic',
            constraint=models.UniqueConstraint(fields=('fixture', 'team', 'stat_type'), name='unique_fixture_team_stat'),
        ),
        migrations.AddIndex(
            model_name='fixturescore',
            index=models.Index(fields=['fixture', 'team'], name='football_fi_fixture_599922_idx'),
        ),
        migrations.AddConstraint(
            model_name='fixturescore',
            constraint=models.UniqueConstraint(fields=('fixture', 'team'), name='unique_fixture_team_score'),
        ),
        migrations.AddIndex(
            model_name='fixtureevent',
            index=models.Index(fields=['fixture', 'time_elapsed'], name='football_fi_fixture_4bbde7_idx'),
        ),
        migrations.AddIndex(
            model_name='fixtureevent',
            index=models.Index(fields=['event_type', 'team'], name='football_fi_event_t_fb5d59_idx'),
        ),
        migrations.AddIndex(
            model_name='coachcareer',
            index=models.Index(fields=['coach', 'team'], name='football_co_coach_i_6151a1_idx'),
        ),
        migrations.AddIndex(
            model_name='coachcareer',
            index=models.Index(fields=['start_date', 'end_date'], name='football_co_start_d_d893f9_idx'),
        ),
        migrations.AddConstraint(
            model_name='coachcareer',
            constraint=models.CheckConstraint(condition=models.Q(('end_date__gt', models.F('start_date')), ('end_date__isnull', True), _connector='OR'), name='career_end_date_after_start'),
        ),
        migrations.AddConstraint(
            model_name='coachcareer',
            constraint=models.CheckConstraint(condition=models.Q(('matches', django.db.models.expressions.CombinedExpression(django.db.models.expressions.CombinedExpression(models.F('wins'), '+', models.F('draws')), '+', models.F('losses')))), name='career_matches_sum_check'),
        ),
        migrations.AddIndex(
            model_name='coach',
            index=models.Index(fields=['name', 'nationality'], name='football_co_name_85bc6b_idx'),
        ),
        migrations.AddConstraint(
            model_name='coach',
            constraint=models.CheckConstraint(condition=models.Q(('birth_date__lt', datetime.datetime(2025, 2, 8, 18, 59, 53, 723089, tzinfo=datetime.timezone.utc))), name='coach_birth_date_past'),
        ),
        migrations.AddIndex(
            model_name='venue',
            index=models.Index(fields=['name', 'city'], name='football_ve_name_517d3b_idx'),
        ),
        migrations.AddIndex(
            model_name='venue',
            index=models.Index(fields=['external_id'], name='football_ve_externa_9f99ff_idx'),
        ),
        migrations.AddIndex(
            model_name='team',
            index=models.Index(fields=['name', 'country'], name='football_te_name_fbcd6d_idx'),
        ),
        migrations.AddIndex(
            model_name='team',
            index=models.Index(fields=['external_id'], name='football_te_externa_5c805f_idx'),
        ),
        migrations.AddIndex(
            model_name='fixture',
            index=models.Index(fields=['date', 'status'], name='football_fi_date_66b220_idx'),
        ),
        migrations.AddIndex(
            model_name='fixture',
            index=models.Index(fields=['league', 'season', 'date'], name='football_fi_league__a9a7fa_idx'),
        ),
        migrations.AddIndex(
            model_name='fixture',
            index=models.Index(fields=['home_team', 'away_team', 'season'], name='football_fi_home_te_5c79f1_idx'),
        ),
        migrations.AddConstraint(
            model_name='fixture',
            constraint=models.CheckConstraint(condition=models.Q(('home_team', models.F('away_team')), _negated=True), name='home_away_teams_different'),
        ),
    ]
