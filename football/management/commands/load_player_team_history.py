import os
import json
import logging
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from football.models import Player, Team, Season, League, Country, PlayerTeam, UpdateLog
import http.client
from urllib.parse import urlparse, urlencode
from typing import Dict, Any, List, Optional, Set, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Charger l\'historique des équipes des joueurs depuis API-Football'

    def __init__(self):
        super().__init__()
        self.base_url = os.getenv('API_SPORTS_BASE_URL')
        self.api_key = os.getenv('API_SPORTS_KEY')
        
        if not self.base_url or not self.api_key:
            raise ValueError("API_SPORTS_BASE_URL et API_SPORTS_KEY sont requis comme variables d'environnement")
        
        parsed_url = urlparse(self.base_url)
        self.host = parsed_url.netloc

    def add_arguments(self, parser):
        # Paramètre obligatoire
        parser.add_argument('--player', type=int, required=True, help='ID du joueur pour charger son historique d\'équipes')
        
        # Options supplémentaires
        parser.add_argument('--create-teams', action='store_true', help='Créer les équipes manquantes')
        parser.add_argument('--create-seasons', action='store_true', help='Créer les saisons manquantes')
        parser.add_argument('--update-current-team', action='store_true', 
                           help='Mettre à jour l\'équipe actuelle du joueur')
        parser.add_argument('--dry-run', action='store_true', help='Afficher la requête API sans l\'exécuter')

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING('Démarrage de l\'importation de l\'historique des équipes...'))
        
        try:
            # Vérifier que le joueur existe
            player_id = options['player']
            try:
                player = Player.objects.get(external_id=player_id)
                self.stdout.write(f"Joueur trouvé: {player.name} (ID: {player.id})")
            except Player.DoesNotExist:
                self.stderr.write(self.style.ERROR(f"Joueur avec ID externe {player_id} non trouvé dans la base de données"))
                self.stdout.write("Veuillez d'abord importer ce joueur avec load_players.py")
                return
            
            # Construire les paramètres de requête
            params = {'player': str(player_id)}
            
            if options['dry_run']:
                self.stdout.write(f"Paramètres de la requête API: {params}")
                query_string = urlencode(params)
                self.stdout.write(f"URL de la requête: GET {self.base_url}/players/teams?{query_string}")
                return
            
            # Récupérer l'historique des équipes
            teams_data = self._fetch_player_teams(params)
            if not teams_data:
                self.stdout.write(self.style.WARNING("Aucune donnée d'équipe trouvée pour ce joueur"))
                return
            
            self.stdout.write(f"Trouvé {len(teams_data)} équipe(s) dans l'historique du joueur")
            
            # Traiter l'historique des équipes
            with transaction.atomic():
                stats = self._process_player_teams(
                    player,
                    teams_data,
                    options.get('create_teams', False),
                    options.get('create_seasons', False),
                    options.get('update_current_team', False)
                )
            
            # Afficher les résultats
            self.stdout.write(self.style.SUCCESS(f"Historique importé avec succès: {stats['total_entries']} entrées créées"))
            if stats['teams_created'] > 0:
                self.stdout.write(self.style.SUCCESS(f"Équipes créées: {stats['teams_created']}"))
            if stats['seasons_created'] > 0:
                self.stdout.write(self.style.SUCCESS(f"Saisons créées: {stats['seasons_created']}"))
            if stats['failed'] > 0:
                self.stdout.write(self.style.WARNING(f"Échecs d'importation: {stats['failed']}"))
            if stats['current_team_updated']:
                self.stdout.write(self.style.SUCCESS(f"Équipe actuelle mise à jour: {player.team.name}"))
            
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'Erreur durant l\'importation: {str(e)}'))
            logger.error('Erreur d\'importation de l\'historique des équipes', exc_info=True)
            raise

    def _fetch_player_teams(self, params: Dict[str, str]) -> List[Dict]:
        """Récupérer l'historique des équipes d'un joueur depuis l'API."""
        conn = None
        try:
            conn = http.client.HTTPSConnection(self.host)
            headers = {
                'x-rapidapi-host': self.host,
                'x-rapidapi-key': self.api_key
            }
            
            query_string = urlencode(params)
            url = f"/players/teams?{query_string}"
            
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

    def _get_or_create_team(self, team_data: Dict, create_missing: bool) -> Tuple[Optional[Team], bool]:
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
                
            # Créer une équipe avec des données minimales
            from football.models import Country
            default_country, _ = Country.objects.get_or_create(
                name="Inconnu",
                defaults={
                    'update_by': 'team_history_import',
                    'update_at': timezone.now()
                }
            )
            
            team = Team.objects.create(
                external_id=team_data['id'],
                name=team_data.get('name', 'Équipe inconnue'),
                country=default_country,
                logo_url=team_data.get('logo'),
                update_by='team_history_import',
                update_at=timezone.now()
            )
            
            self._log_update('Team', team.id, True, team_data)
            self.stdout.write(f"Équipe créée: {team.name}")
            return team, True

    def _get_or_create_season(self, team: Team, year: int, create_missing: bool) -> Tuple[Optional[Season], bool]:
        """Récupérer ou créer une saison pour une équipe."""
        try:
            # Essayer de trouver une saison existante pour cette année
            season = Season.objects.filter(year=year).first()
            if season:
                return season, False
            
            if not create_missing:
                self.stdout.write(f"Saison {year} non trouvée")
                return None, False
            
            # Créer une ligue et une saison par défaut
            from football.models import League
            default_league, _ = League.objects.get_or_create(
                name=f"Ligue de {team.name}",
                defaults={
                    'external_id': 0,
                    'type': 'League',
                    'country': team.country,
                    'update_by': 'team_history_import',
                    'update_at': timezone.now()
                }
            )
            
            # Créer la saison avec des dates approximatives
            start_date = datetime(year, 7, 1).date()  # 1er juillet de l'année
            end_date = datetime(year + 1, 6, 30).date()  # 30 juin de l'année suivante
            
            season = Season.objects.create(
                league=default_league,
                year=year,
                start_date=start_date,
                end_date=end_date,
                is_current=(year == datetime.now().year),
                update_by='team_history_import',
                update_at=timezone.now()
            )
            
            self._log_update('Season', season.id, True, {'year': year, 'league_id': default_league.id})
            self.stdout.write(f"Saison créée: {year}")
            return season, True
            
        except Exception as e:
            self.stderr.write(f"Erreur lors de la récupération/création de la saison: {str(e)}")
            return None, False

    def _process_player_teams(self, player: Player, teams_data: List[Dict], 
                            create_teams: bool, create_seasons: bool,
                            update_current_team: bool) -> Dict[str, Any]:
        """Traiter l'historique des équipes d'un joueur."""
        stats = {
            'total_entries': 0,
            'teams_created': 0,
            'seasons_created': 0,
            'failed': 0,
            'current_team_updated': False
        }
        
        current_team = None
        current_year = datetime.now().year
        
        for team_entry in teams_data:
            try:
                team_data = team_entry.get('team')
                seasons_list = team_entry.get('seasons', [])
                
                if not team_data or not team_data.get('id') or not seasons_list:
                    stats['failed'] += 1
                    continue
                
                # Récupérer ou créer l'équipe
                team, team_created = self._get_or_create_team(team_data, create_teams)
                if team_created:
                    stats['teams_created'] += 1
                
                if not team:
                    stats['failed'] += 1
                    continue
                
                # Vérifier si c'est potentiellement l'équipe actuelle
                if update_current_team and current_year in seasons_list and not team.is_national:
                    current_team = team
                
                # Traiter chaque saison
                for year in seasons_list:
                    try:
                        # Récupérer ou créer la saison
                        season, season_created = self._get_or_create_season(team, year, create_seasons)
                        if season_created:
                            stats['seasons_created'] += 1
                        
                        if not season:
                            continue
                        
                        # Créer l'entrée d'historique
                        player_team, created = PlayerTeam.objects.get_or_create(
                            player=player,
                            team=team,
                            season=season,
                            defaults={
                                'update_by': 'team_history_import',
                                'update_at': timezone.now()
                            }
                        )
                        
                        if created:
                            stats['total_entries'] += 1
                            self._log_update('PlayerTeam', player_team.id, True, 
                                           {'player_id': player.id, 'team_id': team.id, 'season_id': season.id})
                            self.stdout.write(f"Entrée créée: {player.name} à {team.name} ({season.year})")
                        
                    except Exception as e:
                        self.stderr.write(f"Erreur lors du traitement d'une saison: {str(e)}")
                        continue
                
            except Exception as e:
                stats['failed'] += 1
                self.stderr.write(self.style.ERROR(f"Erreur lors du traitement d'une équipe: {str(e)}"))
                logger.error(f"Erreur de traitement d'équipe: {str(e)}", exc_info=True)
        
        # Mettre à jour l'équipe actuelle du joueur si demandé
        if update_current_team and current_team and player.team_id != current_team.id:
            player.team = current_team
            player.save(update_fields=['team', 'update_at'])
            stats['current_team_updated'] = True
        
        return stats

    def _log_update(self, table_name: str, record_id: int, created: bool, data: Dict) -> None:
        """Enregistrer une mise à jour dans la table UpdateLog."""
        try:
            UpdateLog.objects.create(
                table_name=table_name,
                record_id=record_id,
                update_type='create' if created else 'update',
                update_by='team_history_import',
                new_data=data,
                description=f"{'Créé' if created else 'Mis à jour'} {table_name} {record_id}",
                update_at=timezone.now()
            )
        except Exception as e:
            logger.error(f"Échec de création du log de mise à jour: {str(e)}")