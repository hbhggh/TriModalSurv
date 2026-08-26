#!/usr/bin/env python3
"""下载 TCGA Primary Tumor STAR - Counts；不包含任何表达预处理。"""

import argparse
import csv
import hashlib
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


GDC_API_BASE = "https://api.gdc.cancer.gov"
FILE_SELECTION_RULE = "(sample_submitter_id, file_name, file_id) 字典序最小"
MANIFEST_COLUMNS = ("patient_id", "file_id", "file_name", "md5")
REQUIRED_FIELDS = (
    "file_id,file_name,md5sum,access,analysis.workflow_type,"
    "cases.submitter_id,cases.samples.submitter_id,cases.samples.sample_type"
)


def md5_file(path):
    digest = hashlib.md5()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_labels(path, cancers):
    groups = {cancer: set() for cancer in cancers}
    with Path(path).open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or not {"patient_id", "cancer_type"}.issubset(reader.fieldnames):
            raise ValueError("labels CSV 必须包含 patient_id,cancer_type")
        for row in reader:
            cancer = (row.get("cancer_type") or "").strip().upper()
            patient = (row.get("patient_id") or "").strip()
            if cancer in groups and patient:
                groups[cancer].add(patient)
    return groups


def make_filters(cancer, patient_ids):
    return {
        "op": "and",
        "content": [
            {"op": "=", "content": {"field": "cases.project.project_id", "value": f"TCGA-{cancer}"}},
            {"op": "=", "content": {"field": "data_type", "value": "Gene Expression Quantification"}},
            {"op": "=", "content": {"field": "analysis.workflow_type", "value": "STAR - Counts"}},
            {"op": "=", "content": {"field": "access", "value": "open"}},
            {"op": "in", "content": {"field": "cases.submitter_id", "value": sorted(patient_ids)}},
        ],
    }


def query_files(api_base, cancer, patient_ids):
    """读取 GDC 声明的全部 pages；不得因单页响应而静默漏文件。"""
    all_hits = []
    start = 0
    total = None
    while total is None or len(all_hits) < total:
        body = json.dumps({
            "filters": make_filters(cancer, patient_ids),
            "fields": REQUIRED_FIELDS,
            "format": "JSON",
            "size": 10000,
            "from": start,
        }).encode("utf-8")
        request = Request(
            f"{api_base.rstrip('/')}/files", body,
            headers={"Content-Type": "application/json", "Accept": "application/json"}, method="POST",
        )
        with urlopen(request, timeout=60) as response:
            payload = json.load(response)
        try:
            data = payload["data"]
            page = data["hits"]
            page_total = data["pagination"]["total"]
            if not isinstance(page, list) or not isinstance(page_total, int) or page_total < 0:
                raise TypeError
        except (KeyError, TypeError) as error:
            raise RuntimeError("GDC /files 响应缺少有效的 data.hits 或 data.pagination.total") from error
        if total is None:
            total = page_total
        elif total != page_total:
            raise RuntimeError(f"GDC /files 分页 total 不一致: {total} != {page_total}")
        if len(all_hits) + len(page) > total:
            raise RuntimeError("GDC /files 分页返回数量超过 pagination.total")
        all_hits.extend(page)
        if len(all_hits) == total:
            return all_hits
        if not page:
            raise RuntimeError(f"GDC /files 分页未收齐: total={total}, 已收={len(all_hits)}, 空页 from={start}")
        start += len(page)
    return all_hits


def primary_sample(sample):
    sample_id = (sample.get("submitter_id") or "").strip()
    sample_type = (sample.get("sample_type") or "").strip()
    return sample_id[13:15] == "01" and sample_type == "Primary Tumor"


def choose_manifest_rows(hits, wanted_patients):
    candidates = defaultdict(list)
    wanted = set(wanted_patients)
    for item in hits:
        if item.get("access") not in (None, "open"):
            continue
        workflow = (item.get("analysis") or {}).get("workflow_type")
        if workflow not in (None, "STAR - Counts"):
            continue
        file_id = (item.get("file_id") or "").strip()
        file_name = (item.get("file_name") or "").strip()
        checksum = (item.get("md5sum") or "").strip().lower()
        if not file_id or not file_name or not checksum:
            continue
        for case in item.get("cases") or []:
            patient = (case.get("submitter_id") or "").strip()
            if patient not in wanted:
                continue
            for sample in case.get("samples") or []:
                if primary_sample(sample):
                    sample_id = sample["submitter_id"].strip()
                    candidates[patient].append((sample_id, file_name, file_id, checksum))
    rows = []
    for patient in sorted(candidates):
        sample_id, file_name, file_id, checksum = min(candidates[patient])
        rows.append({"patient_id": patient, "file_id": file_id, "file_name": file_name, "md5": checksum})
    return rows


def write_manifest(out_dir, rows):
    path = out_dir / "manifest.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=MANIFEST_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return path


def read_manifest(path):
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != MANIFEST_COLUMNS:
            raise RuntimeError(f"manifest 列不符合契约: {path}")
        return list(reader)


def write_missing(out_dir, cancer, patients, rows):
    path = out_dir / f"missing_{cancer}.csv"
    matched = {row["patient_id"] for row in rows}
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["patient_id"])
        for patient in sorted(set(patients) - matched):
            writer.writerow([patient])
    return path, len(matched), len(set(patients) - matched)


def safe_destination(out_dir, file_name):
    if not isinstance(file_name, str) or not file_name or file_name in (".", ".."):
        raise ValueError(f"不安全的 file_name: {file_name!r}")
    if os.path.isabs(file_name) or "/" in file_name or "\\" in file_name:
        raise ValueError(f"不安全的 file_name: {file_name!r}")
    return out_dir / file_name


def preserve_bad_file(path):
    index = 0
    while True:
        suffix = ".corrupt" if index == 0 else f".corrupt.{index}"
        target = path.with_name(path.name + suffix)
        if not target.exists():
            path.replace(target)
            return target
        index += 1


def validate_manifest_destinations(out_dir, rows):
    """在任何 data 请求前拒绝路径注入和同名目标覆盖。"""
    destinations = {}
    for row in rows:
        target = safe_destination(out_dir, row["file_name"])
        previous = destinations.get(target.name)
        if previous is not None:
            raise RuntimeError(
                f"manifest 目标文件名碰撞: {target.name} "
                f"({previous['patient_id']}/{previous['file_id']} 与 {row['patient_id']}/{row['file_id']})"
            )
        destinations[target.name] = row


def content_range_start(response):
    value = response.headers.get("Content-Range")
    match = re.fullmatch(r"bytes\s+(\d+)-(\d+)/(?:\d+|\*)", value or "")
    if not match:
        raise RuntimeError(f"206 响应缺少或含有无效 Content-Range: {value!r}")
    return int(match.group(1))


def finalize_partial_if_correct(partial, target, expected):
    if partial.exists() and md5_file(partial) == expected:
        partial.replace(target)
        print(f"完成已有 .part（MD5 正确）: {target.name}")
        return True
    return False


def download_one(api_base, out_dir, row):
    target = safe_destination(out_dir, row["file_name"])
    expected = row["md5"].lower()
    if target.exists():
        if md5_file(target) == expected:
            print(f"跳过（已有且 MD5 正确）: {target.name}")
            return "skipped"
        corrupt = preserve_bad_file(target)
        print(f"已有文件 MD5 错误，已保留为: {corrupt.name}")
    partial = target.with_name(target.name + ".part")
    if finalize_partial_if_correct(partial, target, expected):
        return "finalized-part"

    retried_after_416 = False
    while True:
        offset = partial.stat().st_size if partial.exists() else 0
        headers = {"Range": f"bytes={offset}-"} if offset else {}
        request = Request(
            f"{api_base.rstrip('/')}/data/{quote(row['file_id'], safe='')}", headers=headers, method="GET"
        )
        try:
            with urlopen(request, timeout=120) as response:
                status = getattr(response, "status", response.getcode())
                if status == 206:
                    start = content_range_start(response)
                    if start != offset:
                        raise RuntimeError(
                            f"206 Content-Range 起点不匹配: 请求 {offset}, 响应 {start}"
                        )
                    mode = "ab" if offset else "wb"
                elif status == 200:
                    mode = "wb"  # 服务端忽略 Range 时必须从头覆盖 .part。
                else:
                    raise RuntimeError(f"GDC data 响应状态异常: {status}")
                with partial.open(mode) as handle:
                    while True:
                        chunk = response.read(1024 * 1024)
                        if not chunk:
                            break
                        handle.write(chunk)
            break
        except HTTPError as error:
            if error.code != 416 or offset == 0 or retried_after_416:
                raise
            # 416 可能仅说明该 .part 已经完整；重新核验后才决定完成或隔离并重下。
            if finalize_partial_if_correct(partial, target, expected):
                return "finalized-part"
            corrupt = preserve_bad_file(partial)
            print(f"416 且 .part MD5 错误，已保留为: {corrupt.name}；从头重试一次")
            retried_after_416 = True
    actual = md5_file(partial)
    if actual != expected:
        corrupt = preserve_bad_file(partial)
        print(f"下载内容 MD5 错误，已保留为: {corrupt.name}", file=sys.stderr)
        raise RuntimeError(f"MD5 mismatch for {target.name}: expected {expected}, got {actual}")
    partial.replace(target)
    print(f"下载完成（MD5 正确）: {target.name}")
    return "downloaded"


def parse_args(argv=None):
    default_out = Path(__file__).resolve().parents[1] / "scratch" / "gdc_star_counts"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--labels", required=True, help="含 patient_id,cancer_type 的 CSV")
    parser.add_argument("--cancers", required=True, nargs="+", help="例如 BRCA LUAD LGG UCEC")
    parser.add_argument("--dry-run", action="store_true", help="只查询并写 manifest/缺失清单")
    parser.add_argument("--limit", type=int, default=None, help="最多下载 N 个文件；不截断查询或 manifest")
    parser.add_argument("--out", type=Path, default=default_out, help="manifest、缺失清单和文件输出目录")
    parser.add_argument("--api-base", default=GDC_API_BASE, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    args.cancers = sorted(dict.fromkeys(cancer.upper() for cancer in args.cancers))
    if args.limit is not None and args.limit < 0:
        parser.error("--limit 必须不小于 0")
    return args


def run(args):
    out_dir = args.out.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    groups = load_labels(args.labels, args.cancers)
    all_rows = []
    patient_cancer = {}
    summaries = []
    print(f"一病人多文件选择规则: {FILE_SELECTION_RULE}")
    for cancer in args.cancers:
        patients = groups[cancer]
        hits = query_files(args.api_base, cancer, patients) if patients else []
        rows = choose_manifest_rows(hits, patients)
        all_rows.extend(rows)
        for patient in patients:
            patient_cancer[patient] = cancer
        missing_path, matched, missing = write_missing(out_dir, cancer, patients, rows)
        summaries.append((cancer, len(patients), matched, missing, missing_path))
    all_rows.sort(key=lambda row: (patient_cancer[row["patient_id"]], row["patient_id"], row["file_id"], row["file_name"]))
    manifest_path = write_manifest(out_dir, all_rows)
    print(f"完整 manifest: {manifest_path} ({len(all_rows)} 条)")
    for cancer, label_count, matched, missing, missing_path in summaries:
        print(f"{cancer}: labels CSV 病人数={label_count}, 命中数={matched}, 缺失数={missing}, 缺失清单={missing_path}")
    if args.dry_run:
        print("dry-run: 未访问 data 下载端点。")
        return 0
    manifest_rows = read_manifest(manifest_path)
    validate_manifest_destinations(out_dir, manifest_rows)
    selected = manifest_rows if args.limit is None else manifest_rows[:args.limit]
    print(f"下载数量: {len(selected)} / manifest {len(manifest_rows)}")
    for row in selected:
        download_one(args.api_base, out_dir, row)
    return 0


def main(argv=None):
    try:
        return run(parse_args(argv))
    except (OSError, ValueError, RuntimeError, HTTPError, URLError, json.JSONDecodeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
