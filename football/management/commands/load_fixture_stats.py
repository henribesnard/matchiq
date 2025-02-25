import os
import json
import logging
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from football.models import Fixture, FixtureStatistic
import http.client
from urllib.parse import urlparse
from typing import Dict, Any, List, Optional, Set

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Load fixture statistics from API-Football'

    def __init__(self):
        super().__init__()
        self.base_url = os.getenv('API_SPORTS_BASE_URL')
        self.api_key = os.getenv('API_SPORTS_KEY')
        
        if not self.base_url or not self.api_key:
            raise ValueError("API_SPORTS_BASE_URL and API_SPORTS_KEY environment variables are required")
        
        parsed_url = urlparse(self.base_url)
        self.host = parsed_url.netloc
        print(f"Initialized with host: {self.host}")

    def add_arguments(self, parser):
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument(
            '--all',
            action='store_true',
            help='Load stats for all fixtures without statistics'
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
                print(f"Found {len(fixtures)} fixtures without statistics")
            else:
                fixtures = [Fixture.objects.get(external_id=options['fixture_external_id'])]
                print(f"Processing fixture ID: {options['fixture_external_id']}")

            stats = self._process_fixtures(fixtures)
            self._display_summary(stats)

        except Exception as e:
            print(f"Error: {str(e)}")
            logger.error("Statistics import error", exc_info=True)
            raise

    def _get_fixtures_without_stats(self) -> List[Fixture]:
        """Récupère tous les fixtures sans statistiques."""
        # Get fixtures that aren't in FixtureStatistic
        existing_fixtures = Set(FixtureStatistic.objects.values_list('fixture', flat=True).distinct())
        return Fixture.objects.exclude(id__in=existing_fixtures)

    def _fetch_statistics(self, fixture_id: int) -> List[Dict]:
        """Récupère les statistiques depuis l'API."""
        conn = None
        try:
            conn = http.client.HTTPSConnection(self.host)
            headers = {
                'x-rapidapi-host': self.host,
                'x-rapidapi-key': self.api_key
            }
            
            url = f"/fixtures/statistics?fixture={fixture_id}"
            print(f"Fetching stats from: {url}")
            
            conn.request("GET", url, headers=headers)
            response = conn.getresponse()
            
            if response.status != 200:
                raise Exception(f'API returned status {response.status}')
            
            data = json.loads(response.read().decode('utf-8'))
            
            if data.get('errors'):
                print(f"API Errors: {json.dumps(data['errors'], indent=2)}")
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
            'stats_created': 0
        }

        for fixture in fixtures:
            try:
                with transaction.atomic():
                    created = self._process_single_fixture(fixture)
                    stats['processed'] += 1
                    stats['stats_created'] += created
            except Exception as e:
                stats['failed'] += 1
                print(f"Failed to process fixture {fixture.external_id}: {str(e)}")
                logger.error(f"Error processing fixture {fixture.external_id}", exc_info=True)

        return stats

    def _process_single_fixture(self, fixture: Fixture) -> int:
        """Traite un seul fixture. Retourne le nombre de stats créées."""
        stats_data = self._fetch_statistics(fixture.external_id)
        if not stats_data:
            return 0

        stats_created = 0
        for team_stats in stats_data:
            team_id = team_stats['team']['id']
            for stat in team_stats['statistics']:
                try:
                    value = self._convert_stat_value(stat['value'])
                    if value is not None:  # Ne créer que si la valeur n'est pas None
                        FixtureStatistic.objects.update_or_create(
                            fixture=fixture,
                            team=fixture.home_team if team_id == fixture.home_team.external_id else fixture.away_team,
                            stat_type=self._convert_stat_type(stat['type']),
                            defaults={
                                'value': value,
                                'update_by': 'api_import',
                                'update_at': timezone.now()
                            }
                        )
                        stats_created += 1
                except Exception as e:
                    print(f"Error processing stat {stat['type']} for team {team_id}: {str(e)}")

        return stats_created

    def _convert_stat_value(self, value: Any) -> Optional[float]:
        """Convertit une valeur de statistique en float."""
        if value is None:
            return None
        
        if isinstance(value, (int, float)):
            return float(value)
            
        # Gestion des pourcentages
        if isinstance(value, str) and value.endswith('%'):
            try:
                return float(value.rstrip('%'))
            except ValueError:
                return None
                
        return None

    def _convert_stat_type(self, api_type: str) -> str:
        """Convertit le type de stat de l'API en type interne."""
        conversions = {
            'Shots on Goal': 'shots_on_goal',
            'Shots off Goal': 'shots_off_goal',
            'Total Shots': 'total_shots',
            'Blocked Shots': 'blocked_shots',
            'Shots insidebox': 'shots_insidebox',
            'Shots outsidebox': 'shots_outsidebox',
            'Fouls': 'fouls',
            'Corner Kicks': 'corner_kicks',
            'Offsides': 'offsides',
            'Ball Possession': 'ball_possession',
            'Yellow Cards': 'yellow_cards',
            'Red Cards': 'red_cards',
            'Goalkeeper Saves': 'goalkeeper_saves',
            'Total passes': 'total_passes',
            'Passes accurate': 'passes_accurate',
            'Passes %': 'passes_percentage',
            'goals_prevented': 'goals_prevented'
        }
        return conversions[api_type]  # Lève une KeyError si le type n'existe pas

    def _display_summary(self, stats: Dict[str, int]) -> None:
        """Affiche un résumé des opérations."""
        print("\nImport Summary:")
        print(f"Total fixtures: {stats['total']}")
        print(f"Successfully processed: {stats['processed']}")
        print(f"Statistics created: {stats['stats_created']}")
        if stats['failed'] > 0:
            print(f"Failed: {stats['failed']}")

