# Pour charger les country
python manage.py load_countries

# Pour charger toutes les leagues
python manage.py load_leagues

# Pour charger une league spécifique
python manage.py load_leagues --league_id=39

# Charger les status
python manage.py load_fixture_statuses


# Lineups
python manage.py load_fixture_lineups --fixture_external_id=592872
python manage.py load_fixture_lineups --all

# Charger les stats pour tous les matchs sans stats
python manage.py load_fixture_stats --all

# Charger les stats pour un match spécifique    
python manage.py load_fixture_stats --fixture_external_id 867983

# Fixture event
python manage.py load_fixture_events --fixture_external_id=215662
python manage.py load_fixture_events --all

# Fixture player stats
python manage.py load_fixture_player_stats --fixture_external_id=169080
python manage.py load_fixture_player_stats --all

# charger les types de paris 
python manage.py load_odds_types

# Charger les paris
python manage.py load_fixture_odds --fixture_external_id 164327
python manage.py load_fixture_odds --all

# fixtures traités 
867983
867946
867947
867951
867948
1201624
1201625
1038329
1038331
1035550
1035551
1035553
1035545
1035549
1035546
1035552
1035548
1035547
1035544
1035510 # player stat
1035505