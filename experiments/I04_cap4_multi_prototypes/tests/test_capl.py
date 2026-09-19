"""CAPL（箱内多中心 EMA 记忆）单测 + capr 逐位不变对拍（CPU、无数据、<20 s）。

用法（先 `export PYTHONDONTWRITEBYTECODE=1`，cwd = NPJ 仓根）：
    python3 tests/test_capl.py            # 独立运行，逐条打印断言结果
    python3 -m pytest tests/test_capl.py  # pytest 亦可

补丁前 `model/compensator.py` 快照路径由 ``NPJ_COMPENSATOR_BASELINE`` 指定
（默认取本单 scratchpad 快照）；快照不存在时对拍用例 SKIP，其余照跑。

修订 v3（注意力尺度）另需 v2 快照 ``NPJ_COMPENSATOR_BASELINE_V3``（默认
``scratchpad/capl_v3_before/model/compensator.py``），用于证明 `CAPRecall` 未变、
以及「缺 logit_scale 的 v2 state_dict 严格加载必须报错」。
"""

import importlib.util
import os
import sys
import unittest
from pathlib import Path

NPJ_ROOT = Path(__file__).resolve().parents[1]
TESTS_DIR = Path(__file__).resolve().parent
for _path in (str(NPJ_ROOT), str(TESTS_DIR)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from tests.test_mean_fusion import install_stubs  # noqa: E402

install_stubs()

import math  # noqa: E402

import torch  # noqa: E402
import torch.nn.functional as F  # noqa: E402

from experiments.I04_cap4_multi_prototypes import train as main_survival  # noqa: E402
from experiments.I04_cap4_multi_prototypes import model as patched  # noqa: E402

torch.set_num_threads(1)

DIM = 256
N_BINS = 4
MODALITIES = ("text", "rna")
DEFAULT_BASELINE = Path(
    "/private/tmp/claude-501/-Users-wuhao-Desktop-TriModalSurv/"
    "d9b60c11-2928-47a3-b644-ee7a4e66f22c/scratchpad/capl_before/model/compensator.py"
)
DEFAULT_BASELINE_V3 = Path(
    "/private/tmp/claude-501/-Users-wuhao-Desktop-TriModalSurv/"
    "d9b60c11-2928-47a3-b644-ee7a4e66f22c/scratchpad/capl_v3_before/model/compensator.py"
)
INIT_LOGIT_SCALE = math.log(1.0 / 0.07)
LOGIT_SCALE_MAX = math.log(100.0)


# --------------------------------------------------------------------------
# 夹具
# --------------------------------------------------------------------------
def load_baseline_module():
    """把补丁前 compensator.py 快照作为独立模块导入（sys.modules 先注册，见坑 E4）。"""
    baseline = Path(os.environ.get("NPJ_COMPENSATOR_BASELINE", str(DEFAULT_BASELINE)))
    if not baseline.is_file():
        raise unittest.SkipTest(
            f"基线快照不存在: {baseline}（设 NPJ_COMPENSATOR_BASELINE 指定）"
        )
    name = "compensator_baseline_capl"
    spec = importlib.util.spec_from_file_location(name, baseline)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def load_baseline_v3_module():
    """把修订 v3 补丁前（= v2 交付版）compensator.py 快照作为独立模块导入。"""
    baseline = Path(
        os.environ.get("NPJ_COMPENSATOR_BASELINE_V3", str(DEFAULT_BASELINE_V3))
    )
    if not baseline.is_file():
        raise unittest.SkipTest(
            f"v2 基线快照不存在: {baseline}（设 NPJ_COMPENSATOR_BASELINE_V3 指定）"
        )
    name = "compensator_baseline_capl_v3"
    spec = importlib.util.spec_from_file_location(name, baseline)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def fake_modalities():
    import types

    dims = {"img": 1536, "text": 768, "rna": 256}
    return {
        name: types.SimpleNamespace(modality_name=name, feature_dim=dim)
        for name, dim in dims.items()
    }


def load_model_kwargs(**overrides):
    common = dict(
        device="cpu",
        modalities=fake_modalities(),
        hidden_size=DIM,
        pred_dim=N_BINS,
        cancer_types=["BLCA"],
    )
    common.update(overrides)
    return common


def make_capl(proto_per_bin, seed=0, modalities=MODALITIES):
    torch.manual_seed(seed)
    return patched.CAPRecallMulti(
        modalities=modalities, dim=DIM, n_bins=N_BINS, proto_per_bin=proto_per_bin
    )


def capr_fixture_batch(batch=6, seed=7):
    """给 CAPRecall / CAPRecallMulti 共用的合成 batch（含 dropout 位与 _orig）。"""
    generator = torch.Generator().manual_seed(seed)
    tokens = {
        "img": torch.randn(batch, DIM, generator=generator),
        "text": torch.randn(batch, DIM, generator=generator),
        "rna": torch.randn(batch, DIM, generator=generator),
        "text_orig": torch.randn(batch, DIM, generator=generator),
        "rna_orig": torch.randn(batch, DIM, generator=generator),
    }
    valids = {
        "text": torch.tensor([1, 0, 1, 0, 1, 1]).bool(),
        "rna": torch.tensor([0, 1, 1, 1, 0, 1]).bool(),
        "text_dropped": torch.tensor([0, 1, 0, 0, 0, 0]).bool(),
        "rna_dropped": torch.tensor([1, 0, 0, 0, 0, 0]).bool(),
    }
    bin_labels = torch.tensor([0, 1, 2, 3, 0, 1])
    return tokens, valids, bin_labels


def clustered_points(centers, per_center, spread=0.01, seed=0):
    generator = torch.Generator().manual_seed(seed)
    points = []
    for center in centers:
        noise = torch.randn(per_center, DIM, generator=generator) * spread
        points.append(center.unsqueeze(0) + noise)
    return torch.cat(points, dim=0)


def basis(index, scale=10.0):
    vector = torch.zeros(DIM)
    vector[index % DIM] = scale
    return vector


# --------------------------------------------------------------------------
# 验收 ①：capr 逐位不变
# --------------------------------------------------------------------------
def test_capr_bitwise_identical():
    baseline = load_baseline_module()

    torch.manual_seed(0)
    before = baseline.CAPRecall(MODALITIES, DIM)
    torch.manual_seed(0)
    after = patched.CAPRecall(MODALITIES, DIM)

    keys_before = set(before.state_dict())
    keys_after = set(after.state_dict())
    assert keys_before == keys_after, (
        f"state_dict 键集合不同: 仅前={sorted(keys_before - keys_after)} "
        f"仅后={sorted(keys_after - keys_before)}"
    )
    state_before, state_after = before.state_dict(), after.state_dict()
    for key in sorted(keys_before):
        assert torch.equal(state_before[key], state_after[key]), f"参数逐位不同: {key}"

    tokens, valids, bin_labels = capr_fixture_batch()
    for training in (True, False):
        before.train(training)
        after.train(training)
        with torch.no_grad():
            out_before, pairs_before = before(tokens, valids, bin_labels, training=training)
            out_after, pairs_after = after(tokens, valids, bin_labels, training=training)
        assert set(out_before) == set(out_after), "输出 token 键集合不同"
        for key in sorted(out_before):
            assert torch.equal(out_before[key], out_after[key]), (
                f"training={training} 输出 token 逐位不同: {key}"
            )
        assert len(pairs_before) == len(pairs_after), "consistency pairs 数量不同"
        for index, (pair_before, pair_after) in enumerate(zip(pairs_before, pairs_after)):
            for position in (0, 1):
                assert torch.equal(pair_before[position], pair_after[position]), (
                    f"training={training} pairs[{index}][{position}] 逐位不同"
                )
    # 训练前向后 EMA buffer 也必须逐位一致
    for key in sorted(keys_before):
        assert torch.equal(before.state_dict()[key], after.state_dict()[key]), (
            f"前向后 buffer 逐位不同: {key}"
        )


def test_load_model_capr_unchanged():
    model = main_survival.load_model(
        **load_model_kwargs(
            network_type="MainModalityMoE", compensator="capr", fusion_type="mean"
        )
    )
    assert isinstance(model.compensator, patched.CAPRecall), type(model.compensator)
    assert not isinstance(model.compensator, patched.CAPRecallMulti)


# --------------------------------------------------------------------------
# 验收 ②(a)：buffer 形状与 state_dict 键集合
# --------------------------------------------------------------------------
def test_buffer_shapes_and_state_dict_keys():
    for proto_per_bin in (1, 32):
        module = make_capl(proto_per_bin)
        for modality in MODALITIES:
            assert tuple(getattr(module, f"{modality}_prototypes").shape) == (
                N_BINS, proto_per_bin, DIM
            ), modality
            assert tuple(getattr(module, f"{modality}_slot_valid").shape) == (
                N_BINS, proto_per_bin
            ), modality
            assert getattr(module, f"{modality}_slot_valid").dtype == torch.bool
            assert tuple(getattr(module, f"{modality}_slot_counts").shape) == (
                N_BINS, proto_per_bin
            ), modality
            assert getattr(module, f"{modality}_slot_counts").dtype == torch.long

        expected = set()
        for modality in MODALITIES:
            for head in ("query", "key", "output"):
                expected.add(f"{head}.{modality}.weight")
                expected.add(f"{head}.{modality}.bias")
            expected.add(f"{modality}_prototypes")
            expected.add(f"{modality}_slot_valid")
            expected.add(f"{modality}_slot_counts")
            expected.add(f"logit_scale.{modality}")  # 修订 v3
        actual = set(module.state_dict())
        assert actual == expected, (
            f"L={proto_per_bin} state_dict 键集合不符: 多={sorted(actual - expected)} "
            f"少={sorted(expected - actual)}"
        )


# --------------------------------------------------------------------------
# 验收 ②(b)：init_prototypes
# --------------------------------------------------------------------------
def _init_fixture(proto_per_bin=4, seed=123):
    """bin0=2 样本、bin1=10 样本、bin2=0 样本、bin3=4 样本。"""
    module = make_capl(proto_per_bin)
    chunks = []
    labels = []
    bin_plan = {0: 2, 1: 10, 2: 0, 3: 4}
    offset = 0
    for bin_index, count in bin_plan.items():
        if count == 0:
            continue
        centers = [basis(offset + index, scale=10.0 + index) for index in range(count)]
        chunks.append(clustered_points(centers, 1, spread=0.001, seed=bin_index))
        labels.append(torch.full((count,), bin_index, dtype=torch.long))
        offset += count
    tokens = {modality: torch.cat(chunks, dim=0) for modality in MODALITIES}
    bin_labels = {modality: torch.cat(labels, dim=0) for modality in MODALITIES}
    module.init_prototypes(tokens, bin_labels, seed)
    return module, bin_plan


def test_init_prototypes_slot_counts_and_determinism():
    proto_per_bin = 4
    module, bin_plan = _init_fixture(proto_per_bin)
    for modality in MODALITIES:
        slot_valid = getattr(module, f"{modality}_slot_valid")
        prototypes = getattr(module, f"{modality}_prototypes")
        for bin_index, count in bin_plan.items():
            expected = min(proto_per_bin, count)
            actual = int(slot_valid[bin_index].sum().item())
            assert actual == expected, (
                f"{modality} bin={bin_index} 有效槽 {actual} != 期望 {expected}"
            )
            # 有效槽必须在前 expected 个位置
            assert slot_valid[bin_index][:expected].all(), (modality, bin_index)
            assert not slot_valid[bin_index][expected:].any(), (modality, bin_index)
            # 有效槽两两不同
            rows = [prototypes[bin_index, slot] for slot in range(expected)]
            for first in range(len(rows)):
                for second in range(first + 1, len(rows)):
                    assert not torch.equal(rows[first], rows[second]), (
                        f"{modality} bin={bin_index} 槽 {first}/{second} 相同"
                    )
            # 无效槽保持全零
            for slot in range(expected, proto_per_bin):
                assert torch.equal(
                    prototypes[bin_index, slot], torch.zeros(DIM)
                ), (modality, bin_index, slot)

    # 同 seed 两次初始化逐位相同
    again, _ = _init_fixture(proto_per_bin)
    for key, value in module.state_dict().items():
        assert torch.equal(value, again.state_dict()[key]), f"同 seed 初始化不可复现: {key}"


def test_init_prototypes_empty_bin_all_invalid():
    module, _ = _init_fixture(4)
    for modality in MODALITIES:
        slot_valid = getattr(module, f"{modality}_slot_valid")
        assert not slot_valid[2].any(), f"{modality} 空箱应全部无效: {slot_valid[2]}"


# --------------------------------------------------------------------------
# 验收 ②(c)：更新只动自己箱、自己子群的槽
# --------------------------------------------------------------------------
def _two_subgroup_module():
    """L=2；bin0 与 bin1 各两个明显分离的子群。"""
    module = make_capl(2)
    group = {
        (0, 0): basis(0, 10.0),
        (0, 1): basis(1, 10.0),
        (1, 0): basis(2, 10.0),
        (1, 1): basis(3, 10.0),
    }
    chunks, labels = [], []
    for (bin_index, sub), center in group.items():
        chunks.append(clustered_points([center], 3, spread=0.001, seed=bin_index * 10 + sub))
        labels.append(torch.full((3,), bin_index, dtype=torch.long))
    tokens = {modality: torch.cat(chunks, dim=0) for modality in MODALITIES}
    bin_labels = {modality: torch.cat(labels, dim=0) for modality in MODALITIES}
    module.init_prototypes(tokens, bin_labels, 5)
    return module, group


def _slot_of(module, modality, bin_index, center):
    prototypes = getattr(module, f"{modality}_prototypes")
    distances = [
        float((prototypes[bin_index, slot] - center).norm())
        for slot in range(module.proto_per_bin)
    ]
    return int(min(range(len(distances)), key=distances.__getitem__))


def test_update_moves_only_own_slot():
    module, group = _two_subgroup_module()
    module.train(True)
    before = {
        modality: getattr(module, f"{modality}_prototypes").clone()
        for modality in MODALITIES
    }
    target_slot = _slot_of(module, "text", 0, group[(0, 0)])
    other_slot = 1 - target_slot

    # batch：3 个 bin0/子群 A 的有效样本 + 1 个 valid=0 的远点（不得参与）
    members = clustered_points([group[(0, 0)]], 3, spread=0.001, seed=99)
    outlier = basis(5, 100.0).unsqueeze(0)
    tokens_batch = torch.cat([members, outlier], dim=0)
    tokens = {modality: tokens_batch.clone() for modality in MODALITIES}
    valids = {modality: torch.tensor([1, 1, 1, 0]).bool() for modality in MODALITIES}
    bin_labels = torch.tensor([0, 0, 0, 0])

    module.update_prototypes(tokens, valids, bin_labels)

    for modality in MODALITIES:
        prototypes = getattr(module, f"{modality}_prototypes")
        counts = getattr(module, f"{modality}_slot_counts")
        mean = members.mean(dim=0)
        expected = before[modality][0, target_slot] * module.ema + mean * (1.0 - module.ema)
        assert torch.equal(prototypes[0, target_slot], expected), (
            f"{modality} 目标槽未按 0.99p+0.01μ 更新, "
            f"maxdiff={(prototypes[0, target_slot] - expected).abs().max().item():.3e}"
        )
        # 独立 float64 复算，排除「测试复写实现」的自证
        reference = (
            before[modality][0, target_slot].double() * 0.99 + mean.double() * 0.01
        )
        assert torch.allclose(prototypes[0, target_slot].double(), reference, atol=1e-6), (
            f"{modality} 目标槽与 float64 参考不符"
        )
        # 同箱另一槽（空集合）不动
        assert torch.equal(prototypes[0, other_slot], before[modality][0, other_slot]), (
            f"{modality} 空集合槽被改动"
        )
        # 跨箱槽全部不动
        assert torch.equal(prototypes[1], before[modality][1]), f"{modality} 跨箱槽被改动"
        assert int(counts[0, target_slot].item()) == 3, counts[0].tolist()
        assert int(counts[0, other_slot].item()) == 0, counts[0].tolist()
        assert int(counts[1].sum().item()) == 0, counts[1].tolist()
        assert module.used_slots(modality) == 1, module.used_slots(modality)


def test_update_skipped_when_eval():
    module, group = _two_subgroup_module()
    module.eval()
    before = getattr(module, "text_prototypes").clone()
    tokens = {modality: clustered_points([group[(0, 0)]], 2, seed=3) for modality in MODALITIES}
    valids = {modality: torch.tensor([1, 1]).bool() for modality in MODALITIES}
    module.update_prototypes(tokens, valids, torch.tensor([0, 0]))
    assert torch.equal(getattr(module, "text_prototypes"), before), "eval 模式不得更新原型"


# --------------------------------------------------------------------------
# 验收 ②(d)：L=1 一步更新 = 该箱有效样本均值的 EMA
# --------------------------------------------------------------------------
def test_l1_update_equals_bin_mean_ema():
    module = make_capl(1)
    init_tokens = {
        modality: clustered_points([basis(0, 10.0), basis(1, 10.0)], 2, seed=1)
        for modality in MODALITIES
    }
    init_labels = {
        modality: torch.tensor([0, 0, 1, 1]) for modality in MODALITIES
    }
    module.init_prototypes(init_tokens, init_labels, 11)
    module.train(True)
    before = {
        modality: getattr(module, f"{modality}_prototypes").clone()
        for modality in MODALITIES
    }

    generator = torch.Generator().manual_seed(21)
    batch = torch.randn(5, DIM, generator=generator)
    tokens = {modality: batch.clone() for modality in MODALITIES}
    valids = {modality: torch.tensor([1, 1, 0, 1, 1]).bool() for modality in MODALITIES}
    bin_labels = torch.tensor([0, 0, 0, 1, 1])
    module.update_prototypes(tokens, valids, bin_labels)

    for modality in MODALITIES:
        prototypes = getattr(module, f"{modality}_prototypes")
        for bin_index, rows in ((0, [0, 1]), (1, [3, 4])):
            mean = batch[rows].mean(dim=0)
            expected = before[modality][bin_index, 0] * module.ema + mean * (1.0 - module.ema)
            assert torch.equal(prototypes[bin_index, 0], expected), (
                f"{modality} bin={bin_index} L=1 更新不等于该箱有效样本均值的 EMA"
            )
        # 无样本的 bin2/bin3 不动
        assert torch.equal(prototypes[2], before[modality][2])
        assert torch.equal(prototypes[3], before[modality][3])


# --------------------------------------------------------------------------
# 验收 ②(e)：召回注意力与手算
# --------------------------------------------------------------------------
def test_recall_attention_and_manual_output():
    """修订 v3 验收 (iv)：无效槽注意力恰 0、有效槽和为 1、手算 = 实现（float64 独立复算）。"""
    module, _ = _init_fixture(4, seed=31)
    module.eval()
    generator = torch.Generator().manual_seed(41)
    anchor = torch.randn(3, DIM, generator=generator)
    modality = "text"

    prototypes = getattr(module, f"{modality}_prototypes").reshape(-1, DIM)
    slot_valid = getattr(module, f"{modality}_slot_valid").reshape(-1)
    with torch.no_grad():
        # 独立 float64 复算：显式除以 L2 范数，不调用 F.normalize，不复用实现分支
        query64 = module.query[modality](anchor).double()
        query64 = query64 / query64.norm(dim=-1, keepdim=True)
        keys64 = module.key[modality](prototypes).double()
        keys64 = keys64 / keys64.norm(dim=-1, keepdim=True)
        scale = math.exp(
            min(float(module.logit_scale[modality].item()), LOGIT_SCALE_MAX)
        )
        logits = scale * (query64 @ keys64.transpose(-1, -2))
        logits = logits.masked_fill(~slot_valid, float("-inf"))
        attention64 = torch.softmax(logits, dim=-1)
        manual = module.output[modality]((attention64 @ prototypes.double()).float())
        actual = module.recall(anchor, modality)
        attention, _, _ = module._attention(anchor, modality)

    assert torch.equal(attention[:, ~slot_valid], torch.zeros(3, int((~slot_valid).sum()))), (
        "无效槽注意力必须恰为 0"
    )
    row_sums = attention[:, slot_valid].sum(dim=-1)
    assert torch.allclose(row_sums, torch.ones(3), atol=1e-6), row_sums.tolist()
    assert torch.allclose(attention.double(), attention64, atol=1e-6), (
        f"注意力与 float64 手算不符, maxdiff="
        f"{(attention.double() - attention64).abs().max().item():.3e}"
    )
    assert torch.allclose(actual, manual, atol=1e-6), (
        f"召回输出与手算不符, maxdiff={(actual - manual).abs().max().item():.3e}"
    )


def test_recall_path_ignores_bin_labels():
    module, _ = _init_fixture(4, seed=31)
    module.eval()
    tokens, valids, bin_labels = capr_fixture_batch()
    with torch.no_grad():
        without_labels, _ = module(tokens, valids, bin_labels=None, training=False)
        with_labels, _ = module(tokens, valids, bin_labels=bin_labels, training=False)
        direct = module.recall(tokens["img"][~valids["text"]], "text")
    for modality in MODALITIES:
        assert torch.equal(without_labels[modality], with_labels[modality]), (
            f"{modality} 推断期召回受 bin_labels 影响"
        )
    assert torch.equal(without_labels["text"][~valids["text"]], direct), (
        "缺失位召回值与 recall(img 锚) 不一致"
    )


# --------------------------------------------------------------------------
# 验收 ②(f)：退化检验——所有槽相同则 L=32 与 L=1 一致
# --------------------------------------------------------------------------
def _degenerate_recall(proto_per_bin, vector, weights_source):
    module = make_capl(proto_per_bin, seed=0)
    module.load_state_dict(
        {
            key: value.clone()
            for key, value in weights_source.items()
            if not key.endswith(("_prototypes", "_slot_valid", "_slot_counts"))
        },
        strict=False,
    )
    for modality in MODALITIES:
        getattr(module, f"{modality}_prototypes").copy_(
            vector.reshape(1, 1, DIM).expand(N_BINS, proto_per_bin, DIM)
        )
        getattr(module, f"{modality}_slot_valid").fill_(True)
    module.eval()
    return module


def test_degenerate_slots_match_l1():
    reference = make_capl(1, seed=0)
    weights = reference.state_dict()
    generator = torch.Generator().manual_seed(77)
    anchor = torch.randn(4, DIM, generator=generator)

    # 逐位分支：原型取二进制可精确表示的值，排除浮点求和顺序噪声
    dyadic = torch.full((DIM,), 0.5)
    small = _degenerate_recall(1, dyadic, weights)
    large = _degenerate_recall(32, dyadic, weights)
    with torch.no_grad():
        out_small = small.recall(anchor, "text")
        out_large = large.recall(anchor, "text")
    assert torch.equal(out_small, out_large), (
        f"L=32 全同槽召回与 L=1 不逐位一致, maxdiff={(out_small - out_large).abs().max().item():.3e}"
    )

    # 数值分支：任意随机原型下仍需 allclose（浮点求和顺序不同，容差 1e-5）
    random_vector = torch.randn(DIM, generator=torch.Generator().manual_seed(78))
    small_random = _degenerate_recall(1, random_vector, weights)
    large_random = _degenerate_recall(32, random_vector, weights)
    with torch.no_grad():
        assert torch.allclose(
            small_random.recall(anchor, "text"),
            large_random.recall(anchor, "text"),
            atol=1e-5,
        ), "随机原型下退化召回不一致"

    # 不触发侧（坑 V31）：槽不相同时 L=32 与 L=1 必须不同
    diverse = _degenerate_recall(32, dyadic, weights)
    with torch.no_grad():
        getattr(diverse, "text_prototypes")[0, 1] = torch.full((DIM,), -3.0)
        assert not torch.allclose(
            diverse.recall(anchor, "text"), out_large, atol=1e-6
        ), "槽被改成互异后召回却未变化"


def test_recall_without_valid_slot_raises():
    module = make_capl(4)
    module.eval()
    anchor = torch.randn(2, DIM, generator=torch.Generator().manual_seed(5))
    try:
        module.recall(anchor, "text")
    except RuntimeError as error:
        assert "init_prototypes" in str(error), error
    else:
        raise AssertionError("未初始化（无有效槽）时召回应当报错，不得静默返回 NaN")


# --------------------------------------------------------------------------
# 验收 ②(g)：load_model 参数校验
# --------------------------------------------------------------------------
def test_load_model_validations():
    try:
        main_survival.load_model(
            **load_model_kwargs(
                network_type="MainModalityMoE", compensator="capl", fusion_type="mean"
            )
        )
    except ValueError as error:
        assert "proto_per_bin" in str(error), error
    else:
        raise AssertionError("compensator='capl' 缺 proto_per_bin 应当抛 ValueError")

    try:
        main_survival.load_model(
            **load_model_kwargs(
                network_type="MainModalityMoE",
                compensator="capr",
                fusion_type="mean",
                proto_per_bin=8,
            )
        )
    except ValueError as error:
        assert "proto_per_bin" in str(error), error
    else:
        raise AssertionError("compensator='capr' 给 proto_per_bin 应当抛 ValueError")

    for bad in (0, -1):
        try:
            main_survival.load_model(
                **load_model_kwargs(
                    network_type="MainModalityMoE",
                    compensator="capl",
                    fusion_type="mean",
                    proto_per_bin=bad,
                )
            )
        except ValueError as error:
            assert "proto_per_bin" in str(error), error
        else:
            raise AssertionError(f"proto_per_bin={bad} 应当抛 ValueError")

    # 正常构造（D 底座）
    model = main_survival.load_model(
        **load_model_kwargs(
            network_type="MainModalityMoE",
            compensator="capl",
            fusion_type="mean",
            proto_per_bin=32,
        )
    )
    assert isinstance(model.compensator, patched.CAPRecallMulti)
    assert model.compensator.proto_per_bin == 32
    assert model.compensator.n_bins == 4
    assert model.compensator.ema == 0.99
    assert model.compensator.modalities == ("text", "rna")

    # capl + NPJC 允许（本战役不用，但不禁止）
    npjc = main_survival.load_model(
        **load_model_kwargs(network_type="NPJC", compensator="capl", proto_per_bin=8)
    )
    assert isinstance(npjc.compensator, patched.CAPRecallMulti)
    assert npjc.compensator.proto_per_bin == 8


# --------------------------------------------------------------------------
# 验收 ②(h)：strict 加载形状不匹配必须报错
# --------------------------------------------------------------------------
def test_strict_load_shape_mismatch():
    source = make_capl(32, seed=3)
    target = make_capl(8, seed=3)
    try:
        target.load_state_dict(source.state_dict(), strict=True)
    except RuntimeError as error:
        assert "size mismatch" in str(error).lower(), error
    else:
        raise AssertionError("L=32 的 state_dict 载入 L=8 模型必须报错，不得静默成功")

    # 不触发侧（坑 V31）：同 L 可以正常严格加载
    same = make_capl(8, seed=9)
    same.load_state_dict(target.state_dict(), strict=True)
    for key, value in target.state_dict().items():
        assert torch.equal(value, same.state_dict()[key]), key


# --------------------------------------------------------------------------
# 附加：main_survival 初始化趟 / epoch 末诊断 / eval_missing 开关（合成数据端到端）
# --------------------------------------------------------------------------
class _FakeSurvivalDataset(torch.utils.data.Dataset):
    """最小合成 survival dataset：形状与真实 batch 一致，只是 token 数很小。"""

    FEATURE_DIMS = {"img": 1536, "text": 768, "rna": 256}
    TOKEN_COUNTS = {"img": 4, "text": 3, "rna": 5}

    def __init__(self, size=12, seed=0):
        generator = torch.Generator().manual_seed(seed)
        self.size = size
        self.data = {
            name: torch.randn(size, self.TOKEN_COUNTS[name], dim, generator=generator)
            for name, dim in self.FEATURE_DIMS.items()
        }
        self.bins = torch.arange(size) % N_BINS
        # 样本 0：text 被 dropout 置零（_orig 仍是真值）；样本 1：text 天然缺失
        self.text_valid = torch.ones(size).bool()
        self.text_valid[0] = False
        self.text_valid[1] = False
        self.text_dropped = torch.zeros(size).bool()
        self.text_dropped[0] = True
        self.rna_valid = torch.ones(size).bool()
        self.rna_dropped = torch.zeros(size).bool()

    def __len__(self):
        return self.size

    def __getitem__(self, index):
        sample = {
            "idx": torch.tensor(index),
            "cancer_type": "BLCA",
            "label": torch.tensor(0).long(),
            "survival_months": torch.tensor(10.0),
            "survival_months_bin": self.bins[index].clone(),
            "censorship": torch.tensor(0.0),
            "img": self.data["img"][index],
            "text": (
                torch.zeros_like(self.data["text"][index])
                if bool(self.text_dropped[index])
                else self.data["text"][index]
            ),
            "text_orig": self.data["text"][index],
            "text_dropped": self.text_dropped[index].clone(),
            "text_valid": self.text_valid[index].clone(),
            "rna": self.data["rna"][index],
            "rna_orig": self.data["rna"][index],
            "rna_dropped": self.rna_dropped[index].clone(),
            "rna_valid": self.rna_valid[index].clone(),
        }
        return sample


def _capl_model(proto_per_bin=2):
    torch.manual_seed(0)
    return main_survival.load_model(
        **load_model_kwargs(
            network_type="MainModalityMoE",
            compensator="capl",
            fusion_type="mean",
            proto_per_bin=proto_per_bin,
        )
    )


def test_init_pass_uses_orig_and_skips_natural_missing():
    dataset = _FakeSurvivalDataset(size=12, seed=3)
    model = _capl_model(proto_per_bin=2)
    main_survival.init_capl_prototypes(model, dataset, seed=7, device="cpu", batch_size=4)
    compensator = model.compensator

    # text：12 个样本里 1 个天然缺失被排除，dropout 置零的样本仍计入（用 _orig）
    text_valid_slots = int(compensator.text_slot_valid.sum().item())
    rna_valid_slots = int(compensator.rna_slot_valid.sum().item())
    assert text_valid_slots > 0 and rna_valid_slots > 0, (text_valid_slots, rna_valid_slots)
    assert rna_valid_slots == 2 * N_BINS, f"rna 每箱 3 样本应填满 L=2 槽: {rna_valid_slots}"
    # bin1 少了天然缺失的样本 1 → text 该箱只剩 2 个样本，仍能填满 L=2
    assert text_valid_slots == 2 * N_BINS, text_valid_slots

    # dropout 置零的样本用的是 _orig：把 _orig 改成常量后原型必须改变
    baseline_prototypes = compensator.text_prototypes.clone()
    dataset.data["text"][0] = torch.full_like(dataset.data["text"][0], 5.0)
    again = _capl_model(proto_per_bin=2)
    again.load_state_dict(model.state_dict(), strict=True)
    main_survival.init_capl_prototypes(again, dataset, seed=7, device="cpu", batch_size=4)
    assert not torch.equal(again.compensator.text_prototypes, baseline_prototypes), (
        "改动 dropout 样本的 _orig 后原型未变化，说明初始化没有使用 _orig"
    )

    # 初始化后模型仍处于原来的 train/eval 模式
    model.train(True)
    main_survival.init_capl_prototypes(model, dataset, seed=7, device="cpu", batch_size=4)
    assert model.training, "初始化趟后未恢复 train 模式"


def test_epoch_stats_print_format():
    import contextlib
    import io

    dataset = _FakeSurvivalDataset(size=8, seed=5)
    model = _capl_model(proto_per_bin=2)
    main_survival.init_capl_prototypes(model, dataset, seed=7, device="cpu", batch_size=4)
    loader = torch.utils.data.DataLoader(dataset, batch_size=4, shuffle=False)
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        main_survival.print_capl_stats(model, loader, "cpu", epoch=3)
    lines = [line for line in buffer.getvalue().splitlines() if line.startswith("CAPL_STATS")]
    assert len(lines) == len(MODALITIES), buffer.getvalue()
    assert not any("used_slots=" in line for line in lines), (
        f"修订 v3 已把字段名改为 updated_slots: {lines}"
    )
    for modality, line in zip(MODALITIES, lines):
        for token in ("epoch=3", "modality=", "attn_entropy_mean=", "attn_entropy_max=",
                      "top1_share=", "updated_slots=", "valid_slots=", "scale="):
            assert token in line, (token, line)
        # n_bins(4) * L(2) = 8 个槽；尚未训练 → updated_slots 为 0
        assert "updated_slots=0/8" in line, f"尚未训练时 updated_slots 应为 0: {line}"
        expected_valid = int(
            getattr(model.compensator, f"{modality}_slot_valid").sum().item()
        )
        assert f"valid_slots={expected_valid} " in line + " ", (
            f"{modality} valid_slots 与 buffer 不符（期望 {expected_valid}）: {line}"
        )
        assert f"scale={math.exp(INIT_LOGIT_SCALE):.6f}" in line, line
    # updated_slots 与 valid_slots 语义不同：本例 text 有槽有效但一个都没更新过
    assert int(model.compensator.text_slot_valid.sum().item()) > 0
    assert model.compensator.used_slots("text") == 0

    # 训练一步后 used_slots 增加，reset 后归零
    model.compensator.train(True)
    batch_tokens = {
        modality: torch.randn(4, DIM, generator=torch.Generator().manual_seed(1))
        for modality in MODALITIES
    }
    model.compensator.update_prototypes(
        batch_tokens,
        {modality: torch.ones(4).bool() for modality in MODALITIES},
        torch.tensor([0, 0, 1, 1]),
    )
    assert model.compensator.used_slots("text") > 0
    model.compensator.reset_epoch_stats()
    assert model.compensator.used_slots("text") == 0


def test_eval_missing_new_options():
    import argparse
    import inspect
    from unittest import mock

    from trimodalsurv.evaluation import missing as eval_missing

    parameters = inspect.signature(eval_missing._make_dataset).parameters
    assert "bin_mode" in parameters and "bin_edges" in parameters, list(parameters)
    assert parameters["bin_mode"].default == "author"
    assert parameters["bin_edges"].default is None

    argv = [
        "eval_missing.py", "--arm", "m0real", "--cancer", "BLCA", "--seed", "123",
        "--ckpt", "/tmp/x.pth", "--manifest", "/tmp/m.csv", "--label", "/tmp/l.csv",
        "--out-dir", "/tmp/out", "--compensator", "capl", "--proto_per_bin", "32",
        "--bin_mode", "train_quantile", "--fusion_type", "mean",
    ]
    with mock.patch.object(sys, "argv", argv):
        args = eval_missing.parse_args()
    assert args.compensator == "capl"
    assert args.proto_per_bin == 32
    assert args.bin_mode == "train_quantile"

    # 默认值：author + 无 proto_per_bin（与补丁前调用逐字兼容）
    with mock.patch.object(sys, "argv", argv[:15] + ["--bin_mode", "author"]):
        default_args = eval_missing.parse_args()
    assert default_args.bin_mode == "author", default_args.bin_mode
    assert default_args.proto_per_bin is None
    assert default_args.compensator == "none"
    assert isinstance(default_args, argparse.Namespace)


def test_main_survival_cli_defaults():
    args = main_survival.parsing_args(["--bin_mode", "author"])
    assert args.bin_mode == "author", args.bin_mode
    assert args.proto_per_bin is None
    assert args.compensator == "none"
    capl_args = main_survival.parsing_args(
        ["--compensator", "capl", "--proto_per_bin", "32", "--bin_mode", "train_quantile"]
    )
    assert capl_args.compensator == "capl"
    assert capl_args.proto_per_bin == 32
    assert capl_args.bin_mode == "train_quantile"


# ==========================================================================
# 修订 v3（注意力尺度）验收 (i)(ii)(iii)(v)(vi)
# ==========================================================================
def _orthogonal_slot_module(proto_per_bin=8):
    """把 Q/K 设成恒等、原型设成互相正交的基向量：注意力方向可解析预测。

    用于验收 (ii)「确定性方向匹配」——不依赖随机熵门槛。
    """
    module = make_capl(proto_per_bin)
    total = N_BINS * proto_per_bin
    assert total <= DIM, (total, DIM)
    with torch.no_grad():
        for modality in MODALITIES:
            module.query[modality].weight.copy_(torch.eye(DIM))
            module.query[modality].bias.zero_()
            module.key[modality].weight.copy_(torch.eye(DIM))
            module.key[modality].bias.zero_()
            flat = getattr(module, f"{modality}_prototypes").view(total, DIM)
            flat.zero_()
            for index in range(total):
                flat[index, index] = 2.0 + index  # 正交方向、范数各异
            getattr(module, f"{modality}_slot_valid").fill_(True)
    module.eval()
    return module, total


def test_logit_scale_parameter_and_capr_unchanged():
    """验收 (i)：每模态一个标量温度进 state_dict、可训练、初值 log(1/0.07)。"""
    for proto_per_bin in (1, 32):
        module = make_capl(proto_per_bin)
        state = module.state_dict()
        for modality in MODALITIES:
            key = f"logit_scale.{modality}"
            assert key in state, sorted(state)
            assert tuple(state[key].shape) == (), state[key].shape
            assert state[key].dtype == torch.float32, state[key].dtype
            parameter = module.logit_scale[modality]
            assert isinstance(parameter, torch.nn.Parameter), type(parameter)
            assert parameter.requires_grad, f"{key} 必须可训练"
            assert torch.allclose(
                parameter.detach(), torch.tensor(INIT_LOGIT_SCALE), atol=1e-6
            ), parameter.item()
        # 温度是唯一新增的可训练参数；三组 buffer 仍不可训练
        parameter_names = {name for name, _ in module.named_parameters()}
        expected_parameters = set()
        for modality in MODALITIES:
            for head in ("query", "key", "output"):
                expected_parameters.add(f"{head}.{modality}.weight")
                expected_parameters.add(f"{head}.{modality}.bias")
            expected_parameters.add(f"logit_scale.{modality}")
        assert parameter_names == expected_parameters, sorted(
            parameter_names ^ expected_parameters
        )
        for modality in MODALITIES:
            for suffix in ("_prototypes", "_slot_valid", "_slot_counts"):
                assert not getattr(module, f"{modality}{suffix}").requires_grad

    # CAPRecall（历史 E1 行为）相对 v2 快照逐位不变，且不得长出 logit_scale
    baseline = load_baseline_v3_module()
    torch.manual_seed(0)
    before = baseline.CAPRecall(MODALITIES, DIM)
    torch.manual_seed(0)
    after = patched.CAPRecall(MODALITIES, DIM)
    assert set(before.state_dict()) == set(after.state_dict()), (
        sorted(set(before.state_dict()) ^ set(after.state_dict()))
    )
    for key, value in before.state_dict().items():
        assert torch.equal(value, after.state_dict()[key]), key
    assert not any(k.startswith("logit_scale") for k in after.state_dict())

    # CAPRecallMulti 的 Q/K/O 初始化与 v2 逐位相同（logit_scale 不消耗随机数）
    torch.manual_seed(0)
    v2_module = baseline.CAPRecallMulti(MODALITIES, DIM, N_BINS, 4)
    torch.manual_seed(0)
    v3_module = patched.CAPRecallMulti(MODALITIES, DIM, N_BINS, 4)
    v3_state = v3_module.state_dict()
    for key, value in v2_module.state_dict().items():
        assert torch.equal(value, v3_state[key]), f"v2→v3 初始化漂移: {key}"


def test_direction_match_and_scale_monotonic():
    """验收 (ii)：与某槽键方向同向的锚必须命中该槽；温度增大熵严格单调下降。"""
    module, total = _orthogonal_slot_module(8)
    modality = "text"
    flat = getattr(module, f"{modality}_prototypes").reshape(-1, DIM)
    target_slot = 13
    # Q/K 为恒等 → k̂_j 就是归一化后的原型；取该方向作锚
    key_direction = F.normalize(flat[target_slot], dim=-1, eps=1e-8)
    generator = torch.Generator().manual_seed(2026)
    anchors = torch.cat(
        [key_direction.unsqueeze(0), torch.randn(7, DIM, generator=generator)], dim=0
    )

    with torch.no_grad():
        attention, _, slot_valid = module._attention(anchors, modality)
    assert int(slot_valid.sum().item()) == total, slot_valid.sum().item()
    assert int(attention[0].argmax().item()) == target_slot, (
        f"同向锚未命中目标槽: argmax={int(attention[0].argmax().item())}"
    )
    assert float(attention[0, target_slot].item()) >= 0.5, (
        f"同向锚的注意力权重仅 {float(attention[0, target_slot].item()):.4f} < 0.5"
    )

    entropies = []
    for value in (0.0, INIT_LOGIT_SCALE, LOGIT_SCALE_MAX):
        with torch.no_grad():
            for name in MODALITIES:
                module.logit_scale[name].fill_(value)
            entropy, entropy_max, _, n_valid, scale = module.recall_stats(
                anchors, modality
            )
        entropies.append((value, entropy, entropy_max, n_valid, scale))
        assert abs(scale - math.exp(value)) < 1e-4, (value, scale)
    values = [item[1] for item in entropies]
    assert values[0] > values[1] > values[2], (
        f"温度增大熵未严格单调下降: {values}"
    )
    zero_value, zero_entropy, entropy_max, n_valid, _ = entropies[0]
    assert n_valid == total, n_valid
    assert abs(entropy_max - math.log(n_valid)) < 1e-9, (entropy_max, n_valid)
    assert entropy_max - zero_entropy < 0.05, (
        f"logit_scale=0 时熵应贴近上限（差 {entropy_max - zero_entropy:.4f}），"
        "说明尺度确实是那个起作用的因子"
    )


def test_anchor_sensitivity_and_permutation_equivariance():
    """验收 (iii)：不同锚给出不同注意力与不同 ẑ；召回对样本置换等变。"""
    module, _ = _init_fixture(4, seed=31)
    module.eval()
    modality = "text"
    n_anchor = 8
    generator = torch.Generator().manual_seed(4242)
    anchors = torch.randn(n_anchor, DIM, generator=generator)
    # 锚必须互异（否则本用例自证）
    for first in range(n_anchor):
        for second in range(first + 1, n_anchor):
            assert not torch.equal(anchors[first], anchors[second]), (first, second)

    with torch.no_grad():
        attention, _, _ = module._attention(anchors, modality)
        recalled = module.recall(anchors, modality)
    for first in range(n_anchor):
        for second in range(first + 1, n_anchor):
            gap = float((attention[first] - attention[second]).abs().max().item())
            assert gap > 1e-3, (
                f"锚 {first}/{second} 注意力行几乎相同（maxdiff={gap:.3e}），召回仍非个体化"
            )
            assert not torch.allclose(
                recalled[first], recalled[second], atol=1e-6
            ), f"锚 {first}/{second} 的 ẑ 相同"

    permutation = torch.randperm(n_anchor, generator=torch.Generator().manual_seed(9))
    assert not torch.equal(permutation, torch.arange(n_anchor)), permutation.tolist()
    with torch.no_grad():
        permuted = module.recall(anchors[permutation], modality)
    assert torch.allclose(permuted, recalled[permutation], atol=1e-6), (
        "召回不是逐样本置换等变，说明批内样本互相串味"
    )


def test_strict_load_missing_logit_scale_raises():
    """验收 (v)：缺 logit_scale 键的 v2 state_dict 严格加载必须报错。"""
    donor = make_capl(8, seed=3)
    v2_style = {key: value.clone() for key, value in donor.state_dict().items()}
    for modality in MODALITIES:
        v2_style.pop(f"logit_scale.{modality}")

    target = make_capl(8, seed=4)
    try:
        target.load_state_dict(v2_style, strict=True)
    except RuntimeError as error:
        assert "logit_scale" in str(error), error
        assert "missing" in str(error).lower(), error
    else:
        raise AssertionError("缺 logit_scale 的 v2 state_dict 严格加载必须报错")

    # 真实 v2 快照构造的 state_dict 同样必须报错（不只是人工删键）
    baseline = load_baseline_v3_module()
    v2_module = baseline.CAPRecallMulti(MODALITIES, DIM, N_BINS, 8)
    v2_state = v2_module.state_dict()
    assert not any(k.startswith("logit_scale") for k in v2_state), sorted(v2_state)
    try:
        target.load_state_dict(v2_state, strict=True)
    except RuntimeError as error:
        assert "logit_scale" in str(error), error
    else:
        raise AssertionError("v2 快照 state_dict 严格加载必须报错")

    # 不触发侧（坑 V31）：strict=False 时按初值补齐，其余键正常加载
    fallback = make_capl(8, seed=5)
    result = fallback.load_state_dict(v2_state, strict=False)
    assert set(result.missing_keys) == {
        f"logit_scale.{modality}" for modality in MODALITIES
    }, result.missing_keys
    assert not result.unexpected_keys, result.unexpected_keys
    for modality in MODALITIES:
        assert torch.allclose(
            fallback.logit_scale[modality].detach(),
            torch.tensor(INIT_LOGIT_SCALE),
            atol=1e-6,
        )
        assert torch.equal(
            getattr(fallback, f"{modality}_prototypes"),
            getattr(v2_module, f"{modality}_prototypes"),
        )


def test_extreme_logit_scale_finite_gradients():
    """验收 (vi)：logit_scale = log100 / 100（clamp 前）时前向有限、梯度无 NaN/inf。"""
    for value in (LOGIT_SCALE_MAX, 100.0):
        module, _ = _init_fixture(4, seed=31)
        with torch.no_grad():
            for modality in MODALITIES:
                module.logit_scale[modality].fill_(value)
        module.eval()
        module.zero_grad(set_to_none=True)
        anchor = torch.randn(5, DIM, generator=torch.Generator().manual_seed(17))
        recalled = module.recall(anchor, "text")
        assert torch.isfinite(recalled).all(), (
            f"logit_scale={value} 前向出现 NaN/inf"
        )
        _, _, _, _, scale = module.recall_stats(anchor, "text")
        assert abs(scale - 100.0) < 1e-3, (value, scale)
        recalled.sum().backward()
        seen = 0
        for name, parameter in module.named_parameters():
            if parameter.grad is None:
                continue
            seen += 1
            assert torch.isfinite(parameter.grad).all(), (
                f"logit_scale={value} 时参数 {name} 梯度含 NaN/inf"
            )
        assert seen > 0, "反向后没有任何参数拿到梯度"
        for head in ("query", "key", "output"):
            assert getattr(module, head)["text"].weight.grad is not None, head
        assert module.logit_scale["text"].grad is not None
        assert torch.isfinite(module.logit_scale["text"].grad).all()


TESTS = [
    test_capr_bitwise_identical,
    test_load_model_capr_unchanged,
    test_buffer_shapes_and_state_dict_keys,
    test_init_prototypes_slot_counts_and_determinism,
    test_init_prototypes_empty_bin_all_invalid,
    test_update_moves_only_own_slot,
    test_update_skipped_when_eval,
    test_l1_update_equals_bin_mean_ema,
    test_recall_attention_and_manual_output,
    test_recall_path_ignores_bin_labels,
    test_logit_scale_parameter_and_capr_unchanged,
    test_direction_match_and_scale_monotonic,
    test_anchor_sensitivity_and_permutation_equivariance,
    test_strict_load_missing_logit_scale_raises,
    test_extreme_logit_scale_finite_gradients,
    test_degenerate_slots_match_l1,
    test_recall_without_valid_slot_raises,
    test_load_model_validations,
    test_strict_load_shape_mismatch,
    test_init_pass_uses_orig_and_skips_natural_missing,
    test_epoch_stats_print_format,
    test_eval_missing_new_options,
    test_main_survival_cli_defaults,
]


def _main() -> int:
    failures = 0
    skipped = 0
    for test in TESTS:
        try:
            test()
        except unittest.SkipTest as skip:
            skipped += 1
            print(f"SKIP {test.__name__}: {skip}")
        except Exception as error:  # noqa: BLE001
            failures += 1
            print(f"FAIL {test.__name__}: {type(error).__name__}: {error}")
        else:
            print(f"PASS {test.__name__}")
    verdict = "ALL_PASS" if failures == 0 else f"FAILURES={failures}"
    print(f"RESULT={verdict} SKIPPED={skipped}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(_main())
