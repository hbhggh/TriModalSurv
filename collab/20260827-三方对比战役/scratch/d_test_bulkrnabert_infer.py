#!/usr/bin/env python3
"""任务 D 的白名单内回归测试。"""
from __future__ import annotations

import importlib.util
import csv
import pickle
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock

import numpy as np
import torch


TASK_DIR = Path(__file__).resolve().parents[1]
ADAPTER_PATH = TASK_DIR / "adapters" / "bulkrnabert_infer.py"


def load_adapter():
    if not ADAPTER_PATH.is_file():
        raise AssertionError(f"待实现脚本不存在: {ADAPTER_PATH}")
    spec = importlib.util.spec_from_file_location("bulkrnabert_infer", ADAPTER_PATH)
    if spec is None or spec.loader is None:
        raise AssertionError(f"无法加载脚本: {ADAPTER_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class BulkRNABertInferTests(unittest.TestCase):
    def test_cli_help_exposes_required_contract(self):
        completed = subprocess.run(
            [sys.executable, str(ADAPTER_PATH), "--help"],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        for flag in (
            "--manifests",
            "--tsv-dirs",
            "--cancers",
            "--labels",
            "--out",
            "--compare-with",
            "--device",
            "--dtype",
            "--limit",
        ):
            self.assertIn(flag, completed.stdout)

    def test_cli_maps_parallel_inputs_positionally(self):
        adapter = load_adapter()
        self.assertTrue(hasattr(adapter, "parse_args"), "缺少 parse_args")
        self.assertTrue(hasattr(adapter, "validate_input_groups"), "缺少 validate_input_groups")
        args = adapter.parse_args(
            [
                "--manifests",
                "m1.csv",
                "m2.csv",
                "--tsv-dirs",
                "d1",
                "d2",
                "--cancers",
                "blca",
                "brca",
                "--labels",
                "labels_424.csv",
                "--out",
                "out",
                "--compare-with",
                "a1.pkl",
                "a2.pkl",
                "--device",
                "cpu",
                "--limit",
                "5",
            ]
        )
        groups = adapter.validate_input_groups(args)
        self.assertEqual(
            [(group[0].name, group[1].name, group[2]) for group in groups],
            [("m1.csv", "d1", "BLCA"), ("m2.csv", "d2", "BRCA")],
        )
        self.assertEqual(args.dtype, "float32")
        float16_args = adapter.parse_args(
            [
                "--manifests",
                "m1.csv",
                "--tsv-dirs",
                "d1",
                "--cancers",
                "blca",
                "--labels",
                "labels_424.csv",
                "--out",
                "out",
                "--dtype",
                "float16",
            ]
        )
        self.assertEqual(float16_args.dtype, "float16")
        bfloat16_args = adapter.parse_args(
            [
                "--manifests",
                "m1.csv",
                "--tsv-dirs",
                "d1",
                "--cancers",
                "blca",
                "--labels",
                "labels_424.csv",
                "--out",
                "out",
                "--dtype",
                "bfloat16",
            ]
        )
        self.assertEqual(bfloat16_args.dtype, "bfloat16")
        args.tsv_dirs.pop()
        with self.assertRaisesRegex(ValueError, "数量必须一致"):
            adapter.validate_input_groups(args)

    def test_compare_with_author_matches_by_pid_and_reports_distribution(self):
        adapter = load_adapter()
        self.assertTrue(hasattr(adapter, "compare_pickles"), "缺少 compare_pickles")
        scratch = TASK_DIR / "scratch"
        with tempfile.TemporaryDirectory(prefix="d_compare_", dir=scratch) as tmp:
            root = Path(tmp)
            generated = root / "generated.pkl"
            author = root / "author.pkl"
            with generated.open("wb") as handle:
                pickle.dump(
                    {
                        "identifier": ["PID-1", "PID-2"],
                        "embedding": [
                            np.array([[1.0, 0.0]], dtype=np.float32),
                            np.array([[1.0, 0.0]], dtype=np.float32),
                        ],
                    },
                    handle,
                )
            with author.open("wb") as handle:
                pickle.dump(
                    {
                        "identifier": ["PID-2", "PID-1", "PID-EXTRA"],
                        "embedding": [
                            np.array([[0.0, 1.0]], dtype=np.float32),
                            np.array([[1.0, 0.0]], dtype=np.float32),
                            np.array([[1.0, 1.0]], dtype=np.float32),
                        ],
                    },
                    handle,
                )
            stats = adapter.compare_pickles(generated, author)

        self.assertEqual(stats["n"], 2)
        self.assertAlmostEqual(stats["min"], 0.0)
        self.assertAlmostEqual(stats["median"], 0.5)
        self.assertAlmostEqual(stats["mean"], 0.5)
        self.assertAlmostEqual(stats["max"], 1.0)

    def test_official_common_gene_file_has_expected_order_and_count(self):
        adapter = load_adapter()
        self.assertTrue(hasattr(adapter, "read_common_gene_ids"), "缺少 read_common_gene_ids")
        path = TASK_DIR / "scratch" / "d_cache" / "common_gene_id.txt"
        gene_ids = adapter.read_common_gene_ids(path)
        self.assertEqual(len(gene_ids), 19062)
        self.assertEqual(gene_ids[:2], ["ENSG00000000003", "ENSG00000000005"])
        self.assertEqual(gene_ids[-1], "ENSG00000284596")
        self.assertEqual(len(set(gene_ids)), len(gene_ids))

    def test_hf_model_card_log10_preprocessing_and_last_layer_output(self):
        adapter = load_adapter()
        self.assertTrue(hasattr(adapter, "make_infer_one"), "缺少 make_infer_one")

        class FakeTokenizer:
            observed = None

            def batch_encode_plus(self, values, return_tensors):
                self.observed = np.array(values, copy=True)
                if return_tensors != "pt":
                    raise AssertionError(return_tensors)
                return {"input_ids": torch.tensor([[0, 1, 2, 3]], dtype=torch.long)}

        class FakeModel:
            def __call__(self, input_ids):
                if tuple(input_ids.shape) != (1, 4):
                    raise AssertionError(input_ids.shape)
                values = torch.arange(4 * 256, dtype=torch.float32).reshape(1, 4, 256)
                return {"embeddings_4": values}

        tokenizer = FakeTokenizer()
        infer_one = adapter.make_infer_one(
            model=FakeModel(),
            tokenizer=tokenizer,
            torch_module=torch,
            device="cpu",
            layer_key="embeddings_4",
            expected_genes=4,
            expected_dim=256,
        )
        output = infer_one(np.array([0.0, 9.0, 99.0, 999.0], dtype=np.float32))
        np.testing.assert_allclose(
            tokenizer.observed,
            np.array([[0.0, 1.0, 2.0, 3.0]], dtype=np.float32),
            rtol=0,
            atol=1e-6,
        )
        self.assertEqual(output.shape, (4, 256))
        self.assertEqual(output.dtype, np.float32)

    def test_three_dtype_behaviors_and_inference_mode(self):
        adapter = load_adapter()
        self.assertTrue(hasattr(adapter, "configure_model_dtype"), "缺少模型 dtype 配置")

        class FakeTokenizer:
            def batch_encode_plus(self, values, return_tensors):
                if return_tensors != "pt":
                    raise AssertionError(return_tensors)
                return {"input_ids": torch.tensor([[0, 1, 2, 3]], dtype=torch.long)}

        class TinyModel(torch.nn.Module):
            def __init__(self):
                super().__init__()
                self.embedding = torch.nn.Embedding(4, 256)
                self.observed_input_dtype = None
                self.observed_grad_enabled = None
                self.observed_inference_mode = None
                self.observed_output_requires_grad = None

            def forward(self, input_ids):
                self.observed_input_dtype = input_ids.dtype
                self.observed_grad_enabled = torch.is_grad_enabled()
                self.observed_inference_mode = torch.is_inference_mode_enabled()
                embedding = self.embedding(input_ids)
                self.observed_output_requires_grad = embedding.requires_grad
                return {"embeddings_4": embedding}

        for dtype_name, expected_dtype in (
            ("float32", torch.float32),
            ("bfloat16", torch.bfloat16),
        ):
            with self.subTest(dtype=dtype_name):
                model = TinyModel()
                if dtype_name == "float32":
                    model.bfloat16()
                configured = adapter.configure_model_dtype(model, dtype_name)
                self.assertIs(configured, model)
                self.assertEqual(next(model.parameters()).dtype, expected_dtype)
                infer_one = adapter.make_infer_one(
                    model=model,
                    tokenizer=FakeTokenizer(),
                    torch_module=torch,
                    device="cpu",
                    layer_key="embeddings_4",
                    expected_genes=4,
                    expected_dim=256,
                )
                with torch.enable_grad():
                    with mock.patch.object(torch.cuda, "empty_cache") as empty_cache:
                        output = infer_one(np.ones(4, dtype=np.float32))
                self.assertEqual(model.observed_input_dtype, torch.long)
                self.assertFalse(model.observed_grad_enabled)
                self.assertTrue(model.observed_inference_mode)
                self.assertFalse(model.observed_output_requires_grad)
                self.assertEqual(output.dtype, np.float32)
                self.assertEqual(output.shape, (4, 256))
                empty_cache.assert_called_once_with()

        with self.assertRaisesRegex(
            RuntimeError, "该模型官方实现不支持 half（-1e30 掩码溢出）"
        ):
            adapter.configure_model_dtype(TinyModel(), "float16")

        mask = torch.tensor([True, False])
        with self.assertRaisesRegex(RuntimeError, "overflow"):
            torch.where(mask, torch.zeros(2, dtype=torch.float16), -1e30)
        bf16_masked = torch.where(
            mask, torch.zeros(2, dtype=torch.bfloat16), -1e30
        )
        self.assertEqual(bf16_masked.dtype, torch.bfloat16)
        self.assertTrue(torch.isfinite(bf16_masked).all())

    def test_star_counts_alignment_strips_versions_skips_metadata_and_zero_fills(self):
        adapter = load_adapter()
        scratch = TASK_DIR / "scratch"
        with tempfile.TemporaryDirectory(prefix="d_parser_", dir=scratch) as tmp:
            tsv_path = Path(tmp) / "sample.tsv"
            tsv_path.write_text(
                "# gene-model: synthetic\n"
                "gene_id\tgene_name\ttpm_unstranded\n"
                "N_unmapped\t\t\n"
                "ENSG000002.7\tB\t0\n"
                "ENSG000001.12\tA\t2.5\n"
                "ENSG000001.12_PAR_Y\tA_PAR_Y\t7.0\n"
                "ENSG999999.1\tEXTRA\t9.0\n",
                encoding="utf-8",
            )
            try:
                expression = adapter.read_star_counts(tsv_path)
            except ValueError as exc:
                self.fail(f"合法 _PAR_Y 行不应被版本号清理制造为重复: {exc}")
            self.assertEqual(expression["ENSG000001"], 2.5)
            self.assertEqual(expression["ENSG000001_PAR_Y"], 7.0)
            vector = adapter.build_expression_vector(
                expression,
                ["ENSG000002", "ENSG000001", "ENSG_MISSING"],
            )

        self.assertEqual(vector.dtype, np.float32)
        np.testing.assert_array_equal(vector, np.array([0.0, 2.5, 0.0], dtype=np.float32))

    def test_three_synthetic_patients_write_npj_token_embeddings(self):
        adapter = load_adapter()
        self.assertTrue(hasattr(adapter, "read_label_patients"), "缺少 read_label_patients")
        self.assertTrue(hasattr(adapter, "process_cancer"), "缺少 process_cancer")
        scratch = TASK_DIR / "scratch"
        with tempfile.TemporaryDirectory(prefix="d_three_patients_", dir=scratch) as tmp:
            root = Path(tmp)
            tsv_dir = root / "tsv"
            out_dir = root / "out"
            tsv_dir.mkdir()
            labels_path = root / "labels.csv"
            manifest_path = root / "manifest.csv"
            patients = ["TCGA-ZZ-0001", "TCGA-ZZ-0002", "TCGA-ZZ-0003"]

            with labels_path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=["patient_id", "cancer_type"])
                writer.writeheader()
                for patient_id in patients:
                    writer.writerow({"patient_id": patient_id, "cancer_type": "FAKE"})

            with manifest_path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=["patient_id", "file_id", "file_name", "md5"],
                )
                writer.writeheader()
                for index, patient_id in enumerate(patients, start=1):
                    file_name = f"patient_{index}.tsv"
                    writer.writerow(
                        {
                            "patient_id": patient_id,
                            "file_id": f"file-{index}",
                            "file_name": file_name,
                            "md5": f"md5-{index}",
                        }
                    )
                    (tsv_dir / file_name).write_text(
                        "# synthetic\n"
                        "gene_id\ttpm_unstranded\n"
                        "N_unmapped\t\n"
                        f"ENSG000001.9\t{index}.0\n",
                        encoding="utf-8",
                    )

            common_gene_ids = ["ENSG000001"] + [f"ENSGX{index:05d}" for index in range(2047)]

            def fake_infer(vector):
                self.assertEqual(vector.shape, (2048,))
                return np.repeat(vector[:, None], 256, axis=1).astype(np.float32)

            label_patients = adapter.read_label_patients(labels_path, ["FAKE"])["FAKE"]
            stdout = StringIO()
            with redirect_stdout(stdout):
                summary = adapter.process_cancer(
                    cancer="FAKE",
                    label_patients=label_patients,
                    manifest_path=manifest_path,
                    tsv_dir=tsv_dir,
                    common_gene_ids=common_gene_ids,
                    infer_one=fake_infer,
                    out_dir=out_dir,
                    limit=None,
                )

            output_path = out_dir / "RNA_FAKE_embedding_token_lvl.pkl"
            with output_path.open("rb") as handle:
                payload = pickle.load(handle)
            self.assertEqual(payload["identifier"], patients)
            self.assertEqual(len(payload["embedding"]), 3)
            self.assertTrue(all(item.dtype == np.float32 for item in payload["embedding"]))
            self.assertTrue(all(item.shape == (2048, 256) for item in payload["embedding"]))
            self.assertEqual(summary["tsv_hits"], 3)
            self.assertIn("[FAKE] labels=3 manifest命中=3 tsv命中=3 输出=3", stdout.getvalue())
            self.assertIn("shape=(2048, 256)", stdout.getvalue())


if __name__ == "__main__":
    unittest.main(verbosity=2)
