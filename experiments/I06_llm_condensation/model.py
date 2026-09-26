"""I06 核心算子：病理报告 → 预注册字段（结构化臂）/ 事实摘要（摘要臂）→ 送进冻结 NeuML 的文本。

本模块只定义"浓缩成什么样"，不调用任何 LLM：
- 字段清单（五癌通用核心 + 各癌种特异字段）与固定顺序；
- 结构化臂的 JSON schema（给 LLM 的结构化输出用，也用于校验返回值）；
- 序列化规则：只写原文出现的字段，填 ``not mentioned`` 的字段一律省略（用户裁决 2026-09-25），
  其余逐字段写成 ``Label: value.`` 句子；
- 摘要臂的返回 schema。

去重规则（研究计划书 4.2）：癌种特异字段与通用字段语义重合时并入通用字段，只在该字段的取值说明里
写明该癌种的类别，避免同一信息在序列化文本里出现两次。字段清单与顺序须经用户审定后锁定。
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

PROMPT_DIR = Path(__file__).resolve().parent / 'prompts'
PROMPT_FILES = {'system': 'system.txt', 'struct_user': 'struct_user.txt', 'summary_user': 'summary_user.txt',
                'length_retry': 'length_retry.txt'}
NOT_MENTIONED = 'not mentioned'
CANCERS = ('BLCA', 'BRCA', 'LGG', 'LUAD', 'UCEC')
ARMS = ('struct', 'summary')

CANCER_NAMES = {
    'BLCA': 'bladder urothelial carcinoma',
    'BRCA': 'breast invasive carcinoma',
    'LGG': 'lower-grade glioma',
    'LUAD': 'lung adenocarcinoma',
    'UCEC': 'uterine corpus endometrial carcinoma',
}


@dataclass(frozen=True)
class Field:
    key: str
    label: str
    description: str
    kind: str = 'text'  # 'text'：单个字符串；'pairs'：[{name, result}] 列表


# 通用核心（五癌共用）。顺序即序列化顺序：先诊断（类型、分级），再范围与分期要素，最后 IHC / 分子与标本。
GENERAL_FIELDS = (
    Field('histologic_type', 'Histologic type', 'Histologic type or subtype of the tumor as written.'),
    Field('histologic_grade', 'Histologic grade', 'Histologic grade as written (for example "grade 2 of 3").'),
    Field('tumor_size', 'Tumor size', 'Tumor size with units as written.'),
    Field('extent_invasion', 'Extent of invasion', 'Tumor extent or depth of invasion as written.'),
    Field('lymph_nodes', 'Lymph nodes', 'Lymph node status: number positive / number examined as written '
          '(for example "0/12").'),
    Field('margins', 'Margins', 'Surgical margin status as written, including negative margins.'),
    Field('lymphovascular_invasion', 'Lymphovascular invasion', 'Lymphovascular invasion: present, absent, '
          'or as written.'),
    Field('perineural_invasion', 'Perineural invasion', 'Perineural invasion: present, absent, or as written.'),
    Field('ptnm', 'Pathologic stage', 'pT / pN / pM only if explicitly written in the report; never infer.'),
)

# 癌种特异字段（已按去重规则并入通用字段的不再单列，见 MERGED_INTO_GENERAL）。
SPECIFIC_FIELDS = {
    'LGG': (
        Field('necrosis', 'Necrosis', 'Presence or absence of necrosis as written.'),
        Field('microvascular_proliferation', 'Microvascular proliferation',
              'Presence or absence of microvascular (endothelial) proliferation as written.'),
        Field('mitotic_activity', 'Mitotic activity', 'Mitotic activity or mitotic count as written.'),
        Field('ki67', 'Ki-67', 'Ki-67 (MIB-1) labeling index as written.'),
    ),
    'BRCA': (
        Field('er_status', 'ER', 'Estrogen receptor status as written.'),
        Field('pr_status', 'PR', 'Progesterone receptor status as written.'),
        Field('her2_status', 'HER2', 'HER2 status (IHC score and/or ISH) as written.'),
        Field('nottingham_components', 'Nottingham components',
              'Tubule formation, nuclear pleomorphism and mitotic count scores as written.'),
        Field('dcis_component', 'DCIS component', 'Ductal carcinoma in situ component as written.'),
    ),
    'BLCA': (
        Field('variant_histology', 'Variant histology', 'Variant or divergent histology as written.'),
        Field('carcinoma_in_situ', 'Carcinoma in situ', 'Presence or absence of carcinoma in situ as written.'),
        Field('papillary_architecture', 'Papillary architecture', 'Papillary or non-papillary growth as written.'),
    ),
    'LUAD': (
        Field('predominant_pattern', 'Predominant pattern',
              'Predominant growth pattern (lepidic, acinar, papillary, micropapillary, solid) as written.'),
        Field('visceral_pleural_invasion', 'Visceral pleural invasion',
              'Visceral pleural invasion as written.'),
    ),
    'UCEC': (
        Field('cervical_stromal_invasion', 'Cervical stromal invasion', 'Cervical stromal invasion as written.'),
        Field('adnexal_serosal_involvement', 'Adnexal or serosal involvement',
              'Involvement of adnexa or uterine serosa as written.'),
    ),
}

# 放在癌种特异字段之后：IHC / 分子（未被专门字段覆盖的）与标本 / 术式。
TRAILING_FIELDS = (
    Field('ihc_molecular', 'IHC and molecular', 'Other immunohistochemistry or molecular results written in the '
          'report that are not covered by a dedicated field, as marker/result pairs.', kind='pairs'),
    Field('specimen_procedure', 'Specimen', 'Specimen type and surgical procedure as written.'),
)

# 并入通用字段的癌种特异项：在该癌种的通用字段说明里补一句类别提示。
MERGED_INTO_GENERAL = {
    'LGG': {'histologic_type': 'For glioma: astrocytoma, oligodendroglioma or oligoastrocytoma, as written.',
            'histologic_grade': 'For glioma: WHO grade as written.'},
    'BRCA': {'histologic_type': 'For breast: ductal or lobular type, as written.',
             'histologic_grade': 'For breast: Nottingham (combined) grade as written.'},
    'BLCA': {'extent_invasion': 'For bladder: depth of invasion (lamina propria, muscularis propria, '
                                'perivesical fat), as written.'},
    'LUAD': {'margins': 'For lung: include the bronchial margin, as written.'},
    'UCEC': {'histologic_type': 'For endometrium: endometrioid, serous, clear cell or other type, as written.',
             'histologic_grade': 'For endometrium: FIGO grade as written.',
             'extent_invasion': 'For endometrium: myometrial invasion (less than half / half or more), '
                                'as written.',
             'lymphovascular_invasion': 'For endometrium: lymphovascular space invasion (LVSI), as written.'},
}


def fields_for(cancer: str) -> tuple:
    """某癌种的完整字段表（固定顺序），并把合并提示写进对应通用字段的说明。"""
    if cancer not in CANCERS:
        raise ValueError(f'未知癌种 {cancer!r}')
    hints = MERGED_INTO_GENERAL.get(cancer, {})
    general = tuple(Field(f.key, f.label, f'{f.description} {hints[f.key]}' if f.key in hints else f.description,
                          f.kind) for f in GENERAL_FIELDS)
    fields = general + SPECIFIC_FIELDS[cancer] + TRAILING_FIELDS
    keys = [f.key for f in fields]
    if len(keys) != len(set(keys)):
        raise AssertionError(f'{cancer}: 字段键重复')
    return fields


def struct_schema(cancer: str) -> dict:
    """结构化臂的 JSON schema：所有字段必填、禁止额外字段（结构化输出要求）。"""
    properties = {}
    for field in fields_for(cancer):
        if field.kind == 'pairs':
            properties[field.key] = {
                'type': 'array', 'description': field.description,
                'items': {'type': 'object', 'additionalProperties': False, 'required': ['name', 'result'],
                          'properties': {'name': {'type': 'string'}, 'result': {'type': 'string'}}}}
        else:
            properties[field.key] = {'type': 'string',
                                     'description': f'{field.description} Write "{NOT_MENTIONED}" if absent.'}
    return {'type': 'object', 'additionalProperties': False, 'required': list(properties),
            'properties': properties}


SUMMARY_SCHEMA = {'type': 'object', 'additionalProperties': False, 'required': ['summary'],
                  'properties': {'summary': {'type': 'string'}}}


def validate_struct(cancer: str, payload) -> dict:
    """按 schema 严格校验结构化臂返回值（缺字段、多字段、类型不符都拒绝）。"""
    fields = fields_for(cancer)
    if not isinstance(payload, dict):
        raise ValueError('结构化输出必须是 JSON 对象')
    expected = {f.key for f in fields}
    if set(payload) != expected:
        raise ValueError(f'字段集合不符：缺 {sorted(expected - set(payload))}，多 {sorted(set(payload) - expected)}')
    for field in fields:
        value = payload[field.key]
        if field.kind == 'pairs':
            if not isinstance(value, list) or any(
                    not isinstance(item, dict) or set(item) != {'name', 'result'}
                    or not all(isinstance(item[k], str) for k in ('name', 'result')) for item in value):
                raise ValueError(f'{field.key} 必须是 {{name, result}} 字符串对的列表')
        elif not isinstance(value, str):
            raise ValueError(f'{field.key} 必须是字符串')
    return payload


def validate_summary(payload) -> dict:
    if not isinstance(payload, dict) or set(payload) != {'summary'} or not isinstance(payload['summary'], str):
        raise ValueError('摘要输出必须是只含字符串 summary 的 JSON 对象')
    return payload


_SPACE = re.compile(r'\s+')


def _clean(value: str) -> str:
    return _SPACE.sub(' ', value).strip()


def is_not_mentioned(value: str) -> bool:
    return _clean(value).rstrip('.').lower() == NOT_MENTIONED


def _sentence(label: str, value: str) -> str:
    value = _clean(value).rstrip('.').rstrip()
    return f'{label}: {value}.'


# [创新 I06-01] 结构化臂的序列化：固定字段顺序，只写原文出现的字段（省略 not mentioned 与空列表），
# 每个字段一句 "Label: value."。这就是送进冻结 NeuML 的文本；JSON 原样保留用于算字段召回。
def serialize_struct(cancer: str, payload) -> str:
    validate_struct(cancer, payload)
    sentences = []
    for field in fields_for(cancer):
        value = payload[field.key]
        if field.kind == 'pairs':
            items = [(_clean(item['name']), _clean(item['result'])) for item in value]
            items = [(name, result) for name, result in items
                     if name and result and not is_not_mentioned(result)]
            if items:
                sentences.append(_sentence(field.label, '; '.join(f'{name} {result}' for name, result in items)))
        elif _clean(value) and not is_not_mentioned(value):
            sentences.append(_sentence(field.label, value))
    return ' '.join(sentences)


def serialize_summary(payload) -> str:
    validate_summary(payload)
    return _clean(payload['summary'])


def present_fields(cancer: str, payload) -> list:
    """结构化输出里"原文出现"（非 not mentioned、非空）的字段键，按固定顺序；召回统计用。"""
    validate_struct(cancer, payload)
    present = []
    for field in fields_for(cancer):
        value = payload[field.key]
        if field.kind == 'pairs':
            if any(_clean(item['name']) and _clean(item['result']) and not is_not_mentioned(item['result'])
                   for item in value):
                present.append(field.key)
        elif _clean(value) and not is_not_mentioned(value):
            present.append(field.key)
    return present


# ----------------------------------------------------------------------------- prompt 与请求

def load_prompts(prompt_dir=PROMPT_DIR) -> dict:
    """读取 prompt 文件，返回 {name: {'text', 'sha256'}}；freeze manifest 记录这些哈希。"""
    prompts = {}
    for name, file_name in PROMPT_FILES.items():
        raw = (Path(prompt_dir) / file_name).read_bytes()
        prompts[name] = {'text': raw.decode('utf-8').strip(), 'sha256': hashlib.sha256(raw).hexdigest()}
    return prompts


def build_request(arm: str, cancer: str, report: str, *, prompts: dict, target_words: int | None = None) -> dict:
    """一份报告在某一臂下的请求：system、user 与结构化输出 schema。报告只作为取值插入，不参与格式解析。"""
    if arm not in ARMS:
        raise ValueError(f'未知臂 {arm!r}')
    if not isinstance(report, str) or not report.strip():
        raise ValueError('报告正文为空')
    name = CANCER_NAMES[cancer]
    if arm == 'struct':
        user = prompts['struct_user']['text'].format(cancer_name=name, report=report)
        schema = struct_schema(cancer)
    else:
        if not isinstance(target_words, int) or target_words <= 0:
            raise ValueError('摘要臂必须给出正整数的 target_words')
        user = prompts['summary_user']['text'].format(cancer_name=name, report=report, target_words=target_words)
        schema = SUMMARY_SCHEMA
    return {'system': prompts['system']['text'], 'user': user, 'schema': schema}


def length_retry_message(n_tokens: int, max_tokens: int, *, prompts: dict) -> str:
    return prompts['length_retry']['text'].format(n_tokens=n_tokens, max_tokens=max_tokens)


def serialize(arm: str, cancer: str, payload) -> str:
    """送进冻结 encoder 的文本（两臂统一入口）。"""
    return serialize_struct(cancer, payload) if arm == 'struct' else serialize_summary(payload)
