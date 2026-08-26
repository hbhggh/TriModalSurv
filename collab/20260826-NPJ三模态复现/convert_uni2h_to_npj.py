#!/usr/bin/env python3
r"""
convert_uni2h_to_npj.py
把 UNI2-h 预提取特征（HF: MahmoodLab/UNI2-h-features）转换成 NPJ 骨架 loader 期望的格式：

    data/tcga-dataset/<CANCER>/<patient_id>.<slide_id>.pkl   # pandas.DataFrame, .values -> [N_patch, 1536]

骨架 loader（loc_utils_3yr/tcga_dataset.py）用 glob(f"{pid}*.pkl") 找同一病人的所有切片，
然后 pickle.load(f).values 做 MiniBatchKMeans，所以每张切片一个 DataFrame pickle 即可。

用法（BLCA 例）：
    python convert_uni2h_to_npj.py \
        --src   UNI2-h_features/TCGA/TCGA-BLCA.tar.gz   \   # tar.gz 或已解压的目录都可以
        --cancer BLCA \
        --labels data/TCGA_9523sample_label_4-2-4_Censorship_HKUST.csv \
        --out   data/tcga-dataset

自检输出：保留/跳过的切片数、覆盖到的病人数 vs CSV 中该癌种病人数、缺失病人列表（写入 manifest）。
"""
import argparse
import os
import re
import sys
import tarfile
import tempfile
import pickle
from pathlib import Path

import h5py
import numpy as np
import pandas as pd

SLIDE_RE = re.compile(r"^(TCGA-[A-Z0-9]{2}-[A-Z0-9]{4})-(\d{2})[A-Z0-9]-\d{2}-([A-Z0-9]+)")


def parse_slide(name: str):
    """从 h5 文件名解析 patient_id / sample_type / slide_type。
    例：TCGA-2F-A9KO-01Z-00-DX1.<uuid>.h5 -> ('TCGA-2F-A9KO', '01', 'DX1')"""
    stem = name.split("/")[-1]
    stem = stem[:-3] if stem.endswith(".h5") else stem
    m = SLIDE_RE.match(stem)
    if not m:
        return None, None, None, stem
    return m.group(1), m.group(2), m.group(3), stem.split(".")[0]


def load_features(h5_path: str) -> np.ndarray:
    with h5py.File(h5_path, "r") as f:
        feats = f["features"][:]
    feats = np.asarray(feats)
    if feats.ndim == 3:  # [1, N, D]
        feats = feats[0]
    if feats.ndim != 2:
        raise ValueError(f"unexpected feature shape {feats.shape} in {h5_path}")
    return feats


def iter_h5(src: str):
    """统一遍历接口：目录 -> 直接给路径；tar.gz -> 逐个成员解压到临时文件，用完即删。"""
    src_path = Path(src)
    if src_path.is_dir():
        for p in sorted(src_path.rglob("*.h5")):
            yield p.name, str(p), None
        return
    if not tarfile.is_tarfile(src):
        raise ValueError(f"{src} 既不是目录也不是 tar 文件")
    with tarfile.open(src, "r:*") as tar:
        for member in tar:
            if not member.isfile() or not member.name.endswith(".h5"):
                continue
            fobj = tar.extractfile(member)
            tmp = tempfile.NamedTemporaryFile(suffix=".h5", delete=False)
            tmp.write(fobj.read())
            tmp.close()
            yield os.path.basename(member.name), tmp.name, tmp.name


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="UNI2-h 的 TCGA-<CANCER>.tar.gz 或解压后的目录")
    ap.add_argument("--cancer", required=True, help="癌种代码，如 BLCA（决定输出子目录和 CSV 过滤）")
    ap.add_argument("--labels", required=True, help="骨架 Drive 里的 TCGA_9523sample_label_*.csv")
    ap.add_argument("--out", default="data/tcga-dataset", help="输出根目录（骨架 config 里 img.path）")
    ap.add_argument("--keep-non-dx", action="store_true", help="默认只保留 DX(诊断/FFPE) 切片；加此项保留冰冻等其它切片")
    ap.add_argument("--keep-normal", action="store_true", help="默认丢弃样本类型 10-19（正常组织）；加此项保留")
    ap.add_argument("--dtype", default="float32", choices=["float32", "float16"])
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()

    labels = pd.read_csv(args.labels, usecols=["patient_id", "cancer_type", "split"])
    wanted = labels[labels.cancer_type == args.cancer]
    wanted_pids = set(wanted.patient_id)
    if not wanted_pids:
        sys.exit(f"[错误] CSV 里没有 cancer_type == {args.cancer} 的病人，检查癌种代码大小写")

    out_dir = Path(args.out) / args.cancer
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    n_written = 0
    feat_dim = None
    for fname, h5_path, tmp_to_delete in iter_h5(args.src):
        pid, sample_type, slide_type, slide_id = parse_slide(fname)
        status = "kept"
        if pid is None:
            status = "skip:unparsable_name"
        elif pid not in wanted_pids:
            status = "skip:patient_not_in_csv"
        elif (not args.keep_normal) and sample_type is not None and 10 <= int(sample_type) <= 19:
            status = "skip:normal_tissue"
        elif (not args.keep_non_dx) and not slide_type.startswith("DX"):
            status = f"skip:non_dx({slide_type})"

        n_patch = None
        if status == "kept":
            out_file = out_dir / f"{pid}.{slide_id}.pkl"
            if out_file.exists() and not args.overwrite:
                status = "kept:already_exists"
                n_patch = -1
            else:
                feats = load_features(h5_path).astype(args.dtype)
                n_patch = int(feats.shape[0])
                feat_dim = int(feats.shape[1])
                with open(out_file, "wb") as f:
                    pickle.dump(pd.DataFrame(feats), f, protocol=4)
                n_written += 1
                if n_written % 50 == 0:
                    print(f"  ... 已写入 {n_written} 张切片", flush=True)
        rows.append(dict(file=fname, patient_id=pid, sample_type=sample_type,
                         slide_type=slide_type, n_patch=n_patch, status=status))
        if tmp_to_delete:
            os.remove(tmp_to_delete)

    man = pd.DataFrame(rows)
    man_path = out_dir / f"_manifest_{args.cancer}.csv"
    man.to_csv(man_path, index=False)

    kept = man[man.status.str.startswith("kept")]
    covered = set(kept.patient_id)
    missing = sorted(wanted_pids - covered)
    pd.Series(missing, name="patient_id").to_csv(out_dir / f"_missing_patients_{args.cancer}.csv", index=False)

    print("\n================ 自检 ================")
    print(f"癌种: {args.cancer}")
    print(f"h5 切片总数: {len(man)}")
    print(man.status.value_counts().to_string())
    print(f"保留切片数: {len(kept)} ；有切片的病人数: {len(covered)} / CSV 中该癌种病人数: {len(wanted_pids)}")
    print(f"每病人切片数: 中位 {kept.groupby('patient_id').size().median() if len(kept) else 0}, 最大 {kept.groupby('patient_id').size().max() if len(kept) else 0}")
    if len(kept) and (kept.n_patch > 0).any():
        print(f"每切片 patch 数: 中位 {int(kept[kept.n_patch > 0].n_patch.median())}, 最小 {int(kept[kept.n_patch > 0].n_patch.min())}")
    print(f"按 split 覆盖: " + ", ".join(
        f"{s}={wanted[wanted.split == s].patient_id.isin(covered).sum()}/{(wanted.split == s).sum()}"
        for s in ["train", "valid", "test"]))
    print(f"缺失病人数: {len(missing)}（列表见 {out_dir / f'_missing_patients_{args.cancer}.csv'}）")
    print(f"清单: {man_path}")
    print(f"特征维度请填入 config: feature_dim: {feat_dim if feat_dim else '?（本次没有新写入的切片）'}")


if __name__ == "__main__":
    main()
