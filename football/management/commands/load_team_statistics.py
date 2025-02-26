import os
import json
import logging
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from football.models import Team, League, Season, TeamStatistics, UpdateLog
import http.client
from urllib.parse import urlparse, urlencode
from typing import Dict, Any, List, Optional, Set, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Charger les statistiques des équipes depuis API-Football'

    def __init__(self):
        super().__init__()
        self.base_url = os.getenv('API_SPORTS_BASE_URL')
        self.api_key = os.getenv('API_SPORTS_KEY')
        
        if not self.base_url or not self.api_key:
            raise ValueError("API_SPORTS_BASE_URL et API_SPORTS_KEY sont requis comme variables d'environnement")
        
        parsed_url = urlparse(self.base_url)
        self.host = parsed_url.netloc

    def add_arguments(self, parser):
        # Paramètres obligatoires
        parser.add_argument('--team', type=int, required=True, help='ID de l\'équipe')
        parser.add_argument('--league', type=int, required=True, help='ID de la ligue')
        parser.add_argument('--season', type=int, required=True, help='Année de la saison')
        
        # Paramètres optionnels
        parser.add_argument('--date', type=str, help='Date limite pour les statistiques (YYYY-MM-DD)')
        parser.add_argument('--create-missing', action='store_true', help='Créer les entités manquantes (équipe, ligue, saison)')
        parser.add_argument('--dry-run', action='store_true', help='Afficher la requête API sans l\'exécuter')

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING('Démarrage de l\'importation des statistiques d\'équipe...'))
        
        try:
            # Construire les paramètres de requête
            params = self._build_query_params(options)
            
            if options['dry_run']:
                self.stdout.write(f"Paramètres de la requête API: {params}")
                query_string = urlencode(params)
                self.stdout.write(f"URL de la requête: GET {self.base_url}/teams/statistics?{query_string}")
                return
            
            # Vérifier que les entités de base existent
            team_id = options['team']
            league_id = options['league']
            season_year = options['season']
            
            team, league, season = self._check_entities(
                team_id, 
                league_id, 
                season_year, 
                options.get('create_missing', False)
            )
            
            if not team or not league or not season:
                self.stdout.write(self.style.ERROR("Impossible de continuer sans les entités de base"))
                return
            
            # Récupérer les statistiques
            stats_data = self._fetch_statistics(params)
            if not stats_data:
                self.stdout.write(self.style.WARNING("Aucune donnée de statistique trouvée avec les paramètres fournis"))
                return
            
            # Traiter les statistiques
            with transaction.atomic():
                result = self._process_statistics(team, league, season, stats_data)
                
                if result['created']:
                    self.stdout.write(self.style.SUCCESS(f"Statistiques créées pour {team.name} dans {league.name} {season.year}"))
                else:
                    self.stdout.write(self.style.SUCCESS(f"Statistiques mises à jour pour {team.name} dans {league.name} {season.year}"))
                
                # Afficher quelques statistiques clés
                self.stdout.write("\nStatistiques clés:")
                self.stdout.write(f"Matchs joués: {result['stats'].matches_played_total}")
                self.stdout.write(f"Victoires-Nuls-Défaites: {result['stats'].wins_total}-{result['stats'].draws_total}-{result['stats'].losses_total}")
                self.stdout.write(f"Buts marqués/encaissés: {result['stats'].goals_for_total}/{result['stats'].goals_against_total}")
                self.stdout.write(f"Forme actuelle: {result['stats'].form}")
                
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'Erreur durant l\'importation: {str(e)}'))
            logger.error('Erreur d\'importation des statistiques', exc_info=True)
            raise

    def _build_query_params(self, options) -> Dict[str, str]:
        """Construire les paramètres de requête pour l'API."""
        params = {
            'team': str(options['team']),
            'league': str(options['league']),
            'season': str(options['season'])
        }
        
        if options.get('date'):
            params['date'] = options['date']
        
        return params

    def _check_entities(self, team_id: int, league_id: int, 
                       season_year: int, create_missing: bool) -> Tuple[Optional[Team], Optional[League], Optional[Season]]:
        """Vérifier que les entités de base existent et les créer si nécessaire."""
        team = None
        league = None
        season = None
        
        # Vérifier l'équipe
        try:
            team = Team.objects.get(external_id=team_id)
            self.stdout.write(f"Équipe trouvée: {team.name}")
        except Team.DoesNotExist:
            if create_missing:
                from football.models import Country
                default_country, _ = Country.objects.get_or_create(
                    name="Inconnu",
                    defaults={
                        'update_by': 'team_stats_import',
                        'update_at': timezone.now()
                    }
                )
                
                team = Team.objects.create(
                    external_id=team_id,
                    name=f"Équipe ID {team_id}",
                    country=default_country,
                    update_by='team_stats_import',
                    update_at=timezone.now()
                )
                self.stdout.write(f"Équipe créée avec ID {team_id}")
            else:
                self.stdout.write(self.style.ERROR(f"Équipe avec ID {team_id} non trouvée"))
        
        # Vérifier la ligue
        try:
            league = League.objects.get(external_id=league_id)
            self.stdout.write(f"Ligue trouvée: {league.name}")
        except League.DoesNotExist:
            if create_missing:
                from football.models import Country
                default_country, _ = Country.objects.get_or_create(
                    name="Inconnu",
                    defaults={
                        'update_by': 'team_stats_import',
                        'update_at': timezone.now()
                    }
                )
                
                league = League.objects.create(
                    external_id=league_id,
                    name=f"Ligue ID {league_id}",
                    country=default_country,
                    type='League',
                    update_by='team_stats_import',
                    update_at=timezone.now()
                )
                self.stdout.write(f"Ligue créée avec ID {league_id}")
            else:
                self.stdout.write(self.style.ERROR(f"Ligue avec ID {league_id} non trouvée"))
        
        # Vérifier la saison
        if league:
            try:
                season = Season.objects.get(league=league, year=season_year)
                self.stdout.write(f"Saison trouvée: {league.name} {season.year}")
            except Season.DoesNotExist:
                if create_missing:
                    from datetime import datetime
                    start_date = datetime(season_year, 7, 1).date()
                    end_date = datetime(season_year + 1, 6, 30).date()
                    
                    season = Season.objects.create(
                        league=league,
                        year=season_year,
                        start_date=start_date,
                        end_date=end_date,
                        is_current=(season_year == datetime.now().year),
                        update_by='team_stats_import',
                        update_at=timezone.now()
                    )
                    self.stdout.write(f"Saison créée: {league.name} {season.year}")
                else:
                    self.stdout.write(self.style.ERROR(f"Saison {season_year} non trouvée pour la ligue {league.name}"))
        
        return team, league, season

    def _fetch_statistics(self, params: Dict[str, str]) -> Dict:
        """Récupérer les statistiques depuis l'API."""
        conn = None
        try:
            conn = http.client.HTTPSConnection(self.host)
            headers = {
                'x-rapidapi-host': self.host,
                'x-rapidapi-key': self.api_key
            }
            
            query_string = urlencode(params)
            url = f"/teams/statistics?{query_string}"
            
            self.stdout.write(f"Requête API: GET {url}")
            conn.request("GET", url, headers=headers)
            
            response = conn.getresponse()
            if response.status != 200:
                self.stderr.write(f"L'API a retourné le statut {response.status}: {response.read().decode('utf-8')}")
                return {}
            
            data = json.loads(response.read().decode('utf-8'))
            
            # Vérifier les erreurs de l'API
            if data.get('errors'):
                self.stderr.write(f"Erreurs API: {json.dumps(data['errors'], indent=2)}")
                return {}
            
            # Vérifier les limites d'utilisation
            if 'response' in data and 'remaining' in data and 'limit' in data:
                self.stdout.write(self.style.WARNING(
                    f"Limites API: {data['remaining']} requêtes restantes sur {data['limit']} par jour"
                ))
            
            return data.get('response', {})
            
        finally:
            if conn:
                conn.close()

    def _extract_biggest_score(self, score_str: str) -> Optional[Tuple[int, int]]:
        """Extraire les scores à partir d'une chaîne comme '4-0'."""
        if not score_str:
            return None
            
        try:
            parts = score_str.split('-')
            if len(parts) != 2:
                return None
                
            return (int(parts[0]), int(parts[1]))
        except (ValueError, IndexError):
            return None

    def _process_statistics(self, team: Team, league: League, season: Season, 
                           stats_data: Dict) -> Dict[str, Any]:
        """Traiter les données de statistiques d'équipe."""
        if not stats_data:
            return {'created': False, 'stats': None}
        
        try:
            # Récupérer les sections principales des données
            fixtures_data = stats_data.get('fixtures', {})
            goals_data = stats_data.get('goals', {})
            biggest_data = stats_data.get('biggest', {})
            clean_sheet_data = stats_data.get('clean_sheet', {})
            failed_to_score_data = stats_data.get('failed_to_score', {})
            penalty_data = stats_data.get('penalty', {})
            form = stats_data.get('form', '')
            
            # Créer ou mettre à jour les statistiques
            team_stats, created = TeamStatistics.objects.update_or_create(
                team=team,
                league=league,
                season=season,
                defaults={
                    # Forme actuelle
                    'form': form,
                    
                    # Matches joués
                    'matches_played_home': fixtures_data.get('played', {}).get('home', 0),
                    'matches_played_away': fixtures_data.get('played', {}).get('away', 0),
                    'matches_played_total': fixtures_data.get('played', {}).get('total', 0),
                    
                    # Victoires
                    'wins_home': fixtures_data.get('wins', {}).get('home', 0),
                    'wins_away': fixtures_data.get('wins', {}).get('away', 0),
                    'wins_total': fixtures_data.get('wins', {}).get('total', 0),
                    
                    # Nuls
                    'draws_home': fixtures_data.get('draws', {}).get('home', 0),
                    'draws_away': fixtures_data.get('draws', {}).get('away', 0),
                    'draws_total': fixtures_data.get('draws', {}).get('total', 0),
                    
                    # Défaites
                    'losses_home': fixtures_data.get('loses', {}).get('home', 0),
                    'losses_away': fixtures_data.get('loses', {}).get('away', 0),
                    'losses_total': fixtures_data.get('loses', {}).get('total', 0),
                    
                    # Buts marqués
                    'goals_for_home': goals_data.get('for', {}).get('total', {}).get('home', 0),
                    'goals_for_away': goals_data.get('for', {}).get('total', {}).get('away', 0),
                    'goals_for_total': goals_data.get('for', {}).get('total', {}).get('total', 0),
                    
                    # Buts encaissés
                    'goals_against_home': goals_data.get('against', {}).get('total', {}).get('home', 0),
                    'goals_against_away': goals_data.get('against', {}).get('total', {}).get('away', 0),
                    'goals_against_total': goals_data.get('against', {}).get('total', {}).get('total', 0),
                    
                    # Moyennes de buts
                    'goals_for_average_home': float(goals_data.get('for', {}).get('average', {}).get('home', 0)),
                    'goals_for_average_away': float(goals_data.get('for', {}).get('average', {}).get('away', 0)),
                    'goals_for_average_total': float(goals_data.get('for', {}).get('average', {}).get('total', 0)),
                    'goals_against_average_home': float(goals_data.get('against', {}).get('average', {}).get('home', 0)),
                    'goals_against_average_away': float(goals_data.get('against', {}).get('average', {}).get('away', 0)),
                    'goals_against_average_total': float(goals_data.get('against', {}).get('average', {}).get('total', 0)),
                    
                    # Séries
                    'streak_wins': biggest_data.get('streak', {}).get('wins', 0),
                    'streak_draws': biggest_data.get('streak', {}).get('draws', 0),
                    'streak_losses': biggest_data.get('streak', {}).get('loses', 0),
                    
                    # Plus grandes victoires
                    'biggest_win_home': biggest_data.get('wins', {}).get('home', ''),
                    'biggest_win_away': biggest_data.get('wins', {}).get('away', ''),
                    'biggest_loss_home': biggest_data.get('loses', {}).get('home', ''),
                    'biggest_loss_away': biggest_data.get('loses', {}).get('away', ''),
                    
                    # Clean sheets
                    'clean_sheets_home': clean_sheet_data.get('home', 0),
                    'clean_sheets_away': clean_sheet_data.get('away', 0),
                    'clean_sheets_total': clean_sheet_data.get('total', 0),
                    
                    # Failed to score
                    'failed_to_score_home': failed_to_score_data.get('home', 0),
                    'failed_to_score_away': failed_to_score_data.get('away', 0),
                    'failed_to_score_total': failed_to_score_data.get('total', 0),
                    
                    # Penalties
                    'penalties_scored': penalty_data.get('scored', {}).get('total', 0),
                    'penalties_missed': penalty_data.get('missed', {}).get('total', 0),
                    'penalties_total': penalty_data.get('total', 0),
                    
                    # Métadonnées
                    'update_by': 'team_stats_import',
                    'update_at': timezone.now()
                }
            )
            
            # Enregistrer dans le log
            self._log_update('TeamStatistics', team_stats.id, created, stats_data)
            
            return {
                'created': created,
                'stats': team_stats
            }
            
        except Exception as e:
            self.stderr.write(f"Erreur lors du traitement des statistiques: {str(e)}")
            raise

    def _log_update(self, table_name: str, record_id: int, created: bool, data: Dict) -> None:
        """Enregistrer une mise à jour dans la table UpdateLog."""
        try:
            UpdateLog.objects.create(
                table_name=table_name,
                record_id=record_id,
                update_type='create' if created else 'update',
                update_by='team_stats_import',
                new_data=data,
                description=f"{'Créé' if created else 'Mis à jour'} {table_name} {record_id}",
                update_at=timezone.now()
            )
        except Exception as e:
            logger.error(f"Échec de création du log de mise à jour: {str(e)}")