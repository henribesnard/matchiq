import os
import json
import logging
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from football.models import (
    Fixture, FixtureEvent, Player, Team, Country,
    UpdateLog
)
import http.client
from urllib.parse import urlparse
from typing import Dict, Any, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Load fixture events from API-Football'

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
            help='Load events for all fixtures without events'
        )
        group.add_argument(
            '--fixture_external_id',
            type=int,
            help='Load events for specific fixture ID'
        )

    def handle(self, *args, **options):
        try:
            if options['all']:
                fixtures = self._get_fixtures_without_events()
                self.stdout.write(f"Found {len(fixtures)} fixtures without events")
            else:
                fixtures = [Fixture.objects.get(external_id=options['fixture_external_id'])]
                self.stdout.write(f"Processing fixture ID: {options['fixture_external_id']}")

            stats = self._process_fixtures(fixtures)
            self._display_summary(stats)

        except Exception as e:
            self.stderr.write(f"Error: {str(e)}")
            logger.error("Events import error", exc_info=True)
            raise

    def _get_fixtures_without_events(self) -> List[Fixture]:
        """Récupère tous les fixtures sans événements."""
        existing_fixtures = Set(FixtureEvent.objects.values_list('fixture', flat=True).distinct())
        return Fixture.objects.exclude(id__in=existing_fixtures)

    def _fetch_events(self, fixture_id: int) -> List[Dict]:
        """Récupère les événements depuis l'API."""
        conn = None
        try:
            conn = http.client.HTTPSConnection(self.host)
            headers = {
                'x-rapidapi-host': self.host,
                'x-rapidapi-key': self.api_key
            }
            
            url = f"/fixtures/events?fixture={fixture_id}"
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
            'events_created': 0,
            'players_created': 0
        }

        for fixture in fixtures:
            try:
                with transaction.atomic():
                    events_created, players_created = self._process_single_fixture(fixture)
                    stats['processed'] += 1
                    stats['events_created'] += events_created
                    stats['players_created'] += players_created
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
            player, created = Player.objects.get_or_create(
                external_id=player_data['id'],
                defaults={
                    'name': player_data['name'],
                    'team': team,
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
                    description=f"Created player {player.name}",
                    update_at=timezone.now()
                )

            return player, created
        except Exception as e:
            logger.error(f"Error creating player: {str(e)}")
            return None, False

    def _process_single_fixture(self, fixture: Fixture) -> Tuple[int, int]:
        """Traite un seul fixture. Retourne (events_created, players_created)."""
        events_data = self._fetch_events(fixture.external_id)
        if not events_data:
            return 0, 0

        events_created = 0
        players_created = 0

        for event_data in events_data:
            try:
                # Récupérer la team
                team_id = event_data['team']['id']
                team = fixture.home_team if team_id == fixture.home_team.external_id else fixture.away_team

                # Créer ou récupérer les joueurs
                player, player_created = self._get_or_create_player(event_data.get('player'), team)
                if player_created:
                    players_created += 1

                assist_player = None
                if event_data.get('assist'):
                    assist_player, assist_created = self._get_or_create_player(event_data['assist'], team)
                    if assist_created:
                        players_created += 1

                # Créer l'événement
                event = FixtureEvent.objects.create(
                    fixture=fixture,
                    time_elapsed=event_data['time']['elapsed'],
                    event_type=event_data['type'],
                    detail=event_data['detail'],
                    player=player,
                    assist=assist_player,
                    team=team,
                    comments=event_data.get('comments'),
                    update_by='api_import',
                    update_at=timezone.now()
                )

                UpdateLog.objects.create(
                    table_name='FixtureEvent',
                    record_id=event.id,
                    update_type='create',
                    update_by='api_import',
                    new_data=event_data,
                    description=f"Created event {event.event_type} for fixture {fixture.id}",
                    update_at=timezone.now()
                )

                events_created += 1

            except Exception as e:
                logger.error(f"Error processing event: {str(e)}")
                continue

        return events_created, players_created

    def _display_summary(self, stats: Dict[str, int]) -> None:
        """Affiche un résumé des opérations."""
        self.stdout.write("\nImport Summary:")
        self.stdout.write(f"Total fixtures: {stats['total']}")
        self.stdout.write(f"Successfully processed: {stats['processed']}")
        self.stdout.write(f"Events created: {stats['events_created']}")
        self.stdout.write(f"Players created: {stats['players_created']}")
        if stats['failed'] > 0:
            self.stdout.write(self.style.ERROR(f"Failed: {stats['failed']}"))