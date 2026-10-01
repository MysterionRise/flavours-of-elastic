import csv
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from data import generate_descriptions as gen
from search.rag import cli
from search.rag.llm import LlmError, OpenRouter
from search.rag.prompts import check_citations, format_context, messages

HITS = [
    {
        "id": 318,
        "title": "The Shawshank Redemption",
        "year": 1994,
        "genres": ["Crime", "Drama"],
        "overview": "A banker...",
    },
    {
        "id": 3198,
        "title": "Papillon",
        "year": 1973,
        "genres": ["Crime"],
        "overview": "An escape...",
    },
]


class Response:
    def __init__(self, status, payload=None):
        self.status_code, self._payload = status, payload or {}
        self.ok = status < 400
        self.text = str(payload)

    def json(self):
        return self._payload


class PromptTests(unittest.TestCase):
    def test_context_carries_citable_ids(self):
        context = format_context(HITS)
        self.assertIn("[318] The Shawshank Redemption (1994; Crime, Drama)", context)
        self.assertIn("cite", messages("q", HITS)[0]["content"].lower())

    def test_groundedness(self):
        self.assertTrue(
            check_citations("Try Shawshank [318] or Papillon [3198].", HITS).grounded
        )
        made_up = check_citations("Watch Escape from Alcatraz [9999] and [318].", HITS)
        self.assertEqual(
            (made_up.cited, made_up.unknown, made_up.grounded),
            ([318, 9999], [9999], False),
        )
        self.assertFalse(check_citations("No citations here.", HITS).grounded)


class OpenRouterTests(unittest.TestCase):
    def test_missing_key(self):
        with self.assertRaisesRegex(LlmError, "OPENROUTER_API_KEY"):
            OpenRouter(api_key="", model="m").check()

    def test_unknown_model(self):
        session = mock.Mock()
        session.get.return_value = Response(200, {"data": [{"id": "known/model"}]})
        with self.assertRaisesRegex(LlmError, "does not list model 'typo/model'"):
            OpenRouter(api_key="k", model="typo/model", session=session).check()

    def test_http_errors_are_explained(self):
        session = mock.Mock()
        session.post.return_value = Response(402, {"error": {"message": "credits"}})
        with self.assertRaisesRegex(LlmError, "no credits"):
            OpenRouter(api_key="k", model="m", session=session).chat([])

    def test_answer(self):
        session = mock.Mock()
        session.post.return_value = Response(
            200, {"choices": [{"message": {"content": "Shawshank [318]"}}]}
        )
        self.assertEqual(
            OpenRouter(api_key="k", model="m", session=session).chat([]),
            "Shawshank [318]",
        )


class CliTests(unittest.TestCase):
    def test_bm25_uses_the_embeddings_index_when_loaded(self):
        client = mock.Mock()
        client.search.return_value.hits = HITS
        client.http.exists.return_value = False
        cli.retrieve(client, "bm25", "q", 5)
        self.assertIsNone(client.search.call_args.kwargs["index"])
        client.http.exists.return_value = True
        cli.retrieve(client, "bm25", "q", 5)
        self.assertEqual(client.search.call_args.kwargs["index"], "movies-embeddings")

    def test_retrieve_only_needs_no_llm(self):
        client = mock.Mock()
        client.search.return_value.hits = HITS
        result = cli.answer(None, client, "knn", "prison escape", 2)
        self.assertEqual(client.search.call_args.kwargs["mode"], "dense")
        self.assertEqual([m["id"] for m in result["retrieved"]], [318, 3198])
        self.assertIn("[318]", result["context"])

    def test_answer_reports_citations(self):
        client, llm = mock.Mock(), mock.Mock(model="m")
        client.search.return_value.hits = HITS
        llm.chat.return_value = "Shawshank [318], also [42]"
        result = cli.answer(llm, client, "hybrid", "q", 2)
        self.assertEqual(
            (result["cited"], result["unknown_citations"], result["grounded"]),
            ([42, 318], [42], False),
        )


class GenerateDescriptionsTests(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.path = self.dir / "out.csv"

    def write(self, rows, columns):
        with self.path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows)

    def test_resume_retries_failed_rows_and_keeps_extra_columns(self):
        full = {f: "x" for f in gen.FIELDS}
        columns = gen.BASE_COLUMNS + gen.FIELDS + ["vote_average"]
        self.write(
            [
                {
                    "movieId": "1",
                    "title": "A",
                    "genres": "",
                    "vote_average": "7.0",
                    **full,
                },
                {
                    "movieId": "2",
                    "title": "B",
                    "genres": "",
                    "vote_average": "6.0",
                    **{f: "" for f in gen.FIELDS},
                },
            ],
            columns,
        )
        rows, existing = gen.read_existing_output(self.path)
        self.assertEqual(
            [mid for mid, row in rows.items() if gen.is_complete(row)], ["1"]
        )
        self.assertEqual(gen.output_columns(existing)[-1], "vote_average")

    def test_write_is_atomic_and_creates_the_directory(self):
        target = self.dir / "build" / "out.csv"
        gen.write_output(
            target,
            [{"movieId": "1", "title": "A", "genres": "", "extra": "kept"}],
            gen.output_columns(["extra"]),
        )
        with target.open(encoding="utf-8") as handle:
            self.assertEqual(next(csv.DictReader(handle))["extra"], "kept")
        self.assertFalse((self.dir / "build" / "out.csv.tmp").exists())


if __name__ == "__main__":
    unittest.main()
