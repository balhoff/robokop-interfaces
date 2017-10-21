import json
import logging
import logging
import networkx as nx
import networkx.algorithms as nxa
import operator
import os
import traceback
import unittest
from greent.util import LoggingUtil
from networkx.exception import NetworkXNoPath
from pprint import pformat
from reasoner.graph_components import KNode,KEdge,elements_to_json

logger = LoggingUtil.init_logging (__file__, logging.DEBUG)

class Translation (object):
    def __init__(self, obj, type_a=None, type_b=None, description="", then=None):
#        print ("Translation(obj:{0}, type_a: {1} type_b: {2})".format (obj, type_a, type_b))
        self.obj = obj
        self.type_a = type_a
        self.type_b = type_b
        self.desc = description
        self.then = []
        self.response = None
    def __repr__(self):
        return "Translation(obj: {0} type_a: {1} type_b: {2} desc: {3} then: {4} response: {5})".format (
            self.obj, self.type_a, self.type_b, self.desc, "", #self.then,
            pformat (self.response [: min(len(self.response), 2)] if self.response else ""))

default_router_config = {
    "@concepts" : {
        "S"  : [ "c2b2r_drug_id" ],
        "G"  : [ "c2b2r_gene", "hgnc_id" ],
        "P"  : [ "c2b2r_pathway" ],
        "A"  : [ "hetio_cell" ], # anatomy, tissue
        "PH" : [ ],
        "D"  : [ "mesh_disease_id", "mesh_disease_name", "pharos_disease_id", "doid" ],
        "GC" : [ "genetic_condition" ]
    },
    "@curie" : {
        # these are "local" curies.
        "DOID" : "doid",
        "MESH" : "mesh"
        # we supplement this with the uber jsonld context
    },
    "@vocab" : {
        "c2b2r_drug_name"     : "http://chem2bio2rdf.org/drugbank/resource/Generic_Name",
        "c2b2r_drug_id"       : "http://chem2bio2rdf.org/drugbank/resource/drugbank_drug",
        "c2b2r_gene"          : "http://chem2bio2rdf.org/uniprot/resource/gene",
        "c2b2r_pathway"       : "http://chem2bio2rdf.org/kegg/resource/kegg_pathway",
        "doid"                : "http://identifiers.org/doid",
        "genetic_condition"   : "http://identifiers.org/mondo/gentic_condition",
        "hetio_anatomy"       : "http://identifier.org/hetio/anatomy",
        "hetio_cell"          : "http://identifier.org/hetio/cellcomponent",
        "hgnc_id"             : "http://identifier.org/hgnc/gene/id",
        "mesh"                : "http://identifiers.org/mesh",
        "mesh_disease_id"     : "http://identifiers.org/mesh/disease/id",
        "mesh_disease_name"   : "http://identifiers.org/mesh/disease/name",
        "mesh_drug_name"      : "http://identifiers.org/mesh/drug/name",
        "pharos_disease_id"   : "http://pharos.nih.gov/identifier/disease/id",
        "pharos_disease_name" : "http://pharos.nih.gov/identifier/disease/name",
        "root_kind"           : "http://identifiers.org/doi"
    },
    "@transitions" : {
        "mesh_disease_name" : {
            "mesh_drug_name"      : { "op" : "chemotext.disease_name_to_drug_name" }
        },
        "mesh_disease_id"   : {
            "c2b2r_drug_id"       : { "op" : "chembio.get_drugs_by_condition_graph" }
        },
        "doid"              : {
            "mesh_disease_id"     : { "op" : "disease_ontology.doid_to_mesh"   },
            "pharos_disease_id"   : { "op" : "disease_ontology.doid_to_pharos" }
            #,            "hgnc_id"             : { "op" : "pharos.disease_get_gene"         }
        },
        "c2b2r_drug_name"   : {
            "c2b2r_gene"          : { "op" : "chembio.drug_name_to_gene_symbol" }            
        },
        "c2b2r_gene"        : {
            "c2b2r_pathway"       : { "op" : "chembio.gene_symbol_to_pathway" },
            "pharos_disease_name" : { "op" : "pharos.target_to_disease" },
            "hetio_anatomy"       : { "op" : "hetio.gene_to_anatomy" },
            "hetio_cell"          : { "op" : "hetio.gene_to_cell" }
        },
        "hgnc_id"           : {
            "genetic_condition"   : { "op" : "biolink.gene_get_genetic_condition" }
        },
        "pharos_disease_id" : {
            "hgnc_id"             : { "op" : "pharos.disease_get_gene" }
        },
        "mesh"              : {
            "root_kind"           : { "op" : "oxo.mesh_to_other" }
        }
    }
}

class Rosetta:
    def __init__(self, greentConf, config=default_router_config, override={}):
        from greent.core import GreenT
        self.core = GreenT (config=greentConf, override=override)
        self.g = nx.DiGraph ()

        # Prime the vocabulary
        self.vocab = config["@vocab"]
        for k in self.vocab:
            self.g.add_node (self.vocab[k])

        # Store the concept dictionary
        self.concepts = config["@concepts"]
        # Build a curie map. import cmungall's uber context.
        self.curie = config["@curie"]
        with open(os.path.join (os.path.dirname (__file__), "jsonld", "uber_context.jsonld"), "r") as stream:
            uber = json.loads (stream.read ())
            context = uber['@context']
            for k in context:
                self.curie[k] = context[k]
                self.vocab[k] = context[k]

        # Build the transition graph.
        transitions = config["@transitions"]
        for L in transitions:
            for R in transitions[L]:
                logger.debug ("  +edge: {0} {1} {2}".format (L, R, transitions[L][R]))
                self.g.add_edge (L, R, data=transitions[L][R])
                self.g.add_edge (self.vocab[L], self.vocab[R], data=transitions[L][R])
                
    def guess_type (self, thing, source=None):
        if thing and not source and ':' in thing:
            curie = thing.upper ().split (':')[0]
            if curie in self.curie:
                source = self.curie[curie]
        if source and not source.startswith ("http://"):
            source = self.vocab[source] if source in self.vocab else None
        return source

    def map_concept_types (self, thing, object_type=None):
        the_type = self.guess_type (thing.identifier) if thing and thing.identifier else None
        return [ the_type ] if the_type else self.concepts[object_type] if object_type in self.concepts else None

    def get_translations (self, thing, object_type):
        """ 
        A Thing is a node with an identifier and a concept. The identifier could really be a number, an IRI, a curie, a proper noun, etc.
        A concept is a broad notion that maps to many specific real world types.
        Our job here is to do the best we can to figure out what specific type this thing is. i.e., narrower than a concept.
        1. One way to do that is by looking at curies. If it has one we know, use the associated IRI.
        2. If that doesn't work, map the concept to the known specific types associated with it,.
        3. Do this for thing a and thing b.
        4. We want to guess specifically via the curie if possible, to avoid a combinatoric explosion, as we cross product spurious types.
        """
        x_type_a = self.map_concept_types (thing)
        x_type_b = self.map_concept_types (thing=None, object_type=object_type)
        return [ Translation(thing, ta_i, tb_i) for ta_i in x_type_a for tb_i in x_type_b ] if x_type_a and x_type_b else []
        
    def get_transitions (self, source, dest):
        #logger.debug ("get-transitions: {0} {1}".format (source, dest))
        transitions = []
        try:
            paths = nxa.all_shortest_paths (self.g, source=source, target=dest)
            for path in paths:
                logger.debug ("  path: {0}".format (path))
                steps = list(zip(path, path[1:]))
                logger.debug ("  steps: {}".format (steps))
                for step in steps:
                    logger.debug ("    step: {}".format (step))
                    edges = self.g.edges (step, data=True)
                    for e in edges:
                        if step[1] == e[1]:
                            logger.debug ("      trans: {0}".format (e))
                            transition = e[2]['data']['op']
                            transitions.append (transition)
        except NetworkXNoPath:
            pass
        except KeyError:
            pass
        return transitions
    
    def translate (self, thing, source, target):
        if not thing:
            return None
        source = self.guess_type (thing, source)
        target = self.guess_type (None, target)
        transitions = self.get_transitions (source, target)
        stack = [ [ ( None, thing ) ] ]
        if len(transitions) > 0:
            logger.debug ("              [transitions:{3}] {0}->{1} {2}".format (source, target, transitions, len(transitions)))
        for transition in transitions:
            #print ("STACK--: {}".format (stack))
            try:
                data_op = operator.attrgetter(transition)(self.core)
                last = stack[-1:][0] # top
                if not isinstance(last[0], KEdge):
                    stack.pop ()
                #print ("         --last {}".format (last))
                for i in last:
                    #print ("       -------i--> {}".format (i))
                    node = i[1]
                    logger.debug ("              invoke: {0}({1}) => ".format (transition, node)),
                    stack.append (data_op (node))
                    r = stack[-1:]
                    result_text = str(r)
                    #r = stack[-1:]
                    #result_text = r[:min(len(r),3)] if r else None if isinstance(r, list) else r
                    logger.debug ("              invoke: {0}({1}) => {2}".format (transition, node, result_text))
            except:
                traceback.print_exc ()
        return [ pair for level in stack for pair in level if isinstance(pair,tuple) and isinstance(pair[0],KEdge) ]
    
if __name__ == "__main__":
    translator = Rosetta ()
    test = {
        "c2b2r_gene" : "pharos_disease_name",
        "c2b2r_gene" : "hetio_cell",
        "mesh"       : "root_kind",
        "doid"       : "hgnc_id"
    }
    things = [
        "DOID:0060728",
        "DOID:0050777",
        "DOID:2841"
    ]
    quiet = [ "connectionpool", "requests" ]
    for q in quiet:
        logging.getLogger(q).setLevel(logging.WARNING)
    for t in things:

        logging.getLogger("chembio").setLevel (logging.DEBUG)
        m = 'MESH:D001249'
        d    = translator.translate (m, translator.vocab["mesh_disease_id"], translator.vocab["c2b2r_drug_id"])

        print (d)
