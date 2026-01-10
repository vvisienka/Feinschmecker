"""
Ontology initialization and namespace setup for the Feinschmecker recipe ontology.

Unified Version: Forces Schema and KG to share the same namespace to match existing .nt data.
"""

from owlready2 import get_ontology
import os

# --- KEY FIX: Base Namespace matches your existing .nt file data ---
# No /schema/ or /kg/ suffixes for the main ontology to ensure queries find the data.
NAMESPACE = "https://jaron.sprute.com/uni/actionable-knowledge-representation/feinschmecker/"

# Schema ontology (TBox)
# Initialized to the base namespace so classes like Recipe get the correct URI
schema_onto = get_ontology(NAMESPACE)

# --- RESTORED METADATA ---
schema_onto.metadata.comment.append("Schema (TBox) for the Feinschmecker recipe ontology.")
schema_onto.metadata.comment.append("This ontology defines classes, properties, and constraints for recipe knowledge representation.")
schema_onto.metadata.comment.append("This ontology was made by Jaron Sprute, Bhuvenesh Verma and Szymon Czajkowski.")
schema_onto.metadata.versionInfo.append("Version: 2.0 - Schema separated from knowledge graph")

# Registry of knowledge graphs
knowledge_graphs = {}

def create_kg(source_name: str = "default", destroy_existing: bool = False):
    """
    Create a new knowledge graph ontology for a specific data source.
    
    For 'default', it uses the base NAMESPACE to align with existing data.
    """
    # 1. Determine IRI
    if source_name == "default":
        # Force default KG to share namespace with Schema and Data
        iri = NAMESPACE
    else:
        # Other sources can keep their own sub-namespaces if needed
        iri = NAMESPACE + f"kg/{source_name}/"

    # 2. Return existing if loaded
    if source_name in knowledge_graphs and not destroy_existing:
        return knowledge_graphs[source_name]
    
    # 3. Create/Get Ontology
    kg = get_ontology(iri)
    
    if destroy_existing:
        # Note: Be careful destroying 'default' as it clears the Schema too in this unified setup
        kg.destroy(update_relation=True, update_is_a=True)
        kg = get_ontology(iri)
    
    # 4. Add Metadata (Restored)
    kg.metadata.comment.append(f"Knowledge graph (ABox) for {source_name} recipes.")
    kg.metadata.comment.append("This ontology contains recipe instances and data.")
    kg.metadata.comment.append("This ontology was made by Jaron Sprute, Bhuvenesh Verma and Szymon Czajkowski.")
    kg.metadata.versionInfo.append("Version: 2.0 - Multi-source knowledge graph support")
    
    # 5. Import Schema
    # Only append if they are actually different objects (for non-default KGs)
    if kg is not schema_onto and schema_onto not in kg.imported_ontologies:
        kg.imported_ontologies.append(schema_onto)
    
    # 6. Register
    knowledge_graphs[source_name] = kg
    
    return kg

# Default knowledge graph
kg_onto = create_kg("default", destroy_existing=False)

# Backward compatibility alias
onto = kg_onto