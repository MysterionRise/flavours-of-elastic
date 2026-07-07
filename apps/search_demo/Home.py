#!/usr/bin/env python3
"""Streamlit UI for comparing portfolio search modes."""

import sys
from pathlib import Path

import streamlit as st

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from search.client import PortfolioSearchClient  # noqa: E402

st.set_page_config(page_title="Flavours of Elastic Search Demo", layout="wide")

st.title("Flavours of Elastic")
st.caption("BM25, dense vector, and hybrid RRF movie search")

with st.sidebar:
    st.header("Search")
    query = st.text_input("Query", value="space adventure friendship")
    modes = st.multiselect(
        "Modes",
        options=["bm25", "dense", "hybrid_rrf"],
        default=["bm25", "dense", "hybrid_rrf"],
    )
    k = st.slider("Results", min_value=3, max_value=20, value=10)
    num_candidates = st.slider(
        "Vector candidates", min_value=10, max_value=200, value=50, step=10
    )
    rank_constant = st.slider(
        "RRF rank constant", min_value=10, max_value=100, value=60, step=5
    )


client = PortfolioSearchClient()

try:
    info = client.cluster_info()
    st.success(f"Connected to {info.get('cluster_name', 'search cluster')}")
except Exception as exc:
    st.error(f"Search cluster is not reachable: {exc}")
    st.stop()


if not query.strip():
    st.info("Enter a query to search.")
    st.stop()

columns = st.columns(max(1, len(modes)))

for column, mode in zip(columns, modes):
    with column:
        st.subheader(mode)
        try:
            response = client.search(
                query=query,
                mode=mode,
                k=k,
                num_candidates=num_candidates,
                rank_constant=rank_constant,
            )
            st.caption(
                f"{response.took_ms:.1f} ms client-side | {response.engine_took_ms} ms engine"
            )
            for hit in response.hits:
                genres = ", ".join(hit.get("genres") or [])
                year = hit.get("year") or "unknown year"
                st.markdown(f"**{hit['rank']}. {hit['title']}** ({year})")
                st.caption(f"ID {hit['id']} | score {hit.get('score')} | {genres}")
                overview = hit.get("overview") or hit.get("description_en") or ""
                st.write(overview[:320] + ("..." if len(overview) > 320 else ""))
        except Exception as exc:
            st.error(str(exc))

st.divider()
st.markdown(
    "Run `make evaluate` in another terminal to compare NDCG@10, MRR@10, Recall@10, and latency "
    "for the hand-labeled query set."
)
