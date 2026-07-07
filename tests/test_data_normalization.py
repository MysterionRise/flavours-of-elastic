import unittest

from data.load_data import normalize_movie, parse_year, split_genres, strip_year
from search.embeddings import DEFAULT_EMBEDDING_DIMS, deterministic_text_embedding


class DataNormalizationTests(unittest.TestCase):
    def test_parse_year_from_title(self):
        self.assertEqual(parse_year("Toy Story (1995)"), 1995)
        self.assertIsNone(parse_year("No Year"))

    def test_strip_year(self):
        self.assertEqual(strip_year("Toy Story (1995)"), "Toy Story")
        self.assertEqual(
            strip_year("City (Director's Cut) (1995)"), "City (Director's Cut)"
        )

    def test_split_genres(self):
        self.assertEqual(
            split_genres("Action|Crime|Thriller"), ["Action", "Crime", "Thriller"]
        )
        self.assertEqual(split_genres("(no genres listed)"), [])

    def test_normalize_movie_with_embedding(self):
        row = {
            "movieId": "1",
            "title": "Toy Story (1995)",
            "genres": "Adventure|Animation|Children",
            "abstract_en": "Toys come alive and learn friendship.",
            "abstract_kk": "",
            "abstract_fr": "",
            "description_en": "A cowboy doll and space ranger must work together.",
            "description_kk": "",
            "description_fr": "",
        }
        doc = normalize_movie(row, with_embeddings=True)
        self.assertEqual(doc["id"], 1)
        self.assertEqual(doc["title"], "Toy Story")
        self.assertEqual(doc["year"], 1995)
        self.assertEqual(len(doc["overview_embedding"]), DEFAULT_EMBEDDING_DIMS)

    def test_deterministic_embedding_is_stable(self):
        first = deterministic_text_embedding("space adventure")
        second = deterministic_text_embedding("space adventure")
        self.assertEqual(first, second)
        self.assertAlmostEqual(sum(value * value for value in first), 1.0, places=4)


if __name__ == "__main__":
    unittest.main()
