import os
import json
import logging
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from football.models import (
    Fixture, FixtureLineup, FixtureLineupPlayer, 
    FixtureCoach, Player, Coach, Team, UpdateLog
)
import http.client
from urllib.parse import urlparse
from typing import Dict, Any, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Load fixture lineups from API-Football'

    def __init__(self):
        super().__init__()
        self.base_url = os.getenv('API_SPORTS_BASE_URL')
        self.api_key = os.getenv('API_SPORTS_KEY')
        
        if not self.base_url or not self.api_key:
            raise ValueError("API_SPORTS_BASE_URL and API_SPORTS_KEY environment variables are required")
        
        parsed_url = urlparse(self.base_url)
        self.host = parsed_url.netloc

    def add_arguments(self, parser):
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument('--all', action='store_true', help='Load lineups for all fixtures without lineups')
        group.add_argument('--fixture_external_id', type=int, help='Load lineups for specific fixture ID')

    def handle(self, *args, **options):
        try:
            if options['all']:
                fixtures = self._get_fixtures_without_lineups()
                self.stdout.write(f"Found {len(fixtures)} fixtures without lineups")
            else:
                fixtures = [Fixture.objects.get(external_id=options['fixture_external_id'])]
                self.stdout.write(f"Processing fixture ID: {options['fixture_external_id']}")

            stats = self._process_fixtures(fixtures)
            self._display_summary(stats)

        except Exception as e:
            self.stderr.write(f"Error: {str(e)}")
            logger.error("Lineups import error", exc_info=True)
            raise

    def _get_fixtures_without_lineups(self) -> List[Fixture]:
        """Récupère tous les fixtures sans lineups."""
        existing_lineups = FixtureLineup.objects.values_list('fixture', flat=True).distinct()
        return Fixture.objects.exclude(id__in=existing_lineups)

    def _fetch_lineups(self, fixture_id: int) -> List[Dict]:
        """Récupère les lineups depuis l'API."""
        conn = None
        try:
            conn = http.client.HTTPSConnection(self.host)
            headers = {
                'x-rapidapi-host': self.host,
                'x-rapidapi-key': self.api_key
            }
            
            url = f"/fixtures/lineups?fixture={fixture_id}"
            conn.request("GET", url, headers=headers)
            response = conn.getresponse()
            
            if response.status != 200:
                raise Exception(f'API returned status {response.status}')
            
            data = json.loads(response.read().decode('utf-8'))
            
            if data.get('errors'):
                self.stderr.write(f"API Errors: {json.dumps(data['errors'], indent=2)}")
                return []

            return data.get('response', [])
            
        finally:
            if conn:
                conn.close()

    def _process_fixtures(self, fixtures: List[Fixture]) -> Dict[str, int]:
        """Traite une liste de fixtures."""
        stats = {
            'total': len(fixtures),
            'processed': 0,
            'failed': 0,
            'lineups_created': 0,
            'players_created': 0,
            'coaches_created': 0
        }

        for fixture in fixtures:
            try:
                with transaction.atomic():
                    lineups, players, coaches = self._process_single_fixture(fixture)
                    stats['processed'] += 1
                    stats['lineups_created'] += lineups
                    stats['players_created'] += players
                    stats['coaches_created'] += coaches
            except Exception as e:
                stats['failed'] += 1
                self.stderr.write(f"Failed to process fixture {fixture.external_id}: {str(e)}")
                logger.error(f"Error processing fixture {fixture.external_id}", exc_info=True)

        return stats

    def _get_or_create_player(self, player_data: Dict, team: Team) -> Tuple[Player, bool]:
        """Récupère ou crée un joueur."""
        if not player_data or not player_data.get('id'):
            return None, False

        try:
            # Conversion de la position de l'API vers le format interne
            api_position = player_data['pos']
            internal_position = FixtureLineupPlayer.API_POSITION_MAPPING[api_position]

            player, created = Player.objects.get_or_create(
                external_id=player_data['id'],
                defaults={
                    'name': player_data['name'],
                    'team': team,
                    'position': internal_position,
                    'number': player_data.get('number'),
                    'update_by': 'api_import',
                    'update_at': timezone.now()
                }
            )

            if created:
                UpdateLog.objects.create(
                    table_name='Player',
                    record_id=player.id,
                    update_type='create',
                    update_by='api_import',
                    new_data=player_data,
                    description=f"Created player {player.name}"
                )

            return player, created
        except Exception as e:
            logger.error(f"Error creating player: {str(e)}")
            return None, False

    def _get_or_create_coach(self, coach_data: Dict) -> Tuple[Coach, bool]:
        """Récupère ou crée un entraîneur."""
        if not coach_data or not coach_data.get('id'):
            return None, False

        try:
            coach, created = Coach.objects.get_or_create(
                external_id=coach_data['id'],
                defaults={
                    'name': coach_data['name'],
                    'photo_url': coach_data.get('photo'),
                    'update_by': 'api_import',
                    'update_at': timezone.now()
                }
            )

            if created:
                UpdateLog.objects.create(
                    table_name='Coach',
                    record_id=coach.id,
                    update_type='create',
                    update_by='api_import',
                    new_data=coach_data,
                    description=f"Created coach {coach.name}"
                )

            return coach, created
        except Exception as e:
            logger.error(f"Error creating coach: {str(e)}")
            return None, False

    def _create_fixture_lineup(self, fixture: Fixture, team: Team, team_data: Dict) -> Optional[FixtureLineup]:
        """Crée un FixtureLineup."""
        try:
            colors = team_data['team']['colors']
            lineup = FixtureLineup.objects.create(
                fixture=fixture,
                team=team,
                formation=team_data['formation'],
                player_primary_color=colors['player']['primary'],
                player_number_color=colors['player']['number'],
                player_border_color=colors['player']['border'],
                goalkeeper_primary_color=colors['goalkeeper']['primary'],
                goalkeeper_number_color=colors['goalkeeper']['number'],
                goalkeeper_border_color=colors['goalkeeper']['border'],
                update_by='api_import',
                update_at=timezone.now()
            )

            UpdateLog.objects.create(
                table_name='FixtureLineup',
                record_id=lineup.id,
                update_type='create',
                update_by='api_import',
                new_data=team_data,
                description=f"Created lineup for {team.name} in fixture {fixture.id}"
            )

            return lineup
        except Exception as e:
            logger.error(f"Error creating lineup: {str(e)}")
            return None

    def _create_lineup_player(self, lineup: FixtureLineup, player: Player, player_data: Dict, is_substitute: bool) -> bool:
        """Crée un FixtureLineupPlayer."""
        try:
            # Conversion de la position API vers le format interne
            api_position = player_data['pos']
            internal_position = FixtureLineupPlayer.API_POSITION_MAPPING[api_position]

            FixtureLineupPlayer.objects.create(
                lineup=lineup,
                player=player,
                number=player_data['number'],
                position=internal_position,
                grid=None if is_substitute else player_data['grid'],
                is_substitute=is_substitute,
                update_by='api_import',
                update_at=timezone.now()
            )
            return True
        except Exception as e:
            logger.error(f"Error creating lineup player: {str(e)}")
            return False

    def _process_single_fixture(self, fixture: Fixture) -> Tuple[int, int, int]:
        """Traite un seul fixture."""
        lineups_data = self._fetch_lineups(fixture.external_id)
        if not lineups_data:
            return 0, 0, 0

        lineups_created = 0
        players_created = 0
        coaches_created = 0

        for team_data in lineups_data:
            try:
                team_id = team_data['team']['id']
                team = fixture.home_team if team_id == fixture.home_team.external_id else fixture.away_team

                lineup = self._create_fixture_lineup(fixture, team, team_data)
                if lineup:
                    lineups_created += 1

                    # Traiter les joueurs titulaires
                    for player_data in team_data['startXI']:
                        player, created = self._get_or_create_player(player_data['player'], team)
                        if created:
                            players_created += 1
                        if player:
                            self._create_lineup_player(lineup, player, player_data['player'], False)

                    # Traiter les remplaçants
                    for player_data in team_data['substitutes']:
                        player, created = self._get_or_create_player(player_data['player'], team)
                        if created:
                            players_created += 1
                        if player:
                            self._create_lineup_player(lineup, player, player_data['player'], True)

                    # Traiter l'entraîneur
                    coach, created = self._get_or_create_coach(team_data['coach'])
                    if created:
                        coaches_created += 1
                    if coach:
                        FixtureCoach.objects.create(
                            fixture=fixture,
                            team=team,
                            coach=coach,
                            update_by='api_import',
                            update_at=timezone.now()
                        )

            except Exception as e:
                logger.error(f"Error processing team lineup: {str(e)}")
                continue

        return lineups_created, players_created, coaches_created

    def _display_summary(self, stats: Dict[str, int]) -> None:
        """Affiche un résumé des opérations."""
        self.stdout.write("\nImport Summary:")
        self.stdout.write(f"Total fixtures: {stats['total']}")
        self.stdout.write(f"Successfully processed: {stats['processed']}")
        self.stdout.write(f"Lineups created: {stats['lineups_created']}")
        self.stdout.write(f"Players created: {stats['players_created']}")
        self.stdout.write(f"Coaches created: {stats['coaches_created']}")
        if stats['failed'] > 0:
            self.stdout.write(self.style.ERROR(f"Failed: {stats['failed']}"))