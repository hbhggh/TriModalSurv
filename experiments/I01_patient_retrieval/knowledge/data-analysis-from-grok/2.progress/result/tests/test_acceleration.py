"""加速不能改变共同有效行余弦、退化报错与 float64 精度。"""
import importlib.util
import sys
import unittest
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class BatchedCosineTests(unittest.TestCase):
    def engine(self):
        self.assertIsNotNone(importlib.util.find_spec('acceleration'),
                             '缺少批量 float64 检索实现')
        import acceleration
        return acceleration

    def test_mask_applies_to_both_norms_and_dot(self):
        engine = self.engine()
        q = np.array([[1., 0.], [0., 2.], [99., 99.]])
        k = np.array([[[1., 0.], [9., 9.], [8., 8.]],
                      [[0., 1.], [0., 2.], [7., 7.]]])
        result = engine.gpu_cosines(q, k, device='cpu', epsilon=1e-12,
                                    query_mask=np.array([True, True, False]),
                                    key_masks=np.array([[True, False, False], [True, True, False]]))
        np.testing.assert_allclose(result, [1., .8], atol=1e-15, rtol=0)
        self.assertEqual(result.dtype, np.float64)

    def test_vector_cosine_and_zero_norm_rejection(self):
        engine = self.engine()
        result = engine.gpu_cosines(np.array([1., 0.]), np.array([[1., 0.], [0., 1.], [-1., 0.]]),
                                    device='cpu', epsilon=1e-12)
        np.testing.assert_array_equal(result, [1., 0., -1.])
        with self.assertRaises(ValueError):
            engine.gpu_cosines(np.array([1., 0.]), np.zeros((1, 2)), device='cpu', epsilon=1e-12)

    def test_empty_overlap_is_not_silent_fallback(self):
        engine = self.engine()
        with self.assertRaises(ValueError):
            engine.gpu_cosines(np.ones((2, 2)), np.ones((1, 2, 2)), device='cpu', epsilon=1e-12,
                               query_mask=np.array([True, False]), key_masks=np.array([[False, True]]))

    def test_cached_custom_retrieval_matches_reference_and_returns_copies(self):
        engine = self.engine()
        self.assertTrue(hasattr(engine, 'RetrievalCache'), '缺少候选打分缓存')
        from test_rules import fixture, load_path, INFERENCE_PATH
        bank, _, query = fixture()
        inference = load_path('_acceleration_reference', INFERENCE_PATH)
        args = dict(query_split='test', enabled=(2,), grid='text_100',
                    query_rna=np.ones((2, 2)), natural_rna=True, alpha=0., epsilon=1e-12)
        expected = inference._custom_retrieve(bank, 'Q', query, ('text',), **args)
        cache = engine.RetrievalCache(bank, device='cpu', epsilon=1e-12)
        first = cache.custom_retrieve('Q', query, ('text',), **args)
        self.assertEqual(first['donor_id'], expected['donor_id'])
        self.assertEqual(first['similarity'], expected['similarity'])
        first['values']['text'][:] = -100
        second = cache.custom_retrieve('Q', query, ('text',), **args)
        np.testing.assert_array_equal(second['values']['text'], expected['values']['text'])
        self.assertEqual(cache.score_builds, 1)

    def test_inference_hook_reuses_scores_and_does_not_mix_queries(self):
        engine = self.engine()
        from test_rules import fixture, load_path, INFERENCE_PATH
        bank, _, query = fixture()
        inference = load_path('_acceleration_hook', INFERENCE_PATH)
        bank.retrieval_accelerator = engine.RetrievalCache(bank, device='cpu', epsilon=1e-12)
        args = dict(query_split='test', enabled=(2,), grid='text_100',
                    query_rna=np.ones((2, 2)), natural_rna=True, alpha=0., epsilon=1e-12)
        first = inference._custom_retrieve(bank, 'Q', query, ('text',), **args)
        inference._custom_retrieve(bank, 'Q', query, ('text',), **args)
        self.assertEqual(bank.retrieval_accelerator.score_builds, 1,
                         '生产推理未接入缓存，重复网格仍在重新检索')
        changed = np.tile(np.array([1., 4.]), (128, 1))
        second = inference._custom_retrieve(bank, 'Q', changed, ('text',), **args)
        self.assertNotEqual(first['donor_id'], second['donor_id'])
        self.assertEqual(bank.retrieval_accelerator.score_builds, 2)

    def test_joint_retrieval_accepts_config_list_shapes(self):
        engine = self.engine()
        from test_rules import fixture, load_path, INFERENCE_PATH
        bank, _, query = fixture()
        bank.shapes = {k:list(v) for k,v in bank.shapes.items()}
        inference = load_path('_acceleration_list_shapes', INFERENCE_PATH)
        args = dict(query_split='test', enabled=(2, 4), grid='text_100',
                    query_rna=np.ones((2, 2)), natural_rna=True, alpha=1., epsilon=1e-12)
        expected = inference._custom_retrieve(bank, 'Q', query, ('text',), **args)
        result = engine.RetrievalCache(bank, device='cpu', epsilon=1e-12).custom_retrieve(
            'Q', query, ('text',), **args)
        self.assertEqual(result['donor_id'], expected['donor_id'])
        self.assertEqual(result['similarity'], expected['similarity'])


if __name__ == '__main__':
    unittest.main()
