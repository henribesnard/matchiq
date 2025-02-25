import os
import json
import logging
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from football.models import (
    Fixture, Bookmaker, OddsType, OddsValue, Odds, UpdateLog
)
import http.client
from urllib.parse import urlparse
from typing import Dict, Any, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Load fixture odds from API-Football'

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
            help='Load odds for all fixtures without odds'
        )
        group.add_argument(
            '--fixture_external_id',
            type=int,
            help='Load odds for specific fixture ID'
        )

    def handle(self, *args, **options):
        try:
            if options['all']:
                fixtures = self._get_fixtures_without_odds()
                self.stdout.write(f"Found {len(fixtures)} fixtures without odds")
            else:
                fixtures = [Fixture.objects.get(external_id=options['fixture_external_id'])]
                self.stdout.write(f"Processing fixture ID: {options['fixture_external_id']}")

            stats = self._process_fixtures(fixtures)
            self._display_summary(stats)

        except Exception as e:
            self.stderr.write(f"Error: {str(e)}")
            logger.error("Odds import error", exc_info=True)
            raise

    def _get_fixtures_without_odds(self) -> List[Fixture]:
        """Récupère tous les fixtures sans cotes."""
        existing_odds = Odds.objects.values_list('fixture', flat=True).distinct()
        return Fixture.objects.exclude(id__in=existing_odds)

    def _fetch_odds(self, fixture_id: int) -> List[Dict]:
        """Récupère les cotes depuis l'API."""
        conn = None
        try:
            conn = http.client.HTTPSConnection(self.host)
            headers = {
                'x-rapidapi-host': self.host,
                'x-rapidapi-key': self.api_key
            }
            
            url = f"/odds?fixture={fixture_id}"
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

    def _get_or_create_odds_type(self, bet_data: Dict) -> Tuple[OddsType, bool]:
        """Récupère ou crée un type de cote."""
        # Déterminer la catégorie en fonction du nom
        category = self._determine_odds_category(bet_data['name'])
        
        # Générer une clé unique pour le type
        key = self._generate_odds_type_key(bet_data['name'])
        
        return OddsType.objects.get_or_create(
            external_id=bet_data['id'],
            defaults={
                'name': bet_data['name'],
                'key': key,
                'category': category,
                'update_by': 'api_import',
                'update_at': timezone.now()
            }
        )

    def _get_or_create_odds_value(self, odds_type: OddsType, value: str) -> Tuple[OddsValue, bool]:
        """Récupère ou crée une valeur de cote."""
        key = self._generate_odds_value_key(value)
        
        return OddsValue.objects.get_or_create(
            odds_type=odds_type,
            key=key,
            defaults={
                'name': value,
                'update_by': 'api_import',
                'update_at': timezone.now()
            }
        )

    def _determine_odds_category(self, name: str) -> str:
        """Détermine la catégorie d'une cote basée sur son nom."""
        name_lower = name.lower()
        
        if any(term in name_lower for term in ['winner', 'draw', 'win', 'double chance']):
            return 'main'
        elif any(term in name_lower for term in ['goals', 'score']):
            return 'goals'
        elif any(term in name_lower for term in ['half', 'ht', 'ft']):
            return 'halves'
        else:
            return 'specials'

    def _generate_odds_type_key(self, name: str) -> str:
        """Génère une clé unique pour un type de cote."""
        return name.lower().replace(' ', '_').replace('-', '_')

    def _generate_odds_value_key(self, value: str) -> str:
        """Génère une clé unique pour une valeur de cote."""
        return str(value).lower().replace(' ', '_').replace('-', '_').replace('/', '_')

    def _process_fixtures(self, fixtures: List[Fixture]) -> Dict[str, int]:
        """Traite une liste de fixtures."""
        stats = {
            'total': len(fixtures),
            'processed': 0,
            'failed': 0,
            'odds_created': 0
        }

        for fixture in fixtures:
            try:
                with transaction.atomic():
                    odds_created = self._process_single_fixture(fixture)
                    stats['processed'] += 1
                    stats['odds_created'] += odds_created
            except Exception as e:
                stats['failed'] += 1
                self.stderr.write(f"Failed to process fixture {fixture.external_id}: {str(e)}")
                logger.error(f"Error processing fixture {fixture.external_id}", exc_info=True)

        return stats

    def _process_single_fixture(self, fixture: Fixture) -> int:
        """Traite un seul fixture."""
        odds_data = self._fetch_odds(fixture.external_id)
        if not odds_data:
            return 0

        odds_created = 0
        for odds_response in odds_data:
            bookmakers_data = odds_response.get('bookmakers', [])
            
            for bookmaker_data in bookmakers_data:
                try:
                    bookmaker = Bookmaker.objects.get(external_id=bookmaker_data['id'])
                    odds_created += self._process_bookmaker_odds(
                        fixture, bookmaker, bookmaker_data['bets']
                    )
                except Bookmaker.DoesNotExist:
                    logger.warning(f"Bookmaker {bookmaker_data['id']} not found")
                    continue

        return odds_created

    def _process_bookmaker_odds(self, fixture: Fixture, bookmaker: Bookmaker, bets_data: List[Dict]) -> int:
        """Traite les cotes d'un bookmaker pour un fixture."""
        odds_created = 0
        
        for bet_data in bets_data:
            try:
                odds_type, _ = self._get_or_create_odds_type(bet_data)
                
                for value_data in bet_data['values']:
                    odds_value, _ = self._get_or_create_odds_value(
                        odds_type, value_data['value']
                    )
                    
                    # Création ou mise à jour des cotes
                    odds_obj, created = Odds.objects.update_or_create(
                        fixture=fixture,
                        bookmaker=bookmaker,
                        odds_type=odds_type,
                        odds_value=odds_value,
                        defaults={
                            'value': Decimal(str(value_data['odd'])),
                            'is_main': self._is_main_odd(odds_type),
                            'status': 'active',
                            'update_by': 'api_import',
                            'update_at': timezone.now()
                        }
                    )
                    
                    # Créer l'historique si la valeur a changé
                    if not created and odds_obj.value != Decimal(str(value_data['odd'])):
                        self._create_odds_history(odds_obj, value_data['odd'])
                    
                    odds_created += 1

            except Exception as e:
                logger.error(f"Error processing bet {bet_data.get('id')}: {str(e)}")
                continue

        return odds_created

    def _is_main_odd(self, odds_type: OddsType) -> bool:
        """Détermine si un type de cote est principal."""
        main_types = {
            'Match Winner',
            'Double Chance',
            'Both Teams Score',
            'Goals Over/Under'
        }
        return odds_type.name in main_types

    def _create_odds_history(self, odds: Odds, new_value: str) -> None:
        """Crée une entrée dans l'historique des cotes."""
        from football.models import OddsHistory
        
        old_value = odds.value
        new_decimal = Decimal(str(new_value))
        
        # Déterminer le mouvement
        if new_decimal > old_value:
            movement = 'up'
        elif new_decimal < old_value:
            movement = 'down'
        else:
            movement = 'stable'
        
        OddsHistory.objects.create(
            odds=odds,
            old_value=old_value,
            new_value=new_decimal,
            movement=movement,
            update_by='api_import',
            update_at=timezone.now()
        )

    def _display_summary(self, stats: Dict[str, int]) -> None:
        """Affiche un résumé des opérations."""
        self.stdout.write("\nImport Summary:")
        self.stdout.write(f"Total fixtures: {stats['total']}")
        self.stdout.write(f"Successfully processed: {stats['processed']}")
        self.stdout.write(f"Odds created/updated: {stats['odds_created']}")
        if stats['failed'] > 0:
            self.stdout.write(self.style.ERROR(f"Failed: {stats['failed']}"))