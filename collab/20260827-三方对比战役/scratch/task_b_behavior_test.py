#!/usr/bin/env python3
"""本地 HTTP 集成测试：GDC 查询、manifest、续传和完整性边界。"""

import csv
import hashlib
import json
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "adapters" / "gdc_fetch_star_counts.py"
SCRATCH = ROOT / "scratch"


def md5(data):
    return hashlib.md5(data).hexdigest()


def hit(patient, sample, file_id, file_name, checksum, sample_type="Primary Tumor"):
    return {
        "file_id": file_id, "file_name": file_name, "md5sum": checksum,
        "access": "open", "analysis": {"workflow_type": "STAR - Counts"},
        "cases": [{"submitter_id": patient, "samples": [
            {"submitter_id": sample, "sample_type": sample_type},
        ]}],
    }


class FakeGDC(BaseHTTPRequestHandler):
    requests = []
    files_pages = {}
    files_total = 0
    payloads = {}
    data_responses = {}

    def log_message(self, *_args):
        pass

    def _write(self, status, data, content_type="application/json", headers=None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        raw = self.rfile.read(int(self.headers["Content-Length"]))
        self.__class__.requests.append((self.command, self.path, dict(self.headers), raw))
        if self.path != "/files":
            self._write(404, b"{}")
            return
        body = json.loads(raw)
        start = int(body.get("from", 0))
        self._write(200, json.dumps({"data": {
            "hits": self.__class__.files_pages.get(start, []),
            "pagination": {"total": self.__class__.files_total},
        }}).encode())

    def do_GET(self):
        self.__class__.requests.append((self.command, self.path, dict(self.headers), b""))
        file_id = self.path.rsplit("/", 1)[-1]
        queued = self.__class__.data_responses.get(file_id, [])
        if queued:
            response = queued.pop(0)
            self._write(
                response["status"], response["data"], "application/octet-stream", response.get("headers"),
            )
            return
        data = self.__class__.payloads[file_id]
        range_header = self.headers.get("Range")
        if range_header:
            start = int(range_header.split("=", 1)[1].split("-", 1)[0])
            self._write(
                206, data[start:], "application/octet-stream",
                {"Content-Range": f"bytes {start}-{len(data) - 1}/{len(data)}"},
            )
            return
        self._write(200, data, "application/octet-stream")


class GdcFetchCliTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), FakeGDC)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.thread.join()
        cls.server.server_close()

    def setUp(self):
        FakeGDC.requests = []
        FakeGDC.files_pages = {}
        FakeGDC.files_total = 0
        FakeGDC.payloads = {}
        FakeGDC.data_responses = {}
        self.temp = tempfile.TemporaryDirectory(dir=SCRATCH)
        self.work = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def labels(self, *patients):
        path = self.work / "labels.csv"
        with path.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["patient_id", "cancer_type"])
            writer.writeheader()
            for patient in patients:
                writer.writerow({"patient_id": patient, "cancer_type": "BRCA"})
        return path

    def run_cli(self, labels, out, *extra):
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--labels", str(labels), "--cancers", "BRCA",
             "--out", str(out), "--api-base", self.base, *extra],
            text=True, capture_output=True, check=False,
        )

    def data_requests(self):
        return [(path, headers.get("Range")) for _, path, headers, _ in FakeGDC.requests if path.startswith("/data/")]

    def test_dry_run_paginates_and_emits_structured_gdc_filter_with_deterministic_manifest(self):
        """若分页、筛选树、01+Primary、白名单或稳定择一退化，此测试失败。"""
        labels = self.labels("TCGA-AA-0001", "TCGA-BB-0002", "TCGA-CC-0003", "TCGA-DD-0004")
        FakeGDC.files_pages = {
            0: [
                hit("TCGA-AA-0001", "TCGA-AA-0001-01A", "z", "z.tsv", md5(b"z")),
                hit("TCGA-AA-0001", "TCGA-AA-0001-01A", "alpha", "alpha.tsv", md5(b"alpha")),
            ],
            2: [
                hit("TCGA-BB-0002", "TCGA-BB-0002-01A", "beta", "beta.tsv", md5(b"beta")),
                hit("TCGA-AA-0001", "TCGA-AA-0001-01A", "wrongtype", "wrong.tsv", md5(b"wrong"), "Solid Tissue Normal"),
            ],
            4: [
                hit("TCGA-DD-0004", "TCGA-DD-0004-01A", "delta", "delta.tsv", md5(b"delta")),
                hit("TCGA-ZZ-9999", "TCGA-ZZ-9999-01A", "outsider", "out.tsv", md5(b"out")),
            ],
        }
        FakeGDC.files_total = 6
        out = self.work / "dry"
        result = self.run_cli(labels, out, "--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        with (out / "manifest.csv").open(newline="") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(rows, [
            {"patient_id": "TCGA-AA-0001", "file_id": "alpha", "file_name": "alpha.tsv", "md5": md5(b"alpha")},
            {"patient_id": "TCGA-BB-0002", "file_id": "beta", "file_name": "beta.tsv", "md5": md5(b"beta")},
            {"patient_id": "TCGA-DD-0004", "file_id": "delta", "file_name": "delta.tsv", "md5": md5(b"delta")},
        ])
        self.assertEqual((out / "missing_BRCA.csv").read_text().splitlines(), ["patient_id", "TCGA-CC-0003"])
        self.assertIn("BRCA: labels CSV 病人数=4, 命中数=3, 缺失数=1", result.stdout)
        self.assertEqual(self.data_requests(), [])
        file_posts = [json.loads(raw) for method, path, _, raw in FakeGDC.requests if method == "POST" and path == "/files"]
        self.assertEqual([body.get("from", 0) for body in file_posts], [0, 2, 4])
        expected_fields = {
            "file_id", "file_name", "md5sum", "access", "analysis.workflow_type",
            "cases.submitter_id", "cases.samples.submitter_id", "cases.samples.sample_type",
        }
        self.assertEqual(set(file_posts[0]["fields"].split(",")), expected_fields)
        clauses = file_posts[0]["filters"]["content"]
        scalar = {clause["content"]["field"]: clause["content"]["value"] for clause in clauses if clause["op"] == "="}
        self.assertEqual(scalar, {
            "cases.project.project_id": "TCGA-BRCA",
            "data_type": "Gene Expression Quantification",
            "analysis.workflow_type": "STAR - Counts",
            "access": "open",
        })
        patient_clause = next(clause for clause in clauses if clause["op"] == "in")
        self.assertEqual(patient_clause["content"]["field"], "cases.submitter_id")
        self.assertEqual(patient_clause["content"]["value"], ["TCGA-AA-0001", "TCGA-BB-0002", "TCGA-CC-0003", "TCGA-DD-0004"])

    def test_complete_correct_part_finalizes_without_data_request(self):
        """若完整正确的 .part 仍发 Range 或不原子完成，此测试失败。"""
        data = b"already-complete"
        labels = self.labels("TCGA-AA-0001")
        FakeGDC.files_pages = {0: [hit("TCGA-AA-0001", "TCGA-AA-0001-01A", "alpha", "alpha.tsv", md5(data))]}
        FakeGDC.files_total = 1
        out = self.work / "complete-part"
        out.mkdir()
        (out / "alpha.tsv.part").write_bytes(data)
        result = self.run_cli(labels, out, "--limit", "1")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((out / "alpha.tsv").read_bytes(), data)
        self.assertFalse((out / "alpha.tsv.part").exists())
        self.assertEqual(self.data_requests(), [])

    def test_416_corrupt_part_is_quarantined_then_retried_from_zero_once(self):
        """若 416 造成永久续传死锁或不隔离坏 part，此测试失败。"""
        data = b"fresh-full-content"
        labels = self.labels("TCGA-AA-0001")
        FakeGDC.files_pages = {0: [hit("TCGA-AA-0001", "TCGA-AA-0001-01A", "reset", "reset.tsv", md5(data))]}
        FakeGDC.files_total = 1
        FakeGDC.data_responses = {"reset": [
            {"status": 416, "data": b""}, {"status": 200, "data": data},
        ]}
        out = self.work / "reset"
        out.mkdir()
        (out / "reset.tsv.part").write_bytes(b"damaged")
        result = self.run_cli(labels, out, "--limit", "1")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((out / "reset.tsv").read_bytes(), data)
        self.assertEqual((out / "reset.tsv.part.corrupt").read_bytes(), b"damaged")
        self.assertEqual(self.data_requests(), [("/data/reset", "bytes=7-"), ("/data/reset", None)])

    def test_bad_206_content_range_is_rejected_without_appending(self):
        """若 206 起点未核验就追加，损坏 part 会被静默扩大，此测试失败。"""
        data = b"12345"
        labels = self.labels("TCGA-AA-0001")
        FakeGDC.files_pages = {0: [hit("TCGA-AA-0001", "TCGA-AA-0001-01A", "range", "range.tsv", md5(data))]}
        FakeGDC.files_total = 1
        FakeGDC.data_responses = {"range": [
            {"status": 206, "data": b"345", "headers": {"Content-Range": "bytes 1-4/5"}},
        ]}
        out = self.work / "bad-range"
        out.mkdir()
        (out / "range.tsv.part").write_bytes(b"12")
        result = self.run_cli(labels, out, "--limit", "1")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Content-Range", result.stderr)
        self.assertEqual((out / "range.tsv.part").read_bytes(), b"12")
        self.assertFalse((out / "range.tsv").exists())

    def test_server_200_to_range_request_rewrites_part_from_zero(self):
        """若服务端忽略 Range 仍追加，最终文件会把旧 part 和完整文件拼接。"""
        data = b"complete-response"
        labels = self.labels("TCGA-AA-0001")
        FakeGDC.files_pages = {0: [hit("TCGA-AA-0001", "TCGA-AA-0001-01A", "ignored", "ignored.tsv", md5(data))]}
        FakeGDC.files_total = 1
        FakeGDC.data_responses = {"ignored": [{"status": 200, "data": data}]}
        out = self.work / "range-ignored"
        out.mkdir()
        (out / "ignored.tsv.part").write_bytes(b"stale")
        result = self.run_cli(labels, out, "--limit", "1")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((out / "ignored.tsv").read_bytes(), data)
        self.assertFalse((out / "ignored.tsv.part").exists())
        self.assertEqual(self.data_requests(), [("/data/ignored", "bytes=5-")])

    def test_md5_mismatch_quarantines_part_and_next_run_can_recover(self):
        """若 MD5 失败保留同名 .part，下一次会错误续传而非完整重下。"""
        good = b"good-content"
        labels = self.labels("TCGA-AA-0001")
        FakeGDC.files_pages = {0: [hit("TCGA-AA-0001", "TCGA-AA-0001-01A", "recover", "recover.tsv", md5(good))]}
        FakeGDC.files_total = 1
        FakeGDC.data_responses = {"recover": [
            {"status": 200, "data": b"wrong-content"}, {"status": 200, "data": good},
        ]}
        out = self.work / "recover"
        first = self.run_cli(labels, out, "--limit", "1")
        self.assertNotEqual(first.returncode, 0)
        self.assertFalse((out / "recover.tsv.part").exists())
        self.assertEqual((out / "recover.tsv.part.corrupt").read_bytes(), b"wrong-content")
        second = self.run_cli(labels, out, "--limit", "1")
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual((out / "recover.tsv").read_bytes(), good)
        self.assertEqual(self.data_requests(), [("/data/recover", None), ("/data/recover", None)])

    def test_limit_one_keeps_three_row_manifest_but_makes_exactly_one_data_request(self):
        """若 limit 截断 manifest 或下载多于一个目标，此测试失败。"""
        labels = self.labels("TCGA-AA-0001", "TCGA-BB-0002", "TCGA-CC-0003")
        FakeGDC.files_pages = {0: [
            hit("TCGA-AA-0001", "TCGA-AA-0001-01A", "a", "a.tsv", md5(b"a")),
            hit("TCGA-BB-0002", "TCGA-BB-0002-01A", "b", "b.tsv", md5(b"b")),
            hit("TCGA-CC-0003", "TCGA-CC-0003-01A", "c", "c.tsv", md5(b"c")),
        ]}
        FakeGDC.files_total = 3
        FakeGDC.payloads = {"a": b"a", "b": b"b", "c": b"c"}
        out = self.work / "limit"
        result = self.run_cli(labels, out, "--limit", "1")
        self.assertEqual(result.returncode, 0, result.stderr)
        with (out / "manifest.csv").open(newline="") as handle:
            self.assertEqual(len(list(csv.DictReader(handle))), 3)
        self.assertEqual(self.data_requests(), [("/data/a", None)])

    def test_unsafe_filename_and_manifest_collision_fail_before_data_request(self):
        """若路径穿越或不同 row 的同名目标未拒绝，文件可能被覆盖。"""
        labels = self.labels("TCGA-AA-0001")
        FakeGDC.files_pages = {0: [hit("TCGA-AA-0001", "TCGA-AA-0001-01A", "evil", "../evil.tsv", md5(b"evil"))]}
        FakeGDC.files_total = 1
        out = self.work / "unsafe"
        result = self.run_cli(labels, out, "--limit", "1")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("不安全", result.stderr)
        self.assertEqual(self.data_requests(), [])

        FakeGDC.requests = []
        labels = self.labels("TCGA-AA-0001", "TCGA-BB-0002")
        FakeGDC.files_pages = {0: [
            hit("TCGA-AA-0001", "TCGA-AA-0001-01A", "one", "same.tsv", md5(b"one")),
            hit("TCGA-BB-0002", "TCGA-BB-0002-01A", "two", "same.tsv", md5(b"two")),
        ]}
        FakeGDC.files_total = 2
        result = self.run_cli(labels, self.work / "collision", "--limit", "2")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("碰撞", result.stderr)
        self.assertEqual(self.data_requests(), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
