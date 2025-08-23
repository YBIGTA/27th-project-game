
import streamlit as st
import os
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
    generate_response_node
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
    return VectorBasedRecommender(data_path=data_path)

@st.cache_resource
def init_llm():
    # ChatOpenAI 대신 ChatUpstage 사용
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
    final_results: Any # Can be DataFrame or final string

# 각 노드에 리소스(llm, recommender)를 주입하는 래퍼 함수
def build_parser_node(state): return llm_parser_node(state, llm)
def build_similar_node(state): return similar_node(state, recommender)
def build_vibe_node(state): return vibe_node(state, recommender)
def build_hybrid_node(state): return hybrid_node(state, recommender)
def build_response_generator_node(state): return generate_response_node(state, llm)

def rerank_node(state: GraphState):
    appids = state['candidate_appids']
    query_vec = state['query_vector']
    weights = state['rerank_weights']
    reranked_df = recommender.rerank_candidates(appids, query_vec, weights, top_n=5)
    state['final_results'] = reranked_df
    return state

# --- 그래프 빌드 --- #
workflow = StateGraph(GraphState)
workflow.add_node("parser_node", build_parser_node)
workflow.add_node("similar_node", build_similar_node)
workflow.add_node("vibe_node", build_vibe_node)
workflow.add_node("hybrid_node", build_hybrid_node)
workflow.add_node("rerank_node", rerank_node)
workflow.add_node("general_node", general_node)
workflow.add_node("response_generator_node", build_response_generator_node)

workflow.set_entry_point("parser_node")
workflow.add_conditional_edges(
    "parser_node", route_by_mode,
    {
        "similar_node": "similar_node", "vibe_node": "vibe_node",
        "hybrid_node": "hybrid_node", "general_node": "general_node",
    }
)

workflow.add_edge('similar_node', 'rerank_node')
workflow.add_edge('vibe_node', 'rerank_node')
workflow.add_edge('hybrid_node', 'rerank_node')
workflow.add_edge('rerank_node', 'response_generator_node')
workflow.add_edge('general_node', END)
workflow.add_edge('response_generator_node', END)

app_graph = workflow.compile()

# --- Streamlit UI --- #
st.title("✨ LangGraph RAG 챗봇")

with st.sidebar:
    st.header("재정렬 가중치 설정")
    st.caption("각 요소의 중요도를 0~10점으로 평가해주세요.")
    user_weights = {
        "tag_match": st.slider("TagMatch (쿼리-게임 유사도)", 0, 10, 8),
        "novelty": st.slider("Novelty (새로움)", 0, 10, 2),
    }

if "messages" not in st.session_state:
    st.session_state.messages = [AIMessage(content="안녕하세요! 어떤 게임을 추천해드릴까요?")]

for msg in st.session_state.messages:
    if isinstance(msg, AIMessage):
        st.chat_message("assistant").write(msg.content)
    elif isinstance(msg, HumanMessage):
        st.chat_message("user").write(msg.content)
    elif isinstance(msg, SystemMessage):
        st.chat_message("assistant").write(msg.content)

if prompt := st.chat_input("질문을 입력하세요."):
    st.session_state.messages.append(HumanMessage(content=prompt))
    st.chat_message("user").write(prompt)

    with st.spinner("추천 중..."):
        try:
            graph_input = {"user_query": prompt, "rerank_weights": user_weights}
            final_state = app_graph.invoke(graph_input)
            response_content = final_state.get('final_results', "오류: 최종 응답을 생성하지 못했습니다.")
        except Exception as e:
            response_content = f"오류가 발생했습니다: {e}"

    st.session_state.messages.append(AIMessage(content=response_content))
    st.chat_message("assistant").write(response_content)
