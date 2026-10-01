import csv
import re
import unittest
from pathlib import Path

from search.movies import ARTICLES, normalize_title

CSV_PATH = Path(__file__).resolve().parents[1] / "data" / "movies_enriched.csv"

CASES = [
    ("Godfather, The (1972)", "The Godfather", []),
    ("Godfather: Part II, The (1974)", "The Godfather: Part II", []),
    (
        "City of Lost Children, The (Cité des enfants perdus, La) (1995)",
        "The City of Lost Children",
        ["La Cité des enfants perdus"],
    ),
    (
        "Good, the Bad and the Ugly, The (Buono, il brutto, il cattivo, Il) (1966)",
        "The Good, the Bad and the Ugly",
        ["Il Buono, il brutto, il cattivo"],
    ),
    ("Enfer, L' (1994)", "L'Enfer", []),
    ("Boot, Das (Boat, The) (1981)", "Das Boot", ["The Boat"]),
    ("Seven (a.k.a. Se7en) (1995)", "Seven", ["Se7en"]),
    (
        "Raiders of the Lost Ark (Indiana Jones and the Raiders of the Lost Ark) (1981)",
        "Raiders of the Lost Ark",
        ["Indiana Jones and the Raiders of the Lost Ark"],
    ),
    ("Die, Monster, Die! (1965)", "Die, Monster, Die!", []),
    ("Paris, Texas (1984)", "Paris, Texas", []),
    ("Monsters, Inc. (2001)", "Monsters, Inc.", []),
    ("Toy Story (1995)", "Toy Story", []),
]


class NormalizeTitleTests(unittest.TestCase):
    def test_cases(self):
        for raw, title, aka in CASES:
            with self.subTest(raw=raw):
                self.assertEqual(normalize_title(raw), (title, aka))

    def test_idempotent(self):
        for _raw, title, _ in CASES:
            self.assertEqual(normalize_title(title)[0], title)

    def test_every_dataset_title(self):
        trailing = re.compile(r", (" + "|".join(map(re.escape, ARTICLES)) + r")$")
        with CSV_PATH.open(encoding="utf-8", newline="") as handle:
            titles = [row["title"] for row in csv.DictReader(handle)]
        for raw in titles:
            title, aka = normalize_title(raw)
            self.assertTrue(title, raw)
            self.assertIsNone(trailing.search(title), raw)
            self.assertNotIn(title, aka, raw)
            self.assertEqual(normalize_title(title)[0], title, raw)


if __name__ == "__main__":
    unittest.main()
