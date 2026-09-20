#!/usr/bin/env python3
"""只读核验四份文档、正式证据与代码节选；不运行训练或模型评测。"""
import hashlib
import json
import re
from pathlib import Path
from statistics import mean

RESULTS = Path("/Users/wuhao/Desktop/TriModalSurv/experiments/I01_patient_retrieval/results")
SOURCE = Path("/Users/wuhao/Desktop/TriModalSurv/archive/legacy_npj_snapshot/774f-6a04a0bf5c28/code/NPJ")
FORMAL = RESULTS / "legacy-tako-formal-20260915/raw/tako-formal/evidence/formal"
ORIGINAL = {
    "seed单位-实验结果.md": "511f7bcf7a3a5cb0d7ddd0a5bfb645ce5183b0a74e2f242b61583f0a8337eebb",
    "癌症为单位.md": "1c5d80eb2edcd46256a59193c9b50032f4195098d39ff770775ec22ff029c9fd",
}
SOURCE_HASHES = {
    "model/patient_retrieval_bank.py": "1a87fd04dc4ec87591421b76424aba60b0bb523a6849eae2dcc5a6b921663bb0",
    "model/fusion_model.py": "03c4060232d2d18ca277205e5a3dc47a8e3617e930128c839b11402953a7a096",
    "scripts/eval_missing.py": "e42d52c3a87e34ba77d293c61131046cff6bdeadf703c74dde3d2cf59f98ef93",
    "scripts/eval_patient_retrieval.py": "76cf8f3e58703c4615910e8cc3457a6539e9feefc27dc937239ae89a57a334de"
}
DOCS = ["patient-fixed-padmask-v2-总实验map.md", "Grok-patient-fixed-padmask-v2-诊断prompt.md"]
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
for name, expected in ORIGINAL.items():
    assert sha(RESULTS / name) == expected, ("old report changed", name)
for name, expected in SOURCE_HASHES.items():
    assert sha(SOURCE / name) == expected, ("source mismatch", name)
preflight = json.loads((FORMAL / "diagnostics/preflight.json").read_text())
for report in preflight["reports"].values():
    assert report["provenance"]["source_hashes"] == SOURCE_HASHES
data = {}
artifact_count = 0
for p in FORMAL.glob("*.json"):
    item = json.loads(p.read_text())
    assert item["protocol_id"] == "patient-fixed-padmask-v2"
    assert item["stage"] == "formal"
    key = item["cancer"], item["seed"], item["arm"]
    assert key not in data
    data[key] = item
    for grid in item["grids"].values():
        for kind in ("audit", "predictions"):
            assert sha(FORMAL / grid[kind + "_file"]) == grid[kind + "_sha256"]
            artifact_count += 1
        n = grid["n_complete_checked"]
        diff = grid["complete_max_logit_abs_diff"]
        assert isinstance(n, int) and n >= 0
        assert (n == 0 and diff is None) or (n > 0 and 0 <= diff <= 1e-6)
assert len(data) == 75 and artifact_count == 600
cs = ["BLCA", "BRCA", "LGG", "LUAD", "UCEC"]
ss = [123, 132, 213, 231, 321]
gs = ["none", "rna_100", "text_100", "both_100"]
arms = ["retrieval", "m1", "m0real"]
for c in cs:
    for s in ss:
        assert len({data[c,s,a]["checkpoint_sha256"] for a in arms}) == 1
        for a in arms:
            assert set(data[c,s,a]["grids"]) == set(gs)
assert len({data[c,s,"retrieval"]["checkpoint_sha256"] for c in cs for s in ss}) == 25
def aggregate(cancers, seeds, grids):
    return [mean(data[c,s,a]["grids"][g]["cindex_B"] for c in cancers for s in seeds for g in grids) for a in arms]
paired_outcomes = {}
for scope, grids in (("four", gs), ("three", gs[1:])):
    paired_outcomes[scope] = {}
    for baseline in ("m1", "m0real"):
        delta = [data[c,s,"retrieval"]["grids"][g]["cindex_B"] - data[c,s,baseline]["grids"][g]["cindex_B"] for c in cs for s in ss for g in grids]
        paired_outcomes[scope][baseline] = [sum(v > 0 for v in delta), sum(v == 0 for v in delta), sum(v < 0 for v in delta)]
def values(c, g):
    return [mean(data[c,s,a]["grids"][g]["cindex_B"] for s in ss) for a in arms]
def fmt(v):
    return f"{v:.6f}"
def signed(v):
    return f"{v:+.6f}"
def render(vals):
    best = max(vals)
    return [f'<span style="color:#c62828"><strong>{fmt(v)} ★</strong></span>' if v == best else fmt(v) for v in vals]
line_count = 0
snippet_count = 0
for name in DOCS:
    text = (RESULTS / name).read_text()
    assert "边界锁定：K=128；K=8是此前Q2笔误；max_epochs=200、patience=15属于未来方案，不属于本轮零训练评测或历史E0训练。" in text
    for c in cs:
        for g in gs:
            v = values(c, g)
            expected = "| " + " | ".join([c,g,*render(v),signed(v[0]-v[1]),signed(v[0]-v[2])]) + " |"
            assert expected in text, (name, c, g)
            line_count += 1
    def assert_row(label, vals):
        global line_count
        row = "| " + " | ".join([str(label), *render(vals), signed(vals[0]-vals[1]), signed(vals[0]-vals[2])]) + " |"
        assert row in text, (name, label)
        line_count += 1
    for cancer in cs:
        assert_row(cancer, aggregate([cancer], ss, gs))
    for seed in ss:
        assert_row(seed, aggregate(cs, [seed], gs))
    assert_row("四场景（含 none）", aggregate(cs, ss, gs))
    assert_row("三人工缺失场景", aggregate(cs, ss, gs[1:]))
    # 要求正文中的四项计数与原始JSON精确计数一致，不用手填常量背书。
    digits = re.sub(r"[胜平负]", "/", text).replace("//", "/")
    for outcomes in paired_outcomes.values():
        for counts in outcomes.values():
            assert "/".join(map(str, counts)) in digits, (name, counts)
    for block in re.findall(r"```python\n(.*?)\n```", text, re.S):
        assert any(block in (SOURCE / p).read_text() for p in SOURCE_HASHES), ("code altered", name)
        snippet_count += 1
    for target in re.findall(r"\]\((/[^)]+)\)", text):
        target = re.sub(r":\d+$", "", target)
        assert Path(target).exists(), ("broken link", target)
overall = {}
training_log_reconstruction = {}
log_root = Path("/Users/wuhao/Desktop/TriModalSurv/archive/legacy_collab/source-774f/20260915-M3Surv-fixed-bank/formal-preflight/provenance/logs")
for cancer in cs:
    path = log_root / f"c_e0_{cancer.lower()}.log"
    blocks = re.split(r"Training Arguments: ", path.read_bytes().decode())[1:]
    assert len(blocks) == 5
    reconstructed = []
    for block in blocks:
        seed = int(re.search(r"Namespace\(seed=(\d+)", block)[1])
        assert "epochs=50, batch_size=32" in block and "lr=0.0001" in block
        starts = lambda s: len(re.findall(r"(?:^|[\r\n])\s*0%\|[^\r\n]*\| 0/\d+ ", s))
        saves = list(re.finditer("Saving model checkpoint to:", block))
        assert saves and starts(block) == 101  # 50 train + 50 valid + 1 test
        last_epoch = starts(block[:saves[-1].start()]) / 2
        assert last_epoch.is_integer() and 1 <= last_epoch <= 50
        reconstructed.append({"seed": seed, "last_saved_epoch_1based": int(last_epoch)})
    assert [row["seed"] for row in reconstructed] == ss
    expected_row = "| " + " | ".join([cancer, *[str(row["last_saved_epoch_1based"]) for row in reconstructed]]) + " |"
    assert expected_row in (RESULTS / DOCS[0]).read_text()
    training_log_reconstruction[cancer] = {"log_sha256": sha(path), "epochs_completed": 50, "runs": reconstructed}
for label, grids in (("four_including_none", gs), ("three_artificial", gs[1:])):
    overall[label] = {a: mean(data[c,s,a]["grids"][g]["cindex_B"] for c in cs for s in ss for g in grids) for a in arms}
print(json.dumps({
    "status": "PASS",
    "scope": "documentation_only; no model inference or patient-level C-index recomputation",
    "units": len(data), "cindex_readings": 300, "artifact_hashes_verified": artifact_count,
    "paired_checkpoint_groups": 25, "distinct_checkpoint_file_hashes": 25,
    "result_table_rows_verified": line_count, "paired_win_tie_loss": paired_outcomes,
    "verbatim_code_excerpts_verified": snippet_count,
    "historical_training_log_reconstruction": training_log_reconstruction,
    "source_sha256": SOURCE_HASHES, "original_reports_unchanged": ORIGINAL,
    "document_sha256": {name: sha(RESULTS / name) for name in DOCS},
    "overall_recomputed_from_result_json": overall
}, ensure_ascii=False, indent=2))
