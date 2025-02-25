from rdflib import Namespace, RDF, RDFS, XSD
from .config import FOOTBALL, SCHEMA, DCTERMS

# SHACL Shapes Configuration
SHACL_SHAPES = {
    'Country': {
        'class': FOOTBALL.Country,
        'properties': {
            SCHEMA.name: {
                'datatype': XSD.string,
                'min_count': 1,
                'max_count': 1,
                'pattern': r'^[A-Za-z\s\-]+$'
            },
            FOOTBALL.countryCode: {
                'datatype': XSD.string,
                'pattern': r'^[A-Z]{2,3}$',
                'min_count': 1,
                'max_count': 1
            }
        }
    },
    'Player': {
        'class': FOOTBALL.Player,
        'properties': {
            SCHEMA.name: {
                'datatype': XSD.string,
                'min_count': 1,
                'max_count': 1
            },
            SCHEMA.birthDate: {
                'datatype': XSD.date,
                'min_count': 1,
                'max_count': 1
            },
            FOOTBALL.position: {
                'in': ['GK', 'DF', 'MF', 'FW'],
                'min_count': 1,
                'max_count': 1
            }
        }
    },
    'Team': {
        'class': FOOTBALL.Team,
        'properties': {
            SCHEMA.name: {
                'datatype': XSD.string,
                'min_count': 1,
                'max_count': 1
            },
            FOOTBALL.founded: {
                'datatype': XSD.gYear,
                'min_inclusive': 1800,
                'max_inclusive': 2024
            }
        }
    }
}

# Business Rules Configuration
BUSINESS_RULES = {
    'Player': {
        'age_restriction': {
            'rule': 'age >= 16',
            'error_message': 'Player must be at least 16 years old'
        },
        'squad_number': {
            'rule': '1 <= number <= 99',
            'error_message': 'Squad number must be between 1 and 99'
        }
    },
    'Match': {
        'team_uniqueness': {
            'rule': 'home_team != away_team',
            'error_message': 'Home and away teams must be different'
        },
        'score_validation': {
            'rule': 'score >= 0',
            'error_message': 'Score cannot be negative'
        }
    },
    'Transfer': {
        'date_validation': {
            'rule': 'transfer_date >= contract_start_date',
            'error_message': 'Transfer date must be after contract start date'
        }
    }
}

# Validation Error Handling
ERROR_HANDLING = {
    'validation_failure': {
        'log_error': True,
        'raise_exception': True,
        'notification_required': True
    },
    'business_rule_violation': {
        'log_error': True,
        'raise_exception': True,
        'notification_required': True
    },
    'data_quality_issue': {
        'log_error': True,
        'raise_exception': False,
        'notification_required': True
    }
}

# Data Quality Rules
DATA_QUALITY_RULES = {
    'string_fields': {
        'min_length': 2,
        'max_length': 100,
        'pattern': r'^[A-Za-z0-9\s\-\.]+$'
    },
    'numeric_fields': {
        'min_value': 0,
        'max_value': 1000000
    },
    'date_fields': {
        'min_date': '1800-01-01',
        'max_date': '2100-12-31'
    }
}

# Relationship Constraints
RELATIONSHIP_CONSTRAINTS = {
    'Player_Team': {
        'cardinality': 'many-to-one',
        'mandatory': True,
        'temporal_validity': True
    },
    'Team_League': {
        'cardinality': 'many-to-many',
        'mandatory': True,
        'temporal_validity': True
    }
}

# Custom Validation Functions
def validate_player_age(birth_date):
    """Validate player age is within acceptable range"""
    # Implementation
    pass

def validate_match_schedule(match_date, competition_dates):
    """Validate match date is within competition dates"""
    # Implementation
    pass

def validate_transfer_window(transfer_date, window_dates):
    """Validate transfer date is within transfer window"""
    # Implementation
    pass

# Validation Pipeline Configuration
VALIDATION_PIPELINE = {
    'stages': [
        'shacl_validation',
        'business_rules_validation',
        'data_quality_validation',
        'relationship_validation',
        'custom_validation'
    ],
    'parallel_validation': True,
    'fail_fast': True
}