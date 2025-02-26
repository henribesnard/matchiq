import os
import json
import logging
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from football.models import Player, Team, PlayerTransfer, TransferType, UpdateLog
import http.client
from urllib.parse import urlparse, urlencode
from typing import Dict, Any, List, Optional, Set, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Charger les transferts des joueurs depuis API-Football'

    def __init__(self):
        super().__init__()
        self.base_url = os.getenv('API_SPORTS_BASE_URL')
        self.api_key = os.getenv('API_SPORTS_KEY')
        
        if not self.base_url or not self.api_key:
            raise ValueError("API_SPORTS_BASE_URL et API_SPORTS_KEY sont requis comme variables d'environnement")
        
        parsed_url = urlparse(self.base_url)
        self.host = parsed_url.netloc
        
        # Mapping des types de transfert
        self.TRANSFER_TYPE_MAPPING = {
            'Free': TransferType.FREE,
            'Loan': TransferType.LOAN,
            'N/A': TransferType.OTHER,
            None: TransferType.OTHER
        }

    def add_arguments(self, parser):
        # Paramètres de filtrage (au moins un requis)
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument('--player', type=int, help='ID du joueur pour charger ses transferts')
        group.add_argument('--team', type=int, help='ID de l\'équipe pour charger ses transferts')
        
        # Options supplémentaires
        parser.add_argument('--create-players', action='store_true', help='Créer les joueurs manquants')
        parser.add_argument('--create-teams', action='store_true', help='Créer les équipes manquantes')
        parser.add_argument('--create-player-teams', action='store_true', 
                            help='Créer également des entrées dans PlayerTeam pour suivre l\'historique')
        parser.add_argument('--dry-run', action='store_true', help='Afficher la requête API sans l\'exécuter')

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING('Démarrage de l\'importation des transferts...'))
        
        try:
            # Construire les paramètres de requête
            params = self._build_query_params(options)
            
            if options['dry_run']:
                self.stdout.write(f"Paramètres de la requête API: {params}")
                query_string = urlencode(params)
                self.stdout.write(f"URL de la requête: GET {self.base_url}/transfers?{query_string}")
                return
            
            # Récupérer les données de transferts
            transfers_data = self._fetch_transfers(params)
            if not transfers_data:
                self.stdout.write(self.style.WARNING("Aucun transfert trouvé avec les paramètres fournis"))
                return
            
            self.stdout.write(f"Trouvé {len(transfers_data)} joueur(s) avec des transferts")
            
            # Traiter les transferts pour chaque joueur
            with transaction.atomic():
                stats = self._process_transfers(
                    transfers_data,
                    options.get('create_players', False),
                    options.get('create_teams', False),
                    options.get('create_player_teams', False)
                )
            
            # Afficher les résultats
            self.stdout.write(self.style.SUCCESS(f"Transferts importés avec succès: {stats['created']} créés"))
            self.stdout.write(self.style.SUCCESS(f"Transferts mis à jour: {stats['updated']}"))
            if stats['players_created'] > 0:
                self.stdout.write(self.style.SUCCESS(f"Joueurs créés: {stats['players_created']}"))
            if stats['teams_created'] > 0:
                self.stdout.write(self.style.SUCCESS(f"Équipes créées: {stats['teams_created']}"))
            if stats['player_teams_created'] > 0:
                self.stdout.write(self.style.SUCCESS(f"Historiques d'équipe créés: {stats['player_teams_created']}"))
            if stats['failed'] > 0:
                self.stdout.write(self.style.WARNING(f"Échecs d'importation: {stats['failed']}"))
            
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'Erreur durant l\'importation: {str(e)}'))
            logger.error('Erreur d\'importation des transferts', exc_info=True)
            raise

    def _build_query_params(self, options) -> Dict[str, str]:
        """Construire les paramètres de requête pour l'API."""
        params = {}
        
        if options.get('player'):
            params['player'] = str(options['player'])
        
        if options.get('team'):
            params['team'] = str(options['team'])
        
        return params

    def _fetch_transfers(self, params: Dict[str, str]) -> List[Dict]:
        """Récupérer les données de transferts depuis l'API."""
        conn = None
        try:
            conn = http.client.HTTPSConnection(self.host)
            headers = {
                'x-rapidapi-host': self.host,
                'x-rapidapi-key': self.api_key
            }
            
            query_string = urlencode(params)
            url = f"/transfers?{query_string}"
            
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

    def _get_or_create_player(self, player_data: Dict, create_missing: bool) -> Tuple[Optional[Player], bool]:
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
                
            # Créer un joueur avec des données minimales
            # Pour un joueur complet, on devrait utiliser l'API players
            from football.models import Country
            default_country, _ = Country.objects.get_or_create(
                name="Inconnu",
                defaults={
                    'update_by': 'transfers_import',
                    'update_at': timezone.now()
                }
            )
            
            # On a besoin d'une équipe par défaut, on prendra la dernière équipe connue
            default_team = None
            # Cette fonction sera complétée plus tard
            
            player = Player.objects.create(
                external_id=player_data['id'],
                name=player_data.get('name', 'Joueur inconnu'),
                position='FW',  # Position par défaut
                team=default_team,  # Sera mis à jour plus tard
                nationality=default_country,
                update_by='transfers_import',
                update_at=timezone.now()
            )
            
            self._log_update('Player', player.id, True, player_data)
            self.stdout.write(f"Joueur créé: {player.name}")
            return player, True

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
                    'update_by': 'transfers_import',
                    'update_at': timezone.now()
                }
            )
            
            team = Team.objects.create(
                external_id=team_data['id'],
                name=team_data.get('name', 'Équipe inconnue'),
                country=default_country,
                logo_url=team_data.get('logo'),
                update_by='transfers_import',
                update_at=timezone.now()
            )
            
            self._log_update('Team', team.id, True, team_data)
            self.stdout.write(f"Équipe créée: {team.name}")
            return team, True

    def _create_player_team_entry(self, player: Player, team: Team, year: int) -> bool:
        """Créer une entrée d'historique dans PlayerTeam."""
        from football.models import Season, PlayerTeam
        
        try:
            # Trouver une saison appropriée
            season = None
            try:
                # Chercher une saison existante pour cette année
                season = Season.objects.filter(year=year).first()
                
                if not season:
                    # Créer une saison par défaut si nécessaire
                    from football.models import League
                    default_league, _ = League.objects.get_or_create(
                        name="Ligue par défaut",
                        defaults={
                            'external_id': 0,
                            'type': 'League',
                            'country': team.country,
                            'update_by': 'transfers_import',
                            'update_at': timezone.now()
                        }
                    )
                    
                    from datetime import datetime
                    season = Season.objects.create(
                        league=default_league,
                        year=year,
                        start_date=datetime(year, 7, 1).date(),
                        end_date=datetime(year + 1, 6, 30).date(),
                        is_current=(year == datetime.now().year),
                        update_by='transfers_import',
                        update_at=timezone.now()
                    )
            except Exception as e:
                self.stderr.write(f"Erreur lors de la récupération/création de la saison: {str(e)}")
                return False
            
            # Créer l'entrée d'historique
            player_team, created = PlayerTeam.objects.get_or_create(
                player=player,
                team=team,
                season=season,
                defaults={
                    'update_by': 'transfers_import',
                    'update_at': timezone.now()
                }
            )
            
            return created
            
        except Exception as e:
            self.stderr.write(f"Erreur lors de la création de l'historique d'équipe: {str(e)}")
            return False

    def _process_transfers(self, transfers_data: List[Dict], create_players: bool, 
                          create_teams: bool, create_player_teams: bool) -> Dict[str, int]:
        """Traiter les données de transferts."""
        stats = {
            'total_players': len(transfers_data),
            'created': 0,
            'updated': 0,
            'failed': 0,
            'players_created': 0,
            'teams_created': 0,
            'player_teams_created': 0
        }
        
        for player_transfers in transfers_data:
            try:
                player_data = player_transfers.get('player', {})
                transfers_list = player_transfers.get('transfers', [])
                
                if not player_data or not player_data.get('id') or not transfers_list:
                    stats['failed'] += 1
                    continue
                
                # Récupérer ou créer le joueur
                player, player_created = self._get_or_create_player(player_data, create_players)
                if player_created:
                    stats['players_created'] += 1
                
                if not player:
                    stats['failed'] += 1
                    continue
                
                # Traiter tous les transferts
                last_team = None
                
                for transfer_data in transfers_list:
                    try:
                        # Vérifier les données de base
                        if not transfer_data.get('date') or not transfer_data.get('teams'):
                            continue
                        
                        transfer_date_str = transfer_data['date']
                        teams_data = transfer_data['teams']
                        
                        # Convertir la date
                        try:
                            transfer_date = datetime.strptime(transfer_date_str, '%Y-%m-%d').date()
                            transfer_year = transfer_date.year
                        except ValueError:
                            self.stderr.write(f"Format de date invalide: {transfer_date_str}")
                            continue
                        
                        # Récupérer ou créer les équipes
                        team_in_data = teams_data.get('in', {})
                        team_out_data = teams_data.get('out', {})
                        
                        if not team_in_data or not team_out_data:
                            continue
                        
                        team_in, team_in_created = self._get_or_create_team(team_in_data, create_teams)
                        if team_in_created:
                            stats['teams_created'] += 1
                            
                        team_out, team_out_created = self._get_or_create_team(team_out_data, create_teams)
                        if team_out_created:
                            stats['teams_created'] += 1
                        
                        if not team_in or not team_out:
                            continue
                        
                        # Déterminer le type de transfert
                        transfer_type_str = transfer_data.get('type')
                        transfer_type = self.TRANSFER_TYPE_MAPPING.get(transfer_type_str, TransferType.OTHER)
                        
                        # Créer ou mettre à jour le transfert
                        try:
                            transfer, created = PlayerTransfer.objects.update_or_create(
                                player=player,
                                date=transfer_date,
                                defaults={
                                    'type': transfer_type,
                                    'team_in': team_in,
                                    'team_out': team_out,
                                    'update_by': 'transfers_import',
                                    'update_at': timezone.now()
                                }
                            )
                            
                            if created:
                                stats['created'] += 1
                                self._log_update('PlayerTransfer', transfer.id, True, transfer_data)
                                self.stdout.write(f"Transfert créé: {player.name} de {team_out.name} à {team_in.name} le {transfer_date}")
                            else:
                                stats['updated'] += 1
                                self._log_update('PlayerTransfer', transfer.id, False, transfer_data)
                                self.stdout.write(f"Transfert mis à jour: {player.name} de {team_out.name} à {team_in.name} le {transfer_date}")
                            
                            # Créer des entrées PlayerTeam si demandé
                            if create_player_teams:
                                if self._create_player_team_entry(player, team_in, transfer_year):
                                    stats['player_teams_created'] += 1
                            
                            # Garder une trace de la dernière équipe
                            last_team = team_in
                            
                        except Exception as e:
                            self.stderr.write(f"Erreur lors de la création/mise à jour du transfert: {str(e)}")
                            continue
                    
                    except Exception as e:
                        self.stderr.write(f"Erreur lors du traitement d'un transfert: {str(e)}")
                        continue
                
                # Mettre à jour l'équipe actuelle du joueur si nécessaire
                if last_team and player.team_id != last_team.id:
                    player.team = last_team
                    player.save(update_fields=['team', 'update_at'])
                    self.stdout.write(f"Équipe actuelle du joueur mise à jour: {player.name} -> {last_team.name}")
                
            except Exception as e:
                stats['failed'] += 1
                self.stderr.write(self.style.ERROR(f"Erreur lors du traitement des transferts d'un joueur: {str(e)}"))
                logger.error(f"Erreur de traitement des transferts: {str(e)}", exc_info=True)
        
        return stats

    def _log_update(self, table_name: str, record_id: int, created: bool, data: Dict) -> None:
        """Enregistrer une mise à jour dans la table UpdateLog."""
        try:
            UpdateLog.objects.create(
                table_name=table_name,
                record_id=record_id,
                update_type='create' if created else 'update',
                update_by='transfers_import',
                new_data=data,
                description=f"{'Créé' if created else 'Mis à jour'} {table_name} {record_id}",
                update_at=timezone.now()
            )
        except Exception as e:
            logger.error(f"Échec de création du log de mise à jour: {str(e)}")