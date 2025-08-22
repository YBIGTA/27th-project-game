
def similar_node(state, recommender):
    result = recommender.recommend_similar(state['parsed_json'])
    state['candidate_appids'] = result.get("candidates", [])
    state['query_vector'] = result.get("query_vector")
    return state

def vibe_node(state, recommender):
    result = recommender.recommend_vibe(state['parsed_json'])
    state['candidate_appids'] = result.get("candidates", [])
    state['query_vector'] = result.get("query_vector")
    return state

def hybrid_node(state, recommender):
    result = recommender.recommend_hybrid(state['parsed_json'])
    state['candidate_appids'] = result.get("candidates", [])
    state['query_vector'] = result.get("query_vector")
    return state
