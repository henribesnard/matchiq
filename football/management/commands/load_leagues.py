import os
import json
import logging
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from football.models import League, Country, UpdateLog
import http.client
from urllib.parse import urlparse, urlencode
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Load leagues from API-Football with flexible parameters'

    def __init__(self):
        super().__init__()
        self.base_url = os.getenv('API_SPORTS_BASE_URL')
        self.api_key = os.getenv('API_SPORTS_KEY')
        
        if not self.base_url or not self.api_key:
            raise ValueError("API_SPORTS_BASE_URL and API_SPORTS_KEY environment variables are required")
        
        parsed_url = urlparse(self.base_url)
        self.host = parsed_url.netloc
        
    def add_arguments(self, parser):
        # Optional parameters - one of them is required
        parser.add_argument('--id', type=str, help='League ID(s) separated by commas')
        parser.add_argument('--name', type=str, help='League name')
        parser.add_argument('--country', type=str, help='Country name')
        parser.add_argument('--code', type=str, help='Country code (GB, FR, IT, etc.)')
        parser.add_argument('--season', type=str, help='Season year(s) separated by commas')
        parser.add_argument('--team', type=int, help='Team ID')
        parser.add_argument('--search', type=str, help='Search term for league name or country')
        parser.add_argument('--type', type=str, choices=['league', 'cup'], help='League type (league or cup)')
        parser.add_argument('--current', action='store_true', help='Only leagues with current seasons')
        parser.add_argument('--last', type=int, help='Get the last N leagues added to the API')
        
        # Output formatting
        parser.add_argument('--timezone', type=str, default='UTC', help='Timezone for data')
        parser.add_argument('--dry-run', action='store_true', help='Print API request without executing')

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING('Starting leagues import...'))
        
        try:
            # Check if at least one parameter is provided
            params_provided = any(options.get(param) for param in 
                                ['id', 'name', 'country', 'code', 'season', 
                                 'team', 'search', 'type', 'current', 'last'])
            
            if not params_provided:
                self.stdout.write(self.style.ERROR('Error: At least one search parameter is required'))
                self.stdout.write('Available parameters: --id, --name, --country, --code, --season, --team, --search, --type, --current, --last')
                return
            
            # Build query parameters
            params = self._build_query_params(options)
            
            if options['dry_run']:
                self.stdout.write(f"API request parameters: {params}")
                query_string = urlencode(params)
                self.stdout.write(f"Request URL would be: GET {self.base_url}/leagues?{query_string}")
                return
            
            # Fetch leagues data
            leagues_data = self._fetch_leagues(params)
            if not leagues_data:
                self.stdout.write(self.style.WARNING("No leagues data found with given parameters"))
                return
            
            self.stdout.write(f"Found {len(leagues_data)} leagues to process")
            
            # Process leagues
            with transaction.atomic():
                stats = self._process_leagues(leagues_data)
            
            # Display results
            self.stdout.write(self.style.SUCCESS(f"Successfully imported {stats['created']} leagues"))
            self.stdout.write(self.style.SUCCESS(f"Updated {stats['updated']} leagues"))
            if stats['failed'] > 0:
                self.stdout.write(self.style.WARNING(f"Failed to import {stats['failed']} leagues"))
            
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'Error during import: {str(e)}'))
            logger.error('Leagues import error', exc_info=True)
            raise

    def _build_query_params(self, options) -> Dict[str, str]:
        """Build query parameters for the API request."""
        params = {}
        
        # Add parameters if provided
        if options.get('id'):
            params['id'] = options['id']
        
        if options.get('name'):
            params['name'] = options['name']
            
        if options.get('country'):
            params['country'] = options['country']
            
        if options.get('code'):
            params['code'] = options['code']
            
        if options.get('season'):
            params['season'] = options['season']
            
        if options.get('team'):
            params['team'] = str(options['team'])
            
        if options.get('search'):
            params['search'] = options['search']
            
        if options.get('type'):
            params['type'] = options['type']
            
        if options.get('current'):
            params['current'] = 'true'
            
        if options.get('last'):
            params['last'] = str(options['last'])
        
        return params

    def _fetch_leagues(self, params: Dict[str, str]) -> List[Dict]:
        """Fetch leagues data from the API."""
        conn = None
        try:
            conn = http.client.HTTPSConnection(self.host)
            headers = {
                'x-rapidapi-host': self.host,
                'x-rapidapi-key': self.api_key
            }
            
            query_string = urlencode(params)
            url = f"/leagues?{query_string}"
            
            self.stdout.write(f"Making API request: GET {url}")
            conn.request("GET", url, headers=headers)
            
            response = conn.getresponse()
            if response.status != 200:
                self.stderr.write(f"API returned status {response.status}: {response.read().decode('utf-8')}")
                return []
            
            data = json.loads(response.read().decode('utf-8'))
            
            # Check for API errors
            if data.get('errors'):
                self.stderr.write(f"API Errors: {json.dumps(data['errors'], indent=2)}")
                return []
            
            # Check rate limits
            if 'response' in data and 'remaining' in data and 'limit' in data:
                self.stdout.write(self.style.WARNING(
                    f"API limits: {data['remaining']} requests remaining out of {data['limit']} per day"
                ))
            
            return data.get('response', [])
            
        finally:
            if conn:
                conn.close()

    def _process_leagues(self, leagues_data: List[Dict]) -> Dict[str, int]:
        """Process leagues data and update database."""
        stats = {
            'total': len(leagues_data),
            'created': 0,
            'updated': 0,
            'failed': 0
        }
        
        for league_data in leagues_data:
            try:
                league_info = league_data.get('league', {})
                country_info = league_data.get('country', {})
                seasons_info = league_data.get('seasons', [])
                
                if not league_info.get('id') or not league_info.get('name'):
                    self.stderr.write(f"Skipping league with missing data: {league_info}")
                    stats['failed'] += 1
                    continue
                
                # Get or create country
                country, _ = self._get_or_create_country(country_info)
                
                # Get or create league
                league, created = League.objects.update_or_create(
                    external_id=league_info['id'],
                    defaults={
                        'name': league_info['name'],
                        'type': league_info.get('type', 'League'),
                        'logo_url': league_info.get('logo'),
                        'country': country,
                        'update_by': 'api_import',
                        'update_at': timezone.now()
                    }
                )
                
                # Log the update
                self._log_update(
                    'League', 
                    league.id, 
                    created, 
                    {
                        'league': league_info, 
                        'country': country_info,
                        'seasons': seasons_info
                    }
                )
                
                if created:
                    stats['created'] += 1
                    self.stdout.write(self.style.SUCCESS(f"Created league: {league.name}"))
                else:
                    stats['updated'] += 1
                    self.stdout.write(f"Updated league: {league.name}")
                
                # Process seasons if needed
                # This could be extended to create Season objects
                
            except Exception as e:
                stats['failed'] += 1
                league_name = league_data.get('league', {}).get('name', 'Unknown')
                self.stderr.write(self.style.ERROR(f"Failed to process league {league_name}: {str(e)}"))
                logger.error(f"League processing error: {str(e)}", exc_info=True)
        
        return stats
    
    def _get_or_create_country(self, country_info: Dict) -> tuple:
        """Get or create a country from the data."""
        country_name = country_info.get('name')
        if not country_name:
            # Use a default country if none provided
            country_name = "Unknown"
        
        country, created = Country.objects.get_or_create(
            name=country_name,
            defaults={
                'code': country_info.get('code'),
                'flag_url': country_info.get('flag'),
                'update_by': 'api_import',
                'update_at': timezone.now()
            }
        )
        
        if created:
            self.stdout.write(f"Created new country: {country.name}")
            
            # Log the creation
            self._log_update(
                'Country',
                country.id,
                created,
                country_info
            )
        
        return country, created

    def _log_update(self, table_name: str, record_id: int, created: bool, data: Dict) -> None:
        """Log an update to the UpdateLog table."""
        try:
            UpdateLog.objects.create(
                table_name=table_name,
                record_id=record_id,
                update_type='create' if created else 'update',
                update_by='api_import',
                new_data=data,
                description=f"{'Created' if created else 'Updated'} {table_name} {record_id}",
                update_at=timezone.now()
            )
        except Exception as e:
            logger.error(f"Failed to create update log: {str(e)}")