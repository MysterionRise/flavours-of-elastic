import unittest
from unittest import mock

from search import inference, loader, queries
from search.capabilities import Capabilities
from search.client import PortfolioSearchClient
from search.config import Target
from search.connection import EsError
from search.embedders import E5_IN_CLUSTER, for_meta
from search.evaluate import below_floors
from search.mappings import SEMANTIC_FIELD, index_body

BASIC = Capabilities("elasticsearch", "8.19.0", "basic")
ML = Capabilities("elasticsearch", "9.5.0", "trial", ml_nodes=2)
PLATINUM_ML = Capabilities("elasticsearch", "8.19.0", "platinum", ml_nodes=1)


def deploying():
    return EsError(
        408,
        "POST",
        "/_inference",
        {"error": {"type": "model_deployment_timeout_exception", "reason": "wait"}},
    )


class WarmTests(unittest.TestCase):
    def test_retries_until_the_endpoint_answers(self):
        client = mock.Mock()
        client.post.side_effect = [deploying(), deploying(), {"text_embedding": []}]
        with mock.patch("time.sleep"):
            inference.warm(client, inference.E5, timeout=60, progress=lambda _: None)
        self.assertEqual(client.post.call_count, 3)
        self.assertEqual(
            client.post.call_args.args[0], f"/_inference/text_embedding/{inference.E5}"
        )

    def test_gives_up_after_the_timeout(self):
        client = mock.Mock()
        client.post.side_effect = deploying()
        with (
            mock.patch("time.sleep"),
            mock.patch("time.monotonic", side_effect=[0, 0, 1000]),
        ):
            with self.assertRaisesRegex(inference.InferenceNotReady, "not ready after"):
                inference.warm(
                    client, inference.ELSER, timeout=900, progress=lambda _: None
                )

    def test_missing_endpoint_fails_fast(self):
        client = mock.Mock()
        client.post.side_effect = EsError(
            404, "POST", "/_inference", {"error": "missing"}
        )
        with self.assertRaisesRegex(inference.InferenceNotReady, "does not exist"):
            inference.warm(client, inference.E5, progress=lambda _: None)

    def test_pipeline_drops_the_model_id_field(self):
        processors = inference.e5_pipeline("searchable_text", "overview_embedding")[
            "processors"
        ]
        self.assertEqual(processors[0]["inference"]["model_id"], inference.E5)
        self.assertEqual(
            processors[1], {"remove": {"field": "model_id", "ignore_missing": True}}
        )


class LoaderTests(unittest.TestCase):
    def test_inference_needs_an_ml_stack(self):
        for embeddings, elser in (("e5", False), ("none", True)):
            with self.assertRaisesRegex(loader.Refused, "elk-ml"):
                loader.check_capabilities(BASIC, embeddings, elser)
        loader.check_capabilities(ML, "e5", True)

    def test_endpoints(self):
        self.assertEqual(
            loader.endpoints_for("e5", True), [inference.E5, inference.ELSER]
        )
        self.assertEqual(loader.endpoints_for("hash", False), [])

    def test_index_body_with_pipeline_and_semantic_text(self):
        body = index_body(
            ML, {}, 384, semantic_inference=inference.ELSER, default_pipeline="p"
        )
        self.assertEqual(body["settings"], {"index": {"default_pipeline": "p"}})
        self.assertEqual(
            body["mappings"]["properties"][SEMANTIC_FIELD],
            {"type": "semantic_text", "inference_id": inference.ELSER},
        )

    def test_warm_only_exits_6_when_not_ready(self):
        target = mock.Mock()
        target.client.return_value = mock.Mock()
        with (
            mock.patch.object(loader, "resolve", return_value=target),
            mock.patch.object(loader, "detect", return_value=ML),
            mock.patch.object(
                loader, "warm", side_effect=inference.InferenceNotReady("slow")
            ),
            mock.patch("sys.stderr"),
            mock.patch("sys.stdout"),
        ):
            self.assertEqual(loader.main(["--warm-only"]), loader.EXIT_INFERENCE)


class QueryTests(unittest.TestCase):
    def test_e5_queries_use_the_vector_builder(self):
        builder = E5_IN_CLUSTER.query_vector("prison escape")
        self.assertEqual(builder["text_embedding"]["model_id"], inference.E5)
        knn = queries.dense(builder, 10, 50, "elasticsearch")["knn"]
        self.assertIn("query_vector_builder", knn)
        self.assertNotIn("query_vector", knn)
        self.assertIs(
            for_meta({"backend": "e5", "model": inference.E5, "dims": 384}, "x"),
            E5_IN_CLUSTER,
        )

    def test_rrf_all_has_three_retrievers(self):
        retrievers = queries.rrf_all("q", [0.1], 10, 50, 60)["retriever"]["rrf"][
            "retrievers"
        ]
        self.assertEqual(len(retrievers), 3)
        self.assertEqual(
            retrievers[2]["standard"]["query"]["semantic"]["field"], SEMANTIC_FIELD
        )

    def test_hybrid_all_fuses_three_legs_without_the_retriever(self):
        client = PortfolioSearchClient(target=Target("http://es", None, True, "test"))
        client._caps = PLATINUM_ML  # ML but no rrf retriever
        client._embedders["movies-embeddings"] = E5_IN_CLUSTER
        client.http = mock.Mock()
        client.http.post.return_value = {
            "took": 1,
            "hits": {"hits": [{"_id": "1", "_source": {"id": 1}}]},
        }
        response = client.search("q", mode="hybrid_all")
        self.assertEqual((response.fusion, response.embedding), ("client", "e5"))
        self.assertEqual(client.http.post.call_count, 3)


class FloorTests(unittest.TestCase):
    def test_embedding_specific_floors_win(self):
        output = {
            "dense": {
                "summary": {
                    "k": 10,
                    "ndcg": 0.7,
                    "mrr": 0.7,
                    "recall": 0.9,
                    "embedding": "e5",
                }
            }
        }
        floors = {"modes": {"dense": {"ndcg": 0.6}, "dense@e5": {"ndcg": 0.8}}}
        self.assertEqual(
            below_floors(output, floors), ["dense@e5 ndcg@10 0.700 < floor 0.8"]
        )
        output["dense"]["summary"]["embedding"] = "hash"
        self.assertEqual(below_floors(output, floors), [])


if __name__ == "__main__":
    unittest.main()
