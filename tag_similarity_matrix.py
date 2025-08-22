from collections import defaultdict
from itertools import combinations
import pandas as pd
from tqdm import tqdm   # ✅ 진행상황 표시

# CSV 불러오기
df_scores = pd.read_csv("user_game_scores_penalty.csv")
df_tags = pd.read_csv("steam_games_tags.csv")

# 태그 explode
df_tags = df_tags.assign(tag=df_tags["tags"].str.split(", ")).explode("tag")
df = df_scores.merge(df_tags[["appid", "tag"]], on="appid", how="inner")
df = df[["appid", "steamid", "game_score", "tag"]]

# ✅ 시너지 계산
tag_synergy = defaultdict(float)
user_count = defaultdict(int)

print("🚀 태그 시너지 계산 시작...")

for steamid, group in tqdm(df.groupby("steamid"), total=df["steamid"].nunique()):
    tag_scores = group.groupby("tag")["game_score"].sum()
    
    for t1, t2 in combinations(tag_scores.index, 2):
        score = tag_scores[t1] * tag_scores[t2]
        key = tuple(sorted([t1, t2]))   # 중복 제거
        tag_synergy[key] += score
        user_count[key] += 1            # 해당 쌍을 평가한 유저 수 기록

# ✅ 결과 저장 (raw + 정규화)
tag_synergy_df = pd.DataFrame(
    [(t1, t2, raw, raw / user_count[(t1, t2)]) 
     for (t1, t2), raw in tag_synergy.items()],
    columns=["tag1", "tag2", "raw_synergy", "norm_synergy"]
)

tag_synergy_df.to_csv("tag_synergy_matrix.csv", index=False)
print("✅ 저장 완료: tag_synergy_matrix.csv")
