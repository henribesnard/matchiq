import os
import json
import logging
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from football.models import (
    Fixture, Player, Team, FixturePlayerStatistic, UpdateLog
)
import http.client
from urllib.parse import urlparse
from typing import Dict, Any, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Load fixture player statistics from API-Football'

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
        group.add_argument(
            '--all',
            action='store_true',
            help='Load stats for all fixtures without player statistics'
        )
        group.add_argument(
            '--fixture_external_id',
            type=int,
            help='Load stats for specific fixture ID'
        )

    def handle(self, *args, **options):
        try:
            if options['all']:
                fixtures = self._get_fixtures_without_stats()
                self.stdout.write(f"Found {len(fixtures)} fixtures without player statistics")
            else:
                fixtures = [Fixture.objects.get(external_id=options['fixture_external_id'])]
                self.stdout.write(f"Processing fixture ID: {options['fixture_external_id']}")

            stats = self._process_fixtures(fixtures)
            self._display_summary(stats)

        except Exception as e:
            self.stderr.write(f"Error: {str(e)}")
            logger.error("Player statistics import error", exc_info=True)
            raise

    def _get_fixtures_without_stats(self) -> List[Fixture]:
        """Récupère tous les fixtures sans statistiques de joueurs."""
        existing_stats = FixturePlayerStatistic.objects.values_list('fixture', flat=True).distinct()
        return Fixture.objects.exclude(id__in=existing_stats)

    def _fetch_stats(self, fixture_id: int) -> List[Dict]:
        """Récupère les statistiques depuis l'API."""
        conn = None
        try:
            conn = http.client.HTTPSConnection(self.host)
            headers = {
                'x-rapidapi-host': self.host,
                'x-rapidapi-key': self.api_key
            }
            
            url = f"/fixtures/players?fixture={fixture_id}"
            
            # Log de la requête
            self.stdout.write("\n" + "="*80)
            self.stdout.write("API REQUEST:")
            self.stdout.write(f"GET {url}")
            
            conn.request("GET", url, headers=headers)
            response = conn.getresponse()
            data = json.loads(response.read().decode('utf-8'))
            
            # Log de la réponse
            self.stdout.write("\nAPI RESPONSE:")
            self.stdout.write(f"Status: {response.status}")
            
            if response.status != 200:
                raise Exception(f'API returned status {response.status}')

            if data.get('errors'):
                self.stderr.write(f"API Errors: {json.dumps(data['errors'], indent=2)}")
                return []

            return data.get('response', [])
            
        finally:
            if conn:
                conn.close()

    def _convert_position(self, api_position: str) -> str:
        """Convertit la position de l'API vers le format interne."""
        position_mapping = {
            'G': 'GK',
            'D': 'DF',
            'M': 'MF',
            'F': 'FW'
        }
        return position_mapping.get(api_position, 'FW')

    def _convert_percentage(self, value: Optional[str]) -> Optional[float]:
        """Convertit une chaîne de pourcentage en float."""
        if not value:
            return None
        try:
            return float(value.rstrip('%'))
        except (ValueError, AttributeError):
            return None

    def _get_or_create_player(self, player_info: Dict, team: Team, position: str) -> Tuple[Player, bool]:
        """Récupère un joueur existant ou en crée un nouveau."""
        try:
            player = Player.objects.get(external_id=player_info['id'])
            created = False
        except Player.DoesNotExist:
            self.stdout.write(f"Creating new player: {player_info['name']} for team {team.name}")
            player = Player.objects.create(
                external_id=player_info['id'],
                name=player_info['name'],
                team=team,
                position=position,
                photo_url=player_info.get('photo'),
                update_by='api_import',
                update_at=timezone.now()
            )
            created = True
            
            # Log de la création
            UpdateLog.objects.create(
                table_name='Player',
                record_id=player.id,
                update_type='create',
                update_by='api_import',
                new_data=player_info,
                description=f"Created player {player.name} for team {team.name}"
            )
        
        return player, created

    def _create_player_stats(self, fixture: Fixture, team: Team, player_data: Dict) -> Tuple[bool, bool]:
        """Crée ou met à jour les statistiques d'un joueur."""
        try:
            player_info = player_data['player']
            stats = player_data['statistics'][0]
            games = stats['games']
            
            position = self._convert_position(games.get('position', ''))
            player, is_new_player = self._get_or_create_player(player_info, team, position)

            stat_obj, created = FixturePlayerStatistic.objects.update_or_create(
                fixture=fixture,
                player=player,
                team=team,
                defaults={
                    'minutes_played': games.get('minutes', 0) or 0,
                    'position': position,
                    'number': games.get('number', 0) or 0,
                    'rating': float(games.get('rating', 0) or 0),
                    'is_captain': games.get('captain', False),
                    'is_substitute': games.get('substitute', False),
                    
                    # Stats offensives
                    'shots_total': stats['shots'].get('total', 0) or 0,
                    'shots_on_target': stats['shots'].get('on', 0) or 0,
                    'goals_scored': stats['goals'].get('total', 0) or 0,
                    'goals_conceded': stats['goals'].get('conceded', 0) or 0,
                    'assists': stats['goals'].get('assists', 0) or 0,
                    'saves': stats['goals'].get('saves', 0) or 0,
                    
                    # Passes
                    'passes_total': stats['passes'].get('total', 0) or 0,
                    'passes_key': stats['passes'].get('key', 0) or 0,
                    'passes_accuracy': self._convert_percentage(stats['passes'].get('accuracy')),
                    
                    # Défense
                    'tackles_total': stats['tackles'].get('total', 0) or 0,
                    'blocks': stats['tackles'].get('blocks', 0) or 0,
                    'interceptions': stats['tackles'].get('interceptions', 0) or 0,
                    
                    # Duels
                    'duels_total': stats['duels'].get('total', 0) or 0,
                    'duels_won': stats['duels'].get('won', 0) or 0,
                    
                    # Dribbles
                    'dribbles_attempts': stats['dribbles'].get('attempts', 0) or 0,
                    'dribbles_success': stats['dribbles'].get('success', 0) or 0,
                    'dribbles_past': stats['dribbles'].get('past', 0) or 0,
                    
                    # Fautes
                    'fouls_drawn': stats['fouls'].get('drawn', 0) or 0,
                    'fouls_committed': stats['fouls'].get('committed', 0) or 0,
                    
                    # Cartons
                    'yellow_cards': stats['cards'].get('yellow', 0) or 0,
                    'red_cards': stats['cards'].get('red', 0) or 0,
                    
                    # Pénaltys
                    'penalties_won': stats['penalty'].get('won', 0) or 0,
                    'penalties_committed': stats['penalty'].get('commited', 0) or 0,
                    'penalties_scored': stats['penalty'].get('scored', 0) or 0,
                    'penalties_missed': stats['penalty'].get('missed', 0) or 0,
                    'penalties_saved': stats['penalty'].get('saved', 0) or 0,
                    
                    # Hors-jeu
                    'offsides': stats['offsides'] or 0,
                    
                    'update_by': 'api_import',
                    'update_at': timezone.now()
                }
            )

            UpdateLog.objects.create(
                table_name='FixturePlayerStatistic',
                record_id=stat_obj.id,
                update_type='create' if created else 'update',
                update_by='api_import',
                new_data=player_data,
                description=f"{'Created' if created else 'Updated'} stats for {player.name}"
            )

            return True, is_new_player
            
        except Exception as e:
            logger.error(f"Error creating player stats: {str(e)}")
            return False, False

    def _process_fixtures(self, fixtures: List[Fixture]) -> Dict[str, int]:
        """Traite une liste de fixtures."""
        stats = {
            'total': len(fixtures),
            'processed': 0,
            'failed': 0,
            'stats_created': 0,
            'players_created': 0
        }

        for fixture in fixtures:
            try:
                with transaction.atomic():
                    result = self._process_single_fixture(fixture)
                    stats['processed'] += 1
                    stats['stats_created'] += result['stats_created']
                    stats['players_created'] += result['players_created']
            except Exception as e:
                stats['failed'] += 1
                self.stderr.write(f"Failed to process fixture {fixture.external_id}: {str(e)}")
                logger.error(f"Error processing fixture {fixture.external_id}", exc_info=True)

        return stats

    def _process_single_fixture(self, fixture: Fixture) -> Dict[str, int]:
        """Traite un seul fixture."""
        stats_data = self._fetch_stats(fixture.external_id)
        if not stats_data:
            return {'stats_created': 0, 'players_created': 0}

        result = {'stats_created': 0, 'players_created': 0}
        
        for team_data in stats_data:
            try:
                team = Team.objects.get(external_id=team_data['team']['id'])
                
                for player_data in team_data['players']:
                    success, is_new_player = self._create_player_stats(fixture, team, player_data)
                    if success:
                        result['stats_created'] += 1
                        if is_new_player:
                            result['players_created'] += 1

            except Exception as e:
                logger.error(f"Error processing team stats: {str(e)}")
                continue

        return result

    def _display_summary(self, stats: Dict[str, int]) -> None:
        """Affiche un résumé des opérations."""
        self.stdout.write("\nIMPORT SUMMARY:")
        self.stdout.write("="*50)
        self.stdout.write(f"Total fixtures: {stats['total']}")
        self.stdout.write(f"Successfully processed: {stats['processed']}")
        self.stdout.write(f"Statistics created/updated: {stats['stats_created']}")
        self.stdout.write(f"New players created: {stats['players_created']}")
        if stats['failed'] > 0:
            self.stdout.write(self.style.ERROR(f"Failed: {stats['failed']}"))
        self.stdout.write("="*50)