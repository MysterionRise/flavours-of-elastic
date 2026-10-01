#!/usr/bin/env python3
"""Streamlit UI for comparing search modes side by side."""

import re
import sys
from pathlib import Path

import streamlit as st

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from search.client import PortfolioSearchClient  # noqa: E402

MARKDOWN_SPECIAL = re.compile(r"([\\`*_{}\[\]<>()#+\-.!|~$])")


def md_escape(text) -> str:
    """Show titles and overviews literally (e.g. `*batteries not included`, `$9.99`)."""
    return MARKDOWN_SPECIAL.sub(r"\\\1", str(text or ""))


@st.cache_resource
def get_client() -> PortfolioSearchClient:
    return PortfolioSearchClient()


@st.cache_data(ttl=60, show_spinner=False)
def run_search(query: str, mode: str, k: int, num_candidates: int, rank_constant: int):
    return get_client().search(
        query=query,
        mode=mode,
        k=k,
        num_candidates=num_candidates,
        rank_constant=rank_constant,
    )


st.set_page_config(page_title="Flavours of Elastic Search Demo", layout="wide")

st.title("Flavours of Elastic")
st.caption("BM25, dense vector, hybrid RRF and ELSER movie search")

try:
    client = get_client()
    info = client.cluster_info()
    available = client.modes()
except Exception as exc:  # noqa: BLE001 - shown to the user
    st.error(f"Search cluster is not reachable: {exc}")
    st.stop()

st.success(
    f"Connected to {info.get('cluster_name', 'search cluster')} ({client.caps.describe()})"
)

with st.sidebar:
    st.header("Search")
    query = st.text_input("Query", value="space adventure friendship")
    modes = st.multiselect("Modes", options=available, default=available)
    k = st.slider("Results", min_value=3, max_value=20, value=10)
    num_candidates = st.slider(
        "Vector candidates", min_value=10, max_value=200, value=50, step=10
    )
    rank_constant = st.slider(
        "RRF rank constant", min_value=10, max_value=100, value=60, step=5
    )
    if "hybrid_rrf" in available and not client.caps.rrf:
        st.caption(
            "Hybrid uses client-side RRF: the `rrf` retriever needs a trial or enterprise licence."
        )

if not query.strip():
    st.info("Enter a query to search.")
    st.stop()

columns = st.columns(max(1, len(modes)))

for column, mode in zip(columns, modes, strict=False):
    with column:
        st.subheader(mode)
        try:
            response = run_search(query, mode, k, num_candidates, rank_constant)
        except Exception as exc:  # noqa: BLE001 - shown to the user
            st.error(str(exc))
            continue
        fusion = f" | {response.fusion}-side fusion" if response.fusion else ""
        st.caption(
            f"{response.took_ms:.1f} ms client-side | {response.engine_took_ms} ms engine{fusion}"
        )
        for hit in response.hits:
            genres = ", ".join(hit.get("genres") or [])
            year = hit.get("year") or "unknown year"
            st.markdown(f"**{hit['rank']}. {md_escape(hit['title'])}** ({year})")
            st.caption(
                f"ID {hit['id']} | score {hit.get('score')} | {md_escape(genres)}"
            )
            overview = hit.get("overview") or hit.get("description_en") or ""
            st.markdown(
                md_escape(overview[:320] + ("..." if len(overview) > 320 else ""))
            )

st.divider()
st.markdown(
    "Run `make evaluate` in another terminal to compare NDCG@10, MRR@10, Recall@10, and latency "
    "for the hand-labeled query set."
)
st.caption(
    "Movie titles, genres and ratings: [MovieLens ml-32m](https://grouplens.org/datasets/movielens/32m/) "
    "(F. M. Harper and J. A. Konstan, 2015), non-commercial use. Overviews are LLM-generated. "
    "See data/LICENSE-DATA.md."
)
