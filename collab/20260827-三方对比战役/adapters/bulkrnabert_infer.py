#!/usr/bin/env python3
"""把 GDC STAR-Counts TSV 转为 BulkRNABert token 级嵌入。"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import pickle
import re
import tempfile
from pathlib import Path
from typing import Callable, Mapping, Sequence
from urllib.request import Request, urlopen

import numpy as np


MANIFEST_COLUMNS = ("patient_id", "file_id", "file_name", "md5")
TOKEN_COUNT = 2048
EMBED_DIM = 256
MODEL_ID = "InstaDeepAI/BulkRNABert"
COMMON_GENE_URL = (
    "https://raw.githubusercontent.com/instadeepai/multiomics-open-research/"
    "main/data/bulkrnabert/common_gene_id.txt"
)


def read_common_gene_ids(path: Path) -> list[str]:
    """读取官方 common_gene_id.txt，并拒绝空值、版本号或重复基因。"""
    gene_ids = [line.strip() for line in path.read_text(encoding="utf-8-sig").splitlines()]
    if not gene_ids or any(not gene_id for gene_id in gene_ids):
        raise ValueError(f"common_gene_id.txt 为空或含空行: {path}")
    versioned = [gene_id for gene_id in gene_ids if "." in gene_id]
    if versioned:
        raise ValueError(f"common_gene_id.txt 含未去版本号 gene_id: {versioned[:3]}")
    if len(set(gene_ids)) != len(gene_ids):
        raise ValueError(f"common_gene_id.txt 含重复 gene_id: {path}")
    return gene_ids


def configure_model_dtype(model: object, dtype: str) -> object:
    """仅在调用侧把模型浮点权重切换到请求的推理精度。"""
    if dtype == "float32":
        return model.float()
    if dtype == "float16":
        raise RuntimeError("该模型官方实现不支持 half（-1e30 掩码溢出）")
    if dtype == "bfloat16":
        return model.bfloat16()
    raise ValueError(f"不支持的 --dtype: {dtype}")


def make_infer_one(
    *,
    model: object,
    tokenizer: object,
    torch_module: object,
    device: str,
    layer_key: str,
    expected_genes: int,
    expected_dim: int,
) -> Callable[[np.ndarray], np.ndarray]:
    """按 HF 模型卡预处理并返回最后层 token embedding 推理函数。"""

    def infer_one(expression_vector: np.ndarray) -> np.ndarray:
        vector = np.asarray(expression_vector, dtype=np.float32)
        if vector.shape != (expected_genes,):
            raise AssertionError(
                f"表达向量形状错误: {vector.shape}，要求 ({expected_genes},)"
            )
        transformed = np.log10(1.0 + vector).astype(np.float32, copy=False)
        encoded = None
        input_ids = None
        outputs = None
        embedding = None
        try:
            encoded = tokenizer.batch_encode_plus(
                transformed[None, :], return_tensors="pt"
            )
            if "input_ids" not in encoded:
                raise KeyError("BulkRNABert tokenizer 输出缺少 input_ids")
            # input_ids 是 nn.Embedding 的离散索引；低精度模型仍必须保持 long。
            input_ids = encoded["input_ids"].to(
                device=device, dtype=torch_module.long
            )
            with torch_module.inference_mode():
                outputs = model(input_ids)
            if layer_key not in outputs:
                raise KeyError(f"BulkRNABert 输出缺少 {layer_key}: {sorted(outputs)}")
            embedding = outputs[layer_key]
            if tuple(embedding.shape) != (1, expected_genes, expected_dim):
                raise AssertionError(
                    f"{layer_key} 形状错误: {tuple(embedding.shape)}，"
                    f"要求 (1, {expected_genes}, {expected_dim})"
                )
            array = embedding[0].detach().cpu().numpy().astype(np.float32, copy=False)
            if not np.isfinite(array).all():
                raise AssertionError(f"{layer_key} 含 NaN/Inf")
            return np.ascontiguousarray(array)
        finally:
            embedding = None
            outputs = None
            input_ids = None
            encoded = None
            torch_module.cuda.empty_cache()

    return infer_one


def read_star_counts(path: Path) -> dict[str, float]:
    """读取 GDC STAR-Counts，并以去版本号后的 gene_id 为键返回 TPM。"""
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = (line for line in handle if not line.startswith("#"))
        reader = csv.DictReader(rows, delimiter="\t")
        required = {"gene_id", "tpm_unstranded"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            missing = sorted(required - set(reader.fieldnames or ()))
            raise ValueError(f"STAR-Counts 缺少必需列 {missing}: {path}")

        expression: dict[str, float] = {}
        for line_number, row in enumerate(reader, start=2):
            gene_id = (row.get("gene_id") or "").strip()
            if not gene_id or gene_id.startswith("N_"):
                continue
            gene_id = re.sub(r"\.\d+(?=$|_)", "", gene_id, count=1)
            value_text = (row.get("tpm_unstranded") or "").strip()
            try:
                value = float(value_text)
            except ValueError as exc:
                raise ValueError(
                    f"{path} 第 {line_number} 行 tpm_unstranded 不是数值: {value_text!r}"
                ) from exc
            if not math.isfinite(value) or value < 0:
                raise ValueError(
                    f"{path} 第 {line_number} 行 tpm_unstranded 必须是非负有限数: {value_text!r}"
                )
            if gene_id in expression:
                raise ValueError(f"{path} 中 gene_id 去版本号后重复: {gene_id}")
            expression[gene_id] = value
    if not expression:
        raise ValueError(f"STAR-Counts 没有可用基因行: {path}")
    return expression


def build_expression_vector(
    expression: Mapping[str, float], common_gene_ids: Sequence[str]
) -> np.ndarray:
    """按官方 common gene 顺序对齐表达量；TSV 缺失的基因补零。"""
    return np.asarray(
        [expression.get(gene_id, 0.0) for gene_id in common_gene_ids],
        dtype=np.float32,
    )


def read_label_patients(path: Path, cancers: Sequence[str]) -> dict[str, list[str]]:
    """按 labels 文件中的出现顺序返回各癌种唯一患者。"""
    requested = [cancer.strip().upper() for cancer in cancers]
    if not requested or any(not cancer for cancer in requested):
        raise ValueError("--cancers 至少需要一个非空癌种")
    if len(set(requested)) != len(requested):
        raise ValueError(f"--cancers 含重复项: {requested}")
    by_cancer = {cancer: [] for cancer in requested}
    seen: set[str] = set()
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        required = {"patient_id", "cancer_type"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            missing = sorted(required - set(reader.fieldnames or ()))
            raise ValueError(f"labels 缺少必需列 {missing}: {path}")
        for line_number, row in enumerate(reader, start=2):
            cancer = (row.get("cancer_type") or "").strip().upper()
            if cancer not in by_cancer:
                continue
            patient_id = (row.get("patient_id") or "").strip().upper()
            if not patient_id:
                raise ValueError(f"labels 第 {line_number} 行 patient_id 为空: {path}")
            if patient_id in seen:
                raise ValueError(f"labels 中 patient_id 重复: {patient_id}")
            seen.add(patient_id)
            by_cancer[cancer].append(patient_id)
    for cancer, patient_ids in by_cancer.items():
        if not patient_ids:
            raise ValueError(f"labels 中没有癌种 {cancer} 的患者: {path}")
    return by_cancer


def read_manifest(path: Path) -> list[dict[str, str]]:
    """读取并验证 GDC manifest；返回值保留文件行顺序。"""
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or not set(MANIFEST_COLUMNS).issubset(reader.fieldnames):
            missing = sorted(set(MANIFEST_COLUMNS) - set(reader.fieldnames or ()))
            raise ValueError(f"manifest 缺少必需列 {missing}: {path}")
        for line_number, source in enumerate(reader, start=2):
            row = {column: (source.get(column) or "").strip() for column in MANIFEST_COLUMNS}
            patient_id = row["patient_id"].upper()
            file_name = row["file_name"]
            if any(not row[column] for column in MANIFEST_COLUMNS):
                raise ValueError(f"manifest 第 {line_number} 行含空字段: {path}")
            if Path(file_name).name != file_name or "\\" in file_name or file_name in {".", ".."}:
                raise ValueError(f"manifest 第 {line_number} 行 file_name 不安全: {file_name!r}")
            if patient_id in seen:
                raise ValueError(f"manifest 中 patient_id 重复: {patient_id}")
            seen.add(patient_id)
            row["patient_id"] = patient_id
            rows.append(row)
    if not rows:
        raise ValueError(f"manifest 为空: {path}")
    return rows


def _write_pickle_atomic(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent, delete=False
    )
    tmp_path = Path(handle.name)
    try:
        with handle:
            pickle.dump(payload, handle, protocol=pickle.HIGHEST_PROTOCOL)
        os.replace(tmp_path, path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def _load_embedding_pickle(path: Path) -> dict[str, np.ndarray]:
    with path.open("rb") as handle:
        payload = pickle.load(handle)  # 输入为用户指定的可信作者/本脚本 pkl。
    if not isinstance(payload, dict) or set(("identifier", "embedding")) - set(payload):
        raise ValueError(f"pkl 缺少 identifier/embedding: {path}")
    identifiers = payload["identifier"]
    embeddings = payload["embedding"]
    if not isinstance(identifiers, (list, tuple)) or not isinstance(embeddings, (list, tuple)):
        raise ValueError(f"pkl 的 identifier/embedding 必须是列表: {path}")
    if len(identifiers) != len(embeddings):
        raise ValueError(f"pkl 的 identifier/embedding 长度不一致: {path}")
    indexed: dict[str, np.ndarray] = {}
    for index, (identifier, embedding) in enumerate(zip(identifiers, embeddings)):
        patient_id = str(identifier).strip().upper()
        if not patient_id or patient_id in indexed:
            raise ValueError(f"pkl 含空或重复 identifier（索引 {index}）: {path}")
        array = np.asarray(embedding, dtype=np.float32)
        if array.ndim != 2 or not np.isfinite(array).all():
            raise ValueError(f"pkl embedding[{index}] 不是有限二维矩阵: {path}")
        indexed[patient_id] = array
    return indexed


def compare_pickles(generated_path: Path, author_path: Path) -> dict[str, float | int]:
    """按相同 pid 计算两份 token embedding 展平后的余弦分布。"""
    generated = _load_embedding_pickle(generated_path)
    author = _load_embedding_pickle(author_path)
    common = sorted(set(generated) & set(author))
    if not common:
        raise ValueError(f"生成版与作者版没有共同 pid: {generated_path} vs {author_path}")
    similarities: list[float] = []
    for patient_id in common:
        left = generated[patient_id][:TOKEN_COUNT]
        right = author[patient_id][:TOKEN_COUNT]
        if left.shape != right.shape:
            raise ValueError(
                f"{patient_id} 比较形状不一致: generated={left.shape}, author={right.shape}"
            )
        left_flat = left.astype(np.float64, copy=False).reshape(-1)
        right_flat = right.astype(np.float64, copy=False).reshape(-1)
        denominator = float(np.linalg.norm(left_flat) * np.linalg.norm(right_flat))
        if denominator == 0.0 or not math.isfinite(denominator):
            raise ValueError(f"{patient_id} 余弦比较遇到零范数或非有限范数")
        similarities.append(float(np.dot(left_flat, right_flat) / denominator))
    values = np.asarray(similarities, dtype=np.float64)
    return {
        "n": int(values.size),
        "min": float(values.min()),
        "q25": float(np.quantile(values, 0.25)),
        "median": float(np.median(values)),
        "mean": float(values.mean()),
        "q75": float(np.quantile(values, 0.75)),
        "max": float(values.max()),
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="把 GDC STAR-Counts TSV 转为 NPJ 格式的 BulkRNABert token 嵌入"
    )
    parser.add_argument(
        "--manifests",
        nargs="+",
        required=True,
        type=Path,
        help="各癌种 manifest.csv；列为 patient_id,file_id,file_name,md5",
    )
    parser.add_argument(
        "--tsv-dirs", nargs="+", required=True, type=Path, help="与 manifests 对应的 TSV 目录"
    )
    parser.add_argument("--cancers", nargs="+", required=True, help="与 manifests 对应的癌种")
    parser.add_argument("--labels", required=True, type=Path, help="labels_424.csv")
    parser.add_argument("--out", required=True, type=Path, help="输出目录")
    parser.add_argument(
        "--compare-with",
        nargs="+",
        type=Path,
        help="作者版 pkl（按 cancers 顺序）或包含各癌种 pkl 的一个目录",
    )
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument(
        "--dtype",
        choices=("float32", "float16", "bfloat16"),
        default="float32",
    )
    parser.add_argument("--limit", type=int, help="每癌种最多处理 N 个已有 TSV")
    return parser.parse_args(argv)


def validate_input_groups(args: argparse.Namespace) -> list[tuple[Path, Path, str]]:
    counts = (len(args.manifests), len(args.tsv_dirs), len(args.cancers))
    if len(set(counts)) != 1:
        raise ValueError(
            "--manifests、--tsv-dirs、--cancers 数量必须一致，"
            f"当前为 {counts[0]}/{counts[1]}/{counts[2]}"
        )
    cancers = [cancer.strip().upper() for cancer in args.cancers]
    if any(not cancer for cancer in cancers) or len(set(cancers)) != len(cancers):
        raise ValueError(f"--cancers 不能为空或重复: {cancers}")
    if args.limit is not None and args.limit <= 0:
        raise ValueError("--limit 必须是正整数")
    return list(zip(args.manifests, args.tsv_dirs, cancers))


def resolve_compare_paths(
    compare_with: Sequence[Path] | None, cancers: Sequence[str]
) -> dict[str, Path]:
    if not compare_with:
        return {}
    paths = list(compare_with)
    if len(paths) == 1 and paths[0].is_dir():
        return {
            cancer: paths[0] / f"RNA_{cancer}_embedding_token_lvl.pkl"
            for cancer in cancers
        }
    if len(paths) == len(cancers):
        return dict(zip(cancers, paths))
    raise ValueError(
        "--compare-with 必须提供一个目录，或按 --cancers 顺序提供等量 pkl；"
        f"当前 compare={len(paths)}, cancers={len(cancers)}"
    )


def ensure_common_gene_file(cache_dir: Path) -> Path:
    """仅在缓存缺失时下载官方 common_gene_id.txt，并原子发布。"""
    cache_dir.mkdir(parents=True, exist_ok=True)
    target = cache_dir / "common_gene_id.txt"
    if target.is_file():
        return target
    request = Request(COMMON_GENE_URL, headers={"User-Agent": "TriModalSurv-BulkRNABert/1"})
    handle = tempfile.NamedTemporaryFile(
        prefix=".common_gene_id.", suffix=".tmp", dir=cache_dir, delete=False
    )
    tmp_path = Path(handle.name)
    try:
        with handle, urlopen(request, timeout=60) as response:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                handle.write(chunk)
        # 先做结构验证，避免把 HTML 错误页或残缺响应发布为缓存。
        read_common_gene_ids(tmp_path)
        os.replace(tmp_path, target)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()
    return target


def load_hf_runtime(
    *, cache_dir: Path, device: str, dtype: str
) -> tuple[Callable[[np.ndarray], np.ndarray], int, int, str]:
    """按 HF 模型卡加载 PyTorch BulkRNABert，并返回单样本推理函数。"""
    hf_root = cache_dir / "hf"
    hf_root.mkdir(parents=True, exist_ok=True)
    os.environ["HF_HOME"] = str(hf_root / "home")
    os.environ["HF_HUB_CACHE"] = str(hf_root / "hub")
    os.environ["TRANSFORMERS_CACHE"] = str(hf_root / "transformers")
    os.environ["HF_MODULES_CACHE"] = str(hf_root / "modules")
    try:
        import torch
        from transformers import AutoConfig, AutoModel, AutoTokenizer
    except ImportError as exc:
        raise RuntimeError(
            "真实 BulkRNABert 推理需要现有 Python 环境提供 torch 与 transformers；"
            "本脚本不会擅自安装依赖"
        ) from exc

    if device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("--device cuda 已请求，但 torch.cuda.is_available() 为 False")
    torch_device = torch.device(device)
    model_cache = hf_root / "model"
    config = AutoConfig.from_pretrained(
        MODEL_ID, trust_remote_code=True, cache_dir=str(model_cache)
    )
    last_layer = int(config.num_layers)
    config.embeddings_layers_to_save = (last_layer,)
    tokenizer = AutoTokenizer.from_pretrained(
        MODEL_ID, trust_remote_code=True, cache_dir=str(model_cache)
    )
    model = AutoModel.from_pretrained(
        MODEL_ID,
        config=config,
        trust_remote_code=True,
        cache_dir=str(model_cache),
    )
    model.to(torch_device)
    model = configure_model_dtype(model, dtype)
    model.eval()
    expected_genes = int(config.n_genes)
    expected_dim = int(config.embed_dim)
    layer_key = f"embeddings_{last_layer}"
    infer_one = make_infer_one(
        model=model,
        tokenizer=tokenizer,
        torch_module=torch,
        device=str(torch_device),
        layer_key=layer_key,
        expected_genes=expected_genes,
        expected_dim=expected_dim,
    )
    return infer_one, expected_genes, expected_dim, layer_key


def process_cancer(
    *,
    cancer: str,
    label_patients: Sequence[str],
    manifest_path: Path,
    tsv_dir: Path,
    common_gene_ids: Sequence[str],
    infer_one: Callable[[np.ndarray], np.ndarray],
    out_dir: Path,
    limit: int | None,
) -> dict[str, int | str]:
    """处理单癌种，并写出 NPJ 所需的 token-level pkl。"""
    cancer = cancer.strip().upper()
    if limit is not None and limit <= 0:
        raise ValueError("--limit 必须是正整数")
    allowed = {patient_id.strip().upper() for patient_id in label_patients}
    if len(allowed) != len(label_patients):
        raise ValueError(f"{cancer} labels 患者有重复或空值")

    rows = read_manifest(manifest_path)
    matched_rows = [row for row in rows if row["patient_id"] in allowed]
    available_rows = [row for row in matched_rows if (tsv_dir / row["file_name"]).is_file()]
    if limit is not None:
        available_rows = available_rows[:limit]
    if not available_rows:
        raise FileNotFoundError(
            f"{cancer} 没有可处理 TSV（labels={len(allowed)}, manifest命中={len(matched_rows)}）"
        )

    identifiers: list[str] = []
    embeddings: list[np.ndarray] = []
    for row in available_rows:
        expression = read_star_counts(tsv_dir / row["file_name"])
        vector = build_expression_vector(expression, common_gene_ids)
        embedding = np.asarray(infer_one(vector), dtype=np.float32)
        if embedding.ndim != 2 or embedding.shape[0] < TOKEN_COUNT or embedding.shape[1] != EMBED_DIM:
            raise AssertionError(
                f"{row['patient_id']} BulkRNABert 输出形状错误: {embedding.shape}，"
                f"要求至少 ({TOKEN_COUNT}, {EMBED_DIM})"
            )
        embedding = np.ascontiguousarray(embedding[:TOKEN_COUNT], dtype=np.float32)
        if not np.isfinite(embedding).all():
            raise AssertionError(f"{row['patient_id']} embedding 含 NaN/Inf")
        assert embedding.shape == (TOKEN_COUNT, EMBED_DIM)
        identifiers.append(row["patient_id"])
        embeddings.append(embedding)

    output_path = out_dir / f"RNA_{cancer}_embedding_token_lvl.pkl"
    _write_pickle_atomic(output_path, {"identifier": identifiers, "embedding": embeddings})
    shapes = {item.shape for item in embeddings}
    assert shapes == {(TOKEN_COUNT, EMBED_DIM)}
    print(
        f"[{cancer}] labels={len(allowed)} manifest命中={len(matched_rows)} "
        f"tsv命中={len(available_rows)} 输出={len(identifiers)} "
        f"shape=({TOKEN_COUNT}, {EMBED_DIM}) -> {output_path}"
    )
    return {
        "cancer": cancer,
        "labels": len(allowed),
        "manifest_hits": len(matched_rows),
        "tsv_hits": len(available_rows),
        "output": len(identifiers),
        "path": str(output_path),
    }


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    groups = validate_input_groups(args)
    cancers = [group[2] for group in groups]
    for manifest_path, tsv_dir, cancer in groups:
        if not manifest_path.is_file():
            raise FileNotFoundError(f"{cancer} manifest 不存在: {manifest_path}")
        if not tsv_dir.is_dir():
            raise NotADirectoryError(f"{cancer} TSV 目录不存在: {tsv_dir}")
    if not args.labels.is_file():
        raise FileNotFoundError(f"labels 不存在: {args.labels}")

    task_dir = Path(__file__).resolve().parents[1]
    cache_dir = task_dir / "scratch" / "d_cache"
    common_path = ensure_common_gene_file(cache_dir)
    common_gene_ids = read_common_gene_ids(common_path)
    common_sha256 = hashlib.sha256(common_path.read_bytes()).hexdigest()
    print(
        f"[COMMON_GENES] count={len(common_gene_ids)} sha256={common_sha256} "
        f"path={common_path}"
    )

    patients_by_cancer = read_label_patients(args.labels, cancers)
    compare_paths = resolve_compare_paths(args.compare_with, cancers)
    infer_one, model_genes, model_dim, layer_key = load_hf_runtime(
        cache_dir=cache_dir, device=args.device, dtype=args.dtype
    )
    if len(common_gene_ids) != model_genes:
        raise AssertionError(
            f"common gene 数与模型 config.n_genes 不一致: "
            f"{len(common_gene_ids)} != {model_genes}"
        )
    if model_dim != EMBED_DIM:
        raise AssertionError(f"模型 config.embed_dim={model_dim}，要求 {EMBED_DIM}")
    print(
        f"[MODEL] id={MODEL_ID} device={args.device} dtype={args.dtype} "
        f"n_genes={model_genes} "
        f"embed_dim={model_dim} layer={layer_key} cache={cache_dir / 'hf'}"
    )

    summaries: list[dict[str, int | str]] = []
    for manifest_path, tsv_dir, cancer in groups:
        summary = process_cancer(
            cancer=cancer,
            label_patients=patients_by_cancer[cancer],
            manifest_path=manifest_path,
            tsv_dir=tsv_dir,
            common_gene_ids=common_gene_ids,
            infer_one=infer_one,
            out_dir=args.out,
            limit=args.limit,
        )
        summaries.append(summary)
        generated_path = Path(str(summary["path"]))
        if cancer in compare_paths:
            author_path = compare_paths[cancer]
            if not author_path.is_file():
                raise FileNotFoundError(f"{cancer} 作者版 pkl 不存在: {author_path}")
            stats = compare_pickles(generated_path, author_path)
            print(
                f"[COMPARE {cancer}] generated={generated_path} author={author_path} "
                f"stats={json.dumps(stats, ensure_ascii=False, sort_keys=True)}"
            )

    for summary in summaries:
        output_path = Path(str(summary["path"]))
        indexed = _load_embedding_pickle(output_path)
        expected_count = int(summary["output"])
        if len(indexed) != expected_count:
            raise AssertionError(
                f"{summary['cancer']} 输出重新读取人数错误: {len(indexed)} != {expected_count}"
            )
        shapes = {array.shape for array in indexed.values()}
        dtypes = {str(array.dtype) for array in indexed.values()}
        if shapes != {(TOKEN_COUNT, EMBED_DIM)} or dtypes != {"float32"}:
            raise AssertionError(
                f"{summary['cancer']} 输出自检失败: shapes={shapes}, dtypes={dtypes}"
            )
        print(
            f"[SELF-CHECK {summary['cancer']}] patients={len(indexed)} "
            f"shape=({TOKEN_COUNT}, {EMBED_DIM}) dtype=float32 PASS"
        )
    print(f"SELF-CHECK PASS: cancers={len(summaries)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
