import argparse
import unittest
from unittest import mock

from search import evaluate, queries
from search.capabilities import Capabilities
from search.client import PortfolioSearchClient, SearchResponse
from search.config import Target
from search.embedders import HASH, EmbedderMismatch, for_meta
from search.mappings import VECTOR_FIELD

BASIC = Capabilities("elasticsearch", "8.19.0", "basic")
TRIAL = Capabilities("elasticsearch", "9.5.0", "trial", ml_nodes=2)
OPENSEARCH = Capabilities("opensearch", "3.9.0", None)


def hit(doc_id, score=1.0):
    return {
        "_id": str(doc_id),
        "_score": score,
        "_source": {"id": doc_id, "title": f"m{doc_id}"},
    }


class QueryTests(unittest.TestCase):
    def test_dense_sets_size_and_candidates(self):
        body = queries.dense([0.1], k=5, num_candidates=3, distribution="elasticsearch")
        self.assertEqual(body["size"], 5)
        self.assertEqual((body["knn"]["k"], body["knn"]["num_candidates"]), (5, 5))

    def test_opensearch_dense_is_a_knn_query(self):
        body = queries.dense([0.1], k=5, num_candidates=50, distribution="opensearch")
        self.assertEqual(body["query"]["knn"][VECTOR_FIELD]["k"], 50)
        self.assertNotIn("knn", body)

    def test_rrf_knn_leg_covers_the_window(self):
        body = queries.rrf("q", [0.1], k=10, num_candidates=50, rank_constant=60)
        rrf = body["retriever"]["rrf"]
        self.assertEqual(rrf["rank_window_size"], 50)
        self.assertEqual(rrf["retrievers"][1]["knn"]["k"], 50)

    def test_bm25_searches_french_and_kazakh_fields(self):
        fields = queries.bm25("q", 10)["query"]["multi_match"]["fields"]
        self.assertIn("abstract_fr", fields)
        self.assertIn("description_kk", fields)

    def test_rrf_fuse(self):
        fused = queries.rrf_fuse(
            [["a", "b", "c"], ["b", "d"]], rank_constant=60, size=3
        )
        self.assertEqual([doc for doc, _ in fused], ["b", "a", "d"])
        self.assertAlmostEqual(fused[0][1], 1 / 62 + 1 / 61)


class EmbedderTests(unittest.TestCase):
    def test_hash_meta(self):
        self.assertIs(
            for_meta({"backend": "hash", "model": HASH.model, "dims": 384}, "x"), HASH
        )

    def test_mismatches_are_refused(self):
        for meta in (
            None,
            {"backend": "hash", "model": "foe-hash-v1", "dims": 384},
            {"backend": "e5", "model": "x"},
        ):
            with self.assertRaises(EmbedderMismatch):
                for_meta(meta, "movies-embeddings")


def client_for(caps, responses):
    client = PortfolioSearchClient(target=Target("http://es:9200", None, True, "test"))
    client._caps = caps
    client._embedders["movies-embeddings"] = HASH
    client.http = mock.Mock()
    client.http.post.side_effect = responses
    return client


class ClientTests(unittest.TestCase):
    def test_basic_licence_fuses_client_side(self):
        lexical = {"took": 2, "hits": {"hits": [hit(1, 9.0), hit(2, 5.0)]}}
        semantic = {"took": 3, "hits": {"hits": [hit(2, 0.9), hit(3, 0.8)]}}
        client = client_for(BASIC, [lexical, semantic])
        response = client.search("q", mode="hybrid_rrf", k=3)
        self.assertEqual(response.fusion, "client")
        self.assertEqual([h["id"] for h in response.hits], [2, 1, 3])
        self.assertEqual(response.engine_took_ms, 5)

    def test_trial_uses_the_retriever(self):
        client = client_for(TRIAL, [{"took": 1, "hits": {"hits": [hit(7)]}}])
        response = client.search("q", mode="hybrid_rrf")
        self.assertEqual(response.fusion, "server")
        self.assertIn("retriever", client.http.post.call_args.args[1])

    def test_opensearch_dense(self):
        client = client_for(OPENSEARCH, [{"took": 1, "hits": {"hits": [hit(4)]}}])
        client.search("q", mode="dense")
        self.assertIn("query", client.http.post.call_args.args[1])

    def test_modes_follow_capabilities(self):
        client = client_for(Capabilities("elasticsearch-oss", "7.10.2", None), [])
        self.assertEqual(client.modes(), ["bm25"])
        client = client_for(BASIC, [])
        self.assertEqual(client.modes(), ["bm25", "dense", "hybrid_rrf"])


class SeenTextClient:
    """Fakes a cluster that reuses inference work: a text's first request is slow."""

    def __init__(self):
        self.calls, self.seen = [], set()

    def ids_present(self, index, ids):
        return set(ids)

    def search(self, text, mode, **kwargs):
        self.calls.append((text, mode))
        took = 1.0 if text in self.seen else 50.0
        self.seen.add(text)
        return SearchResponse(mode, text, [{"id": 1}], took)


class EvaluateTests(unittest.TestCase):
    MODES = ["bm25", "dense", "hybrid_rrf"]
    QUERIES = [{"id": f"q{i}", "text": f"t{i}", "relevant_ids": [1]} for i in range(6)]

    def args(self, warmup=1):
        return argparse.Namespace(
            k=10, num_candidates=50, rank_constant=60, warmup=warmup
        )

    def test_warmup_rotates_the_first_mode(self):
        client = SeenTextClient()
        evaluate.evaluate(client, self.MODES, self.QUERIES, self.args())
        warmup_calls = client.calls[: len(self.QUERIES) * len(self.MODES)]
        firsts = [
            mode for i, (_, mode) in enumerate(warmup_calls) if i % len(self.MODES) == 0
        ]
        self.assertEqual(firsts, self.MODES * 2)
        self.assertEqual(len(client.calls), 2 * len(self.QUERIES) * len(self.MODES))

    def test_cold_and_warm_latency(self):
        output = evaluate.evaluate(
            SeenTextClient(), self.MODES, self.QUERIES, self.args()
        )
        for mode in self.MODES:
            summary = output[mode]["summary"]
            self.assertEqual(summary["p50_cold_latency_ms"], 50.0)
            self.assertEqual(summary["cold_queries"], 2)
            # Every mode is timed warm, whatever its position in the mode list.
            self.assertEqual(summary["p50_latency_ms"], 1.0)

    def test_without_warmup_the_order_decides_latency(self):
        output = evaluate.evaluate(
            SeenTextClient(), self.MODES, self.QUERIES, self.args(0)
        )
        self.assertEqual(output["bm25"]["summary"]["p50_latency_ms"], 50.0)
        self.assertEqual(output["dense"]["summary"]["p50_latency_ms"], 1.0)
        self.assertNotIn("p50_cold_latency_ms", output["bm25"]["summary"])

    def test_extra_warmup_passes_are_untimed(self):
        client = SeenTextClient()
        output = evaluate.evaluate(client, self.MODES, self.QUERIES, self.args(3))
        self.assertEqual(len(client.calls), 4 * len(self.QUERIES) * len(self.MODES))
        self.assertEqual(output["dense"]["summary"]["cold_queries"], 2)

    def test_one_failing_mode_does_not_hide_the_others(self):
        client = mock.Mock()
        client.ids_present.return_value = {1}
        client.search.side_effect = lambda text, mode, **kwargs: (
            SearchResponse(mode, text, [{"id": 1}], 1.0)
            if mode == "bm25"
            else (_ for _ in ()).throw(RuntimeError("no vectors"))
        )
        output = evaluate.evaluate(
            client,
            ["bm25", "dense"],
            [{"id": "q", "text": "t", "relevant_ids": [1, 2]}],
            self.args(),
        )
        self.assertEqual(output["bm25"]["summary"]["mrr"], 1.0)
        self.assertEqual(output["bm25"]["missing_judged_ids"], [2])
        self.assertIn("no vectors", output["dense"]["error"])
        # The warm-up gave up on dense after its first failure.
        modes_called = [call.kwargs["mode"] for call in client.search.call_args_list]
        self.assertEqual(modes_called.count("dense"), 1)

    def test_floors(self):
        output = {
            "bm25": {"summary": {"k": 10, "ndcg": 0.5, "mrr": 0.9, "recall": 1.0}},
            "dense": {"error": "x"},
        }
        floors = {"modes": {"bm25": {"ndcg": 0.8, "mrr": 0.8}, "dense": {"ndcg": 0.5}}}
        self.assertEqual(
            evaluate.below_floors(output, floors), ["bm25 ndcg@10 0.500 < floor 0.8"]
        )


if __name__ == "__main__":
    unittest.main()
