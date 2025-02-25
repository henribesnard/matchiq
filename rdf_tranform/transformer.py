from rdflib import Graph, Literal, URIRef, Namespace, RDF, RDFS, XSD

class RDFTransformer:
    def __init__(self):
        self.FOOTBALL = Namespace("http://example.org/football/")
        self.SCHEMA = Namespace("http://schema.org/")
        self.graph = Graph()
        self.graph.bind("football", self.FOOTBALL)
        self.graph.bind("schema", self.SCHEMA)

        # Define entity mappings
        self.ENTITY_MAPPINGS = {
            'Country': {
                'rdf_class': self.FOOTBALL.Country,
                'properties': {
                    'name': (self.SCHEMA.name, XSD.string),
                    'code': (self.FOOTBALL.countryCode, XSD.string),
                    'flag_url': (self.SCHEMA.image, XSD.anyURI),
                }
            },
            'Team': {
                'rdf_class': self.FOOTBALL.Team,
                'properties': {
                    'name': (self.SCHEMA.name, XSD.string),
                    'code': (self.FOOTBALL.teamCode, XSD.string),
                    'founded': (self.SCHEMA.foundingDate, XSD.gYear),
                    'is_national': (self.FOOTBALL.isNationalTeam, XSD.boolean),
                    'logo_url': (self.SCHEMA.image, XSD.anyURI),
                    'total_matches': (self.FOOTBALL.totalMatches, XSD.integer),
                    'total_wins': (self.FOOTBALL.totalWins, XSD.integer),
                    'country': (self.FOOTBALL.country, None, 'Country'),
                    'venue': (self.FOOTBALL.homeVenue, None, 'Venue'),
                }
            },
            # Add other entity mappings as needed
        }

    def _get_uri_for_entity(self, model_instance):
        """Generate a URI for a given Django model instance."""
        model_name = model_instance.__class__.__name__
        return URIRef(f"{self.FOOTBALL}{model_name.lower()}/{model_instance.id}")

    def transform_instance(self, instance):
        """Transform a single Django model instance to RDF."""
        model_name = instance.__class__.__name__
        if model_name not in self.ENTITY_MAPPINGS:
            return

        mapping = self.ENTITY_MAPPINGS[model_name]
        subject_uri = self._get_uri_for_entity(instance)

        # Add type triple
        self.graph.add((subject_uri, RDF.type, mapping['rdf_class']))

        # Add property triples
        for field_name, (predicate, datatype, *ref_model) in mapping['properties'].items():
            value = getattr(instance, field_name)
            if value is None:
                continue

            if ref_model:  # Handle relationships
                ref_uri = self._get_uri_for_entity(value)
                self.graph.add((subject_uri, predicate, ref_uri))
            else:  # Handle literal values
                literal = Literal(value, datatype=datatype)
                self.graph.add((subject_uri, predicate, literal))

        return subject_uri
