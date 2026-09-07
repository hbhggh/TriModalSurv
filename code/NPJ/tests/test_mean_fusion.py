"""NPJ-D 消融单测：MeanFusion 语义 + gate 路径逐位不变（CPU、无数据、<10 s）。

用法（任选其一，须先 `export PYTHONDONTWRITEBYTECODE=1`，cwd = NPJ 仓根）：
    python3 tests/test_mean_fusion.py            # 独立运行，逐条打印断言结果
    python3 -m pytest tests/test_mean_fusion.py  # pytest 亦可

gate 对拍用的「补丁前快照」路径由环境变量 ``NPJ_FUSION_BASELINE`` 指定
（默认取本单 scratchpad 快照）；快照不存在时该用例 SKIP，其余用例照跑。

第三方依赖（transformers / sksurv / accelerate / torchmetrics / tqdm /
scattermoe / easydict）与本单被测逻辑无关；本机缺哪个就在**测试进程边界**装最小
替身（真实可用时一律用真实包），不改动生产导入结构。
"""

import os
import sys
import types
import unittest
from importlib.machinery import ModuleSpec
from pathlib import Path


NPJ_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASELINE = Path(
    "/private/tmp/claude-501/-Users-wuhao-Desktop-TriModalSurv/"
    "39ab8862-e8e3-459b-ad68-33110d732efa/scratchpad/fusion_model_before.py"
)


# --------------------------------------------------------------------------
# 测试进程边界的最小替身（只在本机缺该包时安装）
# --------------------------------------------------------------------------
def _available(name: str) -> bool:
    import importlib.util

    try:
        return importlib.util.find_spec(name) is not None
    except Exception:  # 例如 scattermoe -> triton 缺失
        return False


def _make_module(name: str, is_package: bool = False) -> types.ModuleType:
    module = types.ModuleType(name)
    module.__spec__ = ModuleSpec(name, None, is_package=is_package)
    if is_package:
        module.__path__ = []
    sys.modules[name] = module
    return module


def install_stubs() -> None:
    if not _available("transformers"):
        transformers = _make_module("transformers")
        for symbol in ("BertTokenizer", "BertModel", "AdamW"):
            setattr(transformers, symbol, type(symbol, (), {}))
        transformers.get_linear_schedule_with_warmup = lambda *a, **k: None

    if not _available("sksurv"):
        sksurv = _make_module("sksurv", is_package=True)
        metrics = _make_module("sksurv.metrics")
        metrics.concordance_index_censored = lambda *a, **k: None
        sksurv.metrics = metrics

    if not _available("accelerate"):
        accelerate = _make_module("accelerate")
        accelerate.Accelerator = type("Accelerator", (), {})

    if not _available("torchmetrics"):
        torchmetrics = _make_module("torchmetrics")
        for symbol in ("Precision", "Recall", "F1Score", "Accuracy"):
            setattr(torchmetrics, symbol, type(symbol, (), {}))

    if not _available("tqdm"):
        tqdm_module = _make_module("tqdm")
        tqdm_module.tqdm = lambda iterable=None, *a, **k: iterable

    if not _available("scattermoe.mlp"):
        scattermoe = _make_module("scattermoe", is_package=True)
        mlp = _make_module("scattermoe.mlp")
        mlp.GLUMLP = type("GLUMLP", (), {})
        scattermoe.mlp = mlp

    if not _available("easydict"):
        easydict = _make_module("easydict")

        class EasyDict(dict):
            def __init__(self, mapping=None, **kwargs):
                merged = dict(mapping or {}, **kwargs)
                super().__init__(merged)
                for key, value in merged.items():
                    setattr(
                        self, key, EasyDict(value) if isinstance(value, dict) else value
                    )

        easydict.EasyDict = EasyDict

    if str(NPJ_ROOT) not in sys.path:
        sys.path.insert(0, str(NPJ_ROOT))


install_stubs()

import torch  # noqa: E402


# --------------------------------------------------------------------------
# 夹具
# --------------------------------------------------------------------------
FEATURE_DIMS = {"img": 1536, "text": 768, "rna": 256}
TOKEN_COUNTS = {"img": 128, "text": 200, "rna": 2048}
HIDDEN_SIZE = 256
PRED_DIM = 4
BATCH = 2
CANCER = "BLCA"


def fake_modalities():
    return {
        name: types.SimpleNamespace(modality_name=name, feature_dim=dim)
        for name, dim in FEATURE_DIMS.items()
    }


def build_model(module, fusion_type=None):
    """构造 MainModalityMoE；fusion_type=None 表示不传该关键字（补丁前签名）。"""
    kwargs = dict(
        hidden_size=HIDDEN_SIZE,
        pred_dim=PRED_DIM,
        cancer_types=[CANCER],
    )
    if fusion_type is not None:
        kwargs["fusion_type"] = fusion_type
    torch.manual_seed(0)
    model = module.MainModalityMoE("cpu", fake_modalities(), **kwargs)
    model.eval()
    return model


def fake_inputs():
    generator = torch.Generator().manual_seed(1234)
    data = {
        name: torch.randn(
            BATCH, TOKEN_COUNTS[name], FEATURE_DIMS[name], generator=generator
        )
        for name in FEATURE_DIMS
    }
    data["text_valid"] = torch.ones(BATCH)
    data["rna_valid"] = torch.ones(BATCH)
    return data


def manual_forward(model, tokens):
    """给定各模态 token（[B, D] 列表），复算 backbone + head 的 hazard。"""
    fused = torch.stack(tokens, dim=1).mean(dim=1)
    pooled = model.backbone(fused.unsqueeze(1)).mean(dim=1)
    return model.surv_heads[CANCER](pooled)


def project(model, data):
    return [
        model.m_projector[name](data[name].mean(dim=1))
        for name in model.m_projector.keys()
    ]


def load_baseline_module():
    """把补丁前的 fusion_model.py 快照作为独立模块导入（sys.modules 先注册，见坑 E4）。"""
    import importlib.util

    baseline = Path(os.environ.get("NPJ_FUSION_BASELINE", str(DEFAULT_BASELINE)))
    if not baseline.is_file():
        raise unittest.SkipTest(f"基线快照不存在: {baseline}（设 NPJ_FUSION_BASELINE 指定）")
    name = "fusion_model_baseline_npjd"
    spec = importlib.util.spec_from_file_location(name, baseline)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# --------------------------------------------------------------------------
# 验收 ①：gate 路径逐位不变
# --------------------------------------------------------------------------
def test_gate_path_bitwise_identical():
    baseline = load_baseline_module()
    from model import fusion_model as patched

    before = build_model(baseline)  # 补丁前签名，无 fusion_type
    after = build_model(patched, fusion_type="gate")

    keys_before = set(before.state_dict())
    keys_after = set(after.state_dict())
    assert keys_before == keys_after, (
        f"state_dict 键集合不同: 仅前={sorted(keys_before - keys_after)} "
        f"仅后={sorted(keys_after - keys_before)}"
    )
    assert any(key.startswith("fusion.gate.") for key in keys_after), "gate 模型应含 fusion.gate.* 参数"
    state_before = before.state_dict()
    state_after = after.state_dict()
    for key in sorted(keys_before):
        assert torch.equal(state_before[key], state_after[key]), f"参数逐位不同: {key}"

    data = fake_inputs()
    with torch.no_grad():
        hazard_before, surv_before = before(data, cancer_type=[CANCER] * BATCH)
        hazard_after, surv_after = after(data, cancer_type=[CANCER] * BATCH)
    assert torch.equal(hazard_before, hazard_after), "gate 前向 hazard 不逐位相同"
    assert torch.equal(surv_before, surv_after), "gate 前向 surv 不逐位相同"


# --------------------------------------------------------------------------
# 验收 ②(a)：mean 模型 state_dict = gate 模型去掉 fusion.gate.*
# --------------------------------------------------------------------------
def test_mean_state_dict_drops_gate_params():
    from model import fusion_model as patched

    gate_keys = set(build_model(patched, fusion_type="gate").state_dict())
    mean_keys = set(build_model(patched, fusion_type="mean").state_dict())
    dropped = {key for key in gate_keys if key.startswith("fusion.gate.")}
    assert dropped, "gate 模型必须含 fusion.gate.* 才构成有效对照"
    assert mean_keys == gate_keys - dropped, (
        f"mean 键集合不符: 多={sorted(mean_keys - (gate_keys - dropped))} "
        f"少={sorted((gate_keys - dropped) - mean_keys)}"
    )
    mean_model = build_model(patched, fusion_type="mean")
    assert isinstance(mean_model.fusion, patched.MeanFusion)
    assert sum(p.numel() for p in mean_model.fusion.parameters()) == 0, "MeanFusion 不得有可学习参数"


# --------------------------------------------------------------------------
# 验收 ②(b)：mean 前向 == 手算等权平均
# --------------------------------------------------------------------------
def test_mean_forward_matches_manual_average():
    from model import fusion_model as patched

    model = build_model(patched, fusion_type="mean")
    data = fake_inputs()
    with torch.no_grad():
        hazard, surv = model(data, cancer_type=[CANCER] * BATCH)
        hazard_manual, surv_manual = manual_forward(model, project(model, data))
    assert torch.allclose(hazard, hazard_manual, atol=1e-6), (
        f"hazard 与手算等权平均不符, 最大差={(hazard - hazard_manual).abs().max().item():.3e}"
    )
    assert torch.allclose(surv, surv_manual, atol=1e-6)


# --------------------------------------------------------------------------
# 验收 ②(c)：缺失（零特征）模态 = ReLU(bias) 常量 token，且仍参与平均
# --------------------------------------------------------------------------
def test_zero_rna_constant_token_still_averaged():
    from model import fusion_model as patched

    model = build_model(patched, fusion_type="mean")
    data = fake_inputs()
    data["rna"] = torch.zeros_like(data["rna"])
    with torch.no_grad():
        tokens = project(model, data)
        rna_token = tokens[list(model.m_projector.keys()).index("rna")]
        constant = torch.relu(model.m_projector["rna"][0].bias).unsqueeze(0).expand(BATCH, -1)
        assert torch.allclose(rna_token, constant, atol=1e-6), "零特征 rna token 应为 ReLU(bias) 常量"
        assert torch.allclose(rna_token[0], rna_token[1], atol=1e-6), "常量 token 应逐样本相同"

        hazard_all, _ = model(data, cancer_type=[CANCER] * BATCH)
        hazard_excluded, _ = manual_forward(
            model,
            [tokens[index] for index, name in enumerate(model.m_projector.keys()) if name != "rna"],
        )
    gap = (hazard_all - hazard_excluded).abs().max().item()
    assert not torch.allclose(hazard_all, hazard_excluded, atol=1e-6), (
        "常量 token 必须参与平均（NPJ-D 定义），但与剔除 rna 的结果一致"
    )
    assert gap > 1e-6, f"差异过小: {gap:.3e}"


# --------------------------------------------------------------------------
# 验收 ②(d)：load_model 对 fusion_type='mean' + 非 MainModalityMoE 拒绝
# --------------------------------------------------------------------------
def test_load_model_rejects_mean_for_npjc():
    import main_survival

    modalities = fake_modalities()
    common = dict(
        device="cpu",
        modalities=modalities,
        hidden_size=HIDDEN_SIZE,
        pred_dim=PRED_DIM,
        cancer_types=[CANCER],
    )
    try:
        main_survival.load_model(network_type="NPJC", fusion_type="mean", **common)
    except ValueError as error:
        assert "fusion_type" in str(error), f"错误信息未指向 fusion_type: {error}"
    else:
        raise AssertionError("NPJC + fusion_type='mean' 应当抛 ValueError")

    # 不触发侧（坑 V31）：NPJC 默认 gate 正常构建；MainModalityMoE + mean 正常构建
    from model import fusion_model as patched

    npjc = main_survival.load_model(network_type="NPJC", **common)
    assert isinstance(npjc, patched.NPJC)
    moe = main_survival.load_model(
        network_type="MainModalityMoE", fusion_type="mean", **common
    )
    assert isinstance(moe.fusion, patched.MeanFusion)


TESTS = [
    test_gate_path_bitwise_identical,
    test_mean_state_dict_drops_gate_params,
    test_mean_forward_matches_manual_average,
    test_zero_rna_constant_token_still_averaged,
    test_load_model_rejects_mean_for_npjc,
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
