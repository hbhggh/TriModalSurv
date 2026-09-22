"""只读核验4.progress三臂矩阵，并按用户SVG布局输出五seed均值。"""
from pathlib import Path
import hashlib
import itertools
import json
import math
import re
from statistics import fmean

BASE = Path("/Users/wuhao/Desktop/TriModalSurv")
RESULT = BASE / "experiments/I01_patient_retrieval/knowledge/data-analysis-from-grok/4.progress"
CANCERS = ("BRCA", "UCEC", "LUAD", "BLCA", "LGG")
SEEDS = (123, 132, 213, 231, 321)
GRIDS = ("rna_100", "text_100", "both_100", "none")
ARMS = ("m0real", "m1", "strategy0")
FINGERPRINT = "a825b3cc4df41cf56afe228be531a4fc13f69c520bf35a2f2305101652387ec2"


def main():
    source = RESULT / "runs/test/complete.json"
    payload = json.loads(source.read_text())
    assert payload["status"] == "COMPLETED"
    assert payload["run_fingerprint"] == FINGERPRINT
    rows = payload["rows"]
    index = {}
    for row in rows:
        key = (row["cancer"], int(row["seed"]), row["grid"], row["protocol"])
        assert key not in index, ("duplicate", key)
        value = float(row["c_index_b"])
        assert math.isfinite(value) and 0 <= value <= 1, key
        index[key] = value
    assert set(index) == set(itertools.product(CANCERS, SEEDS, GRIDS, ARMS))
    for name, orientation in (("癌症为单位.md", "cancer"), ("seed单位-实验结果.md", "seed")):
        group, seen = None, set()
        for line in (RESULT / name).read_text().splitlines():
            if line.startswith("### "):
                group = line[4:].replace("Seed ", "")
            if not line.startswith("| "):
                continue
            cells = [re.sub(r"<[^>]+>", "", value).strip() for value in line.strip("|").split("|")]
            if len(cells) < 5 or cells[1] not in GRIDS:
                continue
            cancer, seed = (group, int(cells[0])) if orientation == "cancer" else (cells[0], int(group))
            for arm, shown in zip(("strategy0", "m1", "m0real"), cells[2:5]):
                key = cancer, seed, cells[1], arm
                assert key not in seen
                assert f"{index[key]:.6f}" == shown, (name, key, shown)
                seen.add(key)
        assert seen == set(index), (name, len(seen))
        print(f"{name}: 300/300 展示数一致")

    means = {(c, g, a): fmean(index[c, s, g, a] for s in SEEDS)
             for c in CANCERS for g in GRIDS for a in ARMS}
    for c in CANCERS:
        for a in ARMS:
            means[c, "overall", a] = fmean(index[c, s, g, a] for s in SEEDS for g in GRIDS)
    header = ["场景"] + [f"{c}/{a}" for c in CANCERS for a in ARMS]
    lines = ["| " + " | ".join(header) + " |", "| " + " | ".join(["---"] * 16) + " |"]
    for g in (*GRIDS, "overall"):
        cells = [g]
        for c in CANCERS:
            highest = max(means[c, g, a] for a in ARMS)
            for a in ARMS:
                value = means[c, g, a]
                shown = f"{value:.6f}"
                cells.append(f"**{shown}**" if value == highest else shown)
        lines.append("| " + " | ".join(cells) + " |")
    table = "\n".join(lines)
    document = Path(__file__).with_name("实验先验知识与公式说明.md").read_text()
    assert table in document, "先验MD的75个表格值/最高值标记与JSON复算不一致"
    print(table)
    wins = [c for c in CANCERS if means[c, "overall", "strategy0"] >
            max(means[c, "overall", "m1"], means[c, "overall", "m0real"])]
    print("严格胜率:", str(len(wins)) + "/5", "胜出癌种:", ", ".join(wins))
    for a in ARMS:
        print("100格宏平均", a, f"{fmean(index[c,s,g,a] for c in CANCERS for s in SEEDS for g in GRIDS):.12f}")
    print("SOURCE_SHA256", hashlib.sha256(source.read_bytes()).hexdigest())
    print("HANDOFF_DATA_CHECK=PASS")


if __name__ == "__main__":
    main()

