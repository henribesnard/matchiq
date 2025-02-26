import os
import json
import logging
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from football.models import (
    Fixture, FixtureLineup, FixtureLineupPlayer, 
    FixtureCoach, Player, Coach, Team, UpdateLog
)
import http.client
from urllib.parse import urlparse
from typing import Dict, Any, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Load fixture lineups from API-Football'

    def __init__(self):
        super().__init__()
        self.base_url = os.getenv('API_SPORTS_BASE_URL')
        self.api_key = os.getenv('API_SPORTS_KEY')
        
        if not self.base_url or not self.api_key:
            raise ValueError("API_SPORTS_BASE_URL and API_SPORTS_KEY environment variables are required")
        
        parsed_url = urlparse(self.base_url)
        self.host = parsed_url.netloc
        
        # Définir le mapping de positions API vers internes
        self.API_POSITION_MAPPING = {
            'G': 'GK',  # Gardien (Goalkeeper)
            'D': 'DF',  # Défenseur (Defender)
            'M': 'MF',  # Milieu (Midfielder)
            'F': 'FW'   # Attaquant (Forward)
        }

    def add_arguments(self, parser):
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument('--all', action='store_true', help='Load lineups for all fixtures without lineups')
        group.add_argument('--fixture_external_id', type=int, help='Load lineups for specific fixture ID')
        parser.add_argument('--force', action='store_true', help='Force update of existing lineups')

    def handle(self, *args, **options):
        try:
            if options['all']:
                fixtures = self._get_fixtures_without_lineups()
                self.stdout.write(f"Found {len(fixtures)} fixtures without lineups")
            else:
                # Récupérer le match
                fixture_id = options['fixture_external_id']
                try:
                    fixture = Fixture.objects.get(external_id=fixture_id)
                    fixtures = [fixture]
                    
                    # Si --force est spécifié, supprimer d'abord les compositions existantes
                    if options['force']:
                        self._clear_existing_lineups(fixture)
                        self.stdout.write(f"Cleared existing lineups for fixture ID: {fixture_id}")
                    
                    self.stdout.write(f"Processing fixture ID: {fixture_id}")
                except Fixture.DoesNotExist:
                    self.stderr.write(self.style.ERROR(f"Fixture with ID {fixture_id} does not exist"))
                    return

            stats = self._process_fixtures(fixtures, options['force'])
            self._display_summary(stats)

        except Exception as e:
            self.stderr.write(f"Error: {str(e)}")
            logger.error("Lineups import error", exc_info=True)
            raise
            
    def _clear_existing_lineups(self, fixture: Fixture) -> None:
        """Supprime les compositions existantes pour un match."""
        # Supprimer d'abord les joueurs de la composition
        lineup_ids = FixtureLineup.objects.filter(fixture=fixture).values_list('id', flat=True)
        FixtureLineupPlayer.objects.filter(lineup__in=lineup_ids).delete()
        
        # Supprimer les compositions
        FixtureLineup.objects.filter(fixture=fixture).delete()
        
        # Supprimer les entraîneurs
        FixtureCoach.objects.filter(fixture=fixture).delete()

    def _get_fixtures_without_lineups(self) -> List[Fixture]:
        """Récupère tous les fixtures sans lineups."""
        existing_lineups = FixtureLineup.objects.values_list('fixture', flat=True).distinct()
        return Fixture.objects.exclude(id__in=existing_lineups)

    def _fetch_lineups(self, fixture_id: int) -> List[Dict]:
        """Récupère les lineups depuis l'API."""
        conn = None
        try:
            conn = http.client.HTTPSConnection(self.host)
            headers = {
                'x-rapidapi-host': self.host,
                'x-rapidapi-key': self.api_key
            }
            
            url = f"/fixtures/lineups?fixture={fixture_id}"
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

    def _process_fixtures(self, fixtures: List[Fixture], force_update: bool) -> Dict[str, int]:
        """Traite une liste de fixtures."""
        stats = {
            'total': len(fixtures),
            'processed': 0,
            'failed': 0,
            'lineups_created': 0,
            'lineups_updated': 0,
            'players_created': 0,
            'coaches_created': 0
        }

        for fixture in fixtures:
            try:
                with transaction.atomic():
                    # Si force_update est True, supprimer d'abord les compositions existantes
                    if force_update:
                        self._clear_existing_lineups(fixture)
                    
                    result = self._process_single_fixture(fixture)
                    stats['processed'] += 1
                    stats['lineups_created'] += result['lineups_created']
                    stats['lineups_updated'] += result['lineups_updated']
                    stats['players_created'] += result['players_created']
                    stats['coaches_created'] += result['coaches_created']
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
            # Conversion de la position de l'API vers le format interne
            api_position = player_data.get('pos', 'F')  # Défaut à Forward si pas de position
            internal_position = self.API_POSITION_MAPPING.get(api_position, 'FW')  # Défaut à FW

            player, created = Player.objects.get_or_create(
                external_id=player_data['id'],
                defaults={
                    'name': player_data['name'],
                    'team': team,
                    'position': internal_position,
                    'number': player_data.get('number'),
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
                    description=f"Created player {player.name}"
                )
            else:
                # Mettre à jour les informations du joueur
                updated = False
                if player.team_id != team.id:
                    player.team = team
                    updated = True
                if player.number != player_data.get('number') and player_data.get('number') is not None:
                    player.number = player_data.get('number')
                    updated = True
                
                if updated:
                    player.update_by = 'api_import'
                    player.update_at = timezone.now()
                    player.save()

            return player, created
        except Exception as e:
            logger.error(f"Error with player: {str(e)}")
            return None, False

    def _get_or_create_coach(self, coach_data: Dict) -> Tuple[Coach, bool]:
        """Récupère ou crée un entraîneur."""
        if not coach_data or not coach_data.get('id'):
            return None, False

        try:
            coach, created = Coach.objects.get_or_create(
                external_id=coach_data['id'],
                defaults={
                    'name': coach_data['name'],
                    'photo_url': coach_data.get('photo'),
                    'update_by': 'api_import',
                    'update_at': timezone.now()
                }
            )

            if created:
                UpdateLog.objects.create(
                    table_name='Coach',
                    record_id=coach.id,
                    update_type='create',
                    update_by='api_import',
                    new_data=coach_data,
                    description=f"Created coach {coach.name}"
                )

            return coach, created
        except Exception as e:
            logger.error(f"Error with coach: {str(e)}")
            return None, False

    def _update_or_create_fixture_lineup(self, fixture: Fixture, team: Team, team_data: Dict) -> Tuple[FixtureLineup, bool]:
        """Met à jour ou crée une composition d'équipe."""
        try:
            colors = team_data.get('team', {}).get('colors', {})
            
            # Valeurs par défaut si les couleurs ne sont pas définies
            default_color = "ffffff"  # Blanc
            
            player_colors = colors.get('player', {})
            goalkeeper_colors = colors.get('goalkeeper', {})
            
            defaults = {
                'formation': team_data.get('formation', '4-4-2'),
                'player_primary_color': player_colors.get('primary', default_color),
                'player_number_color': player_colors.get('number', default_color),
                'player_border_color': player_colors.get('border', default_color),
                'goalkeeper_primary_color': goalkeeper_colors.get('primary', default_color),
                'goalkeeper_number_color': goalkeeper_colors.get('number', default_color),
                'goalkeeper_border_color': goalkeeper_colors.get('border', default_color),
                'update_by': 'api_import',
                'update_at': timezone.now()
            }
            
            lineup, created = FixtureLineup.objects.update_or_create(
                fixture=fixture,
                team=team,
                defaults=defaults
            )

            update_type = 'create' if created else 'update'
            description = f"{'Created' if created else 'Updated'} lineup for {team.name} in fixture {fixture.id}"
            
            UpdateLog.objects.create(
                table_name='FixtureLineup',
                record_id=lineup.id,
                update_type=update_type,
                update_by='api_import',
                new_data=team_data,
                description=description
            )

            return lineup, created
        except Exception as e:
            logger.error(f"Error with lineup: {str(e)}")
            raise

    def _update_or_create_lineup_player(self, lineup: FixtureLineup, player: Player, player_data: Dict, is_substitute: bool) -> bool:
        """Met à jour ou crée un joueur dans la composition."""
        try:
            # Conversion de la position API vers le format interne
            api_position = player_data.get('pos', 'F')  # Défaut à Forward si pas de position
            internal_position = self.API_POSITION_MAPPING.get(api_position, 'FW')  # Défaut à FW
            
            defaults = {
                'number': player_data.get('number', 0),
                'position': internal_position,
                'grid': None if is_substitute else player_data.get('grid'),
                'is_substitute': is_substitute,
                'update_by': 'api_import',
                'update_at': timezone.now()
            }
            
            lineup_player, created = FixtureLineupPlayer.objects.update_or_create(
                lineup=lineup,
                player=player,
                defaults=defaults
            )
            
            return True
        except Exception as e:
            logger.error(f"Error with lineup player: {str(e)}")
            return False

    def _update_or_create_fixture_coach(self, fixture: Fixture, team: Team, coach: Coach) -> bool:
        """Met à jour ou crée un entraîneur pour le match."""
        try:
            coach_fixture, created = FixtureCoach.objects.update_or_create(
                fixture=fixture,
                team=team,
                defaults={
                    'coach': coach,
                    'update_by': 'api_import',
                    'update_at': timezone.now()
                }
            )
            return True
        except Exception as e:
            logger.error(f"Error with fixture coach: {str(e)}")
            return False

    def _process_single_fixture(self, fixture: Fixture) -> Dict[str, int]:
        """Traite un seul fixture."""
        lineups_data = self._fetch_lineups(fixture.external_id)
        if not lineups_data:
            return {
                'lineups_created': 0,
                'lineups_updated': 0,
                'players_created': 0,
                'coaches_created': 0
            }

        result = {
            'lineups_created': 0,
            'lineups_updated': 0,
            'players_created': 0,
            'coaches_created': 0
        }

        for team_data in lineups_data:
            try:
                # Identifier l'équipe
                team_id = team_data.get('team', {}).get('id')
                if not team_id:
                    self.stdout.write(self.style.WARNING(f"Missing team ID in data, skipping"))
                    continue
                    
                # Trouver l'équipe dans notre base de données
                try:
                    if team_id == fixture.home_team.external_id:
                        team = fixture.home_team
                    elif team_id == fixture.away_team.external_id:
                        team = fixture.away_team
                    else:
                        self.stdout.write(self.style.WARNING(f"Team ID {team_id} does not match fixture teams, skipping"))
                        continue
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f"Error identifying team: {str(e)}"))
                    continue

                # Créer ou mettre à jour la composition
                lineup, created = self._update_or_create_fixture_lineup(fixture, team, team_data)
                if created:
                    result['lineups_created'] += 1
                else:
                    result['lineups_updated'] += 1
                
                # Nettoyer les joueurs existants dans cette composition
                FixtureLineupPlayer.objects.filter(lineup=lineup).delete()

                # Traiter les joueurs titulaires
                for player_item in team_data.get('startXI', []):
                    player_data = player_item.get('player', {})
                    if not player_data or not player_data.get('id'):
                        continue
                        
                    player, player_created = self._get_or_create_player(player_data, team)
                    if player_created:
                        result['players_created'] += 1
                    
                    if player:
                        self._update_or_create_lineup_player(lineup, player, player_data, False)

                # Traiter les remplaçants
                for player_item in team_data.get('substitutes', []):
                    player_data = player_item.get('player', {})
                    if not player_data or not player_data.get('id'):
                        continue
                        
                    player, player_created = self._get_or_create_player(player_data, team)
                    if player_created:
                        result['players_created'] += 1
                    
                    if player:
                        self._update_or_create_lineup_player(lineup, player, player_data, True)

                # Traiter l'entraîneur
                coach_data = team_data.get('coach', {})
                if coach_data and coach_data.get('id'):
                    coach, coach_created = self._get_or_create_coach(coach_data)
                    if coach_created:
                        result['coaches_created'] += 1
                    
                    if coach:
                        self._update_or_create_fixture_coach(fixture, team, coach)

            except Exception as e:
                self.stderr.write(f"Error processing team lineup: {str(e)}")
                logger.error(f"Team lineup error: {str(e)}", exc_info=True)

        return result

    def _display_summary(self, stats: Dict[str, int]) -> None:
        """Affiche un résumé des opérations."""
        self.stdout.write(self.style.SUCCESS("\nImport Summary:"))
        self.stdout.write(f"Total fixtures: {stats['total']}")
        self.stdout.write(f"Successfully processed: {stats['processed']}")
        self.stdout.write(f"Lineups created: {stats['lineups_created']}")
        self.stdout.write(f"Lineups updated: {stats['lineups_updated']}")
        self.stdout.write(f"Players created: {stats['players_created']}")
        self.stdout.write(f"Coaches created: {stats['coaches_created']}")
        if stats['failed'] > 0:
            self.stdout.write(self.style.ERROR(f"Failed: {stats['failed']}"))