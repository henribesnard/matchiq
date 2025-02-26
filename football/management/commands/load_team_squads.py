import os
import json
import logging
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from football.models import Team, Player, TeamPlayer, PlayerPosition, Country, UpdateLog
import http.client
from urllib.parse import urlparse, urlencode
from typing import Dict, Any, List, Optional, Set, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Charger les effectifs des équipes depuis API-Football'

    def __init__(self):
        super().__init__()
        self.base_url = os.getenv('API_SPORTS_BASE_URL')
        self.api_key = os.getenv('API_SPORTS_KEY')
        
        if not self.base_url or not self.api_key:
            raise ValueError("API_SPORTS_BASE_URL et API_SPORTS_KEY sont requis comme variables d'environnement")
        
        parsed_url = urlparse(self.base_url)
        self.host = parsed_url.netloc
        
        # Mapping positions API vers modèle interne
        self.POSITION_MAPPING = {
            'Goalkeeper': PlayerPosition.GOALKEEPER,
            'Defender': PlayerPosition.DEFENDER,
            'Midfielder': PlayerPosition.MIDFIELDER,
            'Attacker': PlayerPosition.FORWARD
        }

    def add_arguments(self, parser):
        # Paramètres de filtrage (au moins un requis)
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument('--team', type=int, help='ID de l\'équipe pour charger son effectif')
        group.add_argument('--player', type=int, help='ID du joueur pour identifier son équipe actuelle')
        
        # Options supplémentaires
        parser.add_argument('--create-players', action='store_true', help='Créer les joueurs manquants')
        parser.add_argument('--update-existing', action='store_true', help='Mettre à jour les joueurs existants')
        parser.add_argument('--deactivate-missing', action='store_true', 
                            help='Désactiver les joueurs qui ne sont plus dans l\'effectif')
        parser.add_argument('--dry-run', action='store_true', help='Afficher la requête API sans l\'exécuter')

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING('Démarrage de l\'importation des effectifs...'))
        
        try:
            # Construire les paramètres de requête
            params = self._build_query_params(options)
            
            if options['dry_run']:
                self.stdout.write(f"Paramètres de la requête API: {params}")
                query_string = urlencode(params)
                self.stdout.write(f"URL de la requête: GET {self.base_url}/players/squads?{query_string}")
                return
            
            # Récupérer les données d'effectif
            squads_data = self._fetch_squads(params)
            if not squads_data:
                self.stdout.write(self.style.WARNING("Aucun effectif trouvé avec les paramètres fournis"))
                return
            
            self.stdout.write(f"Trouvé {len(squads_data)} équipe(s) avec effectif")
            
            # Traiter les effectifs
            with transaction.atomic():
                stats = self._process_squads(
                    squads_data,
                    options.get('create_players', False),
                    options.get('update_existing', False),
                    options.get('deactivate_missing', False)
                )
            
            # Afficher les résultats
            self.stdout.write(self.style.SUCCESS(f"Import terminé: {stats['total_teams']} équipe(s) traitée(s)"))
            self.stdout.write(self.style.SUCCESS(f"Joueurs dans l'effectif: {stats['total_players']}"))
            self.stdout.write(self.style.SUCCESS(f"Joueurs créés: {stats['created']}"))
            self.stdout.write(self.style.SUCCESS(f"Joueurs mis à jour: {stats['updated']}"))
            if stats['deactivated'] > 0:
                self.stdout.write(self.style.SUCCESS(f"Joueurs désactivés: {stats['deactivated']}"))
            if stats['failed'] > 0:
                self.stdout.write(self.style.WARNING(f"Échecs d'importation: {stats['failed']}"))
            
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'Erreur durant l\'importation: {str(e)}'))
            logger.error('Erreur d\'importation des effectifs', exc_info=True)
            raise

    def _build_query_params(self, options) -> Dict[str, str]:
        """Construire les paramètres de requête pour l'API."""
        params = {}
        
        if options.get('team'):
            params['team'] = str(options['team'])
        
        if options.get('player'):
            params['player'] = str(options['player'])
        
        return params

    def _fetch_squads(self, params: Dict[str, str]) -> List[Dict]:
        """Récupérer les données d'effectif depuis l'API."""
        conn = None
        try:
            conn = http.client.HTTPSConnection(self.host)
            headers = {
                'x-rapidapi-host': self.host,
                'x-rapidapi-key': self.api_key
            }
            
            query_string = urlencode(params)
            url = f"/players/squads?{query_string}"
            
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

    def _get_or_create_team(self, team_data: Dict) -> Optional[Team]:
        """Récupérer ou créer une équipe."""
        if not team_data or not team_data.get('id'):
            return None
            
        try:
            team = Team.objects.get(external_id=team_data['id'])
            return team
        except Team.DoesNotExist:
            self.stdout.write(f"Équipe avec ID {team_data['id']} non trouvée")
            
            # On crée l'équipe si elle n'existe pas (pour faciliter l'import)
            from football.models import Country
            default_country, _ = Country.objects.get_or_create(
                name="Inconnu",
                defaults={
                    'update_by': 'squads_import',
                    'update_at': timezone.now()
                }
            )
            
            team = Team.objects.create(
                external_id=team_data['id'],
                name=team_data.get('name', 'Équipe inconnue'),
                country=default_country,
                logo_url=team_data.get('logo'),
                update_by='squads_import',
                update_at=timezone.now()
            )
            
            self._log_update('Team', team.id, True, team_data)
            self.stdout.write(f"Équipe créée: {team.name}")
            return team

    def _get_or_create_player(self, player_data: Dict, team: Team, create_missing: bool, update_existing: bool) -> Tuple[Optional[Player], bool, bool]:
        """Récupérer ou créer un joueur et l'associer à l'équipe."""
        if not player_data or not player_data.get('id'):
            return None, False, False
        
        # Convertir la position
        position = self.POSITION_MAPPING.get(player_data.get('position', 'Attacker'), PlayerPosition.FORWARD)
        
        created = False
        updated = False
        
        try:
            player = Player.objects.get(external_id=player_data['id'])
            
            # Mettre à jour les données du joueur si nécessaire
            if update_existing:
                player_name = player_data.get('name', 'Joueur inconnu')
                
                # Vérifier si des mises à jour sont nécessaires
                update_fields = []
                
                if player.name != player_name:
                    player.name = player_name
                    update_fields.append('name')
                
                if player.position != position:
                    player.position = position
                    update_fields.append('position')
                
                if player.number != player_data.get('number'):
                    player.number = player_data.get('number')
                    update_fields.append('number')
                
                if player.photo_url != player_data.get('photo'):
                    player.photo_url = player_data.get('photo')
                    update_fields.append('photo_url')
                
                # Si l'équipe a changé et que ce n'est pas une sélection nationale
                if player.team_id != team.id and not team.is_national:
                    player.team = team
                    update_fields.append('team')
                
                # Si des mises à jour sont nécessaires
                if update_fields:
                    player.update_by = 'squads_import'
                    player.update_at = timezone.now()
                    update_fields.extend(['update_by', 'update_at'])
                    
                    player.save(update_fields=update_fields)
                    self._log_update('Player', player.id, False, player_data)
                    updated = True
            
            return player, created, updated
            
        except Player.DoesNotExist:
            if not create_missing:
                self.stdout.write(f"Joueur avec ID {player_data['id']} non trouvé")
                return None, False, False
            
            # Créer le joueur
            from football.models import Country
            default_country, _ = Country.objects.get_or_create(
                name="Inconnu",
                defaults={
                    'update_by': 'squads_import',
                    'update_at': timezone.now()
                }
            )
            
            player = Player.objects.create(
                external_id=player_data['id'],
                name=player_data.get('name', 'Joueur inconnu'),
                position=position,
                number=player_data.get('number'),
                team=team,
                nationality=default_country,
                photo_url=player_data.get('photo'),
                update_by='squads_import',
                update_at=timezone.now()
            )
            
            self._log_update('Player', player.id, True, player_data)
            self.stdout.write(f"Joueur créé: {player.name}")
            created = True
            
            return player, created, updated

    def _process_squads(self, squads_data: List[Dict], create_players: bool, 
                       update_existing: bool, deactivate_missing: bool) -> Dict[str, int]:
        """Traiter les données d'effectif d'équipe."""
        stats = {
            'total_teams': len(squads_data),
            'total_players': 0,
            'created': 0,
            'updated': 0,
            'deactivated': 0,
            'failed': 0
        }
        
        for team_data in squads_data:
            try:
                team_info = team_data.get('team', {})
                players_list = team_data.get('players', [])
                
                if not team_info or not team_info.get('id') or not players_list:
                    stats['failed'] += 1
                    continue
                
                # Récupérer ou créer l'équipe
                team = self._get_or_create_team(team_info)
                if not team:
                    stats['failed'] += 1
                    continue
                
                self.stdout.write(self.style.SUCCESS(f"Traitement de l'effectif de {team.name} ({len(players_list)} joueurs)"))
                
                # Garder une trace des joueurs actuels pour désactiver ceux qui ne sont plus dans l'effectif
                current_player_ids = set()
                
                # Traiter tous les joueurs
                for player_data in players_list:
                    try:
                        player, created, updated = self._get_or_create_player(
                            player_data, 
                            team, 
                            create_players,
                            update_existing
                        )
                        
                        if not player:
                            continue
                        
                        # Ajouter à l'effectif de l'équipe
                        position = self.POSITION_MAPPING.get(player_data.get('position', 'Attacker'), PlayerPosition.FORWARD)
                        
                        team_player, tp_created = TeamPlayer.objects.update_or_create(
                            team=team,
                            player=player,
                            defaults={
                                'position': position,
                                'number': player_data.get('number'),
                                'is_active': True,
                                'update_by': 'squads_import',
                                'update_at': timezone.now()
                            }
                        )
                        
                        if tp_created:
                            self._log_update('TeamPlayer', team_player.id, True, player_data)
                            self.stdout.write(f"Joueur ajouté à l'effectif: {player.name}")
                        
                        # Mettre à jour les statistiques
                        stats['total_players'] += 1
                        if created:
                            stats['created'] += 1
                        if updated:
                            stats['updated'] += 1
                        
                        # Ajouter l'ID du joueur à la liste des joueurs actuels
                        current_player_ids.add(player.id)
                        
                    except Exception as e:
                        stats['failed'] += 1
                        self.stderr.write(f"Erreur lors du traitement d'un joueur: {str(e)}")
                        continue
                
                # Désactiver les joueurs qui ne sont plus dans l'effectif
                if deactivate_missing:
                    deactivated = TeamPlayer.objects.filter(
                        team=team,
                        is_active=True
                    ).exclude(
                        player_id__in=current_player_ids
                    ).update(
                        is_active=False,
                        update_by='squads_import',
                        update_at=timezone.now()
                    )
                    
                    stats['deactivated'] += deactivated
                    if deactivated > 0:
                        self.stdout.write(f"{deactivated} joueur(s) désactivé(s) de l'effectif de {team.name}")
                
            except Exception as e:
                stats['failed'] += 1
                self.stderr.write(self.style.ERROR(f"Erreur lors du traitement d'une équipe: {str(e)}"))
                logger.error(f"Erreur de traitement d'équipe: {str(e)}", exc_info=True)
        
        return stats

    def _log_update(self, table_name: str, record_id: int, created: bool, data: Dict) -> None:
        """Enregistrer une mise à jour dans la table UpdateLog."""
        try:
            UpdateLog.objects.create(
                table_name=table_name,
                record_id=record_id,
                update_type='create' if created else 'update',
                update_by='squads_import',
                new_data=data,
                description=f"{'Créé' if created else 'Mis à jour'} {table_name} {record_id}",
                update_at=timezone.now()
            )
        except Exception as e:
            logger.error(f"Échec de création du log de mise à jour: {str(e)}")