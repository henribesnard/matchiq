import os
import json
import logging
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from football.models import Coach, Team, Country, CoachCareer, CoachRole, UpdateLog
import http.client
from urllib.parse import urlparse, urlencode
from typing import Dict, Any, List, Optional, Set, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Charger les entraîneurs depuis API-Football'

    def __init__(self):
        super().__init__()
        self.base_url = os.getenv('API_SPORTS_BASE_URL')
        self.api_key = os.getenv('API_SPORTS_KEY')
        
        if not self.base_url or not self.api_key:
            raise ValueError("API_SPORTS_BASE_URL et API_SPORTS_KEY sont requis comme variables d'environnement")
        
        parsed_url = urlparse(self.base_url)
        self.host = parsed_url.netloc

    def add_arguments(self, parser):
        # Paramètres de recherche (au moins un requis)
        parser.add_argument('--id', type=int, help='ID de l\'entraîneur à charger')
        parser.add_argument('--team', type=int, help='ID de l\'équipe pour charger son entraîneur')
        parser.add_argument('--search', type=str, help='Rechercher un entraîneur par nom')
        
        # Options supplémentaires
        parser.add_argument('--create-teams', action='store_true', help='Créer les équipes manquantes automatiquement')
        parser.add_argument('--create-countries', action='store_true', help='Créer les pays manquants automatiquement')
        parser.add_argument('--include-career', action='store_true', help='Charger également les données de carrière')
        parser.add_argument('--dry-run', action='store_true', help='Afficher la requête API sans l\'exécuter')

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING('Démarrage de l\'importation des entraîneurs...'))
        
        try:
            # Vérifier qu'au moins un paramètre de recherche est fourni
            if not any([options.get('id'), options.get('team'), options.get('search')]):
                self.stdout.write(self.style.ERROR('Erreur: Vous devez spécifier au moins un critère de recherche'))
                self.stdout.write('Options disponibles: --id, --team, --search')
                return
            
            # Construire les paramètres de requête
            params = self._build_query_params(options)
            
            if options['dry_run']:
                self.stdout.write(f"Paramètres de la requête API: {params}")
                query_string = urlencode(params)
                self.stdout.write(f"URL de la requête: GET {self.base_url}/coachs?{query_string}")
                return
            
            # Récupérer les données des entraîneurs
            coaches_data = self._fetch_coaches(params)
            if not coaches_data:
                self.stdout.write(self.style.WARNING("Aucun entraîneur trouvé avec les paramètres fournis"))
                return
            
            self.stdout.write(f"Trouvé {len(coaches_data)} entraîneur(s) à traiter")
            
            # Traiter les entraîneurs
            with transaction.atomic():
                stats = self._process_coaches(
                    coaches_data, 
                    options.get('create_teams', False),
                    options.get('create_countries', False),
                    options.get('include_career', False)
                )
            
            # Afficher les résultats
            self.stdout.write(self.style.SUCCESS(f"Entraîneurs importés avec succès: {stats['created']} créés"))
            self.stdout.write(self.style.SUCCESS(f"Entraîneurs mis à jour: {stats['updated']}"))
            self.stdout.write(self.style.SUCCESS(f"Carrières importées: {stats['careers_created']}"))
            if stats['teams_created'] > 0:
                self.stdout.write(self.style.SUCCESS(f"Équipes créées: {stats['teams_created']}"))
            if stats['countries_created'] > 0:
                self.stdout.write(self.style.SUCCESS(f"Pays créés: {stats['countries_created']}"))
            if stats['failed'] > 0:
                self.stdout.write(self.style.WARNING(f"Échecs d'importation: {stats['failed']}"))
            
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'Erreur durant l\'importation: {str(e)}'))
            logger.error('Erreur d\'importation des entraîneurs', exc_info=True)
            raise

    def _build_query_params(self, options) -> Dict[str, str]:
        """Construire les paramètres de requête pour l'API."""
        params = {}
        
        if options.get('id'):
            params['id'] = str(options['id'])
        
        if options.get('team'):
            params['team'] = str(options['team'])
            
        if options.get('search'):
            params['search'] = options['search']
        
        return params

    def _fetch_coaches(self, params: Dict[str, str]) -> List[Dict]:
        """Récupérer les données des entraîneurs depuis l'API."""
        conn = None
        try:
            conn = http.client.HTTPSConnection(self.host)
            headers = {
                'x-rapidapi-host': self.host,
                'x-rapidapi-key': self.api_key
            }
            
            query_string = urlencode(params)
            url = f"/coachs?{query_string}"
            
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

    def _convert_height_to_cm(self, height_str: Optional[str]) -> Optional[int]:
        """Convertir une chaîne de hauteur (ex: '192 cm') en entier (cm)."""
        if not height_str:
            return None
            
        try:
            return int(height_str.split()[0])
        except (ValueError, IndexError):
            return None

    def _convert_weight_to_kg(self, weight_str: Optional[str]) -> Optional[int]:
        """Convertir une chaîne de poids (ex: '85 kg') en entier (kg)."""
        if not weight_str:
            return None
            
        try:
            return int(weight_str.split()[0])
        except (ValueError, IndexError):
            return None

    def _get_or_create_country(self, country_name: str, create_missing: bool) -> Tuple[Country, bool]:
        """Récupérer ou créer un pays."""
        if not country_name:
            return None, False
            
        try:
            country = Country.objects.get(name=country_name)
            return country, False
        except Country.DoesNotExist:
            if not create_missing:
                self.stdout.write(f"Pays '{country_name}' non trouvé")
                return None, False
                
            country = Country.objects.create(
                name=country_name,
                update_by='coach_import',
                update_at=timezone.now()
            )
            
            self._log_update('Country', country.id, True, {'name': country_name})
            self.stdout.write(f"Pays créé: {country.name}")
            return country, True

    def _get_or_create_team(self, team_data: Dict, create_missing: bool, default_country: Country) -> Tuple[Team, bool]:
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
                
            team = Team.objects.create(
                external_id=team_data['id'],
                name=team_data.get('name', 'Équipe inconnue'),
                country=default_country,
                logo_url=team_data.get('logo'),
                update_by='coach_import',
                update_at=timezone.now()
            )
            
            self._log_update('Team', team.id, True, team_data)
            self.stdout.write(f"Équipe créée: {team.name}")
            return team, True

    def _process_coaches(self, coaches_data: List[Dict], create_teams: bool, 
                        create_countries: bool, include_career: bool) -> Dict[str, int]:
        """Traiter les données des entraîneurs et mettre à jour la base de données."""
        stats = {
            'total': len(coaches_data),
            'created': 0,
            'updated': 0,
            'failed': 0,
            'teams_created': 0,
            'countries_created': 0,
            'careers_created': 0
        }
        
        # Obtenir un pays par défaut pour les équipes
        default_country, created = Country.objects.get_or_create(
            name='Inconnu',
            defaults={
                'update_by': 'coach_import',
                'update_at': timezone.now()
            }
        )
        if created:
            stats['countries_created'] += 1
        
        for coach_data in coaches_data:
            try:
                if not coach_data.get('id'):
                    self.stderr.write(f"Données d'entraîneur incomplètes: {coach_data}")
                    stats['failed'] += 1
                    continue
                
                # Récupérer ou créer le pays de nationalité
                nationality_country = None
                if coach_data.get('nationality'):
                    nationality_country, created = self._get_or_create_country(
                        coach_data['nationality'], 
                        create_countries
                    )
                    if created:
                        stats['countries_created'] += 1
                
                # Récupérer ou créer l'équipe actuelle
                current_team = None
                if coach_data.get('team'):
                    current_team, created = self._get_or_create_team(
                        coach_data['team'], 
                        create_teams,
                        default_country
                    )
                    if created:
                        stats['teams_created'] += 1
                
                # Préparer les données pour la création/mise à jour
                birth_date = None
                if coach_data.get('birth') and coach_data['birth'].get('date'):
                    try:
                        birth_date = datetime.strptime(coach_data['birth']['date'], '%Y-%m-%d').date()
                    except ValueError:
                        pass
                
                # Créer ou mettre à jour l'entraîneur
                try:
                    coach = Coach.objects.get(external_id=coach_data['id'])
                    
                    # Mettre à jour les champs
                    update_fields = []
                    
                    if coach.name != coach_data.get('name'):
                        coach.name = coach_data.get('name')
                        update_fields.append('name')
                        
                    if coach.firstname != coach_data.get('firstname'):
                        coach.firstname = coach_data.get('firstname')
                        update_fields.append('firstname')
                        
                    if coach.lastname != coach_data.get('lastname'):
                        coach.lastname = coach_data.get('lastname')
                        update_fields.append('lastname')
                        
                    if nationality_country and coach.nationality_id != nationality_country.id:
                        coach.nationality = nationality_country
                        update_fields.append('nationality')
                        
                    if birth_date and coach.birth_date != birth_date:
                        coach.birth_date = birth_date
                        update_fields.append('birth_date')
                        
                    if current_team and coach.team_id != current_team.id:
                        coach.team = current_team
                        update_fields.append('team')
                        
                    height = self._convert_height_to_cm(coach_data.get('height'))
                    if height and coach.height != height:
                        coach.height = height
                        update_fields.append('height')
                        
                    weight = self._convert_weight_to_kg(coach_data.get('weight'))
                    if weight and coach.weight != weight:
                        coach.weight = weight
                        update_fields.append('weight')
                        
                    if coach.photo_url != coach_data.get('photo'):
                        coach.photo_url = coach_data.get('photo')
                        update_fields.append('photo_url')
                    
                    # Si au moins un champ a été modifié
                    if update_fields:
                        coach.update_by = 'coach_import'
                        coach.update_at = timezone.now()
                        update_fields.extend(['update_by', 'update_at'])
                        
                        coach.save(update_fields=update_fields)
                        self._log_update('Coach', coach.id, False, coach_data)
                        stats['updated'] += 1
                        self.stdout.write(f"Entraîneur mis à jour: {coach.name}")
                    
                    created = False
                
                except Coach.DoesNotExist:
                    # Créer un nouvel entraîneur
                    coach = Coach.objects.create(
                        external_id=coach_data['id'],
                        name=coach_data.get('name', 'Inconnu'),
                        firstname=coach_data.get('firstname'),
                        lastname=coach_data.get('lastname'),
                        nationality=nationality_country,
                        birth_date=birth_date,
                        team=current_team,
                        height=self._convert_height_to_cm(coach_data.get('height')),
                        weight=self._convert_weight_to_kg(coach_data.get('weight')),
                        photo_url=coach_data.get('photo'),
                        update_by='coach_import',
                        update_at=timezone.now()
                    )
                    
                    self._log_update('Coach', coach.id, True, coach_data)
                    stats['created'] += 1
                    self.stdout.write(self.style.SUCCESS(f"Entraîneur créé: {coach.name}"))
                    created = True
                
                # Traiter les données de carrière si demandé
                if include_career and coach_data.get('career'):
                    career_stats = self._process_coach_career(
                        coach, 
                        coach_data.get('career', []), 
                        create_teams,
                        default_country
                    )
                    
                    stats['careers_created'] += career_stats['created']
                    stats['teams_created'] += career_stats['teams_created']
                
            except Exception as e:
                stats['failed'] += 1
                coach_name = coach_data.get('name', 'Inconnu')
                self.stderr.write(self.style.ERROR(f"Échec du traitement de l'entraîneur {coach_name}: {str(e)}"))
                logger.error(f"Erreur de traitement d'entraîneur: {str(e)}", exc_info=True)
        
        return stats

    def _process_coach_career(self, coach: Coach, career_data: List[Dict], 
                             create_teams: bool, default_country: Country) -> Dict[str, int]:
        """Traiter les données de carrière d'un entraîneur."""
        stats = {
            'created': 0,
            'updated': 0,
            'teams_created': 0
        }
        
        # Supprimer les entrées de carrière existantes
        # (on pourrait aussi les mettre à jour, mais plus simple de tout recréer)
        CoachCareer.objects.filter(coach=coach).delete()
        
        for entry in career_data:
            try:
                team_data = entry.get('team')
                if not team_data:
                    continue
                
                # Récupérer ou créer l'équipe
                team, created = self._get_or_create_team(team_data, create_teams, default_country)
                if created:
                    stats['teams_created'] += 1
                
                if not team:
                    continue
                
                # Convertir les dates
                start_date = None
                end_date = None
                
                if entry.get('start'):
                    try:
                        start_date = datetime.strptime(entry['start'], '%Y-%m-%d').date()
                    except ValueError:
                        pass
                
                if entry.get('end'):
                    try:
                        end_date = datetime.strptime(entry['end'], '%Y-%m-%d').date()
                    except ValueError:
                        pass
                
                # Créer l'entrée de carrière
                career_entry = CoachCareer.objects.create(
                    coach=coach,
                    team=team,
                    role=CoachRole.HEAD_COACH,  # Valeur par défaut
                    start_date=start_date or timezone.now().date(),
                    end_date=end_date,
                    matches=0,  # Pas d'info sur les matchs dans l'API
                    wins=0,
                    draws=0,
                    losses=0,
                    update_by='coach_import',
                    update_at=timezone.now()
                )
                
                self._log_update('CoachCareer', career_entry.id, True, entry)
                stats['created'] += 1
                self.stdout.write(f"Carrière créée: {coach.name} à {team.name}")
                
            except Exception as e:
                self.stderr.write(f"Erreur lors du traitement de la carrière: {str(e)}")
                logger.error(f"Erreur de traitement de carrière: {str(e)}", exc_info=True)
        
        # Mettre à jour les statistiques dénormalisées de l'entraîneur
        career_entries = coach.career_entries.all()
        if career_entries:
            coach.career_matches = sum(entry.matches for entry in career_entries)
            coach.career_wins = sum(entry.wins for entry in career_entries)
            coach.career_draws = sum(entry.draws for entry in career_entries)
            coach.career_losses = sum(entry.losses for entry in career_entries)
            coach.save(update_fields=['career_matches', 'career_wins', 'career_draws', 'career_losses'])
        
        return stats

    def _log_update(self, table_name: str, record_id: int, created: bool, data: Dict) -> None:
        """Enregistrer une mise à jour dans la table UpdateLog."""
        try:
            UpdateLog.objects.create(
                table_name=table_name,
                record_id=record_id,
                update_type='create' if created else 'update',
                update_by='coach_import',
                new_data=data,
                description=f"{'Créé' if created else 'Mis à jour'} {table_name} {record_id}",
                update_at=timezone.now()
            )
        except Exception as e:
            logger.error(f"Échec de création du log de mise à jour: {str(e)}")