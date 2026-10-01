import unittest

import yaml

from data import build_sample
from data.load_data import DATASETS, read_movies


class CuratedSampleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = yaml.safe_load(
            build_sample.CONFIG_PATH.read_text(encoding="utf-8")
        )
        cls.movies = build_sample.load_movies()
        cls.must = build_sample.must_include(cls.config)
        lines = build_sample.OUTPUT_PATH.read_text(encoding="utf-8").splitlines()
        cls.ids = [int(line) for line in lines if line and not line.startswith("#")]

    def test_committed_list_is_current_and_valid(self):
        self.assertEqual(
            build_sample.select(self.movies, self.config, self.must), self.ids
        )
        self.assertEqual(
            build_sample.violations(self.ids, self.movies, self.config, self.must), []
        )

    def test_contains_every_course_film(self):
        course = yaml.safe_load(
            (build_sample.REPO_ROOT / "course" / "movies.yml").read_text(
                encoding="utf-8"
            )
        )
        self.assertLessEqual({int(m["id"]) for m in course["movies"]}, set(self.ids))

    def test_spans_the_whole_dataset(self):
        decades = {self.movies[i].decade for i in self.ids}
        self.assertEqual(decades, {m.decade for m in self.movies.values()})
        genres = {g for i in self.ids for g in self.movies[i].genres}
        self.assertEqual(genres, {g for m in self.movies.values() for g in m.genres})

    def test_loader_reads_the_sample(self):
        small = DATASETS["movies"]["small"]
        docs = read_movies(
            small["path"], small["limit"], with_embeddings=False, ids=small["ids"]
        )
        self.assertEqual(sorted(doc["id"] for doc in docs), self.ids)
        godfather = next(doc for doc in docs if doc["id"] == 858)
        self.assertEqual(godfather["title"], "The Godfather")
        self.assertEqual(godfather["vote_average"], 8.6)


if __name__ == "__main__":
    unittest.main()
