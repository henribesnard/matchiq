import os
import json
import logging
from django.core.management.base import BaseCommand
from django.db import transaction
from football.models import League
import http.client
from urllib.parse import urlparse, urlencode

class Command(BaseCommand):
    help = 'Load fixtures from API-Football'

    def __init__(self):
        super().__init__()
        self.base_url = os.getenv('API_SPORTS_BASE_URL')
        self.api_key = os.getenv('API_SPORTS_KEY')
        
        if not self.base_url or not self.api_key:
            raise ValueError("API_SPORTS_BASE_URL and API_SPORTS_KEY environment variables are required")
        
        parsed_url = urlparse(self.base_url)
        self.host = parsed_url.netloc
        print(f"\nInitialized with host: {self.host}")  # Debug log

    def add_arguments(self, parser):
        parser.add_argument('--league', type=int, required=True)
        parser.add_argument('--season', type=int, required=True)
        parser.add_argument('--timezone', type=str, default='UTC')

    def handle(self, *args, **options):
        league_id = options['league']
        season_year = options['season']
        print("\nStarting fixture import...")  # Debug log

        try:
            league = League.objects.get(external_id=league_id)
            print(f'Processing fixtures for {league.name} - Season {season_year}')

            # Construire l'URL
            params = {
                'league': str(league_id),
                'season': str(season_year),
                'timezone': options['timezone']
            }
            
            api_url = f"https://{self.host}/v3/fixtures?{urlencode(params)}"
            print("\n" + "="*80)
            print("DEBUG: Making API call to:")
            print(f"URL: {api_url}")
            print("="*80)

            # Faire l'appel
            conn = None
            try:
                conn = http.client.HTTPSConnection(self.host)
                headers = {
                    'x-rapidapi-host': self.host,
                    'x-rapidapi-key': self.api_key
                }
                print("\nSending request...")  # Debug log
                
                conn.request("GET", f"/v3/fixtures?{urlencode(params)}", headers=headers)
                print("Request sent, waiting for response...")  # Debug log
                
                response = conn.getresponse()
                print(f"Got response status: {response.status}")  # Debug log
                
                data = json.loads(response.read().decode('utf-8'))
                fixtures = data.get('response', [])
                
                if not fixtures:
                    print('No fixtures found')  # Debug log
                    print('Response data:', json.dumps(data, indent=2))  # Debug log
                    return

                print(f'Found {len(fixtures)} fixtures')  # Debug log
                
            finally:
                if conn:
                    conn.close()
                    print("Connection closed")  # Debug log
            
        except League.DoesNotExist:
            print(f'League with ID {league_id} not found in database')
        except Exception as e:
            print(f'Error during import: {str(e)}')
            raise