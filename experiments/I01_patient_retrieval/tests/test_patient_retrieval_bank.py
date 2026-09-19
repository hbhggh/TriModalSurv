"""固定库的数值、配对、隔离及失败保护契约；纯 numpy / unittest。"""
import copy
import importlib
import sys
import unittest
from pathlib import Path

import numpy as np



def fixture():
    tile = lambda v: np.tile(np.array(v, dtype=np.float32), (128, 1))
    features = {
        'img': {'A': tile([3, 1]), 'B': tile([1, 3]), 'C': tile([-1, -1])},
        'rna': {p: np.full((2, 2), v, np.float32) for p, v in [('A', 10), ('B', 20), ('C', 30)]},
        'text': {p: np.full((3, 2), v, np.float32) for p, v in [('A', 40), ('B', 50), ('C', 60)]},
    }
    splits = {'train': ['C', 'B', 'A'], 'valid': ['V'], 'test': ['Q', 'R']}
    return features, splits, tile([4, 1])


class BankTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        target = Path(__file__).resolve().parents[1] / 'model.py'
        assert target.is_file(), '固定患者库实现尚不存在，不能执行检索契约'
        cls.Bank = importlib.import_module('experiments.I01_patient_retrieval.model').FixedPatientBank

    def build(self, features=None, splits=None):
        f, s, _ = fixture()
        return self.Bank('BLCA', splits or s, features or f)

    def test_top1_returns_full_paired_value_and_shared_mean(self):
        f, s, q = fixture()
        bank = self.build(f, s)
        np.testing.assert_array_equal(bank.mean, [1, 1])
        got = bank.retrieve('Q', q, ('rna',))
        self.assertEqual(got['donor_id'], 'A')
        self.assertAlmostEqual(got['similarity'], 1)
        np.testing.assert_array_equal(got['values']['rna'], np.full((2, 2), 10))
        self.assertEqual(got['candidate_count'], 3)
        self.assertEqual(bank.keys.dtype, np.float64)

    def test_both_missing_requires_one_complete_donor(self):
        f, s, q = fixture()
        del f['text']['A']
        del f['rna']['B']
        got = self.build(f, s).retrieve('Q', q, ('rna', 'text'))
        self.assertEqual(got['donor_id'], 'C')
        self.assertEqual(got['candidate_count'], 1)
        np.testing.assert_array_equal(got['values']['rna'], np.full((2, 2), 30))
        np.testing.assert_array_equal(got['values']['text'], np.full((3, 2), 60))

    def test_self_excluded_and_unregistered_query_rejected(self):
        f, s, q = fixture()
        bank = self.build(f, s)
        self.assertEqual(bank.retrieve('A', f['img']['A'], ('rna',), query_split='train')['donor_id'], 'B')
        with self.assertRaisesRegex(ValueError, 'split'):
            bank.retrieve('A', q, ('rna',))
        with self.assertRaisesRegex(ValueError, 'split'):
            bank.retrieve('UNKNOWN', q, ('rna',))

    def test_nontrain_features_do_not_enter_mean_keys_or_values(self):
        f, s, q = fixture()
        before = self.build(f, s)
        for mm in f:
            f[mm]['Q'] = np.full_like(f[mm]['A'], 999)
        after = self.build(f, s)
        self.assertEqual(before.fingerprint, after.fingerprint)
        self.assertEqual(after.retrieve('Q', q, ('rna',))['donor_id'], 'A')

    def test_exact_tie_uses_sorted_id(self):
        f, s, q = fixture()
        f['img']['B'] = f['img']['A'].copy()
        self.assertEqual(self.build(f, s).retrieve('Q', q, ('rna',))['donor_id'], 'A')

    def test_original_centroid_order_is_preserved(self):
        f, s, _ = fixture()
        f['img']['A'][:64] = [3, 1]
        f['img']['A'][64:] = [1, 3]
        f['img']['B'] = f['img']['A'][::-1].copy()
        bank = self.build(f, s)
        self.assertEqual(bank.retrieve('Q', f['img']['A'], ('rna',))['donor_id'], 'A')
        self.assertEqual(bank.retrieve('Q', f['img']['A'][::-1], ('rna',))['donor_id'], 'B')

    def test_no_mutation_or_value_alias(self):
        f, s, q = fixture()
        original = copy.deepcopy(f)
        bank = self.build(f, s)
        got = bank.retrieve('Q', q, ('rna',))
        got['values']['rna'][:] = 999
        f['rna']['A'][:] = 888
        np.testing.assert_array_equal(bank.retrieve('Q', q, ('rna',))['values']['rna'], original['rna']['A'])
        for p in f['img']:
            np.testing.assert_array_equal(f['img'][p], original['img'][p])

    def test_batch_fill_preserves_original_valid_and_is_partition_invariant(self):
        f, s, q = fixture()
        bank = self.build(f, s)
        values = {'rna': np.zeros((2, 2, 2), np.float32), 'text': np.full((2, 3, 2), 7, np.float32)}
        valids = {'rna': np.array([False, True]), 'text': np.array([True, True])}
        out, masks, records = bank.compensate(['Q', 'R'], np.stack([q, q]), values, valids, 'retrieval')
        np.testing.assert_array_equal(out['rna'][0], f['rna']['A'])
        np.testing.assert_array_equal(out['rna'][1], values['rna'][1])
        np.testing.assert_array_equal(out['text'], values['text'])
        self.assertTrue(masks['rna'].all())
        self.assertFalse(valids['rna'][0])
        self.assertFalse(records[0]['original_valid']['rna'])
        one = bank.compensate(['Q'], q[None], {k:v[:1] for k,v in values.items()}, {k:v[:1] for k,v in valids.items()}, 'retrieval')
        np.testing.assert_array_equal(one[0]['rna'][0], out['rna'][0])
        self.assertEqual(one[2][0], records[0])

    def test_mean_and_no_fill_have_distinct_valid_contracts(self):
        _, _, q = fixture()
        bank = self.build()
        values = {'rna': np.zeros((1, 2, 2), np.float32), 'text': np.zeros((1, 3, 2), np.float32)}
        valids = {'rna': np.array([False]), 'text': np.array([False])}
        mean, masks, _ = bank.compensate(['Q'], q[None], values, valids, 'm1')
        np.testing.assert_array_equal(mean['rna'], np.full((1, 2, 2), 20))
        np.testing.assert_array_equal(mean['text'], np.full((1, 3, 2), 50))
        self.assertTrue(masks['rna'][0])
        none, masks, _ = bank.compensate(['Q'], q[None], values, valids, 'm0real')
        np.testing.assert_array_equal(none['rna'], values['rna'])
        self.assertFalse(masks['rna'][0])

    def test_reject_duplicate_or_overlapping_ids(self):
        f, s, _ = fixture()
        s['train'].append('A')
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            self.build(f, s)
        s['train'].pop()
        s['test'].append('A')
        with self.assertRaisesRegex(ValueError, 'overlap'):
            self.build(f, s)

    def test_reject_padding_nonfinite_shapes_zero_norm_and_empty_candidates(self):
        for defect in ('padding', 'nonfinite', 'shape', 'zero_norm'):
            with self.subTest(defect=defect):
                f, s, _ = fixture()
                if defect == 'padding': f['img']['A'][0] = 0
                if defect == 'nonfinite': f['rna']['A'][0, 0] = np.nan
                if defect == 'shape': f['img']['A'] = f['img']['A'][:32]
                if defect == 'zero_norm': f['img'] = {p: np.ones((128, 2), np.float32) for p in s['train']}
                with self.assertRaises(ValueError): self.build(f, s)
        f, s, q = fixture()
        f['rna'] = {'A': f['rna']['A']}
        f['text'] = {'B': f['text']['B']}
        with self.assertRaisesRegex(ValueError, 'candidate'):
            self.build(f, s).retrieve('Q', q, ('rna', 'text'))
        with self.assertRaisesRegex(ValueError, 'norm'):
            self.build().retrieve('Q', np.ones((128, 2)), ('rna',))


if __name__ == '__main__':
    unittest.main()
