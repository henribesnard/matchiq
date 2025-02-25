from django.db import models
from rdflib import Graph, Literal, URIRef, RDF
from .config import FOOTBALL, SCHEMA, ENTITY_MAPPINGS

class RDFTransformer:
    def __init__(self):
        self.graph = Graph()
        self.graph.bind("football", FOOTBALL)
        self.graph.bind("schema", SCHEMA)

    def _get_uri_for_entity(self, model_instance):
        """Generate a URI for a given Django model instance."""
        model_name = model_instance.__class__.__name__
        return URIRef(f"{FOOTBALL}{model_name.lower()}/{model_instance.id}")

    def transform_instance(self, instance):
        """Transform a single Django model instance to RDF."""
        model_name = instance.__class__.__name__
        if model_name not in ENTITY_MAPPINGS:
            return

        mapping = ENTITY_MAPPINGS[model_name]
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
