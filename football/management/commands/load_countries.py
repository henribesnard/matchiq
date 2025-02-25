import os
import json
import logging
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from football.models import Country, UpdateLog
import http.client
from urllib.parse import urlparse
from typing import Dict, Any

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Load countries from API-Football'

    def __init__(self):
        super().__init__()
        self.base_url = os.getenv('API_SPORTS_BASE_URL')
        self.api_key = os.getenv('API_SPORTS_KEY')
        
        if not self.base_url or not self.api_key:
            raise ValueError("API_SPORTS_BASE_URL and API_SPORTS_KEY environment variables are required")
        
        parsed_url = urlparse(self.base_url)
        self.host = parsed_url.netloc
        
    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING('Starting countries import...'))
        
        try:
            # Établir la connexion
            conn = http.client.HTTPSConnection(self.host)
            headers = {
                'x-rapidapi-host': self.host,
                'x-rapidapi-key': self.api_key
            }
            
            # Faire la requête
            conn.request("GET", "/countries", headers=headers)
            response = conn.getresponse()
            
            if response.status != 200:
                raise Exception(f'API returned status {response.status}: {response.read().decode("utf-8")}')
            
            # Lire et parser les données
            data = json.loads(response.read().decode('utf-8'))
            
            if 'response' not in data:
                raise Exception('Invalid API response format - missing response key')
            
            countries = data['response']
            self.stdout.write(f'Found {len(countries)} countries to process')
            
            # Traiter les pays
            with transaction.atomic():
                successful_imports = 0
                errors = []
                
                for country_data in countries:
                    try:
                        self._process_country(country_data)
                        successful_imports += 1
                    except Exception as e:
                        errors.append(f"{country_data.get('name', 'Unknown')}: {str(e)}")
                        logger.error(f'Country import error', exc_info=True)
            
            # Rapport final
            self.stdout.write(self.style.SUCCESS(f'Successfully imported {successful_imports} countries'))
            if errors:
                self.stdout.write(self.style.WARNING(f'Encountered {len(errors)} errors:'))
                for error in errors:
                    self.stdout.write(self.style.ERROR(f'- {error}'))
            
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'Error during import: {str(e)}'))
            logger.error('Countries import error', exc_info=True)
            raise
        finally:
            conn.close()

    def _process_country(self, country_data: Dict[str, Any]) -> None:
        """Process a single country entry."""
        name = country_data.get('name')
        if not name:
            raise ValueError('Country name is required')

        try:
            country, created = Country.objects.update_or_create(
                name=name,
                defaults={
                    'code': country_data.get('code'),
                    'flag_url': country_data.get('flag'),
                    'update_by': 'api_import',
                    'update_at': timezone.now()
                }
            )

            UpdateLog.objects.create(
                table_name='Country',
                record_id=country.id,
                update_type='create' if created else 'update',
                update_by='api_import',
                new_data=country_data,
                description=f"{'Created' if created else 'Updated'} country {name}",
                update_at=timezone.now()
            )

            self.stdout.write(
                self.style.SUCCESS(f'{"Created" if created else "Updated"} country: {name}')
            )

        except Exception as e:
            logger.error(f'Error processing country {name}', exc_info=True)
            raise