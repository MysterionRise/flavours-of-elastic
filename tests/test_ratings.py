import csv
import re
import unittest
from pathlib import Path

from data.add_ratings import format_average
from data.load_data import DATASETS, normalize_movie

CSV_PATH = Path(__file__).resolve().parents[1] / "data" / "movies_enriched.csv"


def load_rows():
    with CSV_PATH.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


class FormatAverageTests(unittest.TestCase):
    def test_mean_of_half_stars(self):
        # 3.5 and 4.0 stars are 7 and 8 half-stars: mean 7.5 on the 1-10 scale
        self.assertEqual(format_average(15, 2, min_votes=1), "7.5")

    def test_rounds_half_up_without_floats(self):
        self.assertEqual(format_average(29, 4, min_votes=1), "7.3")  # 7.25 -> 7.3
        self.assertEqual(format_average(22, 3, min_votes=1), "7.3")  # 7.333 -> 7.3
        self.assertEqual(format_average(23, 3, min_votes=1), "7.7")  # 7.666 -> 7.7
        self.assertEqual(format_average(10, 1, min_votes=1), "10.0")

    def test_below_min_votes_is_empty(self):
        self.assertEqual(format_average(80, 9, min_votes=10), "")
        self.assertEqual(format_average(0, 0, min_votes=0), "")


class EnrichedCsvTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = load_rows()
        cls.by_id = {row["movieId"]: row for row in cls.rows}

    def test_rating_columns_follow_genres(self):
        header = list(self.rows[0].keys())
        self.assertEqual(
            header[:5], ["movieId", "title", "genres", "vote_average", "vote_count"]
        )

    def test_values_are_well_formed(self):
        for row in self.rows:
            count = int(row["vote_count"])
            self.assertGreaterEqual(count, 0)
            if row["vote_average"]:
                self.assertRegex(row["vote_average"], r"^\d{1,2}\.\d$")
                self.assertTrue(
                    1.0 <= float(row["vote_average"]) <= 10.0, row["movieId"]
                )
                self.assertGreaterEqual(count, 10, row["movieId"])
            else:
                self.assertLess(count, 10, row["movieId"])

    def test_known_films(self):
        shawshank, godfather = self.by_id["318"], self.by_id["858"]
        self.assertGreaterEqual(float(shawshank["vote_average"]), 8.5)
        self.assertGreater(int(shawshank["vote_count"]), 10000)
        self.assertGreaterEqual(float(godfather["vote_average"]), 8.3)
        flop = next(
            r for r in self.rows if re.match(r"Battlefield Earth \(2000\)", r["title"])
        )
        self.assertLess(
            float(flop["vote_average"]), float(shawshank["vote_average"]) - 4
        )


class LoaderTests(unittest.TestCase):
    def test_small_dataset_is_the_head_of_the_full_csv(self):
        movies = DATASETS["movies"]
        self.assertEqual(movies["small"]["path"], movies["full"]["path"])
        self.assertEqual(movies["small"]["limit"], 100)

    def test_mapping_has_rating_fields(self):
        properties = DATASETS["movies"]["mapping"]["properties"]
        self.assertEqual(properties["vote_average"], {"type": "float"})
        self.assertEqual(properties["vote_count"], {"type": "integer"})

    def test_normalize_movie_emits_ratings(self):
        row = {
            "movieId": "318",
            "title": "Shawshank Redemption, The (1994)",
            "genres": "Crime|Drama",
        }
        doc = normalize_movie({**row, "vote_average": "8.8", "vote_count": "102929"})
        self.assertEqual((doc["vote_average"], doc["vote_count"]), (8.8, 102929))
        sparse = normalize_movie({**row, "vote_average": "", "vote_count": "3"})
        self.assertNotIn("vote_average", sparse)
        self.assertEqual(sparse["vote_count"], 3)


if __name__ == "__main__":
    unittest.main()
