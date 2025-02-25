from django.db import models

class PlayerPosition(models.TextChoices):
    """Positions des joueurs"""
    GOALKEEPER = 'GK', 'Goalkeeper'
    DEFENDER = 'DF', 'Defender'
    MIDFIELDER = 'MF', 'Midfielder'
    FORWARD = 'FW', 'Forward'

class LeagueType(models.TextChoices):
    """Types de compétitions"""
    LEAGUE = 'League', 'League'
    CUP = 'Cup', 'Cup'
    OTHER = 'Other', 'Other'

class FixtureStatusType(models.TextChoices):
    """Types de statut des matchs"""
    SCHEDULED = 'scheduled', 'Scheduled'
    IN_PLAY = 'in_play', 'In Play'
    FINISHED = 'finished', 'Finished'
    CANCELLED = 'cancelled', 'Cancelled'
    POSTPONED = 'postponed', 'Postponed'
    ABANDONED = 'abandoned', 'Abandoned'
    NOT_PLAYED = 'not_played', 'Not Played'

class FixtureStatus(models.TextChoices):
    """Statuts détaillés des matchs"""
    TBD = 'TBD', 'Time To Be Defined'
    NS = 'NS', 'Not Started'
    FIRST_HALF = '1H', 'First Half'
    HALF_TIME = 'HT', 'Half Time'
    SECOND_HALF = '2H', 'Second Half'
    EXTRA_TIME = 'ET', 'Extra Time'
    BREAK_TIME = 'BT', 'Break Time'
    PENALTY = 'P', 'Penalty In Progress'
    SUSPENDED = 'SUSP', 'Match Suspended'
    INTERRUPTED = 'INT', 'Match Interrupted'
    FULL_TIME = 'FT', 'Full Time'
    AFTER_EXTRA = 'AET', 'After Extra Time'
    PENALTIES = 'PEN', 'Penalties'
    POSTPONED = 'PST', 'Postponed'
    CANCELLED = 'CANC', 'Cancelled'
    ABANDONED = 'ABD', 'Abandoned'
    TECHNICAL_LOSS = 'AWD', 'Technical Loss'
    WALKOVER = 'WO', 'Walkover'
    LIVE = 'LIVE', 'In Progress'

class EventType(models.TextChoices):
    """Types d'événements pendant un match"""
    GOAL = 'Goal', 'Goal'
    CARD = 'Card', 'Card'
    SUBSTITUTION = 'Substitution', 'Substitution'
    VAR = 'VAR', 'VAR'
    INJURY = 'Injury', 'Injury'
    OTHER = 'Other', 'Other'

class StatType(models.TextChoices):
    """Types de statistiques"""
    SHOTS_ON_GOAL = 'shots_on_goal', 'Shots on Goal'
    SHOTS_OFF_GOAL = 'shots_off_goal', 'Shots off Goal'
    SHOTS_INSIDE = 'shots_insidebox', 'Shots Inside Box'
    SHOTS_OUTSIDE = 'shots_outsidebox', 'Shots Outside Box'
    TOTAL_SHOTS = 'total_shots', 'Total Shots'
    BLOCKED_SHOTS = 'blocked_shots', 'Blocked Shots'
    FOULS = 'fouls', 'Fouls'
    CORNERS = 'corner_kicks', 'Corner Kicks'
    OFFSIDES = 'offsides', 'Offsides'
    POSSESSION = 'ball_possession', 'Ball Possession'
    YELLOW_CARDS = 'yellow_cards', 'Yellow Cards'
    RED_CARDS = 'red_cards', 'Red Cards'
    SAVES = 'goalkeeper_saves', 'Goalkeeper Saves'
    TOTAL_PASSES = 'total_passes', 'Total Passes'
    ACCURATE_PASSES = 'passes_accurate', 'Accurate Passes'
    PASS_PERCENT = 'passes_percentage', 'Pass Percentage'
    GOALS_PREVENTED = 'goals_prevented', 'Goals Prevented'

class InjurySeverity(models.TextChoices):
    """Gravité des blessures"""
    MINOR = 'minor', 'Minor'
    MODERATE = 'moderate', 'Moderate'
    SEVERE = 'severe', 'Severe'
    SEASON_ENDING = 'season_ending', 'Season Ending'

class InjuryStatus(models.TextChoices):
    """Statut de récupération des blessures"""
    RECOVERING = 'recovering', 'Recovering'
    TRAINING = 'training', 'Back in Training'
    AVAILABLE = 'available', 'Available for Selection'
    DOUBTFUL = 'doubtful', 'Doubtful'

class CoachRole(models.TextChoices):
    """Rôles des entraîneurs"""
    HEAD_COACH = 'head_coach', 'Head Coach'
    ASSISTANT = 'assistant', 'Assistant Coach'
    YOUTH_COACH = 'youth_coach', 'Youth Team Coach'
    INTERIM = 'interim', 'Interim Manager'

class OddsCategory(models.TextChoices):
    """Catégories de paris"""
    MAIN = 'main', 'Main'
    GOALS = 'goals', 'Goals'
    HALVES = 'halves', 'Halves'
    SPECIALS = 'specials', 'Specials'

class OddsStatus(models.TextChoices):
    """Statuts des paris"""
    ACTIVE = 'active', 'Active'
    SUSPENDED = 'suspended', 'Suspended'
    SETTLED = 'settled', 'Settled'
    CANCELLED = 'cancelled', 'Cancelled'

class TransferType(models.TextChoices):
    """Types de transferts"""
    FREE = 'Free', 'Free Transfer'
    LOAN = 'Loan', 'Loan'
    PERMANENT = 'Permanent', 'Permanent Transfer'
    NA = 'N/A', 'Not Available'

class UpdateType(models.TextChoices):
    """Types de mises à jour"""
    CREATE = 'create', 'Create'
    UPDATE = 'update', 'Update'
    DELETE = 'delete', 'Delete'
    BULK_UPDATE = 'bulk_update', 'Bulk Update'
    BULK_CREATE = 'bulk_create', 'Bulk Create'

class OddsMovement(models.TextChoices):
    """Direction du mouvement des cotes"""
    UP = 'up', 'Up'
    DOWN = 'down', 'Down'
    STABLE = 'stable', 'Stable'