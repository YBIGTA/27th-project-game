import streamlit as st
import os
import sys

# Add the project root to the Python path to allow absolute imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import json
from dotenv import load_dotenv
from typing import TypedDict, List, Any
import numpy as np
import pandas as pd

from langchain_upstage import ChatUpstage
from langchain.schema.messages import HumanMessage, SystemMessage, AIMessage
from langgraph.graph import StateGraph, END

from rag.retriever import VectorBasedRecommender
from rag.nodes import (
    llm_parser_node,
    similar_node,
    vibe_node,
    hybrid_node,
    general_node,
    route_by_mode,
    generate_response_node,
    game_name_normalizer_node,
    steam_similar_node  # ⭐️ 새로 추가한 노드
)

# --- 초기화 --- #
load_dotenv()

UPSTAGE_API_KEY = os.environ.get("UPSTAGE_API_KEY")
if not UPSTAGE_API_KEY:
    st.error("Upstage API 키가 필요합니다. .env 파일에 UPSTAGE_API_KEY를 설정해주세요.")
    st.stop()

@st.cache_resource
def init_recommender():
    data_path = os.path.join(os.path.dirname(__file__), 'data')
    embedding_model = os.environ.get("UPSTAGE_EMBEDDING_MODEL", "solar-embedding-1-large")
    return VectorBasedRecommender(data_path=data_path, embedding_model=embedding_model)

@st.cache_resource
def init_llm():
    return ChatUpstage(api_key=UPSTAGE_API_KEY)

recommender = init_recommender()
llm = init_llm()

# --- LangGraph 상태 및 노드 정의 --- #

class GraphState(TypedDict):
    user_query: str
    parsed_json: dict
    rerank_weights: dict
    candidate_appids: List[int]
    query_vector: np.ndarray
    final_results: Any

# 래퍼 함수
def build_parser_node(state): return llm_parser_node(state, llm)
def build_normalizer_node(state): return game_name_normalizer_node(state, recommender)
def build_similar_node(state): return similar_node(state, recommender)
def build_vibe_node(state): return vibe_node(state, recommender)
def build_hybrid_node(state): return hybrid_node(state, recommender)
def build_steam_similar_node(state): return steam_similar_node(state, recommender) # ⭐️ 새로 추가
def build_response_generator_node(state): return generate_response_node(state, llm)

def rerank_node(state: GraphState):
    appids = state['candidate_appids']
    query_vec = state['query_vector']
    weights = state['rerank_weights']
    reranked_df = recommender.rerank_candidates(appids, query_vec, weights, top_n=5)
    state['final_results'] = reranked_df
    return state

def route_by_input_type(state: GraphState):
    if state.get('parsed_json', {}).get('is_steam_request', False):
        return "steam_similar_node"
    return "parser_node"

def entry_point_node(state: GraphState):
    """A dummy entry point node that does nothing."""
    return {}

# --- 그래프 빌드 --- #
workflow = StateGraph(GraphState)
workflow.add_node("entry", entry_point_node) # ⭐️ 더미 진입점 노드
workflow.add_node("parser_node", build_parser_node)
workflow.add_node("normalizer_node", build_normalizer_node)
workflow.add_node("similar_node", build_similar_node)
workflow.add_node("vibe_node", build_vibe_node)
workflow.add_node("hybrid_node", build_hybrid_node)
workflow.add_node("steam_similar_node", build_steam_similar_node)
workflow.add_node("rerank_node", rerank_node)
workflow.add_node("general_node", general_node)
workflow.add_node("response_generator_node", build_response_generator_node)

workflow.set_entry_point("entry") # ⭐️ 진입점을 더미 노드로 설정

# ⭐️ 진입점 노드 다음에 분기 로직을 연결
workflow.add_conditional_edges("entry", route_by_input_type, {
    "parser_node": "parser_node",
    "steam_similar_node": "steam_similar_node"
})

workflow.add_edge("parser_node", "normalizer_node")
workflow.add_conditional_edges(
    "normalizer_node", 
    route_by_mode,
    {
        "similar_node": "similar_node", "vibe_node": "vibe_node",
        "hybrid_node": "hybrid_node", "general_node": "general_node",
    }
)

workflow.add_edge('similar_node', 'rerank_node')
workflow.add_edge('vibe_node', 'rerank_node')
workflow.add_edge('hybrid_node', 'rerank_node')
workflow.add_edge('steam_similar_node', 'rerank_node') # ⭐️ steam 노드에서 rerank로 연결
workflow.add_edge('rerank_node', 'response_generator_node')
workflow.add_edge('general_node', END)
workflow.add_edge('response_generator_node', END)

app_graph = workflow.compile(checkpointer=None, debug=True).with_config({"recursion_limit": 10})


# --- 그래프 실행 로직 --- #
def run_graph(graph_input: dict):
    with st.status("추천 파이프라인 실행 중...", expanded=True) as status_container:
        executed_nodes = []
        latest_state = None

        for event in app_graph.stream(graph_input):
            for node_name, node_state in event.items():
                # 'input_router'는 내부 로직이므로 UI에 표시하지 않음
                if node_name == 'input_router':
                    continue
                
                executed_nodes.append(node_name)
                path_str = " -> ".join(f"`{node}`" for node in executed_nodes)
                st.markdown(f"**현재 실행 노드:** `{node_name}`")
                st.markdown(f"**전체 실행 경로:** {path_str}")

                with st.expander(f"`{node_name}` 실행 결과 보기"):
                    # UI 로직 (기존과 동일)
                    if node_name == "parser_node":
                        st.markdown("LLM이 사용자의 쿼리를 분석하여 추천 모드와 키워드를 추출합니다.")
                        st.json(node_state.get('parsed_json', {}))
                    elif node_name == "normalizer_node":
                        st.markdown("쿼리에 포함된 게임 이름이 데이터베이스에 있는지 확인하고 표준화합니다.")
                        st.write("**:red[변경 전]**", latest_state.get('parsed_json', {}))
                        st.write("**:blue[변경 후]**", node_state.get('parsed_json', {}))
                    elif node_name in ["similar_node", "vibe_node", "hybrid_node", "steam_similar_node"]:
                        st.markdown(f"`{node_name}`에 따라 후보 게임 목록을 생성합니다.")
                        candidate_ids = node_state.get('candidate_appids', [])
                        st.write("후보 AppIDs:", candidate_ids)
                        if candidate_ids:
                            df = recommender.games_df.loc[candidate_ids]
                            st.dataframe(df[['game_title', 'tags']])
                    elif node_name == "rerank_node":
                        st.markdown("후보 게임 목록을 사용자가 설정한 가중치에 따라 재정렬하여 최종 5개 게임을 선택합니다.")
                        st.dataframe(node_state.get('final_results'))
                    elif node_name == "response_generator_node":
                        st.markdown("최종 추천 목록을 바탕으로 자연스러운 추천사를 생성합니다.")
                        st.info(node_state.get('final_results'))
                    elif node_name == "general_node":
                        st.markdown("일반적인 대화형 응답을 생성합니다.")
                        st.info(node_state.get('final_results'))

                latest_state = node_state
                st.markdown("---")

        status_container.update(label="추천 완료!", state="complete", expanded=False)

    final_state = latest_state
    if final_state:
        response_content = final_state.get('final_results', "오류: 최종 응답을 생성하지 못했습니다.")
        with st.chat_message("assistant"):
            if isinstance(response_content, pd.DataFrame):
                st.markdown("### 최종 추천 게임 목록")
                st.dataframe(response_content)
                st.session_state.messages.append(AIMessage(content=response_content.to_markdown(index=False)))
            else:
                st.markdown(str(response_content))
                st.session_state.messages.append(AIMessage(content=str(response_content)))
    else:
        with st.chat_message("assistant"):
            st.error("추천을 생성하지 못했습니다 (그래프가 완료되지 않음).")


# --- Streamlit UI --- #
st.title("✨ 게임 추천 서비스")

with st.sidebar:
    st.header("재정렬 가중치 설정")
    st.caption("각 요소의 중요도를 0~10점으로 평가해주세요.")
    user_weights = {
        "tag_match": st.slider("TagMatch (쿼리-게임 유사도)", 0, 10, 8),
        "novelty": st.slider("Novelty (새로움)", 0, 10, 2),
    }

    st.divider()
    st.header("Steam 플레이 기록으로 추천")
    steam_profile_url = st.text_input("Steam 프로필 URL을 입력하세요 (예: https://steamcommunity.com/id/your_id/)", key="steam_url_input")
    
    if st.button("플레이 기록으로 추천 생성"):
        STEAM_API_KEY = os.environ.get("STEAM_API_KEY")
        if not steam_profile_url:
            st.error("Steam 프로필 URL을 입력해주세요.")
        elif not STEAM_API_KEY:
            st.error("Steam API 키가 필요합니다. .env 파일에 STEAM_API_KEY를 설정해주세요.")
        else:
            with st.spinner("Steam 플레이 기록을 가져와 추천을 생성하는 중..."):
                from st_app.steam_api import get_games_from_profile_url
                games_list = get_games_from_profile_url(STEAM_API_KEY, steam_profile_url)
                
                if games_list:
                    st.success(f"총 {len(games_list)}개의 게임 기록을 발견했습니다.")
                    games_df = pd.DataFrame(games_list)
                    games_df['playtime_hours'] = games_df['playtime_forever'] / 60
                    played_games_df = games_df[games_df['playtime_hours'] > 0].copy()
                    
                    # ⭐️ 플레이 시간을 가중치로 변환 (로그 스케일)
                    played_games_df['weight'] = np.log1p(played_games_df['playtime_hours'])
                    
                    games_with_weights = played_games_df[['name', 'weight']].to_dict('records')

                    # ⭐️ 그래프 실행
                    graph_input = {
                        "user_query": "Steam 라이브러리 기반 추천",
                        "rerank_weights": user_weights,
                        "parsed_json": {
                            "is_steam_request": True,
                            "steam_games": games_with_weights
                        }
                    }
                    st.session_state.messages.append(HumanMessage(content=f"Steam 프로필({steam_profile_url}) 기반으로 추천을 요청했습니다."))
                    st.chat_message("user").write(f"Steam 프로필 기반 추천")
                    run_graph(graph_input)
                else:
                    st.error("플레이 기록을 가져오지 못했습니다. 프로필이 비공개이거나 URL이 잘못되었을 수 있습니다.")

if "messages" not in st.session_state:
    st.session_state.messages = [AIMessage(content="안녕하세요! 어떤 게임을 추천해드릴까요?")]

for msg in st.session_state.messages:
    st.chat_message("assistant" if isinstance(msg, (AIMessage, SystemMessage)) else "user").write(msg.content)

if prompt := st.chat_input("질문을 입력하세요."):
    st.session_state.messages.append(HumanMessage(content=prompt))
    st.chat_message("user").write(prompt)
    
    graph_input = {
        "user_query": prompt, 
        "rerank_weights": user_weights,
        "parsed_json": {"is_steam_request": False} # ⭐️ 일반 채팅 요청임을 명시
    }
    run_graph(graph_input)
