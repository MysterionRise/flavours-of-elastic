import unittest

from scripts.check_doc_versions import check_text, minors

ENV = {
    "ELK_VERSION": "8.19.22",
    "ELK9_VERSION": "9.5.4",
    "OPENSEARCH_VERSION": "2.19.6",
    "OPENSEARCH3_VERSION": "3.9.0",
}
FROZEN = {7: "7.10.2"}


def problems(text, env=ENV):
    return check_text(text, minors(env), FROZEN)


class CheckDocVersionsTests(unittest.TestCase):
    def test_current_minors_pass(self):
        text = (
            "| Elastic Single | 8.19.x |\n| Elastic 9 | 9.5.x |\n"
            "OpenSearch 3.9.x and 2.19.x\nElasticsearch 8.19 | Kibana"
        )
        self.assertEqual(problems(text), [])

    def test_patch_bump_needs_no_doc_change(self):
        self.assertEqual(
            problems("Elastic 9 (9.5.x)", {**ENV, "ELK9_VERSION": "9.5.5"}), []
        )

    def test_minor_bump_flags_stale_docs(self):
        found = problems(
            "Elastic 9 (9.5.x)\nElasticsearch 9.5 | ES|QL",
            {**ENV, "ELK9_VERSION": "9.6.0"},
        )
        self.assertEqual([line for line, *_ in found], [1, 2])

    def test_exact_versions_are_flagged_except_frozen_oss(self):
        found = problems(
            "| Elastic Single | 8.19.11 |\nElasticsearch OSS (7.10.2) frozen"
        )
        self.assertEqual(len(found), 1)
        self.assertIn("8.19.11", found[0][1])

    def test_historical_references_are_allowed(self):
        text = (
            "Elasticsearch 8.14+ provides retrievers\n"
            "ES|QL (introduced in 8.11)\nGA since Elasticsearch 8.14"
        )
        self.assertEqual(problems(text), [])

    def test_stale_slide_label_is_flagged(self):
        self.assertEqual(len(problems("Elasticsearch 8.18 | Kibana | Docker")), 1)

    def test_fix_replacements(self):
        found = problems(
            "Elastic 9 (9.4.x)\n| Elastic ML | 8.19.11 |\nElasticsearch 8.18 | Bulk"
        )
        self.assertEqual(
            [(old, new) for _, _, old, new in found],
            [
                ("9.4.x", "9.5.x"),
                ("8.19.11", "8.19.x"),
                ("Elasticsearch 8.18", "Elasticsearch 8.19"),
            ],
        )


if __name__ == "__main__":
    unittest.main()
