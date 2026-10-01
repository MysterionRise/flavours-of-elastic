import tempfile
import unittest
from pathlib import Path

from tests.course.console import (
    ConsoleError,
    esql_request,
    parse_requests,
    strip_comments,
)
from tests.course.markdown import extract_blocks, parse_info
from tests.course.runner import check, subset


class FakeResponse:
    def __init__(self, status, payload=None, headers=None):
        self.status_code, self._payload, self.headers = status, payload, headers or {}

    def json(self):
        if self._payload is None:
            raise ValueError("no body")
        return self._payload


def block_with(**attrs):
    blocks = extract_blocks(
        write_deck(
            "## T\n```json "
            + " ".join(f"{k}={v}" for k, v in attrs.items())
            + "\nGET /x\n```\n"
        )
    )
    return blocks[0]


def write_deck(text):
    handle = tempfile.NamedTemporaryFile(
        "w", suffix=".md", delete=False, encoding="utf-8"
    )
    handle.write(text)
    handle.close()
    return Path(handle.name)


class ConsoleTests(unittest.TestCase):
    def test_comments_are_removed_outside_strings_only(self):
        text = (
            '{ "url": "http://x//y#z", # comment\n "a": 1 // trailing\n /* block */ }'
        )
        self.assertEqual(
            strip_comments(text).split(),
            ["{", '"url":', '"http://x//y#z",', '"a":', "1", "}"],
        )

    def test_triple_quoted_strings(self):
        (request,) = parse_requests(
            'POST /_query\n{\n  "query": """\n    FROM movies\n    | LIMIT 3\n  """\n}'
        )
        self.assertEqual(
            request.body["query"].strip().splitlines(), ["FROM movies", "    | LIMIT 3"]
        )

    def test_several_requests_per_block(self):
        requests = parse_requests(
            'PUT /a/_doc/1\n{"x": 1}\n\nGET /a/_search # find it\n{"query": {"match_all": {}}}'
        )
        self.assertEqual(
            [(r.method, r.path) for r in requests],
            [("PUT", "/a/_doc/1"), ("GET", "/a/_search")],
        )

    def test_bulk_becomes_ndjson(self):
        (request,) = parse_requests(
            'POST /_bulk\n{"index": {"_index": "a", "_id": "1"}}\n{"t": "x"}'
        )
        self.assertTrue(request.ndjson)
        self.assertEqual(request.body.count("\n"), 2)

    def test_kibana_paths_and_missing_slash(self):
        (request,) = parse_requests("POST kbn:/api/sample_data/ecommerce")
        self.assertTrue(request.kibana)
        self.assertEqual(request.path, "/api/sample_data/ecommerce")
        self.assertEqual(parse_requests("GET movies/_count")[0].path, "/movies/_count")

    def test_expectation_comment(self):
        (request,) = parse_requests('GET /_analyze\n{"text": "x"}\n// → {"tokens": []}')
        self.assertEqual(request.expectation, {"tokens": []})

    def test_placeholders_are_rejected(self):
        with self.assertRaises(ConsoleError):
            parse_requests('GET /a/_search\n{ "query": { ... } }')

    def test_bare_esql(self):
        request = esql_request("FROM movies\n| LIMIT 5")
        self.assertEqual(
            (request.method, request.path, request.body["query"]),
            ("POST", "/_query", "FROM movies\n| LIMIT 5"),
        )


class MarkdownTests(unittest.TestCase):
    def test_extracts_blocks_with_context(self):
        deck = write_deck(
            "---\nmarp: true\n---\n# Title\n\n---\n\n## Task 3: Search\n\n```json expect=empty\nGET /m/_search\n```\n\n"
            "> **Hint:**\n> ```json\n> GET /m/_count\n> ```\n"
        )
        first, second = extract_blocks(deck)
        self.assertEqual(
            (first.slide, first.task, first.attrs, first.kind),
            (2, "3", {"expect": "empty"}, "request"),
        )
        self.assertEqual(second.text.strip(), "GET /m/_count")
        self.assertEqual((first.index, second.index), (0, 1))
        self.assertTrue(first.id.endswith("/task-3-search/0"))

    def test_annotation_parsing(self):
        self.assertEqual(
            parse_info("json top=858 track=9"),
            ("json", {"top": "858", "track": "9"}, []),
        )
        self.assertEqual(
            parse_info("json bogus=1")[2], ["unknown fence annotation `bogus=1`"]
        )


class CheckTests(unittest.TestCase):
    def setUp(self):
        self.request = parse_requests("GET /m/_search")[0]

    def test_status_expectations(self):
        self.assertIsNone(
            check(
                block_with(),
                self.request,
                FakeResponse(200, {"hits": {"total": {"value": 2}, "hits": []}}),
            )
        )
        self.assertIn(
            "HTTP 404",
            check(
                block_with(), self.request, FakeResponse(404, {"error": {"type": "x"}})
            ),
        )
        self.assertIsNone(
            check(block_with(expect="404"), self.request, FakeResponse(404, {}))
        )
        self.assertIsNone(
            check(block_with(expect="4xx"), self.request, FakeResponse(400, {}))
        )

    def test_empty_results_fail_unless_expected(self):
        empty = FakeResponse(200, {"hits": {"total": {"value": 0}, "hits": []}})
        self.assertIn("at least 1", check(block_with(), self.request, empty))
        self.assertIsNone(check(block_with(expect="empty"), self.request, empty))

    def test_top_and_contains(self):
        response = FakeResponse(
            200,
            {"hits": {"total": {"value": 2}, "hits": [{"_id": "318"}, {"_id": "858"}]}},
        )
        self.assertIsNone(
            check(block_with(top="318", contains="858"), self.request, response)
        )
        self.assertIn("top hit", check(block_with(top="858"), self.request, response))

    def test_warnings_and_aggregations(self):
        warned = FakeResponse(
            200,
            {"hits": {"total": {"value": 1}, "hits": []}},
            {"Warning": "299 deprecated"},
        )
        self.assertIn("warning", check(block_with(), self.request, warned))
        self.assertIsNone(check(block_with(expect="warning"), self.request, warned))
        null_agg = FakeResponse(
            200,
            {"hits": {"total": {"value": 5}}, "aggregations": {"avg": {"value": None}}},
        )
        self.assertIn("returned null", check(block_with(), self.request, null_agg))

    def test_subset(self):
        self.assertTrue(subset({"a": {"b": 1}}, {"a": {"b": 1, "c": 2}, "d": 3}))
        self.assertFalse(subset([1, 2], [1, 2, 3]))


if __name__ == "__main__":
    unittest.main()
