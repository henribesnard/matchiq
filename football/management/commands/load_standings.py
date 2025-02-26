import os
import json
import logging
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from football.models import Standing, Team, League, Season, Country, UpdateLog
import http.client
from urllib.parse import urlparse, urlencode
from typing import Dict, Any, List, Optional, Set, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Charger les classements depuis API-Football'

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
        parser.add_argument('--league', type=int, help='ID de la ligue')
        parser.add_argument('--season', type=int, required=True, help='Année de la saison')
        parser.add_argument('--team', type=int, help='ID de l\'équipe')
        
        # Options supplémentaires
        parser.add_argument('--create-missing', action='store_true', help='Créer les entités manquantes (équipes, ligues)')
        parser.add_argument('--update-existing', action='store_true', help='Mettre à jour les classements existants')
        parser.add_argument('--timezone', type=str, default='UTC', help='Fuseau horaire pour les dates')
        parser.add_argument('--dry-run', action='store_true', help='Afficher la requête API sans l\'exécuter')
    
    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING('Démarrage de l\'importation des classements...'))
        
        try:
            # Vérifier qu'au moins un paramètre de filtrage est fourni avec la saison
            if not options.get('league') and not options.get('team'):
                self.stdout.write(self.style.ERROR('Erreur: Vous devez spécifier au moins un paramètre parmi --league et --team'))
                return

            # Construire les paramètres de requête
            params = self._build_query_params(options)
            
            if options.get('dry_run'):
                self.stdout.write(f"Paramètres de la requête API: {params}")
                query_string = urlencode(params)
                self.stdout.write(f"URL de la requête: GET {self.base_url}/standings?{query_string}")
                return
            
            # Récupérer les données de classement
            standings_data = self._fetch_standings(params)
            if not standings_data:
                self.stdout.write(self.style.WARNING("Aucun classement trouvé avec les paramètres fournis"))
                return
            
            # Traiter les classements
            with transaction.atomic():
                stats = self._process_standings(
                    standings_data,
                    options.get('create_missing', False),
                    options.get('update_existing', False)
                )
            
            # Afficher les résultats
            self.stdout.write(self.style.SUCCESS(f"Traitement terminé: {stats['total']} ligue(s) traitée(s)"))
            self.stdout.write(self.style.SUCCESS(f"Classements créés: {stats['created']}"))
            self.stdout.write(self.style.SUCCESS(f"Classements mis à jour: {stats['updated']}"))
            if stats['teams_created'] > 0:
                self.stdout.write(self.style.SUCCESS(f"Équipes créées: {stats['teams_created']}"))
            if stats['leagues_created'] > 0:
                self.stdout.write(self.style.SUCCESS(f"Ligues créées: {stats['leagues_created']}"))
            if stats['seasons_created'] > 0:
                self.stdout.write(self.style.SUCCESS(f"Saisons créées: {stats['seasons_created']}"))
            if stats['failed'] > 0:
                self.stdout.write(self.style.WARNING(f"Échecs d'importation: {stats['failed']}"))
            
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'Erreur durant l\'importation: {str(e)}'))
            logger.error('Erreur d\'importation des classements', exc_info=True)
            raise

    def _build_query_params(self, options) -> Dict[str, str]:
        """Construire les paramètres de requête pour l'API."""
        params = {}
        
        # Paramètre obligatoire
        params['season'] = str(options['season'])
        
        # Paramètres optionnels
        if options.get('league'):
            params['league'] = str(options['league'])
        
        if options.get('team'):
            params['team'] = str(options['team'])
        
        return params

    def _fetch_standings(self, params: Dict[str, str]) -> List[Dict]:
        """Récupérer les données de classement depuis l'API."""
        conn = None
        try:
            conn = http.client.HTTPSConnection(self.host)
            headers = {
                'x-rapidapi-host': self.host,
                'x-rapidapi-key': self.api_key
            }
            
            query_string = urlencode(params)
            url = f"/standings?{query_string}"
            
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

    def _get_or_create_country(self, country_name: str, flag_url: Optional[str] = None) -> Tuple[Country, bool]:
        """Récupérer ou créer un pays."""
        if not country_name:
            return None, False
            
        try:
            country = Country.objects.get(name=country_name)
            return country, False
        except Country.DoesNotExist:
            country = Country.objects.create(
                name=country_name,
                flag_url=flag_url,
                update_by='standings_import',
                update_at=timezone.now()
            )
            
            self.stdout.write(f"Pays créé: {country.name}")
            return country, True

    def _get_or_create_league(self, league_data: Dict, create_missing: bool) -> Tuple[League, bool]:
        """Récupérer ou créer une ligue."""
        if not league_data or not league_data.get('id'):
            return None, False
            
        try:
            league = League.objects.get(external_id=league_data['id'])
            return league, False
        except League.DoesNotExist:
            if not create_missing:
                self.stdout.write(f"Ligue avec ID {league_data['id']} non trouvée")
                return None, False
                
            # Obtenir ou créer le pays
            country, _ = self._get_or_create_country(
                league_data.get('country', 'Inconnu'),
                league_data.get('flag')
            )
            
            # Créer la ligue
            league = League.objects.create(
                external_id=league_data['id'],
                name=league_data.get('name', 'Ligue inconnue'),
                type='League',  # Type par défaut
                logo_url=league_data.get('logo'),
                country=country,
                update_by='standings_import',
                update_at=timezone.now()
            )
            
            self._log_update('League', league.id, True, league_data)
            self.stdout.write(f"Ligue créée: {league.name}")
            return league, True

    def _get_or_create_season(self, league: League, year: int, create_missing: bool) -> Tuple[Season, bool]:
        """Récupérer ou créer une saison."""
        try:
            season = Season.objects.get(league=league, year=year)
            return season, False
        except Season.DoesNotExist:
            if not create_missing:
                self.stdout.write(f"Saison {year} pour la ligue {league.name} non trouvée")
                return None, False
                
            # Créer une saison avec des dates approximatives
            from datetime import datetime
            start_date = datetime(year, 7, 1).date()  # 1er juillet de l'année
            end_date = datetime(year + 1, 6, 30).date()  # 30 juin de l'année suivante
            
            season = Season.objects.create(
                league=league,
                year=year,
                start_date=start_date,
                end_date=end_date,
                is_current=(year == datetime.now().year),
                update_by='standings_import',
                update_at=timezone.now()
            )
            
            self._log_update('Season', season.id, True, {'league_id': league.id, 'year': year})
            self.stdout.write(f"Saison créée: {league.name} {year}")
            return season, True

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
                
            # Obtenir un pays par défaut
            default_country, _ = Country.objects.get_or_create(
                name='Inconnu',
                defaults={
                    'update_by': 'standings_import',
                    'update_at': timezone.now()
                }
            )
            
            # Créer l'équipe
            team = Team.objects.create(
                external_id=team_data['id'],
                name=team_data.get('name', 'Équipe inconnue'),
                country=default_country,
                logo_url=team_data.get('logo'),
                update_by='standings_import',
                update_at=timezone.now()
            )
            
            self._log_update('Team', team.id, True, team_data)
            self.stdout.write(f"Équipe créée: {team.name}")
            return team, True

    def _process_standings(self, standings_data: List[Dict], 
                          create_missing: bool, update_existing: bool) -> Dict[str, int]:
        """Traiter les données de classement."""
        stats = {
            'total': len(standings_data),
            'created': 0,
            'updated': 0,
            'failed': 0,
            'teams_created': 0,
            'leagues_created': 0,
            'seasons_created': 0
        }
        
        for league_standings in standings_data:
            try:
                league_data = league_standings.get('league', {})
                if not league_data:
                    continue
                
                # Récupérer ou créer la ligue
                league, league_created = self._get_or_create_league(league_data, create_missing)
                if league_created:
                    stats['leagues_created'] += 1
                
                if not league:
                    stats['failed'] += 1
                    continue
                
                # Récupérer ou créer la saison
                year = league_data.get('season')
                if not year:
                    stats['failed'] += 1
                    continue
                
                season, season_created = self._get_or_create_season(league, year, create_missing)
                if season_created:
                    stats['seasons_created'] += 1
                
                if not season:
                    stats['failed'] += 1
                    continue
                
                # Traiter chaque groupe de classement (souvent un seul)
                standings_groups = league_data.get('standings', [])
                for standings_group in standings_groups:
                    for standing_data in standings_group:
                        # Récupérer ou créer l'équipe
                        team_data = standing_data.get('team')
                        if not team_data:
                            continue
                        
                        team, team_created = self._get_or_create_team(team_data, create_missing)
                        if team_created:
                            stats['teams_created'] += 1
                        
                        if not team:
                            continue
                        
                        # Données de l'équipe dans le classement
                        all_stats = standing_data.get('all', {})
                        home_stats = standing_data.get('home', {})
                        away_stats = standing_data.get('away', {})
                        
                        # Créer ou mettre à jour le classement
                        try:
                            standing = Standing.objects.get(season=season, team=team)
                            
                            # Mise à jour si demandée
                            if update_existing:
                                standing.rank = standing_data.get('rank', 0)
                                standing.points = standing_data.get('points', 0)
                                standing.goals_diff = standing_data.get('goalsDiff', 0)
                                standing.form = standing_data.get('form', '')
                                standing.status = standing_data.get('status', '')
                                standing.description = standing_data.get('description', '')
                                
                                # Statistiques globales
                                standing.played = all_stats.get('played', 0)
                                standing.won = all_stats.get('win', 0)
                                standing.drawn = all_stats.get('draw', 0)
                                standing.lost = all_stats.get('lose', 0)
                                standing.goals_for = all_stats.get('goals', {}).get('for', 0)
                                standing.goals_against = all_stats.get('goals', {}).get('against', 0)
                                
                                # Statistiques à domicile
                                standing.home_played = home_stats.get('played', 0)
                                standing.home_won = home_stats.get('win', 0)
                                standing.home_drawn = home_stats.get('draw', 0)
                                standing.home_lost = home_stats.get('lose', 0)
                                standing.home_goals_for = home_stats.get('goals', {}).get('for', 0)
                                standing.home_goals_against = home_stats.get('goals', {}).get('against', 0)
                                
                                # Statistiques à l'extérieur
                                standing.away_played = away_stats.get('played', 0)
                                standing.away_won = away_stats.get('win', 0)
                                standing.away_drawn = away_stats.get('draw', 0)
                                standing.away_lost = away_stats.get('lose', 0)
                                standing.away_goals_for = away_stats.get('goals', {}).get('for', 0)
                                standing.away_goals_against = away_stats.get('goals', {}).get('against', 0)
                                
                                # Mise à jour des métadonnées
                                standing.update_by = 'standings_import'
                                standing.update_at = timezone.now()
                                
                                standing.save()
                                self._log_update('Standing', standing.id, False, standing_data)
                                stats['updated'] += 1
                                self.stdout.write(f"Classement mis à jour: {team.name} dans {league.name} {season.year}")
                            
                        except Standing.DoesNotExist:
                            # Créer un nouveau classement
                            standing = Standing.objects.create(
                                season=season,
                                team=team,
                                rank=standing_data.get('rank', 0),
                                points=standing_data.get('points', 0),
                                goals_diff=standing_data.get('goalsDiff', 0),
                                form=standing_data.get('form', ''),
                                status=standing_data.get('status', ''),
                                description=standing_data.get('description', ''),
                                
                                # Statistiques globales
                                played=all_stats.get('played', 0),
                                won=all_stats.get('win', 0),
                                drawn=all_stats.get('draw', 0),
                                lost=all_stats.get('lose', 0),
                                goals_for=all_stats.get('goals', {}).get('for', 0),
                                goals_against=all_stats.get('goals', {}).get('against', 0),
                                
                                # Statistiques à domicile
                                home_played=home_stats.get('played', 0),
                                home_won=home_stats.get('win', 0),
                                home_drawn=home_stats.get('draw', 0),
                                home_lost=home_stats.get('lose', 0),
                                home_goals_for=home_stats.get('goals', {}).get('for', 0),
                                home_goals_against=home_stats.get('goals', {}).get('against', 0),
                                
                                # Statistiques à l'extérieur
                                away_played=away_stats.get('played', 0),
                                away_won=away_stats.get('win', 0),
                                away_drawn=away_stats.get('draw', 0),
                                away_lost=away_stats.get('lose', 0),
                                away_goals_for=away_stats.get('goals', {}).get('for', 0),
                                away_goals_against=away_stats.get('goals', {}).get('against', 0),
                                
                                update_by='standings_import',
                                update_at=timezone.now()
                            )
                            
                            self._log_update('Standing', standing.id, True, standing_data)
                            stats['created'] += 1
                            self.stdout.write(self.style.SUCCESS(f"Classement créé: {team.name} dans {league.name} {season.year}"))
                
            except Exception as e:
                stats['failed'] += 1
                self.stderr.write(self.style.ERROR(f"Erreur lors du traitement d'un classement: {str(e)}"))
                logger.error(f"Erreur de traitement de classement: {str(e)}", exc_info=True)
        
        return stats

    def _log_update(self, table_name: str, record_id: int, created: bool, data: Dict) -> None:
        """Enregistrer une mise à jour dans la table UpdateLog."""
        try:
            UpdateLog.objects.create(
                table_name=table_name,
                record_id=record_id,
                update_type='create' if created else 'update',
                update_by='standings_import',
                new_data=data,
                description=f"{'Créé' if created else 'Mis à jour'} {table_name} {record_id}",
                update_at=timezone.now()
            )
        except Exception as e:
            logger.error(f"Échec de création du log de mise à jour: {str(e)}")