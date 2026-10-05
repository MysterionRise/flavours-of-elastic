"""Smoke tests for the Streamlit demo (apps/search_demo/Home.py) against a fake client."""

import logging
import unittest
from importlib.util import find_spec
from pathlib import Path
from unittest import mock

from search.capabilities import Capabilities
from search.client import SearchResponse

HOME = Path(__file__).resolve().parents[1] / "apps" / "search_demo" / "Home.py"
BASIC = Capabilities("elasticsearch", "8.19.0", "basic")


class FakeClient:
    """What Home.py uses of PortfolioSearchClient; configured per test."""

    info_error: Exception | None = None
    available = ["bm25", "dense", "hybrid_rrf"]
    failing_mode: str | None = None

    def __init__(self, *args, **kwargs):
        self.caps = BASIC

    def cluster_info(self):
        if self.info_error:
            raise self.info_error
        return {"cluster_name": "fake-cluster"}

    def modes(self):
        return list(self.available)

    def search(self, query, mode, k, num_candidates, rank_constant):
        if mode == self.failing_mode:
            raise RuntimeError(f"{mode} is broken")
        hits = [
            {
                "rank": 1,
                "id": 6,
                "score": 1.5,
                "title": "*batteries not included",
                "year": 1987,
                "genres": ["Sci-Fi"],
                "overview": f"{mode}: tiny robots fix a tenement.",
            }
        ]
        fusion = "client" if mode == "hybrid_rrf" else None
        return SearchResponse(mode, query, hits, 3.2, 2, fusion=fusion)


@unittest.skipUnless(find_spec("streamlit"), "streamlit not installed (--extra demo)")
class SearchDemoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Clearing the caches outside a Streamlit runtime logs "bare mode" warnings.
        logging.getLogger("streamlit").setLevel(logging.ERROR)

    def run_app(self, **config):
        import streamlit as st
        from streamlit.testing.v1 import AppTest

        st.cache_resource.clear()
        st.cache_data.clear()
        fake = type("Fake", (FakeClient,), config)
        with mock.patch("search.client.PortfolioSearchClient", fake):
            app = AppTest.from_file(str(HOME), default_timeout=30)
            app.run()
        self.assertFalse(app.exception, [e.value for e in app.exception])
        return app

    def test_unreachable_cluster_shows_an_error(self):
        app = self.run_app(info_error=ConnectionError("connection refused"))
        self.assertEqual(len(app.error), 1)
        self.assertIn("not reachable", app.error[0].value)
        self.assertIn("connection refused", app.error[0].value)
        self.assertFalse(app.subheader)

    def test_every_mode_renders_a_column(self):
        app = self.run_app()
        self.assertIn("fake-cluster", app.success[0].value)
        self.assertEqual([h.value for h in app.subheader], FakeClient.available)
        self.assertTrue(
            any("client-side RRF" in c.value for c in app.sidebar.caption),
            "basic licence: hybrid explains client-side fusion",
        )
        captions = [c.value for c in app.caption]
        self.assertTrue(any("client-side fusion" in c for c in captions))
        titles = [m.value for m in app.markdown if "batteries" in m.value]
        self.assertEqual(len(titles), len(FakeClient.available))
        # The leading `*` is escaped, so Markdown shows it instead of starting emphasis.
        self.assertTrue(all(r"\*batteries not included" in t for t in titles))

    def test_a_failing_mode_does_not_hide_the_others(self):
        app = self.run_app(failing_mode="dense")
        self.assertEqual([e.value for e in app.error], ["dense is broken"])
        self.assertEqual([h.value for h in app.subheader], FakeClient.available)
        overviews = [m.value for m in app.markdown if "tiny robots" in m.value]
        self.assertEqual(len(overviews), 2)


if __name__ == "__main__":
    unittest.main()
