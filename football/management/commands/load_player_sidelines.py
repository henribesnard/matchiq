import os
import json
import logging
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from football.models import Player, Coach, PlayerSideline, UpdateLog
import http.client
from urllib.parse import urlparse, urlencode
from typing import Dict, Any, List, Optional, Set, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Charger les indisponibilités des joueurs et entraîneurs depuis API-Football'

    def __init__(self):
        super().__init__()
        self.base_url = os.getenv('API_SPORTS_BASE_URL')
        self.api_key = os.getenv('API_SPORTS_KEY')
        
        if not self.base_url or not self.api_key:
            raise ValueError("API_SPORTS_BASE_URL et API_SPORTS_KEY sont requis comme variables d'environnement")
        
        parsed_url = urlparse(self.base_url)
        self.host = parsed_url.netloc

    def add_arguments(self, parser):
        # Paramètres de filtrage (au moins un requis)
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument('--player', type=int, help='ID du joueur pour charger ses indisponibilités')
        group.add_argument('--players', type=str, help='IDs de joueurs séparés par des tirets (ex: 276-278-279)')
        group.add_argument('--coach', type=int, help='ID de l\'entraîneur pour charger ses indisponibilités')
        group.add_argument('--coaches', type=str, help='IDs d\'entraîneurs séparés par des tirets (ex: 2-6-44)')
        
        # Options supplémentaires
        parser.add_argument('--create-sidelines', action='store_true', default=True, 
                            help='Créer les périodes d\'indisponibilité (activé par défaut)')
        parser.add_argument('--update-sidelines', action='store_true', default=True,
                            help='Mettre à jour les périodes d\'indisponibilité existantes (activé par défaut)')
        parser.add_argument('--as-injury', action='store_true', 
                            help='Créer également des entrées dans PlayerInjury pour les blessures')
        parser.add_argument('--dry-run', action='store_true', 
                            help='Afficher la requête API sans l\'exécuter')

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING('Démarrage de l\'importation des indisponibilités...'))
        
        try:
            # Construire les paramètres de requête
            params = self._build_query_params(options)
            
            if options['dry_run']:
                self.stdout.write(f"Paramètres de la requête API: {params}")
                query_string = urlencode(params)
                self.stdout.write(f"URL de la requête: GET {self.base_url}/sidelined?{query_string}")
                return
            
            # Récupérer les données d'indisponibilités
            sidelines_data = self._fetch_sidelines(params)
            if not sidelines_data:
                self.stdout.write(self.style.WARNING("Aucune donnée d'indisponibilité trouvée avec les paramètres fournis"))
                return
            
            # Identifier le joueur ou l'entraîneur concerné
            person_id = None
            is_coach = False
            
            if options.get('player'):
                person_id = options['player']
                self.stdout.write(f"Traitement des indisponibilités pour le joueur ID: {person_id}")
            elif options.get('players'):
                self.stdout.write(f"Traitement des indisponibilités pour plusieurs joueurs: {options['players']}")
                # On identifiera le joueur avec les données d'API
            elif options.get('coach'):
                person_id = options['coach']
                is_coach = True
                self.stdout.write(f"Traitement des indisponibilités pour l'entraîneur ID: {person_id}")
            elif options.get('coaches'):
                is_coach = True
                self.stdout.write(f"Traitement des indisponibilités pour plusieurs entraîneurs: {options['coaches']}")
                # On identifiera l'entraîneur avec les données d'API
            
            # Traiter les indisponibilités
            with transaction.atomic():
                stats = self._process_sidelines(
                    sidelines_data,
                    person_id,
                    is_coach,
                    options.get('create_sidelines', True),
                    options.get('update_sidelines', True),
                    options.get('as_injury', False)
                )
            
            # Afficher les résultats
            self.stdout.write(self.style.SUCCESS(f"Indisponibilités importées avec succès: {stats['created']} créées"))
            self.stdout.write(self.style.SUCCESS(f"Indisponibilités mises à jour: {stats['updated']}"))
            if stats['injuries_created'] > 0:
                self.stdout.write(self.style.SUCCESS(f"Blessures créées: {stats['injuries_created']}"))
            if stats['failed'] > 0:
                self.stdout.write(self.style.WARNING(f"Échecs d'importation: {stats['failed']}"))
            
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'Erreur durant l\'importation: {str(e)}'))
            logger.error('Erreur d\'importation des indisponibilités', exc_info=True)
            raise

    def _build_query_params(self, options) -> Dict[str, str]:
        """Construire les paramètres de requête pour l'API."""
        params = {}
        
        if options.get('player'):
            params['player'] = str(options['player'])
        
        if options.get('players'):
            params['players'] = options['players']
        
        if options.get('coach'):
            params['coach'] = str(options['coach'])
        
        if options.get('coaches'):
            params['coachs'] = options['coaches']  # Note: l'API utilise "coachs" et non "coaches"
        
        return params

    def _fetch_sidelines(self, params: Dict[str, str]) -> List[Dict]:
        """Récupérer les données d'indisponibilités depuis l'API."""
        conn = None
        try:
            conn = http.client.HTTPSConnection(self.host)
            headers = {
                'x-rapidapi-host': self.host,
                'x-rapidapi-key': self.api_key
            }
            
            query_string = urlencode(params)
            url = f"/sidelined?{query_string}"
            
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

    def _get_player(self, player_id: int) -> Optional[Player]:
        """Récupérer un joueur par son ID externe."""
        try:
            return Player.objects.get(external_id=player_id)
        except Player.DoesNotExist:
            self.stdout.write(self.style.WARNING(f"Joueur avec ID externe {player_id} non trouvé"))
            return None

    def _get_coach(self, coach_id: int) -> Optional[Coach]:
        """Récupérer un entraîneur par son ID externe."""
        try:
            return Coach.objects.get(external_id=coach_id)
        except Coach.DoesNotExist:
            self.stdout.write(self.style.WARNING(f"Entraîneur avec ID externe {coach_id} non trouvé"))
            return None

    def _create_player_injury(self, player: Player, sideline_type: str, start_date, end_date) -> bool:
        """Créer une entrée dans PlayerInjury pour une blessure."""
        from football.models import PlayerInjury, InjurySeverity, InjuryStatus
        
        # Déterminer la sévérité de la blessure en fonction du type
        severity_map = {
            "Sprained Ankle": InjurySeverity.MODERATE,
            "Ankle/Foot Injury": InjurySeverity.MODERATE,
            "Broken Toe": InjurySeverity.MAJOR,
            "Vertebral Fracture": InjurySeverity.SEVERE,
            "Hip/Thigh Injury": InjurySeverity.MODERATE,
            "Thigh Muscle Strain": InjurySeverity.MODERATE,
            "Hamstring": InjurySeverity.MODERATE,
            "Groin Strain": InjurySeverity.MODERATE,
            "Groin/Pelvis Injury": InjurySeverity.MODERATE,
            "Rib Injury": InjurySeverity.MINOR,
            "Virus": InjurySeverity.MINOR,
        }
        
        # Si c'est une suspension ou non reconnu comme blessure, ignorer
        if "Suspended" in sideline_type:
            return False
            
        severity = severity_map.get(sideline_type, InjurySeverity.MODERATE)
        
        try:
            # Vérifier si l'entrée existe déjà
            try:
                injury = PlayerInjury.objects.get(
                    player=player,
                    type=sideline_type,
                    start_date=start_date
                )
                return False  # Déjà existant
            except PlayerInjury.DoesNotExist:
                # Créer l'entrée
                PlayerInjury.objects.create(
                    player=player,
                    type=sideline_type,
                    severity=severity,
                    status=InjuryStatus.RECOVERED,  # Statut par défaut pour les anciennes blessures
                    start_date=start_date,
                    end_date=end_date,
                    update_by='sidelines_import',
                    update_at=timezone.now()
                )
                return True
                
        except Exception as e:
            self.stderr.write(f"Erreur lors de la création de l'entrée de blessure: {str(e)}")
            return False

    def _process_sidelines(self, sidelines_data: List[Dict], person_id: Optional[int], 
                          is_coach: bool, create_sidelines: bool, update_sidelines: bool,
                          as_injury: bool) -> Dict[str, int]:
        """Traiter les données d'indisponibilités."""
        stats = {
            'total': len(sidelines_data),
            'created': 0,
            'updated': 0,
            'injuries_created': 0,
            'failed': 0
        }
        
        # Récupérer la personne (joueur ou entraîneur)
        person = None
        if person_id:
            if is_coach:
                person = self._get_coach(person_id)
            else:
                person = self._get_player(person_id)
                
            if not person:
                self.stderr.write(f"{'Entraîneur' if is_coach else 'Joueur'} avec ID {person_id} non trouvé")
                return stats
        
        # Pour les joueurs uniquement: possibilité de créer des blessures
        if as_injury and not is_coach and person:
            self.stdout.write(f"Création d'entrées de blessures pour le joueur {person.name}")
        
        # Traiter chaque indisponibilité
        for sideline_data in sidelines_data:
            try:
                # Vérifier les données minimales
                if not sideline_data.get('type') or not sideline_data.get('start') or not sideline_data.get('end'):
                    stats['failed'] += 1
                    continue
                
                # Convertir les dates
                try:
                    start_date = datetime.strptime(sideline_data['start'], '%Y-%m-%d').date()
                    end_date = datetime.strptime(sideline_data['end'], '%Y-%m-%d').date()
                except ValueError:
                    self.stderr.write(f"Format de date invalide: {sideline_data['start']} ou {sideline_data['end']}")
                    stats['failed'] += 1
                    continue
                
                # Si on est en mode multiple joueurs/entraîneurs, on saute sans personne identifiée
                if not person:
                    self.stderr.write("Aucune personne identifiée pour cette indisponibilité, impossible de traiter")
                    stats['failed'] += 1
                    continue
                
                # Pour les joueurs uniquement
                if not is_coach:
                    # Créer l'indisponibilité
                    if create_sidelines:
                        try:
                            sideline, created = PlayerSideline.objects.get_or_create(
                                player=person,
                                type=sideline_data['type'],
                                start_date=start_date,
                                defaults={
                                    'end_date': end_date,
                                    'update_by': 'sidelines_import',
                                    'update_at': timezone.now()
                                }
                            )
                            
                            if created:
                                stats['created'] += 1
                                self._log_update('PlayerSideline', sideline.id, True, sideline_data)
                                self.stdout.write(f"Indisponibilité créée: {person.name} - {sideline_data['type']} ({start_date} à {end_date})")
                            elif update_sidelines:
                                # Mettre à jour si nécessaire
                                if sideline.end_date != end_date:
                                    sideline.end_date = end_date
                                    sideline.update_by = 'sidelines_import'
                                    sideline.update_at = timezone.now()
                                    sideline.save()
                                    stats['updated'] += 1
                                    self._log_update('PlayerSideline', sideline.id, False, sideline_data)
                                    self.stdout.write(f"Indisponibilité mise à jour: {person.name} - {sideline_data['type']} ({start_date} à {end_date})")
                        except Exception as e:
                            self.stderr.write(f"Erreur lors de la création/mise à jour de l'indisponibilité: {str(e)}")
                            stats['failed'] += 1
                            continue
                    
                    # Créer une entrée de blessure si demandé
                    if as_injury and "Suspended" not in sideline_data['type']:
                        injury_created = self._create_player_injury(
                            person, 
                            sideline_data['type'],
                            start_date,
                            end_date
                        )
                        if injury_created:
                            stats['injuries_created'] += 1
                            self.stdout.write(f"Blessure créée: {person.name} - {sideline_data['type']} ({start_date} à {end_date})")
                
                # Pour les entraîneurs, juste un log pour l'instant (modèle à créer si nécessaire)
                else:
                    self.stdout.write(f"Indisponibilité d'entraîneur détectée: {person.name} - {sideline_data['type']} ({start_date} à {end_date})")
                    # Ici, vous pourriez créer un modèle CoachSideline similaire à PlayerSideline
                    
            except Exception as e:
                stats['failed'] += 1
                self.stderr.write(self.style.ERROR(f"Erreur lors du traitement d'une indisponibilité: {str(e)}"))
                logger.error(f"Erreur de traitement d'indisponibilité: {str(e)}", exc_info=True)
        
        return stats

    def _log_update(self, table_name: str, record_id: int, created: bool, data: Dict) -> None:
        """Enregistrer une mise à jour dans la table UpdateLog."""
        try:
            UpdateLog.objects.create(
                table_name=table_name,
                record_id=record_id,
                update_type='create' if created else 'update',
                update_by='sidelines_import',
                new_data=data,
                description=f"{'Créé' if created else 'Mis à jour'} {table_name} {record_id}",
                update_at=timezone.now()
            )
        except Exception as e:
            logger.error(f"Échec de création du log de mise à jour: {str(e)}")