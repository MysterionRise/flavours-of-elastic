import json
import unittest
from unittest import mock

from search import config, loader
from search.capabilities import Capabilities, detect
from search.connection import Client, ConnectionFailed, EsError, error_details
from search.embeddings import deterministic_text_embedding, tokenize
from search.mappings import VECTOR_FIELD, index_body

ES8 = Capabilities("elasticsearch", "8.19.0", "basic")
ES9_TRIAL = Capabilities("elasticsearch", "9.5.0", "trial", ml_nodes=2)
OPENSEARCH = Capabilities("opensearch", "3.9.0", None)
OSS = Capabilities("elasticsearch-oss", "7.10.2", None)


class FakeResponse:
    def __init__(self, status, payload=None, method="GET"):
        self.status_code = status
        self._payload = payload
        self.content = b"" if payload is None else json.dumps(payload).encode()
        self.request = mock.Mock(method=method)

    def json(self):
        return self._payload


def client_with(*responses):
    client = Client("http://es:9200", backoff=0)
    client._session = mock.Mock()
    client._session.request.side_effect = list(responses)
    return client


class ConnectionTests(unittest.TestCase):
    def test_error_details_prefer_root_cause(self):
        payload = {
            "error": {
                "type": "search_phase_execution_exception",
                "root_cause": [
                    {"type": "index_not_found_exception", "reason": "no such index [x]"}
                ],
            },
            "status": 404,
        }
        self.assertEqual(
            error_details(payload), ("index_not_found_exception", "no such index [x]")
        )
        self.assertEqual(error_details({"error": "plain"}), ("", "plain"))

    def test_retries_429_then_succeeds(self):
        client = client_with(FakeResponse(429, {}), FakeResponse(200, {"ok": True}))
        self.assertEqual(client.get("/"), {"ok": True})
        self.assertEqual(client._session.request.call_count, 2)

    def test_error_keeps_the_engine_reason(self):
        client = client_with(
            FakeResponse(
                400, {"error": {"type": "mapper_parsing_exception", "reason": "bad"}}
            )
        )
        with self.assertRaises(EsError) as caught:
            client.put("/x", {"mappings": {}})
        self.assertIn("mapper_parsing_exception: bad", str(caught.exception))
        self.assertEqual(caught.exception.status, 400)

    def test_ok_statuses_and_401(self):
        self.assertEqual(
            client_with(FakeResponse(404, {"found": False})).delete("/x", ok=(404,)),
            {"found": False},
        )
        with self.assertRaises(ConnectionFailed):
            client_with(FakeResponse(401, {"error": "unauthorized"})).get("/")

    def test_exists(self):
        self.assertTrue(client_with(FakeResponse(200, None, "HEAD")).exists("/movies"))
        self.assertFalse(client_with(FakeResponse(404, None, "HEAD")).exists("/movies"))


class ConfigTests(unittest.TestCase):
    def test_flags_beat_environment(self):
        environ = {
            "ELASTICSEARCH_URL": "https://env:9200",
            "ELASTIC_USER": "u",
            "ELASTIC_PASSWORD": "p",
        }
        target = config.resolve(url="http://flag:9200", environ=environ)
        self.assertEqual(
            (target.url, target.auth, target.source),
            ("http://flag:9200", ("u", "p"), "--url"),
        )
        self.assertEqual(config.resolve(environ=environ).source, "environment")

    def test_no_auth_and_tls(self):
        environ = {
            "ELASTICSEARCH_URL": "http://x",
            "ELASTIC_NO_AUTH": "true",
            "ELASTIC_VERIFY_SSL": "false",
        }
        target = config.resolve(environ=environ, user="elastic", password="secret")
        self.assertIsNone(target.auth)
        self.assertFalse(target.verify)
        self.assertFalse(
            config.resolve(url="https://x", insecure=True, environ={}).verify
        )

    def test_detection_never_accepts_401(self):
        first = config.Target(
            "https://localhost:9200", ("elastic", "x"), False, "detected"
        )
        second = config.Target(
            "https://localhost:9200", ("admin", "y"), False, "detected"
        )

        def fake_get(self, path, **kwargs):
            if self.auth == ("elastic", "x"):
                raise ConnectionFailed(
                    "https://localhost:9200 rejected the credentials"
                )
            return {"version": {"distribution": "opensearch", "number": "3.9.0"}}

        with (
            mock.patch.object(config, "candidates", return_value=[first, second]),
            mock.patch.object(Client, "get", fake_get),
        ):
            self.assertEqual(config.detect(), second)

    def test_detection_explains_rejected_logins(self):
        only = config.Target(
            "http://localhost:9200", ("elastic", "x"), True, "detected"
        )
        rejected = mock.Mock(
            side_effect=ConnectionFailed(
                "http://localhost:9200 rejected the credentials"
            )
        )
        with (
            mock.patch.object(config, "candidates", return_value=[only]),
            mock.patch.object(Client, "get", rejected),
        ):
            with self.assertRaisesRegex(ConnectionFailed, "rejected every known login"):
                config.detect()

    def test_candidates_cover_each_scheme_and_login_once(self):
        targets = config.candidates()
        pairs = {(t.url.split(":")[0], t.auth[0] if t.auth else None) for t in targets}
        self.assertEqual(len(pairs), len(targets))
        self.assertEqual(
            pairs,
            {
                ("http", "elastic"),
                ("https", "elastic"),
                ("https", "admin"),
                ("http", None),
            },
        )


class CapabilityTests(unittest.TestCase):
    def detect_with(self, root, licence=None, nodes=None):
        responses = {
            "/": root,
            "/_license": licence or {},
            "/_nodes": nodes or {"nodes": {}},
        }
        client = mock.Mock()
        client.get.side_effect = lambda path, **kwargs: responses[path]
        return detect(client)

    def test_distributions(self):
        self.assertEqual(
            self.detect_with(
                {"version": {"distribution": "opensearch", "number": "2.19.6"}}
            ).vectors,
            "knn_vector",
        )
        oss = self.detect_with({"version": {"number": "7.10.2", "build_flavor": "oss"}})
        self.assertEqual((oss.distribution, oss.vectors), ("elasticsearch-oss", None))

    def test_licence_and_ml_nodes(self):
        caps = self.detect_with(
            {"version": {"number": "9.5.4", "build_flavor": "default"}},
            {"license": {"type": "trial", "status": "active"}},
            {
                "nodes": {
                    "a": {"roles": ["master", "ml"]},
                    "b": {"roles": ["data", "ml"]},
                }
            },
        )
        self.assertEqual(
            (caps.licence, caps.ml_nodes, caps.rrf, caps.ml), ("trial", 2, True, True)
        )
        self.assertEqual(ES8.features(), ["dense_vector"])
        self.assertFalse(ES8.rrf)


class MappingTests(unittest.TestCase):
    def test_elasticsearch_uses_explicit_int8_hnsw(self):
        body = index_body(ES9_TRIAL, {"foe": {}}, 384)
        vector = body["mappings"]["properties"][VECTOR_FIELD]
        self.assertEqual((vector["type"], vector["dims"]), ("dense_vector", 384))
        self.assertEqual(vector["index_options"], {"type": "int8_hnsw"})
        self.assertNotIn("settings", body)

    def test_opensearch_uses_knn_vector(self):
        body = index_body(OPENSEARCH, {"foe": {}}, 384)
        self.assertEqual(
            body["mappings"]["properties"][VECTOR_FIELD]["type"], "knn_vector"
        )
        self.assertEqual(body["settings"], {"index": {"knn": True}})

    def test_without_vectors_and_meta(self):
        body = index_body(OSS, {"foe": {"size": "small"}})
        self.assertNotIn(VECTOR_FIELD, body["mappings"]["properties"])
        self.assertEqual(body["mappings"]["_meta"], {"foe": {"size": "small"}})


class LoaderTests(unittest.TestCase):
    def test_bulk_resends_rejected_items_and_counts_errors(self):
        docs = [{"id": 1}, {"id": 2}, {"id": 3}]
        first = {
            "items": [
                {"index": {"status": 201}},
                {
                    "index": {
                        "status": 429,
                        "error": {"type": "es_rejected_execution_exception"},
                    }
                },
                {
                    "index": {
                        "status": 400,
                        "error": {"type": "document_parsing_exception"},
                    }
                },
            ]
        }
        second = {"items": [{"index": {"status": 201}}]}
        client = mock.Mock()
        client.post.side_effect = [first, second]
        indexed, errors = loader.bulk_index(
            client, "movies", docs, backoff=0, progress=lambda _: None
        )
        self.assertEqual((indexed, errors), (2, {"document_parsing_exception": 1}))
        resent = client.post.call_args_list[1].kwargs["ndjson"]
        self.assertIn('"_id": 2', resent)
        self.assertNotIn('"_id": 1', resent)

    def test_vectors_are_refused_on_oss(self):
        with self.assertRaisesRegex(loader.Refused, "no vector field type"):
            loader.load(mock.Mock(), OSS, embeddings="hash", progress=lambda _: None)

    def test_deprecated_flag(self):
        with mock.patch("sys.stderr"):
            self.assertEqual(
                loader.parse_args(["--with-embeddings"]).embeddings, "hash"
            )
        self.assertEqual(loader.parse_args([]).embeddings, "none")
        with self.assertRaises(SystemExit), mock.patch("sys.stderr"):
            loader.parse_args(["--stack", "elk-ml", "--url", "http://x"])

    def test_skip_if_current(self):
        client = mock.Mock()
        meta = {
            "foe": {
                "dataset": "movies",
                "size": "small",
                "source": loader.source_checksum(
                    loader.DATASETS["movies"]["small"]["path"],
                    loader.DATASETS["movies"]["small"]["ids"],
                ),
            }
        }
        client.exists.return_value = True
        client.get.side_effect = lambda path, **kwargs: (
            {"movies": {"mappings": {"_meta": meta}}}
            if path.endswith("_mapping")
            else {"count": 200}
        )
        result = loader.load(
            client, ES8, "small", skip_if_current=True, progress=lambda _: None
        )
        self.assertTrue(result.skipped and result.complete)
        client.put.assert_not_called()


class EmbeddingTests(unittest.TestCase):
    def test_non_latin_text_gets_a_vector(self):
        self.assertEqual(
            tokenize("Ойыншықтар достығы, l'été"), ["ойыншықтар", "достығы", "l", "été"]
        )
        self.assertGreater(
            sum(abs(v) for v in deterministic_text_embedding("Ойыншықтар достығы")), 0
        )


if __name__ == "__main__":
    unittest.main()
