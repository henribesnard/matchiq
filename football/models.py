from django.db import models
from django.utils.timezone import now
from django.core.validators import MinValueValidator, MaxValueValidator, RegexValidator
from datetime import date
from .constants import PlayerPosition,LeagueType,FixtureStatusType,EventType,StatType, InjurySeverity, InjuryStatus, CoachRole,OddsCategory,OddsStatus,TransferType,UpdateType, OddsMovement

class Country(models.Model):
    id = models.AutoField(primary_key=True)
    external_id = models.IntegerField(blank=True, null=True, db_index=True)
    name = models.CharField(max_length=100, unique=True, db_index=True)
    code = models.CharField(
        max_length=20,  
        blank=True, 
        null=True, 
        db_index=True,
        validators=[RegexValidator(r'^[A-Z-]{2,10}$')]
    )
    flag_url = models.URLField(blank=True, null=True)

    update_by = models.CharField(max_length=50, default="manual")
    update_at = models.DateTimeField(default=now)

    def __str__(self):
        return self.name

class Venue(models.Model):
    id = models.AutoField(primary_key=True)
    external_id = models.IntegerField(unique=True, db_index=True)
    name = models.CharField(max_length=255, db_index=True)
    address = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=100, db_index=True)
    country = models.ForeignKey(Country, on_delete=models.CASCADE)
    capacity = models.PositiveIntegerField(blank=True, null=True)  # Changé pour PositiveIntegerField
    surface = models.CharField(max_length=50, blank=True, null=True)
    image_url = models.URLField(blank=True, null=True)

    update_by = models.CharField(max_length=50, default="manual")
    update_at = models.DateTimeField(default=now)

    class Meta:
        indexes = [
            models.Index(fields=['name', 'city']),
            models.Index(fields=['external_id']),
        ]

    def __str__(self):
        return f"{self.name} ({self.city})"

class League(models.Model):
    id = models.AutoField(primary_key=True)
    external_id = models.IntegerField(unique=True, db_index=True)
    name = models.CharField(max_length=255, db_index=True)
    type = models.CharField(max_length=50, choices=LeagueType.choices)
    logo_url = models.URLField(blank=True, null=True)
    country = models.ForeignKey(Country, on_delete=models.CASCADE)

    update_by = models.CharField(max_length=50, default="manual")
    update_at = models.DateTimeField(default=now)

    class Meta:
        indexes = [
            models.Index(fields=['name', 'country']),
        ]

    def __str__(self):
        return self.name

class Team(models.Model):
    id = models.AutoField(primary_key=True)
    external_id = models.IntegerField(unique=True, db_index=True)
    name = models.CharField(max_length=255, db_index=True)
    code = models.CharField(
        max_length=5,  # Réduit car les codes d'équipe sont généralement courts
        blank=True, 
        null=True, 
        db_index=True
    )
    country = models.ForeignKey(Country, on_delete=models.CASCADE)
    founded = models.PositiveSmallIntegerField(  # Optimisé pour les années
        blank=True,
        null=True,
        validators=[
            MinValueValidator(1800),
            MaxValueValidator(2100)
        ]
    )
    is_national = models.BooleanField(default=False)  # Renommé de 'national'
    logo_url = models.URLField(blank=True, null=True)
    venue = models.ForeignKey(Venue, on_delete=models.SET_NULL, blank=True, null=True)

    # Champs dénormalisés pour les performances
    total_matches = models.PositiveIntegerField(default=0)
    total_wins = models.PositiveIntegerField(default=0)
    total_draws = models.PositiveIntegerField(default=0)
    total_losses = models.PositiveIntegerField(default=0)
    total_goals_scored = models.PositiveIntegerField(default=0)
    total_goals_conceded = models.PositiveIntegerField(default=0)

    update_by = models.CharField(max_length=50, default="manual")
    update_at = models.DateTimeField(default=now)

    class Meta:
        indexes = [
            models.Index(fields=['name', 'country']),
            models.Index(fields=['external_id']),
        ]

    def __str__(self):
        return self.name

class Season(models.Model):
    id = models.AutoField(primary_key=True)
    external_id = models.IntegerField(blank=True, null=True, db_index=True)
    league = models.ForeignKey(League, on_delete=models.CASCADE)
    year = models.PositiveSmallIntegerField(  # Optimisé pour les années
        db_index=True,
        validators=[
            MinValueValidator(1800),
            MaxValueValidator(2100)
        ]
    )
    start_date = models.DateField()
    end_date = models.DateField()
    is_current = models.BooleanField(default=False)

    update_by = models.CharField(max_length=50, default="manual")
    update_at = models.DateTimeField(default=now)

    class Meta:
        indexes = [
            models.Index(fields=['league', 'year']),
            models.Index(fields=['is_current']),  # Ajouté pour les requêtes fréquentes
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(end_date__gte=models.F('start_date')),
                name='end_date_after_start_date'
            )
        ]

    def __str__(self):
        return f"{self.league.name} - {self.year}"
    
class FixtureStatus(models.Model):
    id = models.AutoField(primary_key=True)
    short_code = models.CharField(
        max_length=10, 
        unique=True,
        help_text="Ex: FT, HT, NS"
    )
    long_description = models.CharField(
        max_length=100,
        help_text="Ex: Match Finished, Half Time"
    )
    status_type = models.CharField(
        max_length=20,
        choices=FixtureStatusType.choices,
        db_index=True
    )
    description = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name_plural = "Fixture Statuses"
        indexes = [
            models.Index(fields=['short_code', 'status_type'])
        ]

    def __str__(self):
        return f"{self.short_code} - {self.long_description}"

    @classmethod
    def create_default_statuses(cls):
        """Méthode de classe pour créer les statuts par défaut"""
        defaults = {
            'TBD': ('Time To Be Defined', FixtureStatusType.SCHEDULED),
            'NS': ('Not Started', FixtureStatusType.SCHEDULED),
            '1H': ('First Half, Kick Off', FixtureStatusType.IN_PLAY),
            'HT': ('Halftime', FixtureStatusType.IN_PLAY),
            '2H': ('Second Half', FixtureStatusType.IN_PLAY),
            'ET': ('Extra Time', FixtureStatusType.IN_PLAY),
            'BT': ('Break Time', FixtureStatusType.IN_PLAY),
            'P': ('Penalty In Progress', FixtureStatusType.IN_PLAY),
            'SUSP': ('Match Suspended', FixtureStatusType.IN_PLAY),
            'INT': ('Match Interrupted', FixtureStatusType.IN_PLAY),
            'FT': ('Match Finished', FixtureStatusType.FINISHED),
            'AET': ('After Extra Time', FixtureStatusType.FINISHED),
            'PEN': ('Penalties', FixtureStatusType.FINISHED),
            'PST': ('Postponed', FixtureStatusType.POSTPONED),
            'CANC': ('Cancelled', FixtureStatusType.CANCELLED),
            'ABD': ('Abandoned', FixtureStatusType.ABANDONED),
            'AWD': ('Technical Loss', FixtureStatusType.NOT_PLAYED),
            'WO': ('Walkover', FixtureStatusType.NOT_PLAYED),
            'LIVE': ('In Progress', FixtureStatusType.IN_PLAY),
        }
        
        for short_code, (long_desc, status_type) in defaults.items():
            cls.objects.get_or_create(
                short_code=short_code,
                defaults={
                    'long_description': long_desc,
                    'status_type': status_type
                }
            )

class Fixture(models.Model):
    id = models.AutoField(primary_key=True)
    external_id = models.IntegerField(unique=True, db_index=True)
    league = models.ForeignKey(League, on_delete=models.CASCADE, db_index=True)
    season = models.ForeignKey(Season, on_delete=models.CASCADE, db_index=True)  # Corrigé de IntegerField
    round = models.CharField(max_length=100, blank=True, null=True)
    home_team = models.ForeignKey(
        Team, 
        on_delete=models.CASCADE, 
        related_name="home_fixtures",
        db_index=True
    )
    away_team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        related_name="away_fixtures",
        db_index=True
    )
    date = models.DateTimeField(db_index=True)
    venue = models.ForeignKey(Venue, on_delete=models.SET_NULL, blank=True, null=True)
    referee = models.CharField(max_length=100, blank=True, null=True)
    status = models.ForeignKey(
        "FixtureStatus",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        db_index=True 
    )
    elapsed_time = models.SmallIntegerField(blank=True, null=True)  # Optimisé car <= 150 minutes
    timezone = models.CharField(max_length=50, default="UTC")

    # Champs dénormalisés pour les performances
    home_score = models.SmallIntegerField(null=True, blank=True)
    away_score = models.SmallIntegerField(null=True, blank=True)
    is_finished = models.BooleanField(default=False)

    update_by = models.CharField(max_length=50, default="manual")
    update_at = models.DateTimeField(default=now)

    class Meta:
        indexes = [
            models.Index(fields=['date', 'status']),
            models.Index(fields=['league', 'season', 'date']),
            models.Index(fields=['home_team', 'away_team', 'season']),
        ]
        constraints = [
            models.CheckConstraint(
                check=~models.Q(home_team=models.F('away_team')),
                name='home_away_teams_different'
            )
        ]

    def __str__(self):
        return f"{self.home_team} vs {self.away_team} ({self.date.strftime('%Y-%m-%d')})"
    
class FixtureScore(models.Model):
    fixture = models.ForeignKey(Fixture, on_delete=models.CASCADE, db_index=True)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, db_index=True)
    halftime = models.SmallIntegerField(blank=True, null=True)  # Optimisé car rarement > 127
    fulltime = models.SmallIntegerField(blank=True, null=True)
    extratime = models.SmallIntegerField(blank=True, null=True)
    penalty = models.SmallIntegerField(blank=True, null=True)

    update_by = models.CharField(max_length=50, default="manual")
    update_at = models.DateTimeField(default=now)

    class Meta:
        indexes = [
            models.Index(fields=['fixture', 'team']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['fixture', 'team'],
                name='unique_fixture_team_score'
            )
        ]

    def __str__(self):
        return f"{self.fixture} - {self.team.name} : HT {self.halftime}, FT {self.fulltime}"

class FixtureEvent(models.Model):
    fixture = models.ForeignKey(Fixture, on_delete=models.CASCADE, db_index=True)
    time_elapsed = models.SmallIntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(150)]
    )
    event_type = models.CharField(max_length=50, choices=EventType.choices, db_index=True)
    detail = models.CharField(max_length=100)
    player = models.ForeignKey(
        "Player",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="events"
    )
    assist = models.ForeignKey(
        "Player",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="assists"
    )
    team = models.ForeignKey(Team, on_delete=models.CASCADE, db_index=True)
    comments = models.TextField(blank=True, null=True)

    update_by = models.CharField(max_length=50, default="manual")
    update_at = models.DateTimeField(default=now)

    class Meta:
        indexes = [
            models.Index(fields=['fixture', 'time_elapsed']),
            models.Index(fields=['event_type', 'team']),
        ]

class FixtureStatistic(models.Model):
    fixture = models.ForeignKey('Fixture', on_delete=models.CASCADE, db_index=True)
    team = models.ForeignKey('Team', on_delete=models.CASCADE, db_index=True)
    stat_type = models.CharField(
        max_length=50, 
        choices=StatType.choices,
        help_text="Type of statistic from API-Football",
        db_index=True
    )
    value = models.DecimalField(
        max_digits=7, 
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text="Statistical value (percentages are stored as decimals)"
    )

    update_by = models.CharField(max_length=50, default="manual")
    update_at = models.DateTimeField(default=now)

    class Meta:
        indexes = [
            models.Index(fields=['fixture', 'team', 'stat_type']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['fixture', 'team', 'stat_type'],
                name='unique_fixture_team_stat'
            )
        ]
        ordering = ['fixture', 'team', 'stat_type']

    def __str__(self):
        return f"{self.fixture} - {self.team.name} - {self.get_stat_type_display()}: {self.value}"

    @property
    def display_value(self):
        """Affiche la valeur avec le % si nécessaire."""
        if self.stat_type in ['ball_possession', 'passes_percentage']:
            return f"{self.value}%"
        return str(self.value)

class FixtureLineup(models.Model):
    """Représente la composition d'une équipe pour un match."""
    
    fixture = models.ForeignKey('Fixture', on_delete=models.CASCADE, db_index=True)
    team = models.ForeignKey('Team', on_delete=models.CASCADE, db_index=True)
    formation = models.CharField(
        max_length=10,
        validators=[RegexValidator(r'^\d-\d-\d(-\d)?$')],  # Ex: 4-3-3 or 4-3-1-2
    )
    
    # Couleurs de l'équipe pour ce match
    player_primary_color = models.CharField(max_length=6, null=True, blank=True)
    player_number_color = models.CharField(max_length=6, null=True, blank=True)
    player_border_color = models.CharField(max_length=6, null=True, blank=True)
    goalkeeper_primary_color = models.CharField(max_length=6, null=True, blank=True)
    goalkeeper_number_color = models.CharField(max_length=6, null=True, blank=True)
    goalkeeper_border_color = models.CharField(max_length=6, null=True, blank=True)

    update_by = models.CharField(max_length=50, default="manual")
    update_at = models.DateTimeField(default=now)

    class Meta:
        indexes = [
            models.Index(fields=['fixture', 'team']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['fixture', 'team'],
                name='unique_fixture_team_lineup'
            )
        ]

    def __str__(self):
        return f"{self.team.name} ({self.formation}) - {self.fixture}"

class FixtureLineupPlayer(models.Model):
    """Représente un joueur dans la composition d'équipe."""
    
    lineup = models.ForeignKey(
        FixtureLineup,
        on_delete=models.CASCADE,
        related_name='players',
        db_index=True
    )
    player = models.ForeignKey(
        'Player',
        on_delete=models.CASCADE,
        db_index=True
    )
    number = models.PositiveSmallIntegerField()
    position = models.CharField(
        max_length=2,  # Changé à 2 pour accommoder 'GK', 'DF', etc.
        choices=PlayerPosition.choices
    )
    grid = models.CharField(
        max_length=5,
        validators=[RegexValidator(r'^\d:\d$')],  # Format "x:y" pour la position sur le terrain
        null=True,
        blank=True
    )
    is_substitute = models.BooleanField(default=False)
    
    update_by = models.CharField(max_length=50, default="manual")
    update_at = models.DateTimeField(default=now)

    class Meta:
        indexes = [
            models.Index(fields=['lineup', 'player']),
            models.Index(fields=['lineup', 'position']),
            models.Index(fields=['is_substitute']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['lineup', 'player'],
                name='unique_lineup_player'
            ),
            models.UniqueConstraint(
                fields=['lineup', 'number'],
                name='unique_lineup_number'
            ),
            models.UniqueConstraint(
                fields=['lineup', 'grid'],
                name='unique_lineup_grid',
                condition=models.Q(grid__isnull=False)
            )
        ]

    def __str__(self):
        return f"{self.player.name} ({self.number}) - {self.position}"

class FixtureCoach(models.Model):
    """Représente l'entraîneur d'une équipe pour un match."""
    
    fixture = models.ForeignKey('Fixture', on_delete=models.CASCADE, db_index=True)
    team = models.ForeignKey('Team', on_delete=models.CASCADE, db_index=True)
    coach = models.ForeignKey('Coach', on_delete=models.CASCADE, db_index=True)
    
    update_by = models.CharField(max_length=50, default="manual")
    update_at = models.DateTimeField(default=now)

    class Meta:
        indexes = [
            models.Index(fields=['fixture', 'team']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['fixture', 'team'],
                name='unique_fixture_team_coach'
            )
        ]

    def __str__(self):
        return f"{self.coach.name} ({self.team.name}) - {self.fixture}"
    
class Player(models.Model):

    id = models.AutoField(primary_key=True)
    external_id = models.IntegerField(unique=True, db_index=True)
    name = models.CharField(max_length=255, db_index=True)
    firstname = models.CharField(max_length=100, blank=True, null=True)
    lastname = models.CharField(max_length=100, blank=True, null=True)
    birth_date = models.DateField(blank=True, null=True)
    nationality = models.ForeignKey(
        Country,
        on_delete=models.SET_NULL,
        null=True,
        related_name='players'
    )
    height = models.PositiveSmallIntegerField(  # Stocké en cm
        blank=True,
        null=True,
        validators=[MinValueValidator(120), MaxValueValidator(250)]
    )
    weight = models.PositiveSmallIntegerField(  # Stocké en kg
        blank=True,
        null=True,
        validators=[MinValueValidator(30), MaxValueValidator(150)]
    )
    team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        db_index=True,
        related_name='players'
    )
    position = models.CharField(max_length=2, choices=PlayerPosition.choices)
    number = models.PositiveSmallIntegerField(
        blank=True,
        null=True,
        validators=[MinValueValidator(1), MaxValueValidator(99)]
    )
    injured = models.BooleanField(default=False)
    photo_url = models.URLField(blank=True, null=True)

    # Champs dénormalisés pour les performances
    season_goals = models.PositiveIntegerField(default=0)
    season_assists = models.PositiveIntegerField(default=0)
    season_yellow_cards = models.PositiveSmallIntegerField(default=0)
    season_red_cards = models.PositiveSmallIntegerField(default=0)
    total_appearances = models.PositiveIntegerField(default=0)

    update_by = models.CharField(max_length=50, default="manual")
    update_at = models.DateTimeField(default=now)

    class Meta:
        indexes = [
            models.Index(fields=['name', 'team']),
            models.Index(fields=['position', 'team']),
            models.Index(fields=['injured']),
        ]

    def __str__(self):
        return f"{self.name} ({self.team.name})"

class FixturePlayerStatistic(models.Model):
    """Statistiques détaillées d'un joueur pour un match spécifique."""

    fixture = models.ForeignKey('Fixture', on_delete=models.CASCADE, db_index=True)
    player = models.ForeignKey('Player', on_delete=models.CASCADE, db_index=True)
    team = models.ForeignKey('Team', on_delete=models.CASCADE, db_index=True)
    
    # Données de jeu
    minutes_played = models.PositiveSmallIntegerField()
    position = models.CharField(max_length=2, choices=PlayerPosition.choices)
    number = models.PositiveSmallIntegerField()
    rating = models.DecimalField(
        max_digits=3, 
        decimal_places=1,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(10)]
    )
    is_captain = models.BooleanField(default=False)
    is_substitute = models.BooleanField(default=False)

    # Statistiques offensives
    shots_total = models.PositiveSmallIntegerField(default=0)
    shots_on_target = models.PositiveSmallIntegerField(default=0)
    goals_scored = models.PositiveSmallIntegerField(default=0)
    goals_conceded = models.PositiveSmallIntegerField(default=0)
    assists = models.PositiveSmallIntegerField(default=0)
    saves = models.PositiveSmallIntegerField(default=0)
    
    # Passes
    passes_total = models.PositiveSmallIntegerField(default=0)
    passes_key = models.PositiveSmallIntegerField(default=0)
    passes_accuracy = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )

    # Défense
    tackles_total = models.PositiveSmallIntegerField(default=0)
    blocks = models.PositiveSmallIntegerField(default=0)
    interceptions = models.PositiveSmallIntegerField(default=0)

    # Duels
    duels_total = models.PositiveSmallIntegerField(default=0)
    duels_won = models.PositiveSmallIntegerField(default=0)

    # Dribbles
    dribbles_attempts = models.PositiveSmallIntegerField(default=0)
    dribbles_success = models.PositiveSmallIntegerField(default=0)
    dribbles_past = models.PositiveSmallIntegerField(default=0)

    # Fautes
    fouls_drawn = models.PositiveSmallIntegerField(default=0)
    fouls_committed = models.PositiveSmallIntegerField(default=0)
    
    # Cartons
    yellow_cards = models.PositiveSmallIntegerField(default=0)
    red_cards = models.PositiveSmallIntegerField(default=0)

    # Pénaltys
    penalties_won = models.PositiveSmallIntegerField(default=0)
    penalties_committed = models.PositiveSmallIntegerField(default=0)
    penalties_scored = models.PositiveSmallIntegerField(default=0)
    penalties_missed = models.PositiveSmallIntegerField(default=0)
    penalties_saved = models.PositiveSmallIntegerField(default=0)

    # Hors-jeu
    offsides = models.PositiveSmallIntegerField(default=0)

    update_by = models.CharField(max_length=50, default="manual")
    update_at = models.DateTimeField(default=now)

    class Meta:
        indexes = [
            models.Index(fields=['fixture', 'player']),
            models.Index(fields=['fixture', 'team']),
            models.Index(fields=['player', 'team']),
            models.Index(fields=['rating']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['fixture', 'player'],
                name='unique_fixture_player_statistics'
            ),
            models.CheckConstraint(
                check=models.Q(shots_on_target__lte=models.F('shots_total')),
                name='shots_on_target_lte_total_fixture'
            ),
            models.CheckConstraint(
                check=models.Q(duels_won__lte=models.F('duels_total')),
                name='duels_won_lte_total_fixture'
            ),
            models.CheckConstraint(
                check=models.Q(dribbles_success__lte=models.F('dribbles_attempts')),
                name='dribbles_success_lte_attempts_fixture'
            )
        ]

    def __str__(self):
        return f"{self.player.name} - {self.fixture} ({self.rating})"

class PlayerStatistics(models.Model):
    id = models.AutoField(primary_key=True)
    player = models.ForeignKey("Player", on_delete=models.CASCADE, db_index=True)
    fixture = models.ForeignKey("Fixture", on_delete=models.CASCADE, db_index=True)
    team = models.ForeignKey("Team", on_delete=models.CASCADE, db_index=True)
    minutes_played = models.PositiveSmallIntegerField(
        blank=True,
        null=True,
        validators=[MaxValueValidator(150)]
    )
    goals = models.PositiveSmallIntegerField(default=0)
    assists = models.PositiveSmallIntegerField(default=0)
    shots_total = models.PositiveSmallIntegerField(default=0)
    shots_on_target = models.PositiveSmallIntegerField(default=0)
    passes = models.PositiveSmallIntegerField(default=0)
    key_passes = models.PositiveSmallIntegerField(default=0)
    pass_accuracy = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        null=True
    )
    tackles = models.PositiveSmallIntegerField(default=0)
    interceptions = models.PositiveSmallIntegerField(default=0)
    duels_total = models.PositiveSmallIntegerField(default=0)
    duels_won = models.PositiveSmallIntegerField(default=0)
    dribbles_success = models.PositiveSmallIntegerField(default=0)
    fouls_committed = models.PositiveSmallIntegerField(default=0)
    fouls_drawn = models.PositiveSmallIntegerField(default=0)
    yellow_cards = models.PositiveSmallIntegerField(default=0)
    red_cards = models.PositiveSmallIntegerField(default=0)
    rating = models.DecimalField(
        max_digits=3,
        decimal_places=1,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        null=True
    )
    is_substitute = models.BooleanField(default=False)
    update_by = models.CharField(max_length=50, default="manual")
    update_at = models.DateTimeField(default=now)

    class Meta:
        indexes = [
            models.Index(fields=['player', 'fixture']),
            models.Index(fields=['rating']),
            models.Index(fields=['goals']),
            models.Index(fields=['assists']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['player', 'fixture'],
                name='unique_player_fixture_statistics'
            ),
            models.CheckConstraint(
                check=models.Q(shots_on_target__lte=models.F('shots_total')),
                name='shots_on_target_lte_total'
            ),
            models.CheckConstraint(
                check=models.Q(duels_won__lte=models.F('duels_total')),
                name='duels_won_lte_total'
            )
        ]

class PlayerInjury(models.Model):
    id = models.AutoField(primary_key=True)
    player = models.ForeignKey(
        "Player",
        on_delete=models.CASCADE,
        db_index=True,
        related_name='injuries'
    )
    fixture = models.ForeignKey(
        "Fixture",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        db_index=True
    )
    type = models.CharField(max_length=100)
    severity = models.CharField(max_length=20, choices=InjurySeverity.choices)
    status = models.CharField(max_length=20, choices=InjuryStatus.choices)
    start_date = models.DateField(db_index=True)
    end_date = models.DateField(blank=True, null=True)
    expected_return_date = models.DateField(blank=True, null=True)
    recovery_time = models.PositiveSmallIntegerField(  # Stocké en jours
        blank=True,
        null=True,
        validators=[MaxValueValidator(365)]
    )

    update_by = models.CharField(max_length=50, default="manual")
    update_at = models.DateTimeField(default=now)

    class Meta:
        indexes = [
            models.Index(fields=['player', 'start_date']),
            models.Index(fields=['status', 'end_date']),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(end_date__gte=models.F('start_date')) | 
                      models.Q(end_date__isnull=True),
                name='injury_end_date_after_start'
            )
        ]

    def __str__(self):
        return f"{self.player.name} - {self.type} ({self.start_date})"

class Coach(models.Model):
    id = models.AutoField(primary_key=True)
    external_id = models.IntegerField(unique=True, db_index=True)
    name = models.CharField(max_length=255, db_index=True)
    firstname = models.CharField(max_length=100, blank=True, null=True)
    lastname = models.CharField(max_length=100, blank=True, null=True)
    nationality = models.ForeignKey(
        Country,
        on_delete=models.SET_NULL,
        null=True,
        related_name='coaches'
    )
    birth_date = models.DateField(blank=True, null=True)
    team = models.OneToOneField(  # Changed to OneToOneField as a coach can only manage one team
        Team,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='current_coach'
    )
    photo_url = models.URLField(blank=True, null=True)

    # Dénormalized fields for performance
    career_matches = models.PositiveIntegerField(default=0)
    career_wins = models.PositiveIntegerField(default=0)
    career_draws = models.PositiveIntegerField(default=0)
    career_losses = models.PositiveIntegerField(default=0)

    update_by = models.CharField(max_length=50, default="manual")
    update_at = models.DateTimeField(default=now)

    class Meta:
        indexes = [
            models.Index(fields=['name', 'nationality']),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(birth_date__lt=now()),
                name='coach_birth_date_past'
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.nationality})"

class CoachCareer(models.Model):
    id = models.AutoField(primary_key=True)
    coach = models.ForeignKey(
        Coach,
        on_delete=models.CASCADE,
        db_index=True,
        related_name='career_entries'
    )
    team = models.ForeignKey(
        Team,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='coach_history'
    )
    role = models.CharField(max_length=20, choices=CoachRole.choices)
    start_date = models.DateField(db_index=True)
    end_date = models.DateField(blank=True, null=True)
    matches = models.PositiveIntegerField(default=0)
    wins = models.PositiveIntegerField(default=0)
    draws = models.PositiveIntegerField(default=0)
    losses = models.PositiveIntegerField(default=0)

    update_by = models.CharField(max_length=50, default="manual")
    update_at = models.DateTimeField(default=now)

    class Meta:
        indexes = [
            models.Index(fields=['coach', 'team']),
            models.Index(fields=['start_date', 'end_date']),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(end_date__gte=models.F('start_date')) | 
                      models.Q(end_date__isnull=True),
                name='career_end_date_after_start'
            ),
            models.CheckConstraint(
                check=models.Q(matches=models.F('wins') + models.F('draws') + models.F('losses')),
                name='career_matches_sum_check'
            )
        ]

    def __str__(self):
        return f"{self.coach.name} at {self.team.name if self.team else 'Unknown'}"
    
class Bookmaker(models.Model):
    id = models.AutoField(primary_key=True)
    external_id = models.IntegerField(unique=True, db_index=True)
    name = models.CharField(max_length=100)
    logo_url = models.URLField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    priority = models.SmallIntegerField(default=0)  # Pour ordonner les bookmakers

    update_by = models.CharField(max_length=50, default="manual")
    update_at = models.DateTimeField(default=now)

    class Meta:
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['is_active', 'priority']),
        ]

    def __str__(self):
        return self.name

class OddsType(models.Model):
    id = models.AutoField(primary_key=True)
    external_id = models.IntegerField(unique=True, db_index=True)
    name = models.CharField(max_length=100)  # Ex: "Match Winner", "Both Teams Score"
    key = models.CharField(max_length=50, db_index=True)  # Ex: "match_winner", "btts"
    description = models.TextField(blank=True, null=True)
    category = models.CharField(
        max_length=50,
        choices=OddsCategory.choices,
        db_index=True
    )
    update_by = models.CharField(max_length=50, default="manual")
    update_at = models.DateTimeField(default=now)
    display_order = models.SmallIntegerField(default=0)

    class Meta:
        indexes = [
            models.Index(fields=['category', 'display_order']),
        ]

    def __str__(self):
        return f"{self.name} ({self.category})"

class OddsValue(models.Model):
    id = models.AutoField(primary_key=True)
    odds_type = models.ForeignKey(OddsType, on_delete=models.CASCADE)
    name = models.CharField(max_length=100, db_index=True)  # Ex: "Home", "Away", "Over 2.5"
    key = models.CharField(max_length=50)  # Ex: "home", "away", "over_2_5"
    display_order = models.SmallIntegerField(default=0)

    update_by = models.CharField(max_length=50, default="manual")
    update_at = models.DateTimeField(default=now)

    class Meta:
        unique_together = ['odds_type', 'key']
        indexes = [
            models.Index(fields=['odds_type', 'display_order']),
        ]

    def __str__(self):
        return f"{self.odds_type.name} - {self.name}"

class Odds(models.Model):
    id = models.AutoField(primary_key=True)
    fixture = models.ForeignKey('Fixture', on_delete=models.CASCADE, db_index=True)
    bookmaker = models.ForeignKey(Bookmaker, on_delete=models.CASCADE)
    odds_type = models.ForeignKey(OddsType, on_delete=models.CASCADE)
    odds_value = models.ForeignKey(OddsValue, on_delete=models.CASCADE)
    value = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        validators=[MinValueValidator(1.01)]
    )
    is_main = models.BooleanField(default=False)  # Pour identifier les cotes principales
    probability = models.DecimalField(  # Probabilité calculée (1/cote)
        max_digits=5,
        decimal_places=2,
        null=True
    )
    status = models.CharField(
        max_length=20,
        choices=OddsStatus.choices,
        default='active'
    )
    last_update = models.DateTimeField(auto_now=True)
    update_by = models.CharField(max_length=50, default="manual")
    update_at = models.DateTimeField(default=now)

    class Meta:
        indexes = [
            models.Index(fields=['fixture', 'bookmaker', 'odds_type']),
            models.Index(fields=['fixture', 'status']),
            models.Index(fields=['last_update']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['fixture', 'bookmaker', 'odds_type', 'odds_value'],
                name='unique_odds'
            )
        ]

    def save(self, *args, **kwargs):
        # Calculer la probabilité à partir de la cote
        if self.value:
            self.probability = round((1 / float(self.value)) * 100, 2)
        super().save(*args, **kwargs)

class OddsHistory(models.Model):
    id = models.AutoField(primary_key=True)
    odds = models.ForeignKey(Odds, on_delete=models.CASCADE)
    old_value = models.DecimalField(max_digits=7, decimal_places=2)
    new_value = models.DecimalField(max_digits=7, decimal_places=2)
    change_time = models.DateTimeField(auto_now_add=True)
    update_by = models.CharField(max_length=50, default="manual")
    update_at = models.DateTimeField(default=now)
    movement = models.CharField(
        max_length=10,
        choices=OddsMovement.choices
    )

    class Meta:
        indexes = [
            models.Index(fields=['odds', 'change_time']),
        ]

class Standing(models.Model):
    """Représente une entrée dans le classement d'une ligue pour une saison."""
    
    season = models.ForeignKey('Season', on_delete=models.CASCADE, db_index=True)
    team = models.ForeignKey('Team', on_delete=models.CASCADE, db_index=True)
    
    # Position au classement
    rank = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])
    points = models.PositiveSmallIntegerField(default=0)
    goals_diff = models.SmallIntegerField(default=0)
    
    # Form et Status
    form = models.CharField(max_length=10, blank=True, null=True)  # Ex: "WWWLD"
    status = models.CharField(max_length=20, blank=True, null=True)  # Ex: "same", "up", "down"
    description = models.CharField(max_length=100, blank=True, null=True)  # Ex: "Promotion - Champions League"
    
    # Statistiques globales
    played = models.PositiveSmallIntegerField(default=0)
    won = models.PositiveSmallIntegerField(default=0)
    drawn = models.PositiveSmallIntegerField(default=0)
    lost = models.PositiveSmallIntegerField(default=0)
    goals_for = models.PositiveSmallIntegerField(default=0)
    goals_against = models.PositiveSmallIntegerField(default=0)
    
    # Statistiques à domicile
    home_played = models.PositiveSmallIntegerField(default=0)
    home_won = models.PositiveSmallIntegerField(default=0)
    home_drawn = models.PositiveSmallIntegerField(default=0)
    home_lost = models.PositiveSmallIntegerField(default=0)
    home_goals_for = models.PositiveSmallIntegerField(default=0)
    home_goals_against = models.PositiveSmallIntegerField(default=0)
    
    # Statistiques à l'extérieur
    away_played = models.PositiveSmallIntegerField(default=0)
    away_won = models.PositiveSmallIntegerField(default=0)
    away_drawn = models.PositiveSmallIntegerField(default=0)
    away_lost = models.PositiveSmallIntegerField(default=0)
    away_goals_for = models.PositiveSmallIntegerField(default=0)
    away_goals_against = models.PositiveSmallIntegerField(default=0)
    
    # Métadonnées
    update_by = models.CharField(max_length=50, default="manual")
    update_at = models.DateTimeField(default=now)

    class Meta:
        indexes = [
            models.Index(fields=['season', 'team']),
            models.Index(fields=['season', 'rank']),
            models.Index(fields=['season', 'points']),
            models.Index(fields=['update_at']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['season', 'team'],
                name='unique_team_season_standing'
            ),
            # Vérification de la cohérence des matchs joués
            models.CheckConstraint(
                check=models.Q(played=models.F('won') + models.F('drawn') + models.F('lost')),
                name='total_matches_check'
            ),
            models.CheckConstraint(
                check=models.Q(home_played=models.F('home_won') + models.F('home_drawn') + models.F('home_lost')),
                name='home_matches_check'
            ),
            models.CheckConstraint(
                check=models.Q(away_played=models.F('away_won') + models.F('away_drawn') + models.F('away_lost')),
                name='away_matches_check'
            ),
            # Vérification de la cohérence entre total et home/away
            models.CheckConstraint(
                check=models.Q(played=models.F('home_played') + models.F('away_played')),
                name='total_vs_home_away_matches_check'
            ),
            models.CheckConstraint(
                check=models.Q(goals_for=models.F('home_goals_for') + models.F('away_goals_for')),
                name='total_vs_home_away_goals_for_check'
            ),
            models.CheckConstraint(
                check=models.Q(goals_against=models.F('home_goals_against') + models.F('away_goals_against')),
                name='total_vs_home_away_goals_against_check'
            )
        ]

    def __str__(self):
        return f"{self.team.name} - {self.season.year} (Rank: {self.rank})"

    def save(self, *args, **kwargs):
        # Calculer la différence de buts
        self.goals_diff = self.goals_for - self.goals_against
        # Calculer le total des matchs joués
        self.played = self.won + self.drawn + self.lost
        super().save(*args, **kwargs)

class FixtureH2H(models.Model):
    """Modèle pour stocker les relations entre un match de référence et ses confrontations directes."""
    reference_fixture = models.ForeignKey('Fixture', on_delete=models.CASCADE, related_name='h2h_references')
    related_fixture = models.ForeignKey('Fixture', on_delete=models.CASCADE, related_name='h2h_related')
    
    # Métadonnées
    update_by = models.CharField(max_length=50, default="manual")
    update_at = models.DateTimeField(default=now)
    
    class Meta:
        unique_together = ['reference_fixture', 'related_fixture']
        indexes = [
            models.Index(fields=['reference_fixture']),
            models.Index(fields=['related_fixture']),
        ]
    
    def __str__(self):
        return f"H2H: {self.reference_fixture} - {self.related_fixture}"

class PlayerSideline(models.Model):
    """
    Historique des périodes d'indisponibilité des joueurs 
    (blessures, suspensions, etc.)
    """
    
    id = models.AutoField(primary_key=True)
    player = models.ForeignKey(
        Player, 
        on_delete=models.CASCADE,
        db_index=True,
        related_name='sidelines'
    )
    type = models.CharField(
        max_length=100,
        help_text="Type d'indisponibilité (blessure ou suspension)"
    )
    start_date = models.DateField(db_index=True)
    end_date = models.DateField(db_index=True)
    
    # Métadonnées
    update_by = models.CharField(max_length=50, default="manual")
    update_at = models.DateTimeField(default=now)

    class Meta:
        indexes = [
            models.Index(fields=['player', 'start_date']),
            models.Index(fields=['player', 'end_date']),
            models.Index(fields=['type']),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(end_date__gte=models.F('start_date')),
                name='sideline_end_after_start'
            )
        ]
        # Permettre d'avoir plusieurs indisponibilités différentes 
        # sur des périodes qui se chevauchent
        unique_together = ['player', 'type', 'start_date']

    def __str__(self):
        return f"{self.player.name} - {self.type} ({self.start_date} to {self.end_date})"

    def duration_days(self):
        """Retourne la durée en jours"""
        return (self.end_date - self.start_date).days + 1

    @property  
    def is_active(self):
        """Indique si l'indisponibilité est en cours"""
        today = date.today()
        return self.start_date <= today <= self.end_date

class PlayerTransfer(models.Model):
    """
    Historique des transferts des joueurs entre équipes
    """
    id = models.AutoField(primary_key=True)
    player = models.ForeignKey(
        Player, 
        on_delete=models.CASCADE,
        db_index=True,
        related_name='transfers'
    )
    date = models.DateField(db_index=True)
    type = models.CharField(
        max_length=20,
        choices=TransferType.choices,
        null=True,
        blank=True
    )
    team_in = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        related_name='transfers_in',
        db_index=True
    )
    team_out = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        related_name='transfers_out',
        db_index=True
    )
    
    # Métadonnées
    update_by = models.CharField(max_length=50, default="manual")
    update_at = models.DateTimeField(default=now)

    class Meta:
        indexes = [
            models.Index(fields=['player', 'date']),
            models.Index(fields=['team_in', 'date']),
            models.Index(fields=['team_out', 'date']),
            models.Index(fields=['type']),
        ]
        # Un joueur ne peut avoir qu'un seul transfert à une date donnée
        unique_together = ['player', 'date']
        ordering = ['-date']  # Tri par date décroissante

    def __str__(self):
        return f"{self.player.name}: {self.team_out.name} → {self.team_in.name} ({self.date})"
    
class PlayerTeam(models.Model):
    """
    Historique des équipes dans lesquelles un joueur a évolué par saison
    """
    id = models.AutoField(primary_key=True)
    player = models.ForeignKey(
        Player,
        on_delete=models.CASCADE,
        db_index=True,
        related_name='teams_history'
    )
    team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        db_index=True,
        related_name='player_history'
    )
    season = models.ForeignKey(
        Season,
        on_delete=models.CASCADE,
        db_index=True
    )
    
    # Métadonnées
    update_by = models.CharField(max_length=50, default="manual")
    update_at = models.DateTimeField(default=now)

    class Meta:
        indexes = [
            models.Index(fields=['player', 'team']),
            models.Index(fields=['player', 'season']),
            models.Index(fields=['team', 'season']),
        ]
        # Un joueur ne peut jouer que dans une équipe par saison 
        # (sauf en cas de transfert en cours de saison)
        unique_together = ['player', 'team', 'season']
        ordering = ['-season__year']  # Trier par année décroissante

    def __str__(self):
        return f"{self.player.name} - {self.team.name} ({self.season.year})"

    @property
    def is_current(self):
        """Indique si c'est l'équipe actuelle du joueur"""
        return self.team_id == self.player.team_id and self.season.is_current


class TeamPlayer(models.Model):
    """
    Effectif actuel d'une équipe
    """
    id = models.AutoField(primary_key=True)
    team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        db_index=True,
        related_name='squad'
    )
    player = models.ForeignKey(
        Player,
        on_delete=models.CASCADE,
        db_index=True,
        related_name='current_squad'
    )
    
    # Informations spécifiques au joueur dans l'équipe
    position = models.CharField(
        max_length=20,
        choices=PlayerPosition.choices,
        db_index=True
    )
    number = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(99)]
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Indique si le joueur fait partie de l'effectif actif"
    )

    # Métadonnées
    update_by = models.CharField(max_length=50, default="manual")
    update_at = models.DateTimeField(default=now)

    class Meta:
        indexes = [
            models.Index(fields=['team', 'position']),
            models.Index(fields=['team', 'is_active']),
            models.Index(fields=['player', 'is_active']),
        ]
        unique_together = [
            ['team', 'player'],  # Un joueur ne peut être qu'une fois dans l'équipe
            ['team', 'number', 'is_active']  # Numéro unique par équipe (pour les joueurs actifs)
        ]
        ordering = ['position', 'number']  # Tri par position puis numéro

    def __str__(self):
        return f"{self.player.name} ({self.number}) - {self.position} - {self.team.name}"

    def save(self, *args, **kwargs):
        # Désactiver les autres entrées du même joueur si celui-ci est actif
        if self.is_active:
            TeamPlayer.objects.filter(
                player=self.player,
                is_active=True
            ).exclude(id=self.id).update(is_active=False)
        super().save(*args, **kwargs)


class TeamStatistics(models.Model):
    """
    Statistiques globales d'une équipe pour une saison dans une ligue
    """
    id = models.AutoField(primary_key=True)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, db_index=True)
    league = models.ForeignKey(League, on_delete=models.CASCADE, db_index=True)
    season = models.ForeignKey(Season, on_delete=models.CASCADE, db_index=True)

    # Forme actuelle
    form = models.CharField(max_length=100, null=True, blank=True)  # Ex: "WDLDW"

    # Matches joués
    matches_played_home = models.PositiveSmallIntegerField(default=0)
    matches_played_away = models.PositiveSmallIntegerField(default=0)
    matches_played_total = models.PositiveSmallIntegerField(default=0)

    # Victoires
    wins_home = models.PositiveSmallIntegerField(default=0)
    wins_away = models.PositiveSmallIntegerField(default=0)
    wins_total = models.PositiveSmallIntegerField(default=0)

    # Nuls
    draws_home = models.PositiveSmallIntegerField(default=0)
    draws_away = models.PositiveSmallIntegerField(default=0)
    draws_total = models.PositiveSmallIntegerField(default=0)

    # Défaites
    losses_home = models.PositiveSmallIntegerField(default=0)
    losses_away = models.PositiveSmallIntegerField(default=0)
    losses_total = models.PositiveSmallIntegerField(default=0)

    # Buts marqués
    goals_for_home = models.PositiveSmallIntegerField(default=0)
    goals_for_away = models.PositiveSmallIntegerField(default=0)
    goals_for_total = models.PositiveSmallIntegerField(default=0)

    # Buts encaissés
    goals_against_home = models.PositiveSmallIntegerField(default=0)
    goals_against_away = models.PositiveSmallIntegerField(default=0)
    goals_against_total = models.PositiveSmallIntegerField(default=0)

    # Moyennes de buts
    goals_for_average_home = models.DecimalField(max_digits=4, decimal_places=2, default=0)
    goals_for_average_away = models.DecimalField(max_digits=4, decimal_places=2, default=0)
    goals_for_average_total = models.DecimalField(max_digits=4, decimal_places=2, default=0)
    goals_against_average_home = models.DecimalField(max_digits=4, decimal_places=2, default=0)
    goals_against_average_away = models.DecimalField(max_digits=4, decimal_places=2, default=0)
    goals_against_average_total = models.DecimalField(max_digits=4, decimal_places=2, default=0)

    # Séries
    streak_wins = models.PositiveSmallIntegerField(default=0)
    streak_draws = models.PositiveSmallIntegerField(default=0)
    streak_losses = models.PositiveSmallIntegerField(default=0)

    # Plus grandes victoires
    biggest_win_home = models.CharField(max_length=10, null=True, blank=True)  # Ex: "4-0"
    biggest_win_away = models.CharField(max_length=10, null=True, blank=True)  # Ex: "0-3"
    biggest_loss_home = models.CharField(max_length=10, null=True, blank=True)  # Ex: "0-2"
    biggest_loss_away = models.CharField(max_length=10, null=True, blank=True)  # Ex: "2-0"

    # Clean sheets
    clean_sheets_home = models.PositiveSmallIntegerField(default=0)
    clean_sheets_away = models.PositiveSmallIntegerField(default=0)
    clean_sheets_total = models.PositiveSmallIntegerField(default=0)

    # Failed to score
    failed_to_score_home = models.PositiveSmallIntegerField(default=0)
    failed_to_score_away = models.PositiveSmallIntegerField(default=0)
    failed_to_score_total = models.PositiveSmallIntegerField(default=0)

    # Penalties
    penalties_scored = models.PositiveSmallIntegerField(default=0)
    penalties_missed = models.PositiveSmallIntegerField(default=0)
    penalties_total = models.PositiveSmallIntegerField(default=0)

    # Métadonnées
    update_by = models.CharField(max_length=50, default="manual")
    update_at = models.DateTimeField(default=now)

    class Meta:
        indexes = [
            models.Index(fields=['team', 'season']),
            models.Index(fields=['league', 'season']),
        ]
        unique_together = ['team', 'league', 'season']
        ordering = ['-season__year', 'team__name']

    def __str__(self):
        return f"{self.team.name} - {self.league.name} ({self.season.year})"

    def save(self, *args, **kwargs):
        # Calculer les totaux
        self.matches_played_total = self.matches_played_home + self.matches_played_away
        self.wins_total = self.wins_home + self.wins_away
        self.draws_total = self.draws_home + self.draws_away
        self.losses_total = self.losses_home + self.losses_away
        self.goals_for_total = self.goals_for_home + self.goals_for_away
        self.goals_against_total = self.goals_against_home + self.goals_against_away
        self.clean_sheets_total = self.clean_sheets_home + self.clean_sheets_away
        self.failed_to_score_total = self.failed_to_score_home + self.failed_to_score_away
        self.penalties_total = self.penalties_scored + self.penalties_missed

        # Calculer les moyennes
        if self.matches_played_home > 0:
            self.goals_for_average_home = round(self.goals_for_home / self.matches_played_home, 2)
            self.goals_against_average_home = round(self.goals_against_home / self.matches_played_home, 2)
        if self.matches_played_away > 0:
            self.goals_for_average_away = round(self.goals_for_away / self.matches_played_away, 2)
            self.goals_against_average_away = round(self.goals_against_away / self.matches_played_away, 2)
        if self.matches_played_total > 0:
            self.goals_for_average_total = round(self.goals_for_total / self.matches_played_total, 2)
            self.goals_against_average_total = round(self.goals_against_total / self.matches_played_total, 2)

        super().save(*args, **kwargs)


class UpdateLog(models.Model):
    id = models.AutoField(primary_key=True)
    table_name = models.CharField(max_length=100, db_index=True)
    record_id = models.IntegerField(db_index=True)
    update_type = models.CharField(
        max_length=20,
        choices=UpdateType.choices,
        db_index=True
    )
    update_by = models.CharField(max_length=50, db_index=True)
    update_at = models.DateTimeField(default=now, db_index=True)
    old_data = models.JSONField(blank=True, null=True)
    new_data = models.JSONField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    is_success = models.BooleanField(default=True)
    error_message = models.TextField(blank=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=['table_name', 'record_id']),
            models.Index(fields=['update_at', 'update_type']),
        ]

    def __str__(self):
        return f"{self.table_name} - {self.record_id} ({self.update_type})"