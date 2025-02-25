from rdflib import Namespace, RDF, RDFS, XSD

# Core namespaces
FOOTBALL = Namespace("http://example.org/football/")
SCHEMA = Namespace("http://schema.org/")
DCTERMS = Namespace("http://purl.org/dc/terms/")
GEO = Namespace("http://www.w3.org/2003/01/geo/wgs84_pos#")
TIME = Namespace("http://www.w3.org/2006/time#")
STATS = Namespace("http://example.org/football/stats#")
FOAF = Namespace("http://xmlns.com/foaf/0.1/")
ORG = Namespace("http://www.w3.org/ns/org#")
VERSION = Namespace("http://example.org/football/version/")
PROV = Namespace("http://www.w3.org/ns/prov#")

# Configuration for versioning
VERSION_CONFIG = {
    'version_predicate': VERSION.hasVersion,
    'timestamp_predicate': VERSION.timestamp,
    'previous_version': VERSION.previousVersion,
    'author_predicate': VERSION.author,
    'change_type_predicate': VERSION.changeType,
    'version_notes': VERSION.notes
}

# Configuration for provenance
PROVENANCE_CONFIG = {
    'source_predicate': PROV.wasGeneratedBy,
    'timestamp_predicate': PROV.generatedAtTime,
    'agent_predicate': PROV.wasAttributedTo,
    'derived_from': PROV.wasDerivedFrom,
    'activity_type': PROV.Activity
}

# URI patterns for consistent identifier generation
URI_PATTERNS = {
    'Country': FOOTBALL['country/{}'],
    'Team': FOOTBALL['team/{}'],
    'Player': FOOTBALL['player/{}'],
    'Match': FOOTBALL['match/{}'],
    'Version': VERSION['{}'],
    'Activity': PROV['activity/{}']
}

# Language configuration
LANGUAGE_CONFIG = {
    'default_language': 'en',
    'supported_languages': ['en', 'fr', 'es'],
    'label_predicate': RDFS.label,
    'comment_predicate': RDFS.comment
}

# Inference rules configuration
INFERENCE_RULES = {
    'team_player_inference': [
        (FOOTBALL.player, FOOTBALL.playsFor, FOOTBALL.team),
        (FOOTBALL.team, FOOTBALL.hasPlayer, FOOTBALL.player)
    ],
    'match_stats_inference': [
        (FOOTBALL.match, FOOTBALL.hasHomeTeam, FOOTBALL.team),
        (FOOTBALL.team, FOOTBALL.playsHomeMatch, FOOTBALL.match)
    ],
    'league_team_inference': [
        (FOOTBALL.team, FOOTBALL.participatesIn, FOOTBALL.league),
        (FOOTBALL.league, FOOTBALL.hasParticipant, FOOTBALL.team)
    ]
}

# Standard vocabularies
STANDARD_VOCAB = {
    'PlayerPosition': {
        'GK': FOOTBALL.Goalkeeper,
        'DF': FOOTBALL.Defender,
        'MF': FOOTBALL.Midfielder,
        'FW': FOOTBALL.Forward
    },
    'MatchStatus': {
        'SCHEDULED': FOOTBALL.ScheduledMatch,
        'LIVE': FOOTBALL.LiveMatch,
        'FINISHED': FOOTBALL.FinishedMatch,
        'CANCELLED': FOOTBALL.CancelledMatch,
        'POSTPONED': FOOTBALL.PostponedMatch
    },
    'EventType': {
        'GOAL': FOOTBALL.GoalEvent,
        'CARD': FOOTBALL.CardEvent,
        'SUBSTITUTION': FOOTBALL.SubstitutionEvent,
        'VAR': FOOTBALL.VAREvent
    }
}

# Mapping configuration
ENTITY_MAPPINGS = {
    'Country': {
        'rdf_class': FOOTBALL.Country,
        'properties': {
            'external_id': (FOOTBALL.externalId, XSD.integer),
            'name': (SCHEMA.name, XSD.string),
            'code': (FOOTBALL.countryCode, XSD.string),
            'flag_url': (SCHEMA.image, XSD.anyURI),
            'update_by': (DCTERMS.modifiedBy, XSD.string),
            'update_at': (DCTERMS.modified, XSD.dateTime),
        },
        'inverse_relations': {
        'teams': (FOOTBALL.hasTeam, 'Team'),
        'players': (FOOTBALL.hasPlayer, 'Player'),
        'coaches': (FOOTBALL.hasCoach, 'Coach'),
        'venues': (FOOTBALL.hasVenue, 'Venue'),
        'leagues': (FOOTBALL.hasLeague, 'League')
    }
    },
    'Venue': {
        'rdf_class': FOOTBALL.Venue,
        'properties': {
            'external_id': (FOOTBALL.externalId, XSD.integer),
            'name': (SCHEMA.name, XSD.string),
            'address': (SCHEMA.address, XSD.string),
            'city': (SCHEMA.addressLocality, XSD.string),
            'country': (FOOTBALL.country, None, 'Country'), # ForeignKey to Country
            'capacity': (FOOTBALL.capacity, XSD.integer),
            'surface': (FOOTBALL.surfaceType, XSD.string),
            'image_url': (SCHEMA.image, XSD.anyURI),
            'update_by': (DCTERMS.modifiedBy, XSD.string),
            'update_at': (DCTERMS.modified, XSD.dateTime),
        },
        'inverse_relations': {
        'home_teams': (FOOTBALL.isHomeVenueFor, 'Team'),
        'fixtures': (FOOTBALL.hostsFixture, 'Fixture')
    }
    },
    'League': {
        'rdf_class': FOOTBALL.League,
        'properties': {
            'external_id': (FOOTBALL.externalId, XSD.integer),
            'name': (SCHEMA.name, XSD.string),
            'type': (FOOTBALL.leagueType, XSD.string), # Using FOOTBALL namespace for league type, consider a standard vocabulary if exists
            'logo_url': (SCHEMA.logo, XSD.anyURI),
            'country': (FOOTBALL.country, None, 'Country'), # ForeignKey to Country
            'update_by': (DCTERMS.modifiedBy, XSD.string),
            'update_at': (DCTERMS.modified, XSD.dateTime),
        },
        'inverse_relations': {
        'seasons': (FOOTBALL.hasSeason, 'Season'),
        'fixtures': (FOOTBALL.hasFixture, 'Fixture'),
        'standings': (FOOTBALL.hasStanding, 'Standing')
    }
    },
    'Team': {
        'rdf_class': FOOTBALL.Team,
        'properties': {
            'external_id': (FOOTBALL.externalId, XSD.integer),
            'name': (SCHEMA.name, XSD.string),
            'code': (FOOTBALL.teamCode, XSD.string),
            'country': (FOOTBALL.country, None, 'Country'), # ForeignKey to Country
            'founded': (SCHEMA.foundingDate, XSD.gYear),
            'is_national': (FOOTBALL.isNationalTeam, XSD.boolean),
            'logo_url': (SCHEMA.logo, XSD.anyURI),
            'venue': (FOOTBALL.venue, None, 'Venue'), # ForeignKey to Venue
            'total_matches': (FOOTBALL.totalMatches, XSD.integer),
            'total_wins': (FOOTBALL.totalWins, XSD.integer),
            'total_draws': (FOOTBALL.totalDraws, XSD.integer),
            'total_losses': (FOOTBALL.totalLosses, XSD.integer),
            'total_goals_scored': (FOOTBALL.totalGoalsScored, XSD.integer),
            'total_goals_conceded': (FOOTBALL.totalGoalsConceded, XSD.integer),
            'update_by': (DCTERMS.modifiedBy, XSD.string),
            'update_at': (DCTERMS.modified, XSD.dateTime),
        },
        'inverse_relations': {
        'home_fixtures': (FOOTBALL.hasHomeFixture, 'Fixture'),
        'away_fixtures': (FOOTBALL.hasAwayFixture, 'Fixture'),
        'players': (FOOTBALL.hasPlayer, 'Player'),
        'current_coach': (FOOTBALL.hasCoach, 'Coach'),
        'venue': (FOOTBALL.hasHomeVenue, 'Venue'),
        'standings': (FOOTBALL.hasStanding, 'Standing'),
        'statistics': (FOOTBALL.hasStatistics, 'TeamStatistics'),
        'squad': (FOOTBALL.hasSquadMember, 'TeamPlayer')
    }
    },
    'Season': {
        'rdf_class': FOOTBALL.Season,
        'properties': {
            'external_id': (FOOTBALL.externalId, XSD.integer),
            'league': (FOOTBALL.league, None, 'League'), # ForeignKey to League
            'year': (DCTERMS.temporal, XSD.gYear), # Using dcterms:temporal for year
            'start_date': (DCTERMS.startDate, XSD.date),
            'end_date': (DCTERMS.endDate, XSD.date),
            'is_current': (FOOTBALL.isCurrentSeason, XSD.boolean),
            'update_by': (DCTERMS.modifiedBy, XSD.string),
            'update_at': (DCTERMS.modified, XSD.dateTime),
        },
        'inverse_relations': {
        'fixtures': (FOOTBALL.hasFixture, 'Fixture'),
        'standings': (FOOTBALL.hasStanding, 'Standing'),
        'player_teams': (FOOTBALL.hasPlayerTeam, 'PlayerTeam')
    }
    },
    'FixtureStatus': {
        'rdf_class': FOOTBALL.FixtureStatus,
        'properties': {
            'short_code': (FOOTBALL.statusCode, XSD.string),
            'long_description': (RDFS.label, XSD.string), # Using rdfs:label for description
            'status_type': (FOOTBALL.statusType, XSD.string), # Using FOOTBALL namespace for status type, consider a standard vocabulary if exists
            'description': (DCTERMS.description, XSD.string),
        }
    },
    'Fixture': {
        'rdf_class': FOOTBALL.Fixture,
        'properties': {
            'external_id': (FOOTBALL.externalId, XSD.integer),
            'league': (FOOTBALL.league, None, 'League'), # ForeignKey to League
            'season': (FOOTBALL.season, None, 'Season'), # ForeignKey to Season
            'round': (FOOTBALL.round, XSD.string),
            'home_team': (FOOTBALL.homeTeam, None, 'Team'), # ForeignKey to Team (home)
            'away_team': (FOOTBALL.awayTeam, None, 'Team'), # ForeignKey to Team (away)
            'date': (SCHEMA.startDate, XSD.dateTime), # Using schema:startDate for fixture date
            'venue': (FOOTBALL.venue, None, 'Venue'), # ForeignKey to Venue
            'referee': (FOOTBALL.referee, XSD.string),
            'status': (FOOTBALL.status, None, 'FixtureStatus'), # ForeignKey to FixtureStatus
            'elapsed_time': (FOOTBALL.elapsedTime, XSD.integer),
            'timezone': (DCTERMS.temporalResolution, XSD.string), # Using dcterms:temporalResolution for timezone
            'home_score': (FOOTBALL.homeScore, XSD.integer),
            'away_score': (FOOTBALL.awayScore, XSD.integer),
            'is_finished': (FOOTBALL.isFinished, XSD.boolean),
            'update_by': (DCTERMS.modifiedBy, XSD.string),
            'update_at': (DCTERMS.modified, XSD.dateTime),
        },
        'inverse_relations': {
        'events': (FOOTBALL.hasEvent, 'FixtureEvent'),
        'statistics': (FOOTBALL.hasStatistic, 'FixtureStatistic'),
        'lineups': (FOOTBALL.hasLineup, 'FixtureLineup'),
        'player_statistics': (FOOTBALL.hasPlayerStatistic, 'FixturePlayerStatistic'),
        'scores': (FOOTBALL.hasScore, 'FixtureScore'),
        'odds': (FOOTBALL.hasOdds, 'Odds')
    }
    },
    'FixtureScore': {
        'rdf_class': FOOTBALL.FixtureScore,
        'properties': {
            'fixture': (FOOTBALL.fixture, None, 'Fixture'), # ForeignKey to Fixture
            'team': (FOOTBALL.team, None, 'Team'), # ForeignKey to Team
            'halftime': (FOOTBALL.halftimeScore, XSD.integer),
            'fulltime': (FOOTBALL.fulltimeScore, XSD.integer),
            'extratime': (FOOTBALL.extratimeScore, XSD.integer),
            'penalty': (FOOTBALL.penaltyScore, XSD.integer),
            'update_by': (DCTERMS.modifiedBy, XSD.string),
            'update_at': (DCTERMS.modified, XSD.dateTime),
        }
    },
    'FixtureEvent': {
        'rdf_class': FOOTBALL.FixtureEvent,
        'properties': {
            'fixture': (FOOTBALL.fixture, None, 'Fixture'), # ForeignKey to Fixture
            'time_elapsed': (FOOTBALL.eventTime, XSD.integer),
            'event_type': (FOOTBALL.eventType, XSD.string), # Using FOOTBALL namespace for event type, consider a standard vocabulary if exists
            'detail': (DCTERMS.description, XSD.string), # Using dcterms:description for event detail
            'player': (FOOTBALL.player, None, 'Player'), # ForeignKey to Player
            'assist': (FOOTBALL.assistPlayer, None, 'Player'), # ForeignKey to Player (assist)
            'team': (FOOTBALL.team, None, 'Team'), # ForeignKey to Team
            'comments': (RDFS.comment, XSD.string), # Using rdfs:comment for comments
            'update_by': (DCTERMS.modifiedBy, XSD.string),
            'update_at': (DCTERMS.modified, XSD.dateTime),
        }
    },
    'FixtureStatistic': {
        'rdf_class': FOOTBALL.FixtureStatistic,
        'properties': {
            'fixture': (FOOTBALL.fixture, None, 'Fixture'), # ForeignKey to Fixture
            'team': (FOOTBALL.team, None, 'Team'), # ForeignKey to Team
            'stat_type': (FOOTBALL.statisticType, XSD.string), # Using FOOTBALL namespace for statistic type, consider a standard vocabulary if exists
            'value': (FOOTBALL.statisticValue, XSD.decimal),
            'update_by': (DCTERMS.modifiedBy, XSD.string),
            'update_at': (DCTERMS.modified, XSD.dateTime),
        }
    },
    'FixtureLineup': {
        'rdf_class': FOOTBALL.FixtureLineup,
        'properties': {
            'fixture': (FOOTBALL.fixture, None, 'Fixture'), # ForeignKey to Fixture
            'team': (FOOTBALL.team, None, 'Team'), # ForeignKey to Team
            'formation': (FOOTBALL.formation, XSD.string),
            'player_primary_color': (FOOTBALL.playerPrimaryColor, XSD.string), # Assuming color is represented as string (e.g., hex code)
            'player_number_color': (FOOTBALL.playerNumberColor, XSD.string),
            'player_border_color': (FOOTBALL.playerBorderColor, XSD.string),
            'goalkeeper_primary_color': (FOOTBALL.goalkeeperPrimaryColor, XSD.string),
            'goalkeeper_number_color': (FOOTBALL.goalkeeperNumberColor, XSD.string),
            'goalkeeper_border_color': (FOOTBALL.goalkeeperBorderColor, XSD.string),
            'update_by': (DCTERMS.modifiedBy, XSD.string),
            'update_at': (DCTERMS.modified, XSD.dateTime),
        }
    },
    'FixtureLineupPlayer': {
        'rdf_class': FOOTBALL.LineupPlayer, # Renamed to LineupPlayer for clarity
        'properties': {
            'lineup': (FOOTBALL.lineup, None, 'FixtureLineup'), # ForeignKey to FixtureLineup
            'player': (FOOTBALL.player, None, 'Player'), # ForeignKey to Player
            'number': (FOOTBALL.playerNumber, XSD.integer),
            'position': (FOOTBALL.playerPosition, XSD.string), # Using FOOTBALL namespace for player position, consider a standard vocabulary if exists
            'grid': (FOOTBALL.playerPositionGrid, XSD.string),
            'is_substitute': (FOOTBALL.isSubstitute, XSD.boolean),
            'update_by': (DCTERMS.modifiedBy, XSD.string),
            'update_at': (DCTERMS.modified, XSD.dateTime),
        }
    },
    'FixtureCoach': {
        'rdf_class': FOOTBALL.FixtureCoach,
        'properties': {
            'fixture': (FOOTBALL.fixture, None, 'Fixture'), # ForeignKey to Fixture
            'team': (FOOTBALL.team, None, 'Team'), # ForeignKey to Team
            'coach': (FOOTBALL.coach, None, 'Coach'), # ForeignKey to Coach
            'update_by': (DCTERMS.modifiedBy, XSD.string),
            'update_at': (DCTERMS.modified, XSD.dateTime),
        }
    },
    'Player': {
        'rdf_class': FOOTBALL.Player,
        'properties': {
            'external_id': (FOOTBALL.externalId, XSD.integer),
            'name': (SCHEMA.name, XSD.string),
            'firstname': (SCHEMA.givenName, XSD.string),
            'lastname': (SCHEMA.familyName, XSD.string),
            'birth_date': (SCHEMA.birthDate, XSD.date),
            'nationality': (FOOTBALL.nationality, None, 'Country'), # ForeignKey to Country
            'height': (SCHEMA.height, XSD.integer), # Assuming height in cm
            'weight': (SCHEMA.weight, XSD.integer), # Assuming weight in kg
            'team': (FOOTBALL.currentTeam, None, 'Team'), # ForeignKey to Team
            'position': (FOOTBALL.playerPositionType, XSD.string), # Using FOOTBALL namespace for player position type, consider a standard vocabulary if exists
            'number': (FOOTBALL.playerNumber, XSD.integer),
            'injured': (FOOTBALL.isInjured, XSD.boolean),
            'photo_url': (SCHEMA.image, XSD.anyURI),
            'season_goals': (FOOTBALL.seasonGoals, XSD.integer),
            'season_assists': (FOOTBALL.seasonAssists, XSD.integer),
            'season_yellow_cards': (FOOTBALL.seasonYellowCards, XSD.integer),
            'season_red_cards': (FOOTBALL.seasonRedCards, XSD.integer),
            'total_appearances': (FOOTBALL.totalAppearances, XSD.integer),
            'update_by': (DCTERMS.modifiedBy, XSD.string),
            'update_at': (DCTERMS.modified, XSD.dateTime),
        },
        'inverse_relations': {
        'events': (FOOTBALL.hasEvent, 'FixtureEvent'),
        'statistics': (FOOTBALL.hasStatistic, 'PlayerStatistics'),
        'injuries': (FOOTBALL.hasInjury, 'PlayerInjury'),
        'transfers': (FOOTBALL.hasTransfer, 'PlayerTransfer'),
        'teams_history': (FOOTBALL.hasTeamHistory, 'PlayerTeam'),
        'lineup_appearances': (FOOTBALL.hasLineupAppearance, 'FixtureLineupPlayer'),
        'sidelines': (FOOTBALL.hasSideline, 'PlayerSideline')
    }
    },
    'FixturePlayerStatistic': {
        'rdf_class': FOOTBALL.FixturePlayerStatistic,
        'properties': {
            'fixture': (FOOTBALL.fixture, None, 'Fixture'), # ForeignKey to Fixture
            'player': (FOOTBALL.player, None, 'Player'), # ForeignKey to Player
            'team': (FOOTBALL.team, None, 'Team'), # ForeignKey to Team
            'minutes_played': (FOOTBALL.minutesPlayed, XSD.integer),
            'position': (FOOTBALL.playerPosition, XSD.string), # Using FOOTBALL namespace for player position, consider a standard vocabulary if exists
            'number': (FOOTBALL.playerNumber, XSD.integer),
            'rating': (FOOTBALL.ratingValue, XSD.decimal), # Changed to ratingValue to avoid confusion with RDF.type
            'is_captain': (FOOTBALL.isCaptain, XSD.boolean),
            'is_substitute': (FOOTBALL.isSubstitute, XSD.boolean),
            'shots_total': (FOOTBALL.shotsTotal, XSD.integer),
            'shots_on_target': (FOOTBALL.shotsOnTarget, XSD.integer),
            'goals_scored': (FOOTBALL.goalsScored, XSD.integer),
            'goals_conceded': (FOOTBALL.goalsConceded, XSD.integer),
            'assists': (FOOTBALL.assists, XSD.integer),
            'saves': (FOOTBALL.goalkeeperSaves, XSD.integer),
            'passes_total': (FOOTBALL.passesTotal, XSD.integer),
            'passes_key': (FOOTBALL.keyPasses, XSD.integer),
            'passes_accuracy': (FOOTBALL.passAccuracy, XSD.decimal),
            'tackles_total': (FOOTBALL.tacklesTotal, XSD.integer),
            'blocks': (FOOTBALL.blocks, XSD.integer),
            'interceptions': (FOOTBALL.interceptions, XSD.integer),
            'duels_total': (FOOTBALL.duelsTotal, XSD.integer),
            'duels_won': (FOOTBALL.duelsWon, XSD.integer),
            'dribbles_attempts': (FOOTBALL.dribblesAttempts, XSD.integer),
            'dribbles_success': (FOOTBALL.dribblesSuccess, XSD.integer),
            'dribbles_past': (FOOTBALL.dribblesPast, XSD.integer),
            'fouls_drawn': (FOOTBALL.foulsDrawn, XSD.integer),
            'fouls_committed': (FOOTBALL.foulsCommitted, XSD.integer),
            'yellow_cards': (FOOTBALL.yellowCards, XSD.integer),
            'red_cards': (FOOTBALL.redCards, XSD.integer),
            'penalties_won': (FOOTBALL.penaltiesWon, XSD.integer),
            'penalties_committed': (FOOTBALL.penaltiesCommitted, XSD.integer),
            'penalties_scored': (FOOTBALL.penaltiesScored, XSD.integer),
            'penalties_missed': (FOOTBALL.penaltiesMissed, XSD.integer),
            'penalties_saved': (FOOTBALL.penaltiesSaved, XSD.integer),
            'offsides': (FOOTBALL.offsides, XSD.integer),
            'update_by': (DCTERMS.modifiedBy, XSD.string),
            'update_at': (DCTERMS.modified, XSD.dateTime),
        }
    },
    'PlayerStatistics': { # Consider if this is redundant with FixturePlayerStatistic, or if it represents aggregated stats - Based on models.py, it seems redundant and might represent similar data. Consider merging or clarifying purpose.
        'rdf_class': FOOTBALL.PlayerAggregatedStatistic, # Renamed for distinction if needed
        'properties': {
            'player': (FOOTBALL.player, None, 'Player'), # ForeignKey to Player
            'fixture': (FOOTBALL.fixture, None, 'Fixture'), # ForeignKey to Fixture -  If this is aggregated, fixture might not be relevant. Review model purpose.
            'team': (FOOTBALL.team, None, 'Team'), # ForeignKey to Team
            'minutes_played': (FOOTBALL.minutesPlayed, XSD.integer),
            'goals': (FOOTBALL.goalsScored, XSD.integer), # Consistent property name
            'assists': (FOOTBALL.assists, XSD.integer), # Consistent property name
            'shots_total': (FOOTBALL.shotsTotal, XSD.integer),
            'shots_on_target': (FOOTBALL.shotsOnTarget, XSD.integer),
            'passes': (FOOTBALL.passesTotal, XSD.integer), # Consistent property name
            'key_passes': (FOOTBALL.keyPasses, XSD.integer),
            'pass_accuracy': (FOOTBALL.passAccuracy, XSD.decimal),
            'tackles': (FOOTBALL.tacklesTotal, XSD.integer), # Consistent property name
            'interceptions': (FOOTBALL.interceptions, XSD.integer),
            'duels_total': (FOOTBALL.duelsTotal, XSD.integer),
            'duels_won': (FOOTBALL.duelsWon, XSD.integer),
            'dribbles_success': (FOOTBALL.dribblesSuccess, XSD.integer),
            'fouls_committed': (FOOTBALL.foulsCommitted, XSD.integer),
            'fouls_drawn': (FOOTBALL.foulsDrawn, XSD.integer),
            'yellow_cards': (FOOTBALL.yellowCards, XSD.integer),
            'red_cards': (FOOTBALL.redCards, XSD.integer),
            'rating': (FOOTBALL.ratingValue, XSD.decimal), # Consistent property name
            'is_substitute': (FOOTBALL.isSubstitute, XSD.boolean),
            'update_by': (DCTERMS.modifiedBy, XSD.string),
            'update_at': (DCTERMS.modified, XSD.dateTime),
        }
    },
    'PlayerInjury': {
        'rdf_class': FOOTBALL.PlayerInjury,
        'properties': {
            'player': (FOOTBALL.player, None, 'Player'), # ForeignKey to Player
            'fixture': (FOOTBALL.fixture, None, 'Fixture'), # ForeignKey to Fixture - Injury might not always be fixture related. Review model purpose.
            'type': (FOOTBALL.injuryType, XSD.string), # Using FOOTBALL namespace for injury type, consider a standard vocabulary if exists
            'severity': (FOOTBALL.injurySeverity, XSD.string), # Using FOOTBALL namespace for injury severity, consider a standard vocabulary if exists
            'status': (FOOTBALL.injuryStatus, XSD.string), # Using FOOTBALL namespace for injury status, consider a standard vocabulary if exists
            'start_date': (DCTERMS.startDate, XSD.date),
            'end_date': (DCTERMS.endDate, XSD.date),
            'expected_return_date': (FOOTBALL.expectedReturnDate, XSD.date),
            'recovery_time': (FOOTBALL.recoveryTime, XSD.integer), # Time in days
            'update_by': (DCTERMS.modifiedBy, XSD.string),
            'update_at': (DCTERMS.modified, XSD.dateTime),
        }
    },
    'Coach': {
        'rdf_class': FOOTBALL.Coach,
        'properties': {
            'external_id': (FOOTBALL.externalId, XSD.integer),
            'name': (SCHEMA.name, XSD.string),
            'firstname': (SCHEMA.givenName, XSD.string),
            'lastname': (SCHEMA.familyName, XSD.string),
            'nationality': (FOOTBALL.nationality, None, 'Country'), # ForeignKey to Country
            'birth_date': (SCHEMA.birthDate, XSD.date),
            'team': (FOOTBALL.currentTeam, None, 'Team'), # ForeignKey to Team (current team managed)
            'photo_url': (SCHEMA.image, XSD.anyURI),
            'career_matches': (FOOTBALL.careerMatches, XSD.integer),
            'career_wins': (FOOTBALL.careerWins, XSD.integer),
            'career_draws': (FOOTBALL.careerDraws, XSD.integer),
            'career_losses': (FOOTBALL.careerLosses, XSD.integer),
            'update_by': (DCTERMS.modifiedBy, XSD.string),
            'update_at': (DCTERMS.modified, XSD.dateTime),
        },
        'inverse_relations': {
        'career_entries': (FOOTBALL.hasCareerEntry, 'CoachCareer'),
        'fixture_appearances': (FOOTBALL.hasFixtureAppearance, 'FixtureCoach')
    }
    },
    'CoachCareer': {
        'rdf_class': FOOTBALL.CoachCareer,
        'properties': {
            'coach': (FOOTBALL.coach, None, 'Coach'), # ForeignKey to Coach
            'team': (FOOTBALL.team, None, 'Team'), # ForeignKey to Team (historical team)
            'role': (FOOTBALL.coachRoleType, XSD.string), # Using FOOTBALL namespace for coach role type, consider a standard vocabulary if exists
            'start_date': (DCTERMS.startDate, XSD.date),
            'end_date': (DCTERMS.endDate, XSD.date),
            'matches': (FOOTBALL.careerMatchesCount, XSD.integer), # More specific property name
            'wins': (FOOTBALL.careerWinsCount, XSD.integer), # More specific property name
            'draws': (FOOTBALL.careerDrawsCount, XSD.integer), # More specific property name
            'losses': (FOOTBALL.careerLossesCount, XSD.integer), # More specific property name
            'update_by': (DCTERMS.modifiedBy, XSD.string),
            'update_at': (DCTERMS.modified, XSD.dateTime),
        }
    },
    'Bookmaker': {
        'rdf_class': FOOTBALL.Bookmaker,
        'properties': {
            'external_id': (FOOTBALL.externalId, XSD.integer),
            'name': (SCHEMA.name, XSD.string),
            'logo_url': (SCHEMA.logo, XSD.anyURI),
            'is_active': (FOOTBALL.isActive, XSD.boolean),
            'priority': (FOOTBALL.priorityOrder, XSD.integer),
            'update_by': (DCTERMS.modifiedBy, XSD.string),
            'update_at': (DCTERMS.modified, XSD.dateTime),
        },
        'inverse_relations': {
        'odds': (FOOTBALL.hasOdds, 'Odds')
    }
    },
    'OddsType': {
        'rdf_class': FOOTBALL.OddsType,
        'properties': {
            'external_id': (FOOTBALL.externalId, XSD.integer),
            'name': (SCHEMA.name, XSD.string),
            'key': (FOOTBALL.oddsKey, XSD.string),
            'description': (DCTERMS.description, XSD.string),
            'category': (FOOTBALL.oddsCategoryType, XSD.string), # Using FOOTBALL namespace for odds category type, consider a standard vocabulary if exists
            'display_order': (FOOTBALL.displayOrder, XSD.integer),
            'update_by': (DCTERMS.modifiedBy, XSD.string),
            'update_at': (DCTERMS.modified, XSD.dateTime),
        }
    },
    'OddsValue': {
        'rdf_class': FOOTBALL.OddsValue,
        'properties': {
            'odds_type': (FOOTBALL.oddsType, None, 'OddsType'), # ForeignKey to OddsType
            'name': (SCHEMA.name, XSD.string),
            'key': (FOOTBALL.oddsValueKey, XSD.string),
            'display_order': (FOOTBALL.displayOrder, XSD.integer),
            'update_by': (DCTERMS.modifiedBy, XSD.string),
            'update_at': (DCTERMS.modified, XSD.dateTime),
        }
    },
    'Odds': {
        'rdf_class': FOOTBALL.Odds,
        'properties': {
            'fixture': (FOOTBALL.fixture, None, 'Fixture'), # ForeignKey to Fixture
            'bookmaker': (FOOTBALL.bookmaker, None, 'Bookmaker'), # ForeignKey to Bookmaker
            'odds_type': (FOOTBALL.oddsType, None, 'OddsType'), # ForeignKey to OddsType
            'odds_value': (FOOTBALL.oddsValue, None, 'OddsValue'), # ForeignKey to OddsValue
            'value': (FOOTBALL.oddsValueAmount, XSD.decimal), # More specific property name
            'is_main': (FOOTBALL.isMainOdds, XSD.boolean),
            'probability': (FOOTBALL.probabilityValue, XSD.decimal), # More specific property name
            'status': (FOOTBALL.oddsStatusType, XSD.string), # Using FOOTBALL namespace for odds status type, consider a standard vocabulary if exists
            'last_update': (DCTERMS.modified, XSD.dateTime), # Using dcterms:modified for last update
            'update_by': (DCTERMS.modifiedBy, XSD.string),
            'update_at': (DCTERMS.modified, XSD.dateTime),
        }
    },
    'OddsHistory': {
        'rdf_class': FOOTBALL.OddsHistory,
        'properties': {
            'odds': (FOOTBALL.odds, None, 'Odds'), # ForeignKey to Odds
            'old_value': (FOOTBALL.oldOddsValue, XSD.decimal),
            'new_value': (FOOTBALL.newOddsValue, XSD.decimal),
            'change_time': (DCTERMS.created, XSD.dateTime), # Using dcterms:created for change time
            'movement': (FOOTBALL.oddsMovementType, XSD.string), # Using FOOTBALL namespace for odds movement type, consider a standard vocabulary if exists
            'update_by': (DCTERMS.modifiedBy, XSD.string),
            'update_at': (DCTERMS.modified, XSD.dateTime),
        }
    },
    'Standing': {
        'rdf_class': FOOTBALL.Standing,
        'properties': {
            'season': (FOOTBALL.season, None, 'Season'), # ForeignKey to Season
            'team': (FOOTBALL.team, None, 'Team'), # ForeignKey to Team
            'rank': (FOOTBALL.rankingPosition, XSD.integer), # More specific property name
            'points': (FOOTBALL.pointsTotal, XSD.integer), # More specific property name
            'goals_diff': (FOOTBALL.goalDifference, XSD.integer),
            'form': (FOOTBALL.form, XSD.string),
            'status': (FOOTBALL.standingStatusType, XSD.string), # Using FOOTBALL namespace for standing status type, consider a standard vocabulary if exists
            'description': (DCTERMS.description, XSD.string),
            'played': (FOOTBALL.matchesPlayedCount, XSD.integer), # More specific property name
            'won': (FOOTBALL.matchesWonCount, XSD.integer), # More specific property name
            'drawn': (FOOTBALL.matchesDrawnCount, XSD.integer), # More specific property name
            'lost': (FOOTBALL.matchesLostCount, XSD.integer), # More specific property name
            'goals_for': (FOOTBALL.goalsForCount, XSD.integer), # More specific property name
            'goals_against': (FOOTBALL.goalsAgainstCount, XSD.integer), # More specific property name
            'home_played': (FOOTBALL.homeMatchesPlayedCount, XSD.integer), # More specific property name
            'home_won': (FOOTBALL.homeMatchesWonCount, XSD.integer), # More specific property name
            'home_drawn': (FOOTBALL.homeMatchesDrawnCount, XSD.integer), # More specific property name
            'home_lost': (FOOTBALL.homeMatchesLostCount, XSD.integer), # More specific property name
            'home_goals_for': (FOOTBALL.homeGoalsForCount, XSD.integer), # More specific property name
            'home_goals_against': (FOOTBALL.homeGoalsAgainstCount, XSD.integer), # More specific property name
            'away_played': (FOOTBALL.awayMatchesPlayedCount, XSD.integer), # More specific property name
            'away_won': (FOOTBALL.awayMatchesWonCount, XSD.integer), # More specific property name
            'away_drawn': (FOOTBALL.awayMatchesDrawnCount, XSD.integer), # More specific property name
            'away_lost': (FOOTBALL.awayMatchesLostCount, XSD.integer), # More specific property name
            'away_goals_for': (FOOTBALL.awayGoalsForCount, XSD.integer), # More specific property name
            'away_goals_against': (FOOTBALL.awayGoalsAgainstCount, XSD.integer), # More specific property name
            'update_by': (DCTERMS.modifiedBy, XSD.string),
            'update_at': (DCTERMS.modified, XSD.dateTime),
        }
    },
    'PlayerSideline': {
        'rdf_class': FOOTBALL.PlayerSideline,
        'properties': {
            'player': (FOOTBALL.player, None, 'Player'),
            'type': (FOOTBALL.sidelineType, XSD.string), # Type of sideline (injury, suspension etc.)
            'start_date': (DCTERMS.startDate, XSD.date),
            'end_date': (DCTERMS.endDate, XSD.date),
            'update_by': (DCTERMS.modifiedBy, XSD.string),
            'update_at': (DCTERMS.modified, XSD.dateTime),
        }
    },
    'PlayerTransfer': {
        'rdf_class': FOOTBALL.PlayerTransfer,
        'properties': {
            'player': (FOOTBALL.player, None, 'Player'),
            'date': (DCTERMS.date, XSD.date), # Date of transfer
            'type': (FOOTBALL.transferType, XSD.string), # Type of transfer (loan, permanent etc.)
            'team_in': (FOOTBALL.teamIn, None, 'Team'), # Team player is transferred to
            'team_out': (FOOTBALL.teamOut, None, 'Team'), # Team player is transferred from
            'update_by': (DCTERMS.modifiedBy, XSD.string),
            'update_at': (DCTERMS.modified, XSD.dateTime),
        }
    },
    'PlayerTeam': {
        'rdf_class': FOOTBALL.PlayerTeamHistory, # Class representing player's team history
        'properties': {
            'player': (FOOTBALL.player, None, 'Player'),
            'team': (FOOTBALL.team, None, 'Team'),
            'season': (FOOTBALL.season, None, 'Season'),
            'is_current': (FOOTBALL.isCurrentTeamForSeason, XSD.boolean), # Flag if this is the current team for that season
            'update_by': (DCTERMS.modifiedBy, XSD.string),
            'update_at': (DCTERMS.modified, XSD.dateTime),
        }
    },
     'TeamPlayer': { # Represents current squad. Consider if this is needed separately from PlayerTeam or can be inferred.
        'rdf_class': FOOTBALL.TeamSquadMember, # Class for team squad member
        'properties': {
            'team': (FOOTBALL.team, None, 'Team'),
            'player': (FOOTBALL.player, None, 'Player'),
            'position': (FOOTBALL.playerPositionType, XSD.string), # Player's position in the team
            'number': (FOOTBALL.playerNumber, XSD.integer),
            'is_active': (FOOTBALL.isActiveSquadMember, XSD.boolean), # If player is active in the squad
            'update_by': (DCTERMS.modifiedBy, XSD.string),
            'update_at': (DCTERMS.modified, XSD.dateTime),
        }
    },
    'TeamStatistics': { # Team statistics for a season.
        'rdf_class': FOOTBALL.TeamSeasonStatistics, # Class for team season statistics
        'properties': {
            'team': (FOOTBALL.team, None, 'Team'),
            'league': (FOOTBALL.league, None, 'League'),
            'season': (FOOTBALL.season, None, 'Season'),
            'form': (FOOTBALL.form, XSD.string),
            'matches_played_home': (FOOTBALL.homeMatchesPlayedCount, XSD.integer),
            'matches_played_away': (FOOTBALL.awayMatchesPlayedCount, XSD.integer),
            'matches_played_total': (FOOTBALL.totalMatchesPlayedCount, XSD.integer),
            'wins_home': (FOOTBALL.homeWinsCount, XSD.integer),
            'wins_away': (FOOTBALL.awayWinsCount, XSD.integer),
            'wins_total': (FOOTBALL.totalWinsCount, XSD.integer),
            'draws_home': (FOOTBALL.homeDrawsCount, XSD.integer),
            'draws_away': (FOOTBALL.awayDrawsCount, XSD.integer),
            'draws_total': (FOOTBALL.totalDrawsCount, XSD.integer),
            'losses_home': (FOOTBALL.homeLossesCount, XSD.integer),
            'losses_away': (FOOTBALL.awayLossesCount, XSD.integer),
            'losses_total': (FOOTBALL.totalLossesCount, XSD.integer),
            'goals_for_home': (FOOTBALL.homeGoalsForCount, XSD.integer),
            'goals_for_away': (FOOTBALL.awayGoalsForCount, XSD.integer),
            'goals_for_total': (FOOTBALL.totalGoalsForCount, XSD.integer),
            'goals_against_home': (FOOTBALL.homeGoalsAgainstCount, XSD.integer),
            'goals_against_away': (FOOTBALL.awayGoalsAgainstCount, XSD.integer),
            'goals_against_total': (FOOTBALL.totalGoalsAgainstCount, XSD.integer),
            'goals_for_average_home': (FOOTBALL.homeGoalsForAverage, XSD.decimal),
            'goals_for_average_away': (FOOTBALL.awayGoalsForAverage, XSD.decimal),
            'goals_for_average_total': (FOOTBALL.totalGoalsForAverage, XSD.decimal),
            'goals_against_average_home': (FOOTBALL.homeGoalsAgainstAverage, XSD.decimal),
            'goals_against_average_away': (FOOTBALL.awayGoalsAgainstAverage, XSD.decimal),
            'goals_against_average_total': (FOOTBALL.totalGoalsAgainstAverage, XSD.decimal),
            'streak_wins': (FOOTBALL.winningStreak, XSD.integer),
            'streak_draws': (FOOTBALL.drawingStreak, XSD.integer),
            'streak_losses': (FOOTBALL.losingStreak, XSD.integer),
            'biggest_win_home': (FOOTBALL.biggestHomeWin, XSD.string),
            'biggest_win_away': (FOOTBALL.biggestAwayWin, XSD.string),
            'biggest_loss_home': (FOOTBALL.biggestHomeLoss, XSD.string),
            'biggest_loss_away': (FOOTBALL.biggestAwayLoss, XSD.string),
            'clean_sheets_home': (FOOTBALL.homeCleanSheetsCount, XSD.integer),
            'clean_sheets_away': (FOOTBALL.awayCleanSheetsCount, XSD.integer),
            'clean_sheets_total': (FOOTBALL.totalCleanSheetsCount, XSD.integer),
            'failed_to_score_home': (FOOTBALL.homeFailedToScoreCount, XSD.integer),
            'failed_to_score_away': (FOOTBALL.awayFailedToScoreCount, XSD.integer),
            'failed_to_score_total': (FOOTBALL.totalFailedToScoreCount, XSD.integer),
            'penalties_scored': (FOOTBALL.penaltiesScoredCount, XSD.integer),
            'penalties_missed': (FOOTBALL.penaltiesMissedCount, XSD.integer),
            'penalties_total': (FOOTBALL.totalPenaltiesCount, XSD.integer),
            'update_by': (DCTERMS.modifiedBy, XSD.string),
            'update_at': (DCTERMS.modified, XSD.dateTime),
        }
    },
}

# CDC Configuration
CDC_CONFIG = {
    'batch_size': 1000,
    'version_control': True,
    'track_provenance': True,
    'validation_required': True,
    'error_handling': {
        'max_retries': 3,
        'retry_delay': 5,
        'error_log': True
    }
}

# Performance optimization settings
PERFORMANCE_CONFIG = {
    'batch_processing': True,
    'cache_enabled': True,
    'cache_size': 10000,
    'parallel_processing': True,
    'max_workers': 4
}