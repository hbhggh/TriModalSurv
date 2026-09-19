"""补零不进入患者统计、分子或分母；保持原模型输入与行序。"""
import copy
import importlib
import sys
import unittest
from pathlib import Path

import numpy as np

from experiments.I01_patient_retrieval.tests.test_patient_retrieval_bank import fixture


class PaddingBankTests(unittest.TestCase):
    def setUp(self):
        self.module = importlib.import_module('experiments.I01_patient_retrieval.model')

    def padded_fixture(self):
        features, splits, query = fixture()
        features['img']['A'][75:] = 0
        features['img']['B'][124:] = 0
        query[96:] = 0
        return features, splits, query

    def build(self, features, splits):
        try:
            return self.module.FixedPatientBank('BLCA', splits, features)
        except ValueError as error:
            self.fail(f'已批准的尾部补零应可建库，而非拒绝: {error}')

    def test_patient_equal_mean_and_targeted_padding_retrieval(self):
        features, splits, query = self.padded_fixture()
        original = copy.deepcopy(features)
        bank = self.build(features, splits)
        np.testing.assert_array_equal(bank.mean, [1., 1.])
        got = bank.retrieve('Q', query, ('rna', 'text'))
        self.assertEqual(got['donor_id'], 'A')
        self.assertAlmostEqual(got['similarity'], 1.0)
        self.assertEqual((got['query_valid_rows'], got['donor_valid_rows'], got['common_valid_rows']), (96, 75, 75))
        np.testing.assert_array_equal(got['values']['rna'], original['rna']['A'])
        for mm in original:
            for pid in original[mm]:
                np.testing.assert_array_equal(features[mm][pid], original[mm][pid])
        metadata = bank.metadata()
        self.assertEqual(metadata['valid_row_counts'], {'A': 75, 'B': 124, 'C': 128})
        self.assertEqual(metadata['protocol_id'], 'patient-fixed-padmask-v2')

    def test_mask_excludes_padding_and_nonoverlap_from_both_norms(self):
        self.assertTrue(hasattr(self.module, 'masked_cosine'), '需要共同有效行的独立评分入口')
        q = np.tile([1., 0.], (128, 1))
        k = np.tile([1., 1.], (128, 1))
        qm, km = np.arange(128) < 75, np.arange(128) < 124
        score = self.module.masked_cosine(q, k, qm, km)
        self.assertAlmostEqual(score, 1 / np.sqrt(2), places=14)
        q[75:] = [9e8, -8e8]
        k[75:] = [-6e9, 2e9]
        self.assertEqual(self.module.masked_cosine(q, k, qm, km), score)
        for a, b in ((123, 124), (128, 128)):
            self.assertAlmostEqual(self.module.masked_cosine(np.ones((128, 2)),
                np.ones((128, 2)), np.arange(128) < a, np.arange(128) < b), 1.0)

    def test_zero_centered_real_row_still_counts_as_real(self):
        features, splits, query = fixture()
        bank = self.build(features, splits)
        query[0] = bank.mean
        got = bank.retrieve('Q', query, ('rna',))
        self.assertIn('query_valid_rows', got)
        self.assertEqual(got['query_valid_rows'], 128)
        self.assertEqual(got['common_valid_rows'], 128)

    def test_invalid_pair_norm_not_silently_skipped(self):
        features, splits, query = self.padded_fixture()
        bank = self.build(features, splits)
        query[:75] = bank.mean
        with self.assertRaisesRegex(ValueError, 'norm'):
            bank.retrieve('Q', query, ('rna',))

    def test_invalid_masks_empty_overlap_and_norm_are_rejected(self):
        self.assertTrue(hasattr(self.module, 'masked_cosine'), '需要共同有效行的独立评分入口')
        cosine = self.module.masked_cosine
        a = np.ones((128, 2))
        mask = np.ones(128, dtype=bool)
        for m in (np.ones(127, dtype=bool), np.ones(128), np.ones((128, 1), dtype=bool)):
            with self.assertRaises(ValueError):
                cosine(a, a, mask, m)
        with self.assertRaisesRegex(ValueError, 'overlap'):
            cosine(a, a, np.arange(128) < 64, np.arange(128) >= 64)
        with self.assertRaisesRegex(ValueError, 'norm'):
            cosine(np.zeros_like(a), a, mask, mask)

    def test_bad_zero_layout_and_allzero_still_rejected(self):
        for defect in ('internal', 'allzero', 'nonfinite', 'shape'):
            with self.subTest(defect=defect):
                features, splits, _ = fixture()
                if defect == 'internal': features['img']['A'][3] = 0
                if defect == 'allzero': features['img']['A'][:] = 0
                if defect == 'nonfinite': features['img']['A'][0, 0] = np.inf
                if defect == 'shape': features['img']['A'] = features['img']['A'][:75]
                with self.assertRaises(ValueError):
                    self.module.FixedPatientBank('BLCA', splits, features)

    def test_nonpadding_matches_original_score_and_order(self):
        self.assertTrue(hasattr(self.module, 'masked_cosine'), '需要共同有效行的独立评分入口')
        features, splits, query = fixture()
        bank = self.build(features, splits)
        q = (query.astype(np.float64) - bank.mean).reshape(-1)
        q /= np.linalg.norm(q)
        for pid in sorted(splits['train']):
            key = (features['img'][pid].astype(np.float64) - bank.mean).reshape(-1)
            key /= np.linalg.norm(key)
            old_score = float(np.sum(q * key, dtype=np.float64))
            new_score = self.module.masked_cosine(query - bank.mean, features['img'][pid] - bank.mean,
                                                 np.ones(128, dtype=bool), np.ones(128, dtype=bool))
            np.testing.assert_allclose(new_score, old_score, atol=1e-12, rtol=0)

    def test_padding_query_cache_and_partition_are_stable(self):
        features, splits, query = self.padded_fixture()
        bank = self.build(features, splits)
        values = {'rna': np.zeros((2, 2, 2)), 'text': np.zeros((2, 3, 2))}
        valids = {mm: np.zeros(2, dtype=bool) for mm in values}
        all_result = bank.compensate(['Q', 'R'], np.stack([query, query]), values, valids, 'retrieval')
        for idx, pid in enumerate(('Q', 'R')):
            one = bank.compensate([pid], query[None], {k:v[idx:idx+1] for k,v in values.items()},
                                 {k:v[idx:idx+1] for k,v in valids.items()}, 'retrieval')
            self.assertEqual(one[2][0], all_result[2][idx])
        for arm in ('m0real', 'm1'):
            result = bank.compensate(['Q'], query[None], {k:v[:1] for k,v in values.items()},
                                    {k:v[:1] for k,v in valids.items()}, arm)[2][0]
            self.assertEqual(result['query_valid_rows'], 96)
            self.assertIsNone(result['donor_valid_rows'])
            self.assertIsNone(result['common_valid_rows'])


if __name__ == '__main__':
    unittest.main()
