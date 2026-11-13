"""往 .excalidraw 副本里追加一个 frame 的公共工具（I08 框架图脚本共用）。

样式沿用原 PS3 定稿 frame：Excalifont（fontFamily 5）、lineHeight 1.25、圆角矩形、浅色填充。
守卫（坑 E38 / E49）：只追加不改旧元素；目标区域必须空；frame.id 等于全部子元素 frameId；id 全局唯一；
文字必须放得进框；子元素不得越出 frame；源里已有同 id frame 即拒绝。
"""
from __future__ import annotations

import copy
import json
import random
import unicodedata

LH = 1.25
NOW = 1793952000000


def text_width(line, size):
    w = 0.0   # 逐项累加：sum() 在 Python ≥3.12 用补偿求和，末位会变，破坏旧图逐字节回归
    for ch in line:
        w += size * (1.0 if unicodedata.east_asian_width(ch) in ('W', 'F') else 0.6)
    return w


class Canvas:
    def __init__(self, frame_id, id_prefix, seed, font=20):
        self.frame_id, self.prefix, self.font = frame_id, id_prefix, font
        self.rng = random.Random(seed)
        self.n = 0
        self.index_base = None          # main 里按源文件最大索引设定

    def _id(self, tag):
        self.n += 1
        return f'{self.prefix}-{tag}-{self.n:03d}'

    def _common(self, t, x, y, w, h, **kw):
        e = {'id': self._id(t), 'type': t, 'x': x, 'y': y, 'width': w, 'height': h, 'angle': 0,
             'strokeColor': '#1e1e1e', 'backgroundColor': 'transparent', 'fillStyle': 'solid', 'strokeWidth': 1,
             'strokeStyle': 'solid', 'roughness': 1, 'opacity': 100, 'groupIds': [], 'frameId': self.frame_id,
             'index': None, 'roundness': None, 'seed': self.rng.randrange(1, 2**31), 'version': 1,
             'versionNonce': self.rng.randrange(1, 2**31), 'isDeleted': False, 'boundElements': [], 'updated': NOW,
             'link': None, 'locked': False}
        e.update(kw)
        e['index'] = f'{self.index_base}{self.n:03d}V'   # 结尾不能是 0（fractional index 规则）
        return e

    def text(self, x, y, s, size=None, color='#1e1e1e'):
        size = size or self.font
        lines = s.split('\n')
        w = max(text_width(l, size) for l in lines)
        h = len(lines) * size * LH
        return self._common('text', x, y, w, h, strokeColor=color, strokeWidth=2, text=s, originalText=s,
                            fontSize=size, fontFamily=5, textAlign='left', verticalAlign='top', containerId=None,
                            autoResize=True, lineHeight=LH)

    def rect(self, x, y, w, h, fill, dashed=False, stroke='#1e1e1e', width=None):
        return self._common('rectangle', x, y, w, h, backgroundColor=fill, roundness={'type': 3},
                            strokeStyle='dashed' if dashed else 'solid', strokeColor=stroke,
                            strokeWidth=width or (2 if dashed else 1))

    def box(self, x, y, w, h, fill, body, dashed=False, stroke='#1e1e1e', size=None):
        r = self.rect(x, y, w, h, fill, dashed, stroke)
        t = self.text(x + 15, y + 12, body, size)
        assert t['width'] <= w - 20 and t['height'] <= h - 14, \
            f'文字溢出：{body.splitlines()[0]} {t["width"]:.0f}×{t["height"]:.0f} > {w}×{h}'
        return [r, t]

    def arrow(self, pts, dashed=False, color='#1e1e1e', width=1):
        (x, y), rel = pts[0], [[px - pts[0][0], py - pts[0][1]] for px, py in pts]
        xs, ys = [p[0] for p in rel], [p[1] for p in rel]
        return self._common('arrow', x, y, max(xs) - min(xs), max(ys) - min(ys),
                            roundness={'type': 2} if len(pts) == 2 else None,
                            strokeStyle='dashed' if dashed else 'solid', strokeColor=color, strokeWidth=width,
                            points=rel, lastCommittedPoint=None, startBinding=None, endBinding=None,
                            startArrowhead=None, endArrowhead='arrow', elbowed=False)

    def frame(self, x, y, w, h, name):
        f = self._common('frame', x, y, w, h, frameId=None, strokeWidth=2, name=name)
        f['id'] = self.frame_id          # 子元素的 frameId 指向它（坑 E49）
        return f


def append_frame(src, out, canvas, x0, y0, w, h, build):
    """build(canvas) -> (子元素列表, frame 元素)。只追加，不改旧元素。"""
    d = json.load(open(src, encoding='utf-8'))
    before = copy.deepcopy(d['elements'])
    if any(e['id'] == canvas.frame_id for e in before):
        raise SystemExit(f'源文件已含 {canvas.frame_id}，拒绝重复追加')
    for e in before:
        if e.get('isDeleted'):
            continue
        if e['x'] < x0 + w and e['x'] + e.get('width', 0) > x0 and e['y'] < y0 + h and e['y'] + e.get('height', 0) > y0:
            raise SystemExit(f'目标区域已被占用：{e["id"]} {e["type"]}')
    canvas.index_base = max((e.get('index') or '') for e in before) + 'V'   # 排在已有最大分数索引之后
    new, frame = build(canvas)
    frame['index'] = canvas.index_base + 'zzV'
    for e in new:
        assert x0 <= e['x'] and e['x'] + e['width'] <= x0 + w + 1 and y0 <= e['y'] and e['y'] + e['height'] <= y0 + h + 1, \
            f'元素越出 frame：{e["id"]} {e.get("text", "")[:20]}'
    assert frame['id'] == canvas.frame_id and all(e['frameId'] == frame['id'] for e in new), '子元素未挂到 frame 上'
    assert len({e['id'] for e in before + new + [frame]}) == len(before) + len(new) + 1, 'id 重复'
    d['elements'] = before + new + [frame]
    assert d['elements'][:len(before)] == before, '已有元素被改动'
    json.dump(d, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print(f'追加 {len(new) + 1} 个元素（{len(new)} 个子元素 + 1 个 frame）→ {out}')
    return new, frame
