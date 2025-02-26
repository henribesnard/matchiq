import os
import json
import logging
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from football.models import Player, Team, Country, UpdateLog
import http.client
from urllib.parse import urlparse, urlencode
from typing import Dict, Any, List, Optional, Set, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Load players from API-Football with flexible parameters'

    def __init__(self):
        super().__init__()
        self.base_url = os.getenv('API_SPORTS_BASE_URL')
        self.api_key = os.getenv('API_SPORTS_KEY')
        
        if not self.base_url or not self.api_key:
            raise ValueError("API_SPORTS_BASE_URL and API_SPORTS_KEY environment variables are required")
        
        parsed_url = urlparse(self.base_url)
        self.host = parsed_url.netloc
        
        # Define API position to internal position mapping
        self.POSITION_MAPPING = {
            'Goalkeeper': 'GK',
            'Defender': 'DF',
            'Midfielder': 'MF',
            'Attacker': 'FW'
        }

    def add_arguments(self, parser):
        # Arguments for filtering
        parser.add_argument('--id', type=int, help='Specific player ID')
        parser.add_argument('--search', type=str, help='Search term for player name')
        parser.add_argument('--team', type=int, help='Team ID to filter players')
        parser.add_argument('--league', type=int, help='League ID to filter players')
        parser.add_argument('--season', type=int, help='Season to filter players')
        parser.add_argument('--page', type=int, default=1, help='Page number for pagination')
        parser.add_argument('--limit', type=int, default=100, help='Max number of players to process')
        
        # Output control
        parser.add_argument('--dry-run', action='store_true', help='Print API request without executing')
        parser.add_argument('--update-teams', action='store_true', help='Update player teams if they exist')

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING('Starting players import...'))
        
        try:
            # Build query parameters
            params = self._build_query_params(options)
            
            if options['dry_run']:
                self.stdout.write(f"API request parameters: {params}")
                query_string = urlencode(params)
                self.stdout.write(f"Request URL would be: GET {self.base_url}/players?{query_string}")
                return
            
            # Determine the appropriate endpoint based on filtering
            endpoint = "players"
            if options.get('id'):
                endpoint = "players"
            elif options.get('search'):
                endpoint = "players"
            elif options.get('team') and options.get('season'):
                endpoint = "players/squads"
                
            # Fetch player data
            players_data = self._fetch_players(endpoint, params)
            if not players_data:
                self.stdout.write(self.style.WARNING("No players data found with given parameters"))
                return
            
            self.stdout.write(f"Found {len(players_data)} players to process")
            
            # Process the players
            with transaction.atomic():
                stats = self._process_players(players_data, options.get('update_teams', False))
            
            # Display results
            self.stdout.write(self.style.SUCCESS(f"Successfully imported {stats['created']} players"))
            self.stdout.write(self.style.SUCCESS(f"Updated {stats['updated']} players"))
            if stats['failed'] > 0:
                self.stdout.write(self.style.WARNING(f"Failed to import {stats['failed']} players"))
            
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'Error during import: {str(e)}'))
            logger.error('Players import error', exc_info=True)
            raise

    def _build_query_params(self, options) -> Dict[str, str]:
        """Build query parameters for the API request."""
        params = {}
        
        if options.get('id'):
            params['id'] = str(options['id'])
        
        if options.get('search'):
            params['search'] = options['search']
            
        if options.get('team'):
            params['team'] = str(options['team'])
            
        if options.get('league'):
            params['league'] = str(options['league'])
            
        if options.get('season'):
            params['season'] = str(options['season'])
            
        if options.get('page'):
            params['page'] = str(options['page'])
        
        return params

    def _fetch_players(self, endpoint: str, params: Dict[str, str]) -> List[Dict]:
        """Fetch players data from the API."""
        conn = None
        try:
            conn = http.client.HTTPSConnection(self.host)
            headers = {
                'x-rapidapi-host': self.host,
                'x-rapidapi-key': self.api_key
            }
            
            query_string = urlencode(params)
            url = f"/{endpoint}?{query_string}"
            
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

    def _convert_height_to_cm(self, height_str: Optional[str]) -> Optional[int]:
        """Convert height string (e.g., '175 cm') to integer centimeters."""
        if not height_str:
            return None
            
        try:
            return int(height_str.split()[0])
        except (ValueError, IndexError):
            return None

    def _convert_weight_to_kg(self, weight_str: Optional[str]) -> Optional[int]:
        """Convert weight string (e.g., '68 kg') to integer kilograms."""
        if not weight_str:
            return None
            
        try:
            return int(weight_str.split()[0])
        except (ValueError, IndexError):
            return None

    def _get_or_create_country(self, country_name: str) -> Country:
        """Get or create a country by name."""
        if not country_name:
            return None
            
        country, created = Country.objects.get_or_create(
            name=country_name,
            defaults={
                'update_by': 'player_import',
                'update_at': timezone.now()
            }
        )
        
        if created:
            self.stdout.write(f"Created new country: {country.name}")
            
        return country

    def _get_or_create_team(self, team_data: Dict) -> Optional[Team]:
        """Get or create a team from team data."""
        if not team_data or not team_data.get('id'):
            return None
            
        try:
            team = Team.objects.get(external_id=team_data['id'])
            return team
        except Team.DoesNotExist:
            # In a real implementation, you might want to create the team
            # But for now, we'll return None to avoid cascading created objects
            self.stdout.write(f"Team with ID {team_data['id']} not found")
            return None

    def _process_players(self, players_data: List[Dict], update_teams: bool) -> Dict[str, int]:
        """Process players data and update database."""
        stats = {
            'total': len(players_data),
            'created': 0,
            'updated': 0,
            'failed': 0
        }
        
        for player_item in players_data:
            try:
                # Extract player data - handle different API response formats
                if 'player' in player_item:
                    player_data = player_item['player']
                else:
                    player_data = player_item
                
                if not player_data.get('id') or not player_data.get('name'):
                    self.stderr.write(f"Skipping player with missing data: {player_data}")
                    stats['failed'] += 1
                    continue
                
                # Get nationality country
                nationality = self._get_or_create_country(player_data.get('nationality'))
                
                # For birth country, if available
                birth_country = None
                if player_data.get('birth') and player_data['birth'].get('country'):
                    birth_country = self._get_or_create_country(player_data['birth']['country'])
                
                # Handle team assignment if available
                team = None
                if player_item.get('statistics') and len(player_item['statistics']) > 0:
                    team_data = player_item['statistics'][0].get('team')
                    if team_data:
                        team = self._get_or_create_team(team_data)
                
                # Build defaults for player
                defaults = {
                    'name': player_data['name'],
                    'firstname': player_data.get('firstname'),
                    'lastname': player_data.get('lastname'),
                    'nationality': nationality,
                    'position': self.POSITION_MAPPING.get(player_data.get('position'), 'FW'),
                    'number': player_data.get('number'),
                    'height': self._convert_height_to_cm(player_data.get('height')),
                    'weight': self._convert_weight_to_kg(player_data.get('weight')),
                    'photo_url': player_data.get('photo'),
                    'update_by': 'player_import',
                    'update_at': timezone.now()
                }
                
                # Handle birth date
                if player_data.get('birth') and player_data['birth'].get('date'):
                    try:
                        defaults['birth_date'] = datetime.strptime(
                            player_data['birth']['date'], '%Y-%m-%d'
                        ).date()
                    except ValueError:
                        pass
                
                # Only set team if available and valid
                if team:
                    defaults['team'] = team
                
                # Check if player exists
                try:
                    player = Player.objects.get(external_id=player_data['id'])
                    created = False
                    
                    # Update the player if needed
                    player_updated = False
                    
                    # Update data fields
                    for field, value in defaults.items():
                        if field == 'team' and not update_teams:
                            continue  # Skip team update unless explicitly requested
                            
                        if value is not None and getattr(player, field) != value:
                            setattr(player, field, value)
                            player_updated = True
                    
                    if player_updated:
                        player.save()
                        self._log_update('Player', player.id, False, player_data)
                        stats['updated'] += 1
                        self.stdout.write(f"Updated player: {player.name}")
                    
                except Player.DoesNotExist:
                    # Filter out None values for required fields
                    clean_defaults = {k: v for k, v in defaults.items() if v is not None or k not in ['team']}
                    
                    # Create the player
                    player = Player.objects.create(
                        external_id=player_data['id'],
                        **clean_defaults
                    )
                    
                    created = True
                    stats['created'] += 1
                    self._log_update('Player', player.id, True, player_data)
                    self.stdout.write(self.style.SUCCESS(f"Created player: {player.name}"))
                
            except Exception as e:
                stats['failed'] += 1
                player_name = player_data.get('name', 'Unknown')
                self.stderr.write(self.style.ERROR(f"Failed to process player {player_name}: {str(e)}"))
                logger.error(f"Player processing error: {str(e)}", exc_info=True)
        
        return stats

    def _log_update(self, table_name: str, record_id: int, created: bool, data: Dict) -> None:
        """Log an update to the UpdateLog table."""
        try:
            UpdateLog.objects.create(
                table_name=table_name,
                record_id=record_id,
                update_type='create' if created else 'update',
                update_by='player_import',
                new_data=data,
                description=f"{'Created' if created else 'Updated'} {table_name} {record_id}",
                update_at=timezone.now()
            )
        except Exception as e:
            logger.error(f"Failed to create update log: {str(e)}")