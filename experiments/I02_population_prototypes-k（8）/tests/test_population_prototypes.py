"""Population prototype bank 与 NPJC 接线的 CPU 契约测试。

独立运行：
    PYTHONDONTWRITEBYTECODE=1 python tests/test_population_prototypes.py

Torch、sklearn 与业务模型保持真实；仅在测试进程边界替代与本功能无关、
且当前解释器缺失的可选导入。
"""

import copy
import importlib.util
import sys
import types
import unittest
import warnings
from importlib.machinery import ModuleSpec
from pathlib import Path


NPJ_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = NPJ_ROOT / "model.py"


def _available(name):
    try:
        return importlib.util.find_spec(name) is not None
    except Exception:
        return False


def _make_module(name, is_package=False):
    module = types.ModuleType(name)
    module.__spec__ = ModuleSpec(name, None, is_package=is_package)
    if is_package:
        module.__path__ = []
    sys.modules[name] = module
    return module


def install_optional_import_stubs():
    if not _available("transformers"):
        transformers = _make_module("transformers")
        for symbol in ("BertTokenizer", "BertModel", "AdamW"):
            setattr(transformers, symbol, type(symbol, (), {}))
        transformers.get_linear_schedule_with_warmup = lambda *args, **kwargs: None

    if not _available("scattermoe.mlp"):
        scattermoe = _make_module("scattermoe", is_package=True)
        mlp = _make_module("scattermoe.mlp")
        mlp.GLUMLP = type("GLUMLP", (), {})
        scattermoe.mlp = mlp

    if str(NPJ_ROOT) not in sys.path:
        sys.path.insert(0, str(NPJ_ROOT))


install_optional_import_stubs()

import torch  # noqa: E402
import torch.nn as nn  # noqa: E402


def population_bank_class():
    assert MODULE_PATH.is_file(), (
        "缺少 model/population_prototypes.py：请实现 PopulationPrototypeBank"
    )
    from experiments.I02_population_prototypes.model import PopulationPrototypeBank

    return PopulationPrototypeBank


def test_population_prototype_module_exists():
    assert MODULE_PATH.is_file(), (
        "缺少 model/population_prototypes.py：请实现 PopulationPrototypeBank"
    )


def test_bank_registers_only_buffers_and_dictionary_view():
    bank = population_bank_class()(k=2, dim=3, seed=7)

    assert bank.k == 2
    assert bank.dim == 3
    assert bank.seed == 7
    assert bank.modalities == ("rna", "text")
    assert bank.inference_only is True
    assert list(bank.parameters()) == [], "PopulationPrototypeBank 不得引入可学习参数"
    assert set(bank.prototypes) == {"wsi", "rna", "text"}
    registered = dict(bank.named_buffers())
    assert {"wsi", "rna", "text", "counts", "ready"}.issubset(registered), (
        "brief 要求 wsi/rna/text/counts/ready 均以原名注册为 buffer"
    )
    assert bank.prototypes["wsi"] is bank.wsi
    assert bank.prototypes["rna"] is bank.rna
    assert bank.prototypes["text"] is bank.text
    assert bank.wsi.shape == (2, 3)
    assert bank.rna.shape == (2, 3)
    assert bank.text.shape == (2, 3)
    assert bank.counts.shape == (2,)
    assert bank.counts.dtype == torch.long
    assert bank.ready.shape == torch.Size([])
    assert bank.ready.dtype == torch.bool
    assert not bank.ready.item()
    assert {
        "wsi",
        "rna",
        "text",
        "counts",
        "ready",
    }.issubset(bank.state_dict())


def paired_projected_rows():
    # 两团 WSI 足够远；RNA/Text 数值不参与聚类，只按 WSI 共享标签聚合。
    wsi = torch.tensor(
        [[10.0, 0.0], [12.0, 0.0], [0.0, 10.0], [0.0, 14.0]]
    )
    rna = torch.tensor(
        [[100.0, 1.0], [300.0, 3.0], [20.0, 200.0], [40.0, 400.0]]
    )
    text = torch.tensor(
        [[5.0, 50.0], [7.0, 70.0], [9.0, 90.0], [11.0, 110.0]]
    )
    return wsi, rna, text


def test_update_uses_raw_wsi_labels_for_all_paired_means():
    Bank = population_bank_class()
    bank = Bank(k=2, dim=2, seed=123)
    wsi, rna, text = paired_projected_rows()

    labels = bank.update_memory_bank(wsi, rna, text)

    assert labels.shape == (4,)
    assert labels.dtype == torch.long
    for cluster in range(2):
        selected = labels == cluster
        assert selected.any(), f"cluster {cluster} 不得为空"
        assert torch.equal(bank.counts[cluster], selected.sum())
        assert torch.allclose(
            bank.wsi[cluster], wsi[selected].mean(dim=0)
        )
        assert torch.allclose(
            bank.rna[cluster], rna[selected].mean(dim=0)
        )
        assert torch.allclose(
            bank.text[cluster], text[selected].mean(dim=0)
        )
    assert bank.ready.item()


def test_eval_fills_each_missing_target_by_wsi_cosine_top1_only():
    Bank = population_bank_class()
    bank = Bank(k=2, dim=2, seed=123)
    wsi, rna, text = paired_projected_rows()
    bank.update_memory_bank(wsi, rna, text)
    bank.eval()

    tokens = {
        "img": torch.stack(
            [bank.wsi[0] * 3.0, bank.wsi[1] * 2.0]
        ),
        "rna": torch.tensor([[901.0, 902.0], [903.0, 904.0]]),
        "text": torch.tensor([[801.0, 802.0], [803.0, 804.0]]),
    }
    valids = {
        "img": torch.tensor([1, 1]),
        "rna": torch.tensor([0, 1]),
        "text": torch.tensor([1, 0]),
    }

    filled, pairs = bank(tokens, valids, bin_labels=torch.tensor([-99, 999]))

    assert pairs == []
    assert torch.equal(filled["rna"][0], bank.rna[0])
    assert torch.equal(filled["rna"][1], tokens["rna"][1]), "可用 RNA 不得改写"
    assert torch.equal(filled["text"][0], tokens["text"][0]), "可用 Text 不得改写"
    assert torch.equal(filled["text"][1], bank.text[1])
    assert torch.equal(tokens["rna"], torch.tensor([[901.0, 902.0], [903.0, 904.0]])), (
        "forward 不得原地改写输入 tokens"
    )


def test_training_is_a_strict_no_read_no_fill_path():
    Bank = population_bank_class()
    bank = Bank(k=2, dim=2)
    tokens = {
        "img": torch.tensor([[1.0, 0.0], [0.0, 1.0]]),
        "rna": torch.tensor([[1.0, 2.0], [3.0, 4.0]]),
        "text": torch.tensor([[5.0, 6.0], [7.0, 8.0]]),
    }
    valids = {
        "img": torch.tensor([0, 0]),
        "rna": torch.tensor([0, 1]),
        "text": torch.tensor([1, 0]),
    }

    bank.wsi.fill_(float("nan"))
    before = {name: value.clone() for name, value in tokens.items()}
    filled, pairs = bank(tokens, valids, training=True)

    assert pairs == []
    for name in before:
        assert torch.equal(filled[name], before[name]), f"训练期不得改写 {name}"


def test_unready_bank_errors_only_when_eval_fill_is_needed():
    Bank = population_bank_class()
    bank = Bank(k=2, dim=2)
    bank.eval()
    tokens = {
        "img": torch.tensor([[1.0, 0.0]]),
        "rna": torch.tensor([[2.0, 3.0]]),
        "text": torch.tensor([[4.0, 5.0]]),
    }
    all_valid = {"img": [1], "rna": [1], "text": [1]}
    unchanged, _ = bank(tokens, all_valid, training=False)
    assert all(torch.equal(unchanged[key], value) for key, value in tokens.items())

    missing = {"img": [1], "rna": [0], "text": [1]}
    with unittest.TestCase().assertRaisesRegex(RuntimeError, "not ready|未就绪"):
        bank(tokens, missing, training=False)


def test_update_is_hard_overwrite_and_failed_update_is_atomic():
    Bank = population_bank_class()
    bank = Bank(k=2, dim=2, seed=123)
    wsi, rna, text = paired_projected_rows()
    bank.update_memory_bank(wsi, rna, text)

    shifted = (wsi + 100.0, rna + 1000.0, text - 500.0)
    labels = bank.update_memory_bank(*shifted)
    for cluster in range(2):
        selected = labels == cluster
        assert torch.allclose(
            bank.rna[cluster], shifted[1][selected].mean(dim=0)
        ), "更新必须硬覆盖，不得 EMA 混入旧值"

    snapshot = copy.deepcopy(bank.state_dict())
    bad_text = shifted[2].clone()
    bad_text[0, 0] = float("nan")
    with unittest.TestCase().assertRaisesRegex(ValueError, "finite|有限"):
        bank.update_memory_bank(shifted[0], shifted[1], bad_text)
    for name, value in snapshot.items():
        assert torch.equal(bank.state_dict()[name], value), f"失败更新污染了 {name}"


def test_state_dict_roundtrip_preserves_ready_bank():
    Bank = population_bank_class()
    source = Bank(k=2, dim=2, seed=123)
    source.update_memory_bank(*paired_projected_rows())
    restored = Bank(k=2, dim=2, seed=999)
    restored.load_state_dict(source.state_dict())

    assert restored.ready.item()
    for key in ("wsi", "rna", "text"):
        assert torch.equal(restored.prototypes[key], source.prototypes[key])
    assert torch.equal(restored.counts, source.counts)


def test_constructor_and_update_reject_invalid_inputs():
    Bank = population_bank_class()
    for kwargs in ({"k": 0, "dim": 2}, {"k": 2, "dim": 0}):
        with unittest.TestCase().assertRaisesRegex(ValueError, "positive|正"):
            Bank(**kwargs)

    bank = Bank(k=2, dim=2)
    valid = torch.ones(3, 2)
    bad_cases = [
        ((torch.ones(3, 3), valid, valid), "shape"),
        ((valid, torch.ones(2, 2), valid), "same|相同"),
        ((valid[:1], valid[:1], valid[:1]), "at least|至少|eligible"),
    ]
    for args, message in bad_cases:
        with unittest.TestCase().assertRaisesRegex(ValueError, message):
            bank.update_memory_bank(*args)

    nonfinite = valid.clone()
    nonfinite[0, 0] = float("inf")
    with unittest.TestCase().assertRaisesRegex(ValueError, "finite|有限"):
        bank.update_memory_bank(valid, nonfinite, valid)

    identical = torch.ones(3, 2)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        with unittest.TestCase().assertRaisesRegex(ValueError, "empty|空"):
            bank.update_memory_bank(identical, valid, valid)


def _modalities():
    return {
        name: types.SimpleNamespace(modality_name=name, feature_dim=2)
        for name in ("img", "rna", "text")
    }


def _build_npjc(compensator):
    from trimodalsurv.models.npjc import NPJC

    torch.manual_seed(11)
    model = NPJC(
        device="cpu",
        modalities=_modalities(),
        hidden_size=2,
        dropout_rate=0.0,
        pred_dim=2,
        mlp_ratio=2,
        n_backbone=1,
        n_head=2,
        cancer_types=["BLCA"],
        compensator=compensator,
    )
    # 测试只观察语义和 padding mask；关闭实验性 nested-tensor 快路以免输出无关警告。
    model.backbone.enable_nested_tensor = False
    model.backbone.use_nested_tensor = False
    for projector in model.m_projector.values():
        linear = projector[0]
        with torch.no_grad():
            linear.weight.copy_(torch.eye(2))
            linear.bias.zero_()
    return model


def _patient_inputs(rna_valid=(1, 0), text_valid=(1, 1), img_valid=None):
    data = {
        "img": torch.tensor(
            [[[2.0, 0.0], [4.0, 0.0]], [[0.0, 6.0], [0.0, 8.0]]]
        ),
        "rna": torch.tensor([[[1.0, 3.0]], [[9.0, 9.0]]]),
        "text": torch.tensor([[[5.0, 7.0]], [[11.0, 13.0]]]),
        "rna_valid": torch.tensor(rna_valid),
        "text_valid": torch.tensor(text_valid),
    }
    if img_valid is not None:
        data["img_valid"] = torch.tensor(img_valid)
    return data


class PaddingMaskCapture:
    def __init__(self, module):
        self.mask = None
        self.handle = module.register_forward_pre_hook(self._capture, with_kwargs=True)

    def _capture(self, module, args, kwargs):
        del module, args
        self.mask = kwargs["src_key_padding_mask"].detach().clone()

    def close(self):
        self.handle.remove()


def test_npjc_encode_exposes_exact_mean_projector_tokens_and_real_valids():
    model = _build_npjc(compensator=None)
    data = _patient_inputs(img_valid=(1, 0))
    model.eval()

    with torch.no_grad():
        tokens, valids = model.encode_patient_modalities(data)

    assert torch.equal(tokens["img"], torch.tensor([[3.0, 0.0], [0.0, 7.0]]))
    assert torch.equal(tokens["rna"], torch.tensor([[1.0, 3.0], [9.0, 9.0]]))
    assert torch.equal(tokens["text"], torch.tensor([[5.0, 7.0], [11.0, 13.0]]))
    assert torch.equal(valids["img"], torch.tensor([True, True]))
    assert torch.equal(valids["rna"], torch.tensor([True, False]))
    assert torch.equal(valids["text"], torch.tensor([True, True]))


def test_npjc_population_encode_exposes_img_valid_for_complete_patient_filter():
    Bank = population_bank_class()
    model = _build_npjc(Bank(k=2, dim=2))
    data = _patient_inputs(img_valid=(1, 0))

    with torch.no_grad():
        _, valids = model.encode_patient_modalities(data)

    assert torch.equal(valids["img"], torch.tensor([True, False])), (
        "population collector 必须能从 helper 排除 WSI 无效患者"
    )


def test_npjc_population_eval_fills_and_promotes_only_missing_targets():
    Bank = population_bank_class()
    bank = Bank(k=2, dim=2, seed=123)
    bank.update_memory_bank(*paired_projected_rows())
    model = _build_npjc(bank)
    model.eval()
    capture = PaddingMaskCapture(model.backbone)
    try:
        with torch.no_grad():
            output = model(_patient_inputs(), cancer_type=["BLCA", "BLCA"])
    finally:
        capture.close()

    assert len(output) == 3
    assert capture.mask is not None
    assert torch.equal(capture.mask, torch.zeros(2, 3, dtype=torch.bool)), (
        "评估期已填充 RNA 必须晋升为有效 token"
    )


def test_npjc_population_training_skips_bank_and_valid_promotion():
    Bank = population_bank_class()
    bank = Bank(k=2, dim=2)
    bank.wsi.fill_(float("nan"))
    model = _build_npjc(bank)
    model.train()
    capture = PaddingMaskCapture(model.backbone)
    try:
        output = model(_patient_inputs(), cancer_type=["BLCA", "BLCA"])
    finally:
        capture.close()

    assert len(output) == 3
    assert torch.equal(
        capture.mask,
        torch.tensor([[False, False, False], [False, True, False]]),
    ), "训练期 population bank 不得填充或晋升 RNA validity"


def test_npjc_population_eval_rejects_invalid_wsi_even_when_targets_are_valid():
    Bank = population_bank_class()
    bank = Bank(k=2, dim=2, seed=123)
    bank.update_memory_bank(*paired_projected_rows())
    model = _build_npjc(bank)
    model.eval()
    data = _patient_inputs(
        rna_valid=(1, 1), text_valid=(1, 1), img_valid=(1, 0)
    )

    with unittest.TestCase().assertRaisesRegex(ValueError, "img|WSI|wsi"):
        model(data, cancer_type=["BLCA", "BLCA"])


def test_npjc_population_eval_uses_default_target_valids_to_reject_invalid_wsi():
    Bank = population_bank_class()
    bank = Bank(k=2, dim=2, seed=123)
    bank.update_memory_bank(*paired_projected_rows())
    model = _build_npjc(bank)
    model.eval()
    data = _patient_inputs(img_valid=(1, 0))
    data.pop("rna_valid")
    data.pop("text_valid")

    with unittest.TestCase().assertRaisesRegex(ValueError, "img|WSI|wsi"):
        model(data, cancer_type=["BLCA", "BLCA"])


def test_npjc_old_compensator_training_behavior_is_unchanged():
    from trimodalsurv.models.compensator import MissingBank

    model = _build_npjc(MissingBank(modalities=("rna", "text"), dim=2))
    model.train()
    capture = PaddingMaskCapture(model.backbone)
    try:
        output = model(_patient_inputs(), cancer_type=["BLCA", "BLCA"])
    finally:
        capture.close()

    assert len(output) == 3
    assert torch.equal(capture.mask, torch.zeros(2, 3, dtype=torch.bool)), (
        "既有 compensator 在训练期仍须工作并晋升缺失 target validity"
    )


TESTS = [
    test_population_prototype_module_exists,
    test_bank_registers_only_buffers_and_dictionary_view,
    test_update_uses_raw_wsi_labels_for_all_paired_means,
    test_eval_fills_each_missing_target_by_wsi_cosine_top1_only,
    test_training_is_a_strict_no_read_no_fill_path,
    test_unready_bank_errors_only_when_eval_fill_is_needed,
    test_update_is_hard_overwrite_and_failed_update_is_atomic,
    test_state_dict_roundtrip_preserves_ready_bank,
    test_constructor_and_update_reject_invalid_inputs,
    test_npjc_encode_exposes_exact_mean_projector_tokens_and_real_valids,
    test_npjc_population_encode_exposes_img_valid_for_complete_patient_filter,
    test_npjc_population_eval_fills_and_promotes_only_missing_targets,
    test_npjc_population_training_skips_bank_and_valid_promotion,
    test_npjc_population_eval_rejects_invalid_wsi_even_when_targets_are_valid,
    test_npjc_population_eval_uses_default_target_valids_to_reject_invalid_wsi,
    test_npjc_old_compensator_training_behavior_is_unchanged,
]


def _main():
    failures = 0
    for test in TESTS:
        try:
            test()
        except Exception as error:  # noqa: BLE001
            failures += 1
            print(f"FAIL {test.__name__}: {type(error).__name__}: {error}")
        else:
            print(f"PASS {test.__name__}")
    print("RESULT=ALL_PASS" if failures == 0 else f"RESULT=FAILURES={failures}")
    return int(failures != 0)


if __name__ == "__main__":
    raise SystemExit(_main())
