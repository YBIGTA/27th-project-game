
import numpy as np
import pandas as pd
import faiss
from sklearn.metrics.pairwise import cosine_similarity
from datetime import datetime

class VectorBasedRecommender:
    def __init__(self, data_path):
        self.data_path = data_path
        self._load_data()

    def _load_data(self):
        """데이터 아티팩트를 로드하고, 정규화를 위한 min/max 값을 미리 계산합니다."""
        try:
            self.faiss_index = faiss.read_index(f"{self.data_path}/faiss_index.faiss")
            self.games_df = pd.read_csv(f"{self.data_path}/games.csv").set_index('appid')
            self.game_vecs = np.load(f"{self.data_path}/game_vecs.npy").astype('float32')
            self.tag_vecs = np.load(f"{self.data_path}/tag_vecs.npy").astype('float32')
            tags_df = pd.read_csv(f"{self.data_path}/tags.csv")
            
            # Mappings
            self.tag_to_idx = {tag: i for i, tag in enumerate(tags_df['tag'])}
            self.idx_to_tag = {i: tag for i, tag in enumerate(tags_df['tag'])}
            self.appid_to_idx = {appid: i for i, appid in enumerate(self.games_df.index)}
            self.idx_to_appid = {i: appid for i, appid in enumerate(self.games_df.index)}

            # Min-Max 값 사전 계산
            self.games_df['release_date'] = pd.to_datetime(self.games_df['release_date'], errors='coerce')
            self.min_date = self.games_df['release_date'].min()
            self.max_date = self.games_df['release_date'].max()
            self.min_popularity = self.games_df['popularity_proxy'].min()
            self.max_popularity = self.games_df['popularity_proxy'].max()

        except FileNotFoundError as e:
            print(f"Warning: Could not find data file {e}. Some features may not work.")
            self.faiss_index = None
        except KeyError as e:
            print(f"Warning: Column {e} not found in games.csv. Some features may not work.")

    def _create_query_vector(self, parsed_json):
        if self.tag_vecs is None: return np.zeros(1)
        final_vector = np.zeros(self.tag_vecs.shape[1], dtype=np.float32)
        total_weight = 0
        for tag_info in parsed_json.get('target_tags', []):
            tag_name = tag_info.get('name')
            if tag_name in self.tag_to_idx:
                tag_idx = self.tag_to_idx[tag_name]
                weight = tag_info.get('weight', 1.0)
                final_vector += self.tag_vecs[tag_idx] * weight
                total_weight += weight
        for tag_name in parsed_json.get('avoid_tags', []):
            if tag_name in self.tag_to_idx:
                tag_idx = self.tag_to_idx[tag_name]
                final_vector -= self.tag_vecs[tag_idx]
        return final_vector

    def recommend_similar(self, parsed_json, top_k=200):
        if not self.faiss_index: return {"error": "Recommender not initialized"}
        seed_game_titles = parsed_json.get('games', [])
        if not seed_game_titles: return {"error": "No seed games"}
        
        seed_vectors = []
        seed_appids = set()
        for title in seed_game_titles:
            game_row = self.games_df[self.games_df['title'].str.lower() == title.lower()]
            if not game_row.empty:
                appid = game_row.index[0]
                seed_appids.add(appid)
                seed_vectors.append(self.game_vecs[self.appid_to_idx[appid]])
        
        if not seed_vectors: return {"error": f"Seed games not found: {seed_game_titles}"}
        
        query_vector = np.mean(seed_vectors, axis=0).reshape(1, -1)
        distances, indices = self.faiss_index.search(query_vector, top_k + len(seed_appids))
        
        candidate_appids = [self.idx_to_appid[i] for i in indices[0] if self.idx_to_appid[i] not in seed_appids]
        return {"candidates": candidate_appids[:top_k], "query_vector": query_vector}

    def recommend_vibe(self, parsed_json, top_k=200):
        if not self.faiss_index: return {"error": "Recommender not initialized"}
        query_vector = self._create_query_vector(parsed_json).reshape(1, -1)
        if np.all(query_vector == 0): return {"error": "No valid tags"}

        distances, indices = self.faiss_index.search(query_vector, top_k)
        candidate_appids = [self.idx_to_appid[i] for i in indices[0]]
        return {"candidates": candidate_appids, "query_vector": query_vector}

    def recommend_hybrid(self, parsed_json, top_k=200):
        if not self.faiss_index: return {"error": "Recommender not initialized"}
        game_title = parsed_json.get('games', [])[0]
        game_row = self.games_df[self.games_df['title'].str.lower() == game_title.lower()]
        if game_row.empty: return {"error": f"Game '{game_title}' not found."}
        
        game_appid = game_row.index[0]
        base_game_vector = self.game_vecs[self.appid_to_idx[game_appid]]
        vibe_vector = self._create_query_vector(parsed_json)
        
        weights = parsed_json.get('weights', {"similar_weight": 0.5, "vibe_weight": 0.5})
        query_vector = (weights['similar_weight'] * base_game_vector + weights['vibe_weight'] * vibe_vector).reshape(1, -1)

        distances, indices = self.faiss_index.search(query_vector, top_k + 1)
        candidate_appids = [self.idx_to_appid[i] for i in indices[0] if self.idx_to_appid[i] != game_appid]
        return {"candidates": candidate_appids[:top_k], "query_vector": query_vector}

    def rerank_candidates(self, candidate_appids, query_vector, weights, top_n=10):
        if not candidate_appids: return ["No candidates to rerank."]
        
        # 1. 가중치 정규화
        total_weight = sum(weights.values())
        alpha = weights.get('tag_match', 0) / total_weight
        beta = weights.get('novelty', 0) / total_weight
        gamma = weights.get('recency', 0) / total_weight
        delta = weights.get('popularity', 0) / total_weight

        # 2. 후보군 데이터프레임 생성
        candidates_df = self.games_df.loc[candidate_appids].copy()
        candidate_vectors = self.game_vecs[[self.appid_to_idx[appid] for appid in candidate_appids]]

        # 3. 스코어 계산
        # TagMatch Score
        tag_match_scores = cosine_similarity(query_vector, candidate_vectors)[0]
        candidates_df['tag_match_score'] = np.clip(tag_match_scores, 0, 1)

        # Recency Score
        time_diff = (self.max_date - candidates_df['release_date']).dt.days
        total_time_diff = (self.max_date - self.min_date).dt.days
        candidates_df['recency_score'] = 1 - (time_diff / total_time_diff)
        candidates_df['recency_score'].fillna(0, inplace=True)

        # Popularity Score
        pop_range = self.max_popularity - self.min_popularity
        candidates_df['popularity_score'] = (candidates_df['popularity_proxy'] - self.min_popularity) / pop_range
        candidates_df['popularity_score'].fillna(0, inplace=True)

        # Novelty Score (Placeholder)
        candidates_df['novelty_score'] = 0.5

        # 4. 최종 점수 계산
        candidates_df['final_score'] = (
            alpha * candidates_df['tag_match_score'] +
            beta * candidates_df['novelty_score'] +
            gamma * candidates_df['recency_score'] +
            delta * candidates_df['popularity_score']
        )

        # 5. 최종 순위 매겨서 상위 N개의 데이터프레임 반환
        top_games_df = candidates_df.sort_values(by='final_score', ascending=False).head(top_n)
        return top_games_df
