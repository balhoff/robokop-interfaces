from graphql.type.definition import GraphQLArgument, GraphQLField, GraphQLNonNull, GraphQLObjectType
from graphql.type.scalars import GraphQLString
from graphql.type.schema import GraphQLSchema

from core import GreenT

def resolve_raises(*_):
    raise Exception("Throws!")

greenT = GreenT ()

def get_exposure_scores (obj, args, context, info):
    return greenT.get_exposure_scores (
        exposure_type  = args.get ("exposureType"),
        start_date     = args.get ("startDate"),
        end_date       = args.get ("endDate"),
        exposure_point = args.get ("exposurePoint"))
    
def get_exposure_values (obj, args, context, info):
    return greenT.get_exposure_values (
        exposure_type  = args.get ("exposureType"),
        start_date     = args.get ("startDate"),
        end_date       = args.get ("endDate"),
        exposure_point = args.get ("exposurePoint"))

def get_patients (obj, args, context, info):
    return greenT.get_patients (
        age = args.get ("age"),
        sex = args.get ("sex"),
        race = args.get ("race"),
        location = args.get ("location"))

def get_exposure_conditions (obj, args, context, info):
    return greenT.get_exposure_conditions (chemicals = args.get ("chemicals"))

def get_drugs_by_condition (obj, args, context, info):
    return greenT.get_drugs_by_condition (conditions = args.get ("conditions"))

def get_genes_pathways_by_disease (obj, args, context, info):
    return greenT.get_genes_pathways_by_condition (conditions = args.get ("diseases"))

QueryRootType = GraphQLObjectType(
    name='QueryRoot',
    fields={
        'thrower': GraphQLField(GraphQLNonNull(GraphQLString), resolver=resolve_raises),
        'request': GraphQLField(GraphQLNonNull(GraphQLString),
                                resolver=lambda obj, args, context, info: context.args.get('q')),
        'context': GraphQLField(GraphQLNonNull(GraphQLString),
                                resolver=lambda obj, args, context, info: context),
        'test': GraphQLField(
            type=GraphQLString,
            args={
                'who': GraphQLArgument(GraphQLString)
            },
            resolver=lambda obj, args, context, info: 'Hello %s' % (args.get('who') or 'World')
        ),
        
        'patients' : GraphQLField (
            type=GraphQLString,
            args = {
                'age' : GraphQLArgument (GraphQLString),
                'sex' : GraphQLArgument (GraphQLString),
                'race' : GraphQLArgument (GraphQLString),
                'location' : GraphQLArgument (GraphQLString)
            },
            resolver = get_patients
        ),

        'exposureScore' : GraphQLField (
            type=GraphQLString,
            args = {
                'type' : GraphQLArgument (GraphQLString),
                'startDate' : GraphQLArgument (GraphQLString),
                'endDate' : GraphQLArgument (GraphQLString),
                'exposurePoint' : GraphQLArgument (GraphQLString)
            },
            resolver = get_exposure_scores
        ),

        'exposureValue' : GraphQLField (
            type=GraphQLString,
            args = {
                'type' : GraphQLArgument (GraphQLString),
                'startDate' : GraphQLArgument (GraphQLString),
                'endDate' : GraphQLArgument (GraphQLString),
                'exposurePoint' : GraphQLArgument (GraphQLString)
           },
            resolver = get_exposure_values
        ),

        'exposureConditions' : GraphQLField (
            type = GraphQLString,
            args = {
                'chemicals' : GraphQLArgument (GraphQLString) 
            },
            resolver = get_exposure_conditions            
        ),

        'drugsByCondition' : GraphQLField (
            type = GraphQLString,
            args = {
                'conditions' : GraphQLArgument (GraphQLString)                 
            },
            resolver = get_drugs_by_condition
        ),

        'genesPathwaysByDisease' : GraphQLField (
            type = GraphQLString,
            args = {
                'diseases' : GraphQLArgument (GraphQLString)                 
            },
            resolver = get_genes_pathways_by_disease
        )

    }
)

Schema = GraphQLSchema (QueryRootType)