def similar_node(state, recommender):
    expanded = recommender.expand_query_tags(state['parsed_json'], top_k=5)  # ← 추가
    state['parsed_json'] = expanded
    result = recommender.recommend_similar(expanded)
    state['candidate_appids'] = result.get("candidates", [])
    state['query_vector'] = result.get("query_vector")
    return state

def vibe_node(state, recommender):
    expanded = recommender.expand_query_tags(state['parsed_json'], top_k=5)  # ← 추가
    state['parsed_json'] = expanded
    result = recommender.recommend_vibe(expanded)
    state['candidate_appids'] = result.get("candidates", [])
    state['query_vector'] = result.get("query_vector")
    return state

def hybrid_node(state, recommender):
    expanded = recommender.expand_query_tags(state['parsed_json'], top_k=5)  # ← 추가
    state['parsed_json'] = expanded
    result = recommender.recommend_hybrid(expanded)
    state['candidate_appids'] = result.get("candidates", [])
    state['query_vector'] = result.get("query_vector")
    return state

def steam_similar_node(state, recommender):
    """Recommends games based on a weighted list of games from Steam."""
    steam_games = state['parsed_json'].get('steam_games', [])
    if not steam_games:
        # Fallback or error handling
        state['candidate_appids'] = []
        state['query_vector'] = None
        return state

    result = recommender.recommend_similar_with_weights(steam_games)
    state['candidate_appids'] = result.get("candidates", [])
    state['query_vector'] = result.get("query_vector")
    return state