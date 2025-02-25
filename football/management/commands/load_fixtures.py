import os
import json
import logging
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from football.models import (
    League, Season, Team, Venue, Country, FixtureStatus, Fixture, 
    FixtureScore, UpdateLog
)
import http.client
from urllib.parse import urlparse, urlencode
from datetime import datetime, timedelta
import pytz
from typing import Dict, Any, Optional, List, Tuple

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Load fixtures from API-Football with flexible parameters'

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
        # Paramètres obligatoires
        parser.add_argument('--league', type=str, required=True, 
                           help='League ID(s) separated by commas, or "all" for all leagues')
        
        # Paramètres facultatifs
        parser.add_argument('--season', type=str, help='Season year(s) separated by commas')
        parser.add_argument('--last', type=int, help='Load last X fixtures')
        parser.add_argument('--next', type=int, help='Load next X fixtures')
        parser.add_argument('--date', type=str, help='Load fixtures for a specific date (YYYY-MM-DD)')
        parser.add_argument('--from', dest='from_date', type=str, help='Start date for fixtures (YYYY-MM-DD)')
        parser.add_argument('--to', dest='to_date', type=str, help='End date for fixtures (YYYY-MM-DD)')
        parser.add_argument('--team', type=str, help='Team ID(s) separated by commas')
        parser.add_argument('--status', type=str, help='Status code(s) separated by commas (e.g., NS,FT,PST)')
        parser.add_argument('--round', type=str, help='Specific round (e.g., "Regular Season - 1")')
        parser.add_argument('--live', action='store_true', help='Load fixtures currently in play')
        parser.add_argument('--timezone', type=str, default='UTC', help='Timezone for fixtures')
        parser.add_argument('--include-events', action='store_true', help='Include event data')
        parser.add_argument('--include-lineups', action='store_true', help='Include lineup data')
        parser.add_argument('--include-statistics', action='store_true', help='Include statistics data')
        parser.add_argument('--dry-run', action='store_true', help='Print API request without executing')

    def handle(self, *args, **options):
        try:
            # Construire les paramètres de requête
            params = self._build_query_params(options)
            
            if options['dry_run']:
                self.stdout.write(f"API request parameters: {params}")
                return
                
            # Récupérer les fixtures
            fixtures_data = self._fetch_fixtures(params)
            if not fixtures_data:
                self.stdout.write(self.style.WARNING("No fixtures data received"))
                return

            self.stdout.write(self.style.SUCCESS(f"Found {len(fixtures_data)} fixtures to process"))

            # Traiter les fixtures
            with transaction.atomic():
                stats = self._process_fixtures(fixtures_data)
                self.stdout.write(self.style.SUCCESS(f"Processing complete. Stats: {stats}"))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error: {str(e)}"))
            logger.error("Fixture import error", exc_info=True)
            raise

    def _build_query_params(self, options) -> Dict[str, str]:
        """Construit les paramètres de requête API en fonction des options fournies."""
        params = {'timezone': options['timezone']}
        
        # Traitement des leagues
        if options['league'] and options['league'].lower() != 'all':
            params['league'] = options['league'].replace(' ', '')
        
        # Traitement de season
        if options['season']:
            params['season'] = options['season'].replace(' ', '')
        
        # Options temporelles
        if options['last']:
            params['last'] = str(options['last'])
        
        if options['next']:
            params['next'] = str(options['next'])
        
        if options['date']:
            params['date'] = options['date']
        
        if options['from_date']:
            params['from'] = options['from_date']
        
        if options['to_date']:
            params['to'] = options['to_date']
        
        # Autres filtres
        if options['team']:
            params['team'] = options['team'].replace(' ', '')
        
        if options['status']:
            params['status'] = options['status'].lower().replace(' ', '')
        
        if options['round']:
            params['round'] = options['round']
        
        if options['live']:
            params['live'] = 'all'
        
        return params

    def _fetch_fixtures(self, params: Dict[str, str]) -> List[Dict[str, Any]]:
        """Récupère les fixtures depuis l'API."""
        conn = None
        try:
            conn = http.client.HTTPSConnection(self.host)
            headers = {
                'x-rapidapi-host': self.host,
                'x-rapidapi-key': self.api_key
            }
            
            url_path = f"/fixtures?{urlencode(params)}"
            self.stdout.write(f"Making request to: {url_path}")
            
            conn.request("GET", url_path, headers=headers)
            response = conn.getresponse()
            data = json.loads(response.read().decode('utf-8'))
            
            if data.get('errors') and data['errors']:
                self.stdout.write(self.style.ERROR("API Errors: " + json.dumps(data['errors'], indent=2)))
                return []

            # Vérifier les limites de l'API
            if 'response' in data and 'remaining' in data and 'limit' in data:
                self.stdout.write(self.style.WARNING(
                    f"API limits: {data['remaining']} requests remaining out of {data['limit']} per day"
                ))

            return data.get('response', [])
        finally:
            if conn:
                conn.close()

    def _get_status_type(self, short_code: str) -> str:
        """Détermine le type de statut en fonction du code court."""
        finished_codes = ['FT', 'AET', 'PEN']
        in_play_codes = ['1H', 'HT', '2H', 'ET', 'BT', 'P', 'SUSP', 'INT', 'LIVE']
        postponed_codes = ['PST']
        cancelled_codes = ['CANC', 'ABD', 'AWD', 'WO']
        
        if short_code in finished_codes:
            return 'FINISHED'
        elif short_code in in_play_codes:
            return 'IN_PLAY'
        elif short_code in postponed_codes:
            return 'POSTPONED'
        elif short_code in cancelled_codes:
            return 'CANCELLED'
        else:
            return 'SCHEDULED'

    def _process_fixtures(self, fixtures_data: List[Dict]) -> Dict[str, int]:
        stats = {'total': len(fixtures_data), 'created': 0, 'updated': 0, 'failed': 0}

        for fixture_data in fixtures_data:
            try:
                with transaction.atomic():
                    is_new = self._process_single_fixture(fixture_data)
                    stats['created' if is_new else 'updated'] += 1
            except Exception as e:
                stats['failed'] += 1
                self.stdout.write(self.style.ERROR(f"Failed to process fixture: {str(e)}"))
                logger.error("Fixture processing error", exc_info=True)

        return stats

    def _process_single_fixture(self, fixture_data: Dict) -> bool:
        """Traite un fixture. Retourne True si créé, False si mis à jour."""
        # Créer les entités nécessaires
        country = self._get_or_create_country(
            fixture_data['league']['country'],
            fixture_data['league'].get('flag')
        )
        
        league = self._get_or_create_league(fixture_data['league'], country)
        season = self._get_or_create_season(league, fixture_data['league']['season'])
        
        home_team = self._get_or_create_team(fixture_data['teams']['home'], country)
        away_team = self._get_or_create_team(fixture_data['teams']['away'], country)
        
        status = self._get_or_create_status(fixture_data['fixture']['status'])
        venue = self._get_or_create_venue(fixture_data['fixture'].get('venue', {}), country)

        # Créer ou mettre à jour le fixture
        fixture, created = Fixture.objects.update_or_create(
            external_id=fixture_data['fixture']['id'],
            defaults={
                'league': league,
                'season': season,
                'round': fixture_data['league'].get('round'),
                'home_team': home_team,
                'away_team': away_team,
                'date': datetime.fromtimestamp(fixture_data['fixture']['timestamp'], pytz.UTC),
                'venue': venue,
                'referee': fixture_data['fixture'].get('referee'),
                'status': status,
                'elapsed_time': fixture_data['fixture']['status'].get('elapsed'),
                'timezone': fixture_data['fixture'].get('timezone', 'UTC'),
                'home_score': fixture_data['goals'].get('home'),
                'away_score': fixture_data['goals'].get('away'),
                'is_finished': status.short_code in ['FT', 'AET', 'PEN'],
                'update_by': 'api_import',
                'update_at': timezone.now()
            }
        )

        # Créer ou mettre à jour les scores
        self._update_fixture_scores(fixture, fixture_data)

        # Logger la modification
        self._log_update('Fixture', fixture.id, created, fixture_data)

        return created

    def _get_or_create_country(self, country_name: str, flag_url: Optional[str] = None) -> Country:
        """Récupère ou crée un pays."""
        country, created = Country.objects.get_or_create(
            name=country_name,
            defaults={
                'flag_url': flag_url,
                'update_by': 'api_import',
                'update_at': timezone.now()
            }
        )
        if created:
            self.stdout.write(f"Created new country: {country.name}")
        return country

    def _get_or_create_league(self, league_data: Dict, country: Country) -> League:
        """Récupère ou crée une league."""
        league, created = League.objects.get_or_create(
            external_id=league_data['id'],
            defaults={
                'name': league_data['name'],
                'type': league_data.get('type', 'League'),
                'logo_url': league_data.get('logo'),
                'country': country,
                'update_by': 'api_import',
                'update_at': timezone.now()
            }
        )
        if created:
            self.stdout.write(f"Created new league: {league.name}")
        return league

    def _get_or_create_season(self, league: League, year: int) -> Season:
        """Récupère ou crée une saison."""
        # Pour simplifier, on utilise des dates par défaut pour la saison
        start_date = datetime(year, 7, 1).date()
        end_date = datetime(year + 1, 6, 30).date()
        
        season, created = Season.objects.get_or_create(
            league=league,
            year=year,
            defaults={
                'start_date': start_date,
                'end_date': end_date,
                'is_current': True,  # À gérer plus finement si nécessaire
                'update_by': 'api_import',
                'update_at': timezone.now()
            }
        )
        if created:
            self.stdout.write(f"Created new season: {league.name} {year}")
        return season

    def _get_or_create_team(self, team_data: Dict, country: Country) -> Team:
        """Récupère ou crée une équipe."""
        team, created = Team.objects.get_or_create(
            external_id=team_data['id'],
            defaults={
                'name': team_data['name'],
                'code': team_data.get('code'),
                'country': country,
                'logo_url': team_data.get('logo'),
                'update_by': 'api_import',
                'update_at': timezone.now()
            }
        )
        if created:
            self.stdout.write(f"Created new team: {team.name}")
        return team

    def _get_or_create_venue(self, venue_data: Dict, country: Country) -> Optional[Venue]:
        """Récupère ou crée un stade."""
        if not venue_data.get('id'):
            return None
            
        venue, created = Venue.objects.get_or_create(
            external_id=venue_data['id'],
            defaults={
                'name': venue_data['name'],
                'city': venue_data.get('city', ''),
                'country': country,
                'capacity': venue_data.get('capacity'),
                'image_url': venue_data.get('image'),
                'update_by': 'api_import',
                'update_at': timezone.now()
            }
        )
        if created:
            self.stdout.write(f"Created new venue: {venue.name}")
        return venue

    def _get_or_create_status(self, status_data: Dict) -> FixtureStatus:
        """Récupère ou crée un statut."""
        status_type = self._get_status_type(status_data['short'])
        
        status, created = FixtureStatus.objects.get_or_create(
            short_code=status_data['short'],
            defaults={
                'long_description': status_data['long'],
                'status_type': status_type,
            }
        )
        if created:
            self.stdout.write(f"Created new status: {status.short_code}")
        return status

    def _update_fixture_scores(self, fixture: Fixture, fixture_data: Dict) -> None:
        """Met à jour les scores du fixture."""
        for team_type in ['home', 'away']:
            team = fixture.home_team if team_type == 'home' else fixture.away_team
            
            FixtureScore.objects.update_or_create(
                fixture=fixture,
                team=team,
                defaults={
                    'halftime': fixture_data['score']['halftime'].get(team_type),
                    'fulltime': fixture_data['score']['fulltime'].get(team_type),
                    'extratime': fixture_data['score']['extratime'].get(team_type),
                    'penalty': fixture_data['score']['penalty'].get(team_type),
                    'update_by': 'api_import',
                    'update_at': timezone.now()
                }
            )

    def _log_update(self, table_name: str, record_id: int, created: bool, data: Dict) -> None:
        """Log une mise à jour dans UpdateLog."""
        UpdateLog.objects.create(
            table_name=table_name,
            record_id=record_id,
            update_type='create' if created else 'update',
            update_by='api_import',
            new_data=data,
            description=f"{'Created' if created else 'Updated'} {table_name} {record_id}",
            update_at=timezone.now()
        )