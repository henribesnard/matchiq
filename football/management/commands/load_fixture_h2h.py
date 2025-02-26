import os
import json
import logging
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from football.models import (
    Fixture, Team, FixtureH2H, FixtureStatus, FixtureScore, 
    League, Season, Venue, UpdateLog
)
import http.client
from urllib.parse import urlparse, urlencode
from typing import Dict, Any, List, Optional, Set, Tuple
from datetime import datetime
import pytz

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Charger les confrontations directes (head-to-head) depuis API-Football'

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
        group.add_argument('--all', action='store_true', help='Charger les h2h pour tous les matchs sans h2h')
        group.add_argument('--fixture_external_id', type=int, help='Charger les h2h pour un match spécifique')
        group.add_argument('--team_external_ids', type=str, help='Charger les h2h pour deux équipes (format: "id1-id2")')
        
        # Options supplémentaires
        parser.add_argument('--limit', type=int, help='Nombre de confrontations à charger (last=X)')
        parser.add_argument('--season', type=int, help='Saison spécifique')
        parser.add_argument('--league', type=int, help='Ligue spécifique')
        parser.add_argument('--from_date', type=str, help='Date de début (YYYY-MM-DD)')
        parser.add_argument('--to_date', type=str, help='Date de fin (YYYY-MM-DD)')
        parser.add_argument('--status', type=str, help='Statut des matchs (ex: FT,NS)')
        parser.add_argument('--timezone', type=str, default='UTC', help='Fuseau horaire')
        parser.add_argument('--dry-run', action='store_true', help='Afficher seulement la requête sans l\'exécuter')

    def handle(self, *args, **options):
        try:
            if options['all']:
                # Trouver tous les matchs sans h2h
                fixtures = self._get_fixtures_without_h2h()
                self.stdout.write(f"Trouvé {len(fixtures)} matchs sans relations h2h")
                
                # Traiter par lots de 10 pour éviter de surcharger l'API
                for i in range(0, len(fixtures), 10):
                    batch = fixtures[i:i+10]
                    self.stdout.write(f"Traitement du lot {i//10 + 1}/{(len(fixtures)-1)//10 + 1} ({len(batch)} matchs)")
                    self._process_fixtures_batch(batch, options)
                    
            elif options['fixture_external_id']:
                # Traiter un match spécifique
                fixture_id = options['fixture_external_id']
                try:
                    fixture = Fixture.objects.get(external_id=fixture_id)
                    self.stdout.write(f"Traitement des h2h pour le match ID: {fixture_id}")
                    stats = self._process_fixture_h2h(fixture, options)
                    self._display_summary(stats)
                except Fixture.DoesNotExist:
                    self.stderr.write(self.style.ERROR(f"Match avec ID {fixture_id} introuvable"))
                    return
                    
            elif options['team_external_ids']:
                # Traiter une paire d'équipes
                team_ids = options['team_external_ids'].split('-')
                if len(team_ids) != 2:
                    self.stderr.write(self.style.ERROR("Format invalide pour team_external_ids. Utilisez 'id1-id2'"))
                    return
                
                self.stdout.write(f"Récupération des h2h pour les équipes {team_ids[0]} et {team_ids[1]}")
                stats = self._fetch_and_process_team_h2h(team_ids[0], team_ids[1], options)
                self._display_summary(stats)
                
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Erreur: {str(e)}"))
            logger.error("Erreur lors du chargement des h2h", exc_info=True)
            raise
            
    def _get_fixtures_without_h2h(self) -> List[Fixture]:
        """Récupère tous les fixtures sans relations h2h."""
        # Récupère les IDs de fixtures qui ont déjà des h2h
        fixtures_with_h2h = FixtureH2H.objects.values_list('reference_fixture', flat=True).distinct()
        
        # Récupère tous les fixtures qui n'ont pas de h2h
        # On priorise les matchs terminés (qui ont plus de chances d'avoir un historique)
        return Fixture.objects.exclude(id__in=fixtures_with_h2h).filter(
            is_finished=True
        ).order_by('-date')
        
    def _process_fixtures_batch(self, fixtures: List[Fixture], options: Dict[str, Any]) -> None:
        """Traite un lot de fixtures pour h2h."""
        stats = {
            'total': len(fixtures),
            'processed': 0,
            'failed': 0,
            'created_links': 0,
            'created_fixtures': 0
        }
        
        for fixture in fixtures:
            try:
                result = self._process_fixture_h2h(fixture, options)
                stats['processed'] += 1
                stats['created_links'] += result.get('created_links', 0)
                stats['created_fixtures'] += result.get('created_fixtures', 0)
            except Exception as e:
                stats['failed'] += 1
                self.stderr.write(f"Échec du traitement pour {fixture.external_id}: {str(e)}")
                logger.error(f"Erreur de traitement h2h: {str(e)}", exc_info=True)
                
        self._display_summary(stats)
            
    def _process_fixture_h2h(self, fixture: Fixture, options: Dict[str, Any]) -> Dict[str, int]:
        """Traite un fixture individuel pour h2h."""
        # Récupérer les IDs externes des équipes
        home_team_id = fixture.home_team.external_id
        away_team_id = fixture.away_team.external_id
        
        if not home_team_id or not away_team_id:
            raise ValueError(f"Les IDs externes des équipes sont manquants pour le match {fixture.id}")
        
        # Construire les paramètres de requête
        params = self._build_h2h_params(home_team_id, away_team_id, options)
        
        # Option dry-run
        if options.get('dry_run'):
            self.stdout.write(f"Paramètres de la requête: {params}")
            return {'created_links': 0, 'created_fixtures': 0, 'total': 1, 'processed': 0}

        # Récupérer les données h2h
        h2h_data = self._fetch_h2h(params)
        
        # Traiter les résultats
        with transaction.atomic():
            results = self._process_h2h_data(fixture, h2h_data)
        
        # Ajouter les stats de traitement
        results['total'] = 1  # Un seul match de référence traité
        results['processed'] = 1  # Un seul match de référence traité
        
        return results
    
    def _build_h2h_params(self, team1_id: int, team2_id: int, options: Dict[str, Any]) -> Dict[str, str]:
        """Construit les paramètres pour la requête API h2h."""
        params = {
            'h2h': f"{team1_id}-{team2_id}",
            'timezone': options.get('timezone', 'UTC')
        }
        
        # Paramètre de limite
        if options.get('limit') is not None and 'limit' in options.__getattribute__('_explicit')():
            params['last'] = str(options['limit'])
            
        # Paramètres optionnels
        if options.get('season'):
            params['season'] = str(options['season'])
            
        if options.get('league'):
            params['league'] = str(options['league'])
            
        if options.get('from_date'):
            params['from'] = options['from_date']
            
        if options.get('to_date'):
            params['to'] = options['to_date']
            
        if options.get('status'):
            params['status'] = options['status']
            
        return params
    
    def _fetch_h2h(self, params: Dict[str, str]) -> List[Dict]:
        """Récupère les données h2h depuis l'API."""
        conn = None
        try:
            conn = http.client.HTTPSConnection(self.host)
            headers = {
                'x-rapidapi-host': self.host,
                'x-rapidapi-key': self.api_key
            }
            
            query_string = urlencode(params)
            url = f"/fixtures/headtohead?{query_string}"
            
            self.stdout.write(f"Requête API: GET {url}")
            conn.request("GET", url, headers=headers)
            
            response = conn.getresponse()
            if response.status != 200:
                raise Exception(f'API a retourné le statut {response.status}')
            
            data = json.loads(response.read().decode('utf-8'))
            
            if data.get('errors'):
                self.stderr.write(f"Erreurs API: {json.dumps(data['errors'], indent=2)}")
                return []
            
            # Vérifier les limites API
            if 'response' in data and 'remaining' in data and 'limit' in data:
                self.stdout.write(self.style.WARNING(
                    f"Limites API: {data['remaining']} requêtes restantes sur {data['limit']} par jour"
                ))
            
            return data.get('response', [])
            
        finally:
            if conn:
                conn.close()
                
    def _fetch_and_process_team_h2h(self, team1_id: str, team2_id: str, options: Dict[str, Any]) -> Dict[str, int]:
        """Récupère et traite les h2h pour deux équipes spécifiques."""
        # Construire les paramètres
        params = self._build_h2h_params(team1_id, team2_id, options)
        
        # Option dry-run
        if options.get('dry_run'):
            self.stdout.write(f"Paramètres de la requête: {params}")
            return {'created_fixtures': 0, 'created_links': 0}
        
        # Récupérer les h2h
        h2h_data = self._fetch_h2h(params)
        
        if not h2h_data:
            self.stdout.write("Aucune donnée h2h trouvée")
            return {'created_fixtures': 0, 'created_links': 0}
        
        # Traiter les données
        created_fixtures = 0
        
        with transaction.atomic():
            for fixture_data in h2h_data:
                # Essayer de récupérer les équipes
                team1, _ = Team.objects.get_or_create(external_id=int(team1_id))
                team2, _ = Team.objects.get_or_create(external_id=int(team2_id))
                
                # Créer ou mettre à jour le fixture
                fixture, created = self._get_or_create_fixture(fixture_data)
                if created:
                    created_fixtures += 1
        
        return {'created_fixtures': created_fixtures, 'created_links': 0}
                
    def _process_h2h_data(self, reference_fixture: Fixture, h2h_data: List[Dict]) -> Dict[str, int]:
        """Traite les données h2h pour un fixture de référence."""
        if not h2h_data:
            self.stdout.write(f"Aucune donnée h2h trouvée pour le match {reference_fixture.id}")
            return {'created_links': 0, 'created_fixtures': 0}
            
        created_links = 0
        created_fixtures = 0
        
        for fixture_data in h2h_data:
            external_id = fixture_data['fixture']['id']
            
            # Ne pas traiter le match de référence lui-même
            if external_id == reference_fixture.external_id:
                continue
                
            # Récupérer ou créer le fixture associé
            related_fixture, created = self._get_or_create_fixture(fixture_data)
            if created:
                created_fixtures += 1
                
            # Créer le lien h2h
            h2h_link, link_created = FixtureH2H.objects.get_or_create(
                reference_fixture=reference_fixture,
                related_fixture=related_fixture
            )
            
            if link_created:
                created_links += 1
                
        return {'created_links': created_links, 'created_fixtures': created_fixtures}
        
    def _get_or_create_fixture(self, fixture_data: Dict) -> Tuple[Fixture, bool]:
        """Récupère ou crée un fixture à partir des données de l'API."""
        # Extraire l'ID externe
        external_id = fixture_data['fixture']['id']
        
        # Vérifier si le fixture existe déjà
        try:
            fixture = Fixture.objects.get(external_id=external_id)
            return fixture, False
        except Fixture.DoesNotExist:
            pass
            
        # Récupérer ou créer les entités liées
        league_data = fixture_data.get('league', {})
        venue_data = fixture_data.get('fixture', {}).get('venue', {})
        home_team_data = fixture_data.get('teams', {}).get('home', {})
        away_team_data = fixture_data.get('teams', {}).get('away', {})
        status_data = fixture_data.get('fixture', {}).get('status', {})
        
        # Récupérer ou créer la ligue
        league, _ = League.objects.get_or_create(
            external_id=league_data.get('id', 0),
            defaults={
                'name': league_data.get('name', 'Unknown League'),
                'type': 'League',
                'country': None,  # Vous devrez gérer cela séparément
                'update_by': 'h2h_import',
                'update_at': timezone.now()
            }
        )
        
        # Récupérer ou créer la saison
        season, _ = Season.objects.get_or_create(
            league=league,
            year=league_data.get('season', datetime.now().year),
            defaults={
                'start_date': datetime.now().date(),  # Valeur par défaut
                'end_date': datetime.now().date(),    # Valeur par défaut
                'update_by': 'h2h_import',
                'update_at': timezone.now()
            }
        )
        
        # Récupérer ou créer le lieu
        venue = None
        if venue_data and venue_data.get('id'):
            venue, _ = Venue.objects.get_or_create(
                external_id=venue_data.get('id'),
                defaults={
                    'name': venue_data.get('name', 'Unknown Venue'),
                    'city': venue_data.get('city', 'Unknown City'),
                    'country': None,  # Vous devrez gérer cela séparément
                    'update_by': 'h2h_import',
                    'update_at': timezone.now()
                }
            )
        
        # Récupérer ou créer les équipes
        home_team, _ = Team.objects.get_or_create(
            external_id=home_team_data.get('id', 0),
            defaults={
                'name': home_team_data.get('name', 'Unknown Team'),
                'country': None,  # Vous devrez gérer cela séparément
                'update_by': 'h2h_import',
                'update_at': timezone.now()
            }
        )
        
        away_team, _ = Team.objects.get_or_create(
            external_id=away_team_data.get('id', 0),
            defaults={
                'name': away_team_data.get('name', 'Unknown Team'),
                'country': None,  # Vous devrez gérer cela séparément
                'update_by': 'h2h_import',
                'update_at': timezone.now()
            }
        )
        
        # Récupérer ou créer le statut
        status_code = status_data.get('short', 'NS')
        status = None
        try:
            status = FixtureStatus.objects.get(short_code=status_code)
        except FixtureStatus.DoesNotExist:
            # Créer un statut par défaut si nécessaire
            status, _ = FixtureStatus.objects.get_or_create(
                short_code='NS',
                defaults={
                    'long_description': 'Not Started',
                    'status_type': 'scheduled'
                }
            )
        
        # Créer le fixture
        fixture = Fixture.objects.create(
            external_id=external_id,
            league=league,
            season=season,
            round=league_data.get('round', ''),
            home_team=home_team,
            away_team=away_team,
            date=datetime.fromtimestamp(fixture_data['fixture']['timestamp'], pytz.UTC),
            venue=venue,
            referee=fixture_data['fixture'].get('referee'),
            status=status,
            elapsed_time=status_data.get('elapsed'),
            timezone=fixture_data['fixture'].get('timezone', 'UTC'),
            home_score=fixture_data.get('goals', {}).get('home'),
            away_score=fixture_data.get('goals', {}).get('away'),
            is_finished=status_code in ['FT', 'AET', 'PEN'],
            update_by='h2h_import',
            update_at=timezone.now()
        )
        
        # Créer les scores
        scores = fixture_data.get('score', {})
        
        # Score domicile
        FixtureScore.objects.create(
            fixture=fixture,
            team=home_team,
            halftime=scores.get('halftime', {}).get('home'),
            fulltime=scores.get('fulltime', {}).get('home'),
            extratime=scores.get('extratime', {}).get('home'),
            penalty=scores.get('penalty', {}).get('home'),
            update_by='h2h_import',
            update_at=timezone.now()
        )
        
        # Score extérieur
        FixtureScore.objects.create(
            fixture=fixture,
            team=away_team,
            halftime=scores.get('halftime', {}).get('away'),
            fulltime=scores.get('fulltime', {}).get('away'),
            extratime=scores.get('extratime', {}).get('away'),
            penalty=scores.get('penalty', {}).get('away'),
            update_by='h2h_import',
            update_at=timezone.now()
        )
        
        # Enregistrer dans le log
        UpdateLog.objects.create(
            table_name='Fixture',
            record_id=fixture.id,
            update_type='create',
            update_by='h2h_import',
            new_data=fixture_data,
            description=f"Created fixture {fixture.id} during h2h import",
            update_at=timezone.now()
        )
        
        return fixture, True
        
    def _display_summary(self, stats: Dict[str, int]) -> None:
        """Affiche un résumé des opérations."""
        self.stdout.write(self.style.SUCCESS("\nRésumé de l'importation:"))
        self.stdout.write(f"Total de matchs traités: {stats.get('total', 0)}")
        self.stdout.write(f"Traités avec succès: {stats.get('processed', 0)}")
        self.stdout.write(f"Matchs créés: {stats.get('created_fixtures', 0)}")
        self.stdout.write(f"Liens h2h créés: {stats.get('created_links', 0)}")
        if stats.get('failed', 0) > 0:
            self.stdout.write(self.style.ERROR(f"Échecs: {stats.get('failed', 0)}"))