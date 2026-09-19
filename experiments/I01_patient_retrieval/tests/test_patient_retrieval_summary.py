import csv
import hashlib
import importlib.util
import json
import math
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "summarize.py"
ARMS = ("m0real", "m1", "retrieval")
CANCERS = ("BLCA", "BRCA", "LGG", "LUAD", "UCEC")
SEEDS = (123, 132, 213, 231, 321)
GRIDS = ("none", "rna_100", "text_100", "both_100")
SEED_OFFSET = {123: -0.02, 132: -0.01, 213: 0.0, 231: 0.01, 321: 0.02}
ARM_BASE = {"m0real": 0.40, "m1": 0.50, "retrieval": 0.60}
GRID_OFFSET = {"none": 0.10, "rna_100": 0.0, "text_100": 0.02, "both_100": -0.02}


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_module():
    spec = importlib.util.spec_from_file_location("patient_retrieval_summary", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PatientRetrievalSummaryTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.input_dir = self.root / "input"
        self.output_dir = self.root / "output"
        self.input_dir.mkdir()
        self._build_complete_fixture()

    def tearDown(self):
        self.tempdir.cleanup()

    def _identity_path(self, arm, cancer, seed):
        return self.input_dir / f"{arm}_{cancer}_s{seed}.json"

    def _read_unit(self, arm="m0real", cancer="BLCA", seed=123):
        path = self._identity_path(arm, cancer, seed)
        return path, json.loads(path.read_text(encoding="utf-8"))

    def _write_unit(self, path, payload):
        path.write_text(json.dumps(payload, allow_nan=True), encoding="utf-8")

    def _build_complete_fixture(self):
        artifacts_dir = self.input_dir / "artifacts"
        artifacts_dir.mkdir()
        diagnostics_dir = self.input_dir / "diagnostics"
        diagnostics_dir.mkdir()
        (diagnostics_dir / "campaign_status.json").write_text(
            json.dumps({"stage": "formal", "status": "COMPLETED"}), encoding="utf-8"
        )
        for cancer_index, cancer in enumerate(CANCERS):
            fingerprint = f"fingerprint-{cancer}"
            for seed in SEEDS:
                checkpoint = f"checkpoint-{cancer}-{seed}"
                for arm in ARMS:
                    grids = {}
                    for grid in GRIDS:
                        stem = f"{arm}_{cancer}_s{seed}_{grid}"
                        prediction = artifacts_dir / f"{stem}.predictions.json"
                        audit = artifacts_dir / f"{stem}.audit.json"
                        prediction.write_text(
                            json.dumps({"patient_ids": ["P1", "P2"]}), encoding="utf-8"
                        )
                        audit.write_text(json.dumps({"checked": True}), encoding="utf-8")
                        grids[grid] = {
                            "cindex_B": round(
                                ARM_BASE[arm]
                                + cancer_index * 0.01
                                + SEED_OFFSET[seed]
                                + GRID_OFFSET[grid],
                                8,
                            ),
                            "n_test": 2,
                            "n_complete_checked": 1 if grid == "none" else 0,
                            "complete_max_logit_abs_diff": 0.0 if grid == "none" else None,
                            "complete_logit_atol": 1e-6,
                            "grid_sha": f"grid-{cancer}-{seed}-{grid}",
                            "predictions_file": str(prediction.relative_to(self.input_dir)),
                            "predictions_sha256": sha256(prediction),
                            "audit_file": str(audit.relative_to(self.input_dir)),
                            "audit_sha256": sha256(audit),
                        }
                    payload = {
                        "arm": arm,
                        "cancer": cancer,
                        "seed": seed,
                        "checkpoint_sha256": checkpoint,
                        "comparison_fingerprint": fingerprint,
                        "protocol_id": "patient-fixed-padmask-v2",
                        "grids": grids,
                    }
                    self._write_unit(self._identity_path(arm, cancer, seed), payload)

    def _summarize(self):
        return load_module().summarize(self.input_dir, self.output_dir)

    def _write_run_manifests(self):
        digest = 'a' * 64
        payloads = {
            'source_manifest.json': {
                'source_commit': '6a04a0bf5c283a57e90207899ddffe3867fd5e0a',
                'cancers': {c: {'src/trimodalsurv/models/npjc.py': digest} for c in CANCERS},
                'failures': {},
            },
            'data_manifest.json': {
                'cancers': {c: {'bank': {'fingerprint': digest, 'train_ids': ['TRAIN']},
                                'label_sha256': digest, 'manifest_sha256': digest,
                                'cache_hashes': {'img_sur_train.pkl': digest}} for c in CANCERS},
                'failures': {},
            },
            'checkpoint_manifest.json': {
                'cancers': {c: {str(seed): {'path': f'/weights/{c}/{seed}.pth',
                                           'sha256': digest, 'state_sha256': digest,
                                           'strict_load': True} for seed in SEEDS} for c in CANCERS},
                'failures': {},
            },
        }
        for name, payload in payloads.items():
            self._write_unit(self.input_dir / name, payload)
        return payloads

    def test_new_run_layout_manifests_preserve_full_summary(self):
        self._write_run_manifests()
        (self.input_dir / 'resolved_config.yaml').write_text('{}')
        (self.input_dir / 'analysis.md').write_text('preflight boundary')
        raw, audit = self.input_dir / 'raw', self.input_dir / 'audit'
        raw.mkdir()
        audit.mkdir()
        for path in self.input_dir.glob('*_s*.json'):
            payload = json.loads(path.read_text())
            for grid in payload['grids'].values():
                for key, directory in (('predictions_file', raw), ('audit_file', audit)):
                    old = self.input_dir / grid[key]
                    new = directory / old.name
                    old.rename(new)
                    grid[key] = str(new.relative_to(self.input_dir))
            self._write_unit(path, payload)
        summary = self._summarize()
        self.assertEqual(summary['unit_count'], 75)
        self.assertEqual(len(summary['per_cell']), 60)
        self.assertEqual(len(summary['contrasts']), 40)

    def test_known_manifest_malformed_schema_is_rejected(self):
        payloads = self._write_run_manifests()
        for name, original in payloads.items():
            malformed = [[], {}, dict(original, failures={'BLCA': 'failed'}),
                         dict(original, cancers={'BLCA': {}})]
            if name == 'source_manifest.json':
                malformed.append(dict(original, source_commit='wrong'))
            for payload in malformed:
                with self.subTest(name=name, payload=payload):
                    self._write_unit(self.input_dir / name, payload)
                    with self.assertRaisesRegex(ValueError, 'manifest schema'):
                        self._summarize()
                    self.assertFalse(self.output_dir.exists())
            self._write_unit(self.input_dir / name, original)

    def test_00_production_module_exists(self):
        self.assertTrue(SCRIPT.is_file(), "汇总器模块尚未实现")

    def test_report_none_does_not_claim_complete_data(self):
        self._summarize()
        report = (self.output_dir / 'report.md').read_text()
        self.assertIn('无额外人工遮挡（`none`，保留天然缺失）', report)
        self.assertIn('天然缺失仍按三臂各自规则处理', report)
        self.assertNotIn('Complete-data', report)

    def test_v1_v2_mixed_protocol_is_rejected(self):
        path, payload = self._read_unit('retrieval')
        payload['protocol_id'] = 'patient-fixed-v1'
        self._write_unit(path, payload)
        with self.assertRaisesRegex(ValueError, 'protocol'):
            self._summarize()
        self.assertFalse(self.output_dir.exists())

    def test_inconsistent_check_diagnostics_rejected(self):
        path, payload = self._read_unit()
        baseline = dict(payload['grids']['none'])
        invalid = [
            {'n_complete_checked': 0, 'complete_max_logit_abs_diff': 0.0},
            {'n_complete_checked': 1, 'complete_max_logit_abs_diff': None},
            {'n_complete_checked': -1}, {'n_complete_checked': 3},
            {'n_complete_checked': True}, {'n_complete_checked': 1.5},
            {'complete_max_logit_abs_diff': -1e-9},
            {'complete_max_logit_abs_diff': 2e-6},
            {'complete_max_logit_abs_diff': math.nan},
            {'complete_max_logit_abs_diff': True},
            {'complete_logit_atol': 1e-3},
        ]
        for changes in invalid:
            with self.subTest(changes=changes):
                value = dict(baseline, **changes)
                with self.assertRaisesRegex(ValueError, 'complete'):
                    load_module()._validate_grid(value, path, 'none')

    def test_missing_check_count_rejected_for_formal_summary(self):
        path, payload = self._read_unit()
        del payload['grids']['none']['n_complete_checked']
        with self.assertRaisesRegex(ValueError, 'n_complete_checked'):
            load_module()._validate_grid(payload['grids']['none'], path, 'none')

    def test_artificial_missing_cannot_claim_complete_checks(self):
        path, payload = self._read_unit()
        value = payload['grids']['both_100']
        value.update(n_complete_checked=1, complete_max_logit_abs_diff=0.0)
        with self.assertRaisesRegex(ValueError, 'complete'):
            load_module()._validate_grid(value, path, 'both_100')

    def test_paired_check_metadata_must_match(self):
        path, payload = self._read_unit('m1')
        payload['grids']['none']['complete_max_logit_abs_diff'] = 5e-7
        self._write_unit(path, payload)
        with self.assertRaisesRegex(ValueError, 'paired.*metadata'):
            self._summarize()

    def test_complete_75_unit_fixture_writes_expected_outputs_and_arithmetic(self):
        self._summarize()
        self.assertEqual(
            {path.name for path in self.output_dir.iterdir()},
            {"summary.json", "per_cell.csv", "paired_deltas.csv", "report.md"},
        )
        summary = json.loads((self.output_dir / "summary.json").read_text(encoding="utf-8"))
        self.assertEqual(summary["unit_count"], 75)
        cell = next(
            item
            for item in summary["per_cell"]
            if item["cancer"] == "BLCA"
            and item["grid"] == "rna_100"
            and item["arm"] == "retrieval"
        )
        self.assertEqual(cell["n_seeds"], 5)
        self.assertAlmostEqual(cell["mean"], 0.60)
        self.assertAlmostEqual(cell["sample_std"], 0.015811388300841896)

        contrast = next(
            item
            for item in summary["contrasts"]
            if item["cancer"] == "BLCA"
            and item["grid"] == "rna_100"
            and item["contrast"] == "retrieval-minus-m1"
        )
        for delta in contrast["deltas"]:
            self.assertAlmostEqual(delta, 0.10)
        self.assertAlmostEqual(contrast["mean"], 0.10)
        self.assertAlmostEqual(contrast["sample_std"], 0.0)
        self.assertEqual(
            {key: contrast[key] for key in ("wins", "ties", "losses")},
            {"wins": 5, "ties": 0, "losses": 0},
        )

        with (self.output_dir / "per_cell.csv").open(newline="", encoding="utf-8") as handle:
            self.assertEqual(len(list(csv.DictReader(handle))), 60)
        with (self.output_dir / "paired_deltas.csv").open(newline="", encoding="utf-8") as handle:
            self.assertEqual(len(list(csv.DictReader(handle))), 200)

    def test_macro_overview_excludes_none_and_reports_worst_missing_grid(self):
        self._summarize()
        summary = json.loads((self.output_dir / "summary.json").read_text(encoding="utf-8"))
        self.assertAlmostEqual(summary["overview_missing_only"]["arms"]["m0real"], 0.42)
        self.assertAlmostEqual(summary["overview_missing_only"]["arms"]["m1"], 0.52)
        self.assertAlmostEqual(summary["overview_missing_only"]["arms"]["retrieval"], 0.62)
        self.assertAlmostEqual(
            summary["overview_missing_only"]["contrasts"]["retrieval-minus-m1"], 0.10
        )
        worst = next(
            item
            for item in summary["worst_missing_grid"]
            if item["cancer"] == "UCEC" and item["arm"] == "m1"
        )
        self.assertEqual(worst["grid"], "both_100")
        self.assertAlmostEqual(worst["mean"], 0.52)

    def test_exact_zero_delta_is_counted_as_tie(self):
        for seed in SEEDS:
            m1_path, m1 = self._read_unit("m1", "BLCA", seed)
            retrieval_path, retrieval = self._read_unit("retrieval", "BLCA", seed)
            retrieval["grids"]["rna_100"]["cindex_B"] = m1["grids"]["rna_100"]["cindex_B"]
            self._write_unit(retrieval_path, retrieval)
        self._summarize()
        summary = json.loads((self.output_dir / "summary.json").read_text(encoding="utf-8"))
        contrast = next(
            item
            for item in summary["contrasts"]
            if item["cancer"] == "BLCA"
            and item["grid"] == "rna_100"
            and item["contrast"] == "retrieval-minus-m1"
        )
        self.assertEqual((contrast["wins"], contrast["ties"], contrast["losses"]), (0, 5, 0))
        self.assertEqual(contrast["deltas"], [0.0] * 5)

    def test_missing_unit_is_rejected_without_outputs(self):
        self._identity_path("m0real", "BLCA", 123).unlink()
        with self.assertRaises(ValueError):
            self._summarize()
        self.assertFalse(self.output_dir.exists())

    def test_missing_campaign_status_is_rejected(self):
        (self.input_dir / "diagnostics" / "campaign_status.json").unlink()
        with self.assertRaises(ValueError):
            self._summarize()

    def test_running_campaign_is_rejected(self):
        status_path = self.input_dir / "diagnostics" / "campaign_status.json"
        status_path.write_text(
            json.dumps({"stage": "formal", "status": "RUNNING"}), encoding="utf-8"
        )
        with self.assertRaises(ValueError):
            self._summarize()

    def test_failed_campaign_is_rejected(self):
        status_path = self.input_dir / "diagnostics" / "campaign_status.json"
        status_path.write_text(
            json.dumps({"stage": "formal", "status": "FAILED"}), encoding="utf-8"
        )
        with self.assertRaises(ValueError):
            self._summarize()

    def test_duplicate_identity_in_differently_named_json_is_rejected(self):
        _, payload = self._read_unit()
        self._write_unit(self.input_dir / "duplicate.json", payload)
        with self.assertRaises(ValueError):
            self._summarize()

    def test_unknown_seed_is_rejected(self):
        path, payload = self._read_unit()
        path.unlink()
        payload["seed"] = 999
        self._write_unit(self.input_dir / "m0real_BLCA_s999.json", payload)
        with self.assertRaises(ValueError):
            self._summarize()

    def test_nan_cindex_is_rejected(self):
        path, payload = self._read_unit()
        payload["grids"]["none"]["cindex_B"] = math.nan
        self._write_unit(path, payload)
        with self.assertRaises(ValueError):
            self._summarize()

    def test_paired_checkpoint_or_fingerprint_mismatch_is_rejected(self):
        path, payload = self._read_unit("retrieval", "BLCA", 123)
        payload["checkpoint_sha256"] = "other-checkpoint"
        self._write_unit(path, payload)
        with self.assertRaises(ValueError):
            self._summarize()

    def test_same_cancer_fingerprint_mismatch_across_seeds_is_rejected(self):
        for arm in ARMS:
            path, payload = self._read_unit(arm, "BLCA", 132)
            payload["comparison_fingerprint"] = "other-fingerprint"
            self._write_unit(path, payload)
        with self.assertRaises(ValueError):
            self._summarize()

    def test_same_cancer_duplicate_checkpoint_across_seeds_is_rejected(self):
        _, seed_123 = self._read_unit("m0real", "BLCA", 123)
        for arm in ARMS:
            path, payload = self._read_unit(arm, "BLCA", 132)
            payload["checkpoint_sha256"] = seed_123["checkpoint_sha256"]
            self._write_unit(path, payload)
        with self.assertRaisesRegex(ValueError, "checkpoint_sha256 reused"):
            self._summarize()

    def test_paired_grid_sample_count_mismatch_is_rejected(self):
        path, payload = self._read_unit("retrieval", "BLCA", 123)
        payload["grids"]["none"]["n_test"] = 3
        self._write_unit(path, payload)
        with self.assertRaises(ValueError):
            self._summarize()

    def test_paired_grid_sha_mismatch_is_rejected(self):
        path, payload = self._read_unit("retrieval", "BLCA", 123)
        payload["grids"]["none"]["grid_sha"] = "other-grid"
        self._write_unit(path, payload)
        with self.assertRaises(ValueError):
            self._summarize()

    def test_missing_artifact_is_rejected(self):
        _, payload = self._read_unit()
        artifact = self.input_dir / payload["grids"]["none"]["predictions_file"]
        artifact.unlink()
        with self.assertRaises(ValueError):
            self._summarize()

    def test_tampered_artifact_is_rejected(self):
        path, payload = self._read_unit()
        artifact = self.input_dir / payload["grids"]["none"]["predictions_file"]
        artifact.write_text("tampered", encoding="utf-8")
        with self.assertRaises(ValueError):
            self._summarize()

    def test_artifact_path_escape_is_rejected_even_when_hash_matches(self):
        path, payload = self._read_unit()
        outside = self.root / "outside.json"
        outside.write_text("outside", encoding="utf-8")
        payload["grids"]["none"]["audit_file"] = "../outside.json"
        payload["grids"]["none"]["audit_sha256"] = sha256(outside)
        self._write_unit(path, payload)
        with self.assertRaises(ValueError):
            self._summarize()

    def test_existing_output_target_is_never_overwritten(self):
        self.output_dir.mkdir()
        sentinel = self.output_dir / "summary.json"
        sentinel.write_text("keep", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            self._summarize()
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep")

    def test_cli_accepts_required_directories(self):
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), "--input-dir", str(self.input_dir), "--out-dir", str(self.output_dir)],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertTrue((self.output_dir / "summary.json").is_file())


if __name__ == "__main__":
    unittest.main()
