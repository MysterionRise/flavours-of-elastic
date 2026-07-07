import unittest

from search.evaluate import ndcg_at_k, recall_at_k, reciprocal_rank


class EvaluationMetricTests(unittest.TestCase):
    def test_reciprocal_rank(self):
        self.assertEqual(reciprocal_rank([3, 2, 1], {1}), 1 / 3)
        self.assertEqual(reciprocal_rank([3, 2], {1}), 0)

    def test_recall_at_k(self):
        self.assertEqual(recall_at_k([1, 2, 3], {1, 4}, 3), 0.5)
        self.assertEqual(recall_at_k([1, 2, 3], set(), 3), 0)

    def test_ndcg_at_k(self):
        perfect = ndcg_at_k([1, 2, 3], {1: 3, 2: 2, 3: 1}, 3)
        imperfect = ndcg_at_k([3, 2, 1], {1: 3, 2: 2, 3: 1}, 3)
        self.assertEqual(perfect, 1.0)
        self.assertLess(imperfect, perfect)


if __name__ == "__main__":
    unittest.main()
