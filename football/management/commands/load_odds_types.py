import os
import json
import logging
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from football.models import OddsType, UpdateLog
import http.client
from urllib.parse import urlparse
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Load odds types from API-Football'

    def __init__(self):
        super().__init__()
        self.base_url = os.getenv('API_SPORTS_BASE_URL')
        self.api_key = os.getenv('API_SPORTS_KEY')
        
        if not self.base_url or not self.api_key:
            raise ValueError("API_SPORTS_BASE_URL and API_SPORTS_KEY environment variables are required")
        
        parsed_url = urlparse(self.base_url)
        self.host = parsed_url.netloc

    def handle(self, *args, **options):
        try:
            odds_types = self._fetch_odds_types()
            if not odds_types:
                self.stderr.write("No odds types found")
                return

            stats = self._process_odds_types(odds_types)
            self._display_summary(stats)

        except Exception as e:
            self.stderr.write(f"Error: {str(e)}")
            logger.error("Odds types import error", exc_info=True)
            raise

    def _fetch_odds_types(self) -> List[Dict]:
        """Récupère les types de paris depuis l'API."""
        conn = None
        try:
            conn = http.client.HTTPSConnection(self.host)
            headers = {
                'x-rapidapi-host': self.host,
                'x-rapidapi-key': self.api_key
            }
            
            url = "/odds/bets"
            self.stdout.write(f"Fetching odds types from: {url}")
            
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

    def _determine_category(self, name: str) -> str:
        """Détermine la catégorie du pari basé sur son nom."""
        name_lower = name.lower()
        
        if any(word in name_lower for word in ['score', 'goals', 'result', 'winner']):
            return 'main'
        elif any(word in name_lower for word in ['goal', 'score', 'netted']):
            return 'goals'
        elif any(word in name_lower for word in ['half', 'ht', 'ft']):
            return 'halves'
        else:
            return 'specials'

    def _generate_key(self, name: str) -> str:
        """Génère une clé unique à partir du nom."""
        return name.lower().replace(' ', '_').replace('/', '_').replace('-', '_')

    def _process_odds_types(self, odds_types: List[Dict]) -> Dict[str, int]:
        """Traite la liste des types de paris."""
        stats = {
            'total': len(odds_types),
            'created': 0,
            'updated': 0,
            'failed': 0
        }

        display_order = 0
        
        try:
            with transaction.atomic():
                for odds_type in odds_types:
                    try:
                        name = odds_type.get('name')
                        if not name:
                            continue

                        display_order += 10  # Incrément de 10 pour permettre des insertions futures
                        category = self._determine_category(name)
                        key = self._generate_key(name)

                        odds_type_obj, created = OddsType.objects.update_or_create(
                            external_id=odds_type['id'],
                            defaults={
                                'name': name,
                                'key': key,
                                'description': odds_type.get('description'),
                                'category': category,
                                'display_order': display_order,
                                'update_by': 'api_import',
                                'update_at': timezone.now()
                            }
                        )

                        UpdateLog.objects.create(
                            table_name='OddsType',
                            record_id=odds_type_obj.id,
                            update_type='create' if created else 'update',
                            update_by='api_import',
                            new_data=odds_type,
                            description=f"{'Created' if created else 'Updated'} odds type {name}"
                        )

                        if created:
                            stats['created'] += 1
                        else:
                            stats['updated'] += 1

                    except Exception as e:
                        stats['failed'] += 1
                        logger.error(f"Error processing odds type: {str(e)}")
                        continue

        except Exception as e:
            self.stderr.write(f"Transaction failed: {str(e)}")
            raise

        return stats

    def _display_summary(self, stats: Dict[str, int]) -> None:
        """Affiche un résumé des opérations."""
        self.stdout.write("\nImport Summary:")
        self.stdout.write(f"Total odds types: {stats['total']}")
        self.stdout.write(f"Created: {stats['created']}")
        self.stdout.write(f"Updated: {stats['updated']}")
        if stats['failed'] > 0:
            self.stdout.write(self.style.ERROR(f"Failed: {stats['failed']}"))