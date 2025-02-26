import os
import json
import logging
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from football.models import Player, Team, Fixture, Country, League, Season, PlayerInjury, InjuryStatus, InjurySeverity, UpdateLog
import http.client
from urllib.parse import urlparse, urlencode
from typing import Dict, Any, List, Optional, Set, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Charger les blessures des joueurs depuis API-Football'

    def __init__(self):
        super().__init__()
        self.base_url = os.getenv('API_SPORTS_BASE_URL')
        self.api_key = os.getenv('API_SPORTS_KEY')
        
        if not self.base_url or not self.api_key:
            raise ValueError("API_SPORTS_BASE_URL et API_SPORTS_KEY sont requis comme variables d'environnement")
        
        parsed_url = urlparse(self.base_url)
        self.host = parsed_url.netloc
        
        # Mapping pour convertir les types de blessures en sévérité
        self.SEVERITY_MAPPING = {
            'Knock': InjurySeverity.MINOR,
            'Muscle Injury': InjurySeverity.MODERATE,
            'Calf Injury': InjurySeverity.MODERATE,
            'Hamstring': InjurySeverity.MODERATE,
            'Knee Injury': InjurySeverity.MAJOR,
            'Broken ankle': InjurySeverity.SEVERE,
            'Tendon Injury': InjurySeverity.MAJOR,
            'Illness': InjurySeverity.MINOR,
            'Suspended': InjurySeverity.OTHER
        }

    def add_arguments(self, parser):
        # Arguments de filtrage
        parser.add_argument('--league', type=int, help='ID de la ligue pour filtrer les blessures')
        parser.add_argument('--season', type=int, help='Saison pour filtrer les blessures')
        parser.add_argument('--team', type=int, help='ID de l\'équipe pour filtrer les blessures')
        parser.add_argument('--player', type=int, help='ID du joueur pour filtrer les blessures')
        parser.add_argument('--fixture', type=int, help='ID du match pour filtrer les blessures')
        parser.add_argument('--ids', type=str, help='IDs de matchs séparés par des tirets (ex: 686314-686315)')
        parser.add_argument('--date', type=str, help='Date pour filtrer les blessures (YYYY-MM-DD)')
        parser.add_argument('--timezone', type=str, default='UTC', help='Fuseau horaire pour les dates')
        
        # Options supplémentaires
        parser.add_argument('--dry-run', action='store_true', help='Afficher la requête API sans l\'exécuter')
        parser.add_argument('--create-missing', action='store_true', help='Créer les joueurs/équipes manquants automatiquement')

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING('Démarrage de l\'importation des blessures...'))
        
        try:
            # Vérifier si au moins un paramètre de filtrage est fourni
            filter_params = ['league', 'season', 'team', 'player', 'fixture', 'ids', 'date']
            if not any(options.get(param) for param in filter_params):
                self.stdout.write(self.style.ERROR('Erreur: Au moins un paramètre de filtrage est requis'))
                self.stdout.write('Paramètres disponibles: --league, --season, --team, --player, --fixture, --ids, --date')
                return
            
            # Construire les paramètres de requête
            params = self._build_query_params(options)
            
            if options['dry_run']:
                self.stdout.write(f"Paramètres de la requête API: {params}")
                query_string = urlencode(params)
                self.stdout.write(f"URL de la requête: GET {self.base_url}/injuries?{query_string}")
                return
            
            # Récupérer les données sur les blessures
            injuries_data = self._fetch_injuries(params)
            if not injuries_data:
                self.stdout.write(self.style.WARNING("Aucune donnée de blessure trouvée avec les paramètres fournis"))
                return
            
            self.stdout.write(f"Trouvé {len(injuries_data)} blessures à traiter")
            
            # Traiter les blessures
            with transaction.atomic():
                stats = self._process_injuries(injuries_data, options.get('create_missing', False))
            
            # Afficher les résultats
            self.stdout.write(self.style.SUCCESS(f"Blessures importées avec succès: {stats['created']} créées"))
            self.stdout.write(self.style.SUCCESS(f"Blessures mises à jour: {stats['updated']}"))
            if stats['players_created'] > 0:
                self.stdout.write(self.style.SUCCESS(f"Joueurs créés: {stats['players_created']}"))
            if stats['failed'] > 0:
                self.stdout.write(self.style.WARNING(f"Échecs d'importation: {stats['failed']}"))
            
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'Erreur durant l\'importation: {str(e)}'))
            logger.error('Erreur d\'importation des blessures', exc_info=True)
            raise

    def _build_query_params(self, options) -> Dict[str, str]:
        """Construire les paramètres de requête pour l'API."""
        params = {}
        
        # Ajouter les paramètres s'ils sont fournis
        if options.get('league'):
            params['league'] = str(options['league'])
        
        if options.get('season'):
            params['season'] = str(options['season'])
            
        if options.get('team'):
            params['team'] = str(options['team'])
            
        if options.get('player'):
            params['player'] = str(options['player'])
            
        if options.get('fixture'):
            params['fixture'] = str(options['fixture'])
            
        if options.get('ids'):
            params['ids'] = options['ids']
            
        if options.get('date'):
            params['date'] = options['date']
            
        if options.get('timezone'):
            params['timezone'] = options['timezone']
        
        return params

    def _fetch_injuries(self, params: Dict[str, str]) -> List[Dict]:
        """Récupérer les données de blessures depuis l'API."""
        conn = None
        try:
            conn = http.client.HTTPSConnection(self.host)
            headers = {
                'x-rapidapi-host': self.host,
                'x-rapidapi-key': self.api_key
            }
            
            query_string = urlencode(params)
            url = f"/injuries?{query_string}"
            
            self.stdout.write(f"Requête API: GET {url}")
            conn.request("GET", url, headers=headers)
            
            response = conn.getresponse()
            if response.status != 200:
                self.stderr.write(f"L'API a retourné le statut {response.status}: {response.read().decode('utf-8')}")
                return []
            
            data = json.loads(response.read().decode('utf-8'))
            
            # Vérifier les erreurs de l'API
            if data.get('errors'):
                self.stderr.write(f"Erreurs API: {json.dumps(data['errors'], indent=2)}")
                return []
            
            # Vérifier les limites d'utilisation
            if 'response' in data and 'remaining' in data and 'limit' in data:
                self.stdout.write(self.style.WARNING(
                    f"Limites API: {data['remaining']} requêtes restantes sur {data['limit']} par jour"
                ))
            
            return data.get('response', [])
            
        finally:
            if conn:
                conn.close()

    def _get_or_create_player(self, player_data: Dict, team: Team, create_missing: bool) -> Tuple[Player, bool]:
        """Récupérer ou créer un joueur."""
        if not player_data or not player_data.get('id'):
            return None, False
        
        try:
            player = Player.objects.get(external_id=player_data['id'])
            return player, False
        except Player.DoesNotExist:
            if not create_missing:
                self.stdout.write(f"Joueur avec ID {player_data['id']} non trouvé")
                return None, False
            
            # Créer le joueur si demandé
            player = Player.objects.create(
                external_id=player_data['id'],
                name=player_data.get('name', 'Inconnu'),
                team=team,
                position='FW',  # Position par défaut, à corriger plus tard
                photo_url=player_data.get('photo'),
                update_by='injury_import',
                update_at=timezone.now()
            )
            
            self._log_update('Player', player.id, True, player_data)
            self.stdout.write(f"Joueur créé: {player.name}")
            return player, True

    def _get_or_create_team(self, team_data: Dict, create_missing: bool) -> Tuple[Team, bool]:
        """Récupérer ou créer une équipe."""
        if not team_data or not team_data.get('id'):
            return None, False
        
        try:
            team = Team.objects.get(external_id=team_data['id'])
            return team, False
        except Team.DoesNotExist:
            if not create_missing:
                self.stdout.write(f"Équipe avec ID {team_data['id']} non trouvée")
                return None, False
            
            # Créer une équipe de base
            # Nous avons besoin d'un pays par défaut
            default_country, _ = Country.objects.get_or_create(
                name="Inconnu",
                defaults={
                    'update_by': 'injury_import',
                    'update_at': timezone.now()
                }
            )
            
            team = Team.objects.create(
                external_id=team_data['id'],
                name=team_data.get('name', 'Équipe inconnue'),
                country=default_country,
                logo_url=team_data.get('logo'),
                update_by='injury_import',
                update_at=timezone.now()
            )
            
            self._log_update('Team', team.id, True, team_data)
            self.stdout.write(f"Équipe créée: {team.name}")
            return team, True

    def _get_or_create_fixture(self, fixture_data: Dict, create_missing: bool) -> Tuple[Fixture, bool]:
        """Récupérer ou créer un match."""
        if not fixture_data or not fixture_data.get('id'):
            return None, False
        
        try:
            fixture = Fixture.objects.get(external_id=fixture_data['id'])
            return fixture, False
        except Fixture.DoesNotExist:
            if not create_missing:
                # Pour les blessures, on peut souvent se passer du match
                return None, False
            
            # Si on voulait créer le match, il faudrait plus d'informations
            # Pour simplifier, on retourne None
            return None, False

    def _determine_severity(self, reason: str) -> str:
        """Déterminer la sévérité de la blessure en fonction de la raison."""
        for key, value in self.SEVERITY_MAPPING.items():
            if key in reason:
                return value
        return InjurySeverity.MODERATE  # Valeur par défaut

    def _process_injuries(self, injuries_data: List[Dict], create_missing: bool) -> Dict[str, int]:
        """Traiter les données de blessures et mettre à jour la base de données."""
        stats = {
            'total': len(injuries_data),
            'created': 0,
            'updated': 0,
            'failed': 0,
            'players_created': 0,
            'teams_created': 0
        }
        
        for injury_data in injuries_data:
            try:
                player_data = injury_data.get('player', {})
                team_data = injury_data.get('team', {})
                fixture_data = injury_data.get('fixture', {})
                
                # Vérifier les données essentielles
                if not player_data.get('id') or not team_data.get('id'):
                    self.stderr.write(f"Données de blessure incomplètes: {injury_data}")
                    stats['failed'] += 1
                    continue
                
                # Récupérer ou créer l'équipe
                team, team_created = self._get_or_create_team(team_data, create_missing)
                if not team:
                    stats['failed'] += 1
                    continue
                
                if team_created:
                    stats['teams_created'] += 1
                
                # Récupérer ou créer le joueur
                player, player_created = self._get_or_create_player(player_data, team, create_missing)
                if not player:
                    stats['failed'] += 1
                    continue
                
                if player_created:
                    stats['players_created'] += 1
                
                # Récupérer le match (optionnel)
                fixture, _ = self._get_or_create_fixture(fixture_data, False)
                
                # Type et raison de la blessure
                injury_type = player_data.get('type', 'Unknown')
                injury_reason = player_data.get('reason', 'Unknown')
                
                # Déterminer la sévérité et le statut
                severity = self._determine_severity(injury_reason)
                status = InjuryStatus.INJURED
                
                # Créer ou mettre à jour la blessure
                # Utilisons la date du match comme date de début par défaut
                start_date = None
                if fixture_data.get('date'):
                    try:
                        start_date = datetime.fromisoformat(fixture_data['date'].replace('Z', '+00:00')).date()
                    except (ValueError, TypeError):
                        start_date = timezone.now().date()
                else:
                    start_date = timezone.now().date()
                
                # Essayer de trouver une blessure existante pour ce joueur/match
                try:
                    if fixture:
                        injury = PlayerInjury.objects.get(
                            player=player,
                            fixture=fixture,
                            type=injury_reason
                        )
                        created = False
                    else:
                        # Si pas de match, chercher par date
                        injury = PlayerInjury.objects.get(
                            player=player,
                            start_date=start_date,
                            type=injury_reason
                        )
                        created = False
                except PlayerInjury.DoesNotExist:
                    # Créer une nouvelle blessure
                    injury = PlayerInjury.objects.create(
                        player=player,
                        fixture=fixture,
                        type=injury_reason,
                        severity=severity,
                        status=status,
                        start_date=start_date,
                        update_by='injury_import',
                        update_at=timezone.now()
                    )
                    created = True
                
                # Mettre à jour le joueur pour indiquer qu'il est blessé
                if player.injured != True:
                    player.injured = True
                    player.save(update_fields=['injured', 'update_at'])
                
                # Enregistrer dans le log
                self._log_update(
                    'PlayerInjury',
                    injury.id,
                    created,
                    injury_data
                )
                
                if created:
                    stats['created'] += 1
                    self.stdout.write(f"Blessure créée: {player.name} - {injury_reason}")
                else:
                    stats['updated'] += 1
                    self.stdout.write(f"Blessure mise à jour: {player.name} - {injury_reason}")
                
            except Exception as e:
                stats['failed'] += 1
                self.stderr.write(self.style.ERROR(f"Échec du traitement de la blessure: {str(e)}"))
                logger.error(f"Erreur de traitement de blessure: {str(e)}", exc_info=True)
        
        return stats

    def _log_update(self, table_name: str, record_id: int, created: bool, data: Dict) -> None:
        """Enregistrer une mise à jour dans la table UpdateLog."""
        try:
            UpdateLog.objects.create(
                table_name=table_name,
                record_id=record_id,
                update_type='create' if created else 'update',
                update_by='injury_import',
                new_data=data,
                description=f"{'Créé' if created else 'Mis à jour'} {table_name} {record_id}",
                update_at=timezone.now()
            )
        except Exception as e:
            logger.error(f"Échec de création du log de mise à jour: {str(e)}")