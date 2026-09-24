# Bug 现象描述

标题正文具有局部删除线、加粗或文字颜色，但 Office Viewer 的大纲/TOC 没有显示同样的格式，或格式范围不一致。

归档核对时间：`2026-09-15T14:35:59+09:00`。目标历史版本：`cweijan.vscode-office-4.2.0`。

本次更新：`2026-09-22 22:04:40 JST`，补丁 C（目录颜色 / 加粗 / 删除线同步 + Obsidian 标签单次计数）已安装到同一版本，详见文末「2026-09-22 补丁 C」节。

| 实现 | 归档时状态 | 证据边界 |
| --- | --- | --- |
| A：局部删除线 | 已被 C 取代（C 内含等价删除线映射，32 项旧回归仍通过） | 历史32项程序测试及原生局部删除线测试已通过；不代表所有嵌套语法均正常。 |
| B：删除线＋加粗＋前景色 | 历史候选，已回滚；其目录部分于 2026-09-22 以 C 重建 | 历史31项富文本测试通过，但完整原生验收失败；原生失败项为正文解析既有缺陷，与目录增量无关。 |
| C：颜色＋加粗＋删除线＋Obsidian 标签单次计数（2026-09-22） | 已安装、运行中已加载、原生已验证 | 87 项程序测试 + 32 项删除线回归 + 原生大纲截图；Obsidian 标签开启（非当前运行配置）时含标签标题安全跳过不着色。 |

普通 Markdown 加粗本身已有部分支持；B是在A上扩展，并不是A/B同时安装。正文先发生丢字时，目录补丁不能恢复正文语义。

已知原生阻断：`<span style="color:red">甲 <span style="color:blue">乙</span> 丙</span>` 出现正文错序/范围异常；`<span style="color:red">**~~红😀粗删~~**</span> 尾` 在正文仅显示“尾”。回滚后同输入仍复现，属于原正文处理路径问题。本指南记录候选，但不授权未来AI顺带改正文解析。

# 修改的目标文件路径

扩展根目录的相对路径：`resource/markdown/dist/index.min.js`。

历史绝对路径：`/Users/wuhao/.vscode/extensions/cweijan.vscode-office-4.2.0/resource/markdown/dist/index.min.js`。

定位目录生成链：遍历正文直接子标题 → 收集标题ID → `SetToC` / `SpinVditorDOM` / `HTML2VditorDOM` → `li > span[data-target-id]` → 包装折叠图标与文字标签。不要误改VS Code自身的Outline或Markdown正文转换。

# 核心修复逻辑

A在标题副本中排除IR标记，记录删除线覆盖的可见文字区间，再沿既有标题顺序/ID关系装饰对应目录标签的文本节点。B在目录专用副本中还原HTML-inline元数据，以同一文字区间叠加粗体、合法CSS前景色和删除线，内层显式颜色优先。

两者都不按标题文字搜索，避免重名串位；正文与目录规范化文字不相等时安全跳过，不猜测范围。每次目录重建重新计算，以清除已取消的样式；保留折叠按钮、跳转ID与既有格式。

- 先识别实际启用的 `cweijan.vscode-office` 版本与扩展根目录；4.2.0 的绝对路径只是历史定位，不得当成未来版本固定路径。检查新版是否已具备相同行为，避免重复注入。
- 在任何写入前备份将修改的实际文件、记录版本和 SHA-256。已存在其他本地改动时，以当次磁盘内容为基线，不从旧备份整文件覆盖新版。
- 下文压缩符号仅用于解释历史上下文；通过函数职责、DOM选择器、调用链定位对应实现。锚点不唯一或接口已变时先定位，不得强制字符串替换。
- 仅处理本指南对应问题；大纲与刷新分别打补丁、分别验收、分别回滚。不要改正文序列化、快捷键或授权状态，不添加公共API、宿主消息协议或生产依赖。
- 如临时应用后验收失败，仅撤销本次差异。清楚区分“候选”“已安装”“运行中已加载”“原生已验证”，代码测试通过不等于界面修复成功。

# Before & After 代码对比（Diff）

以下代码从历史补丁原样提取。代码使用现有bundle的其他符号与Lute对象，必须放回对应词法作用域；它不是可脱离Vditor独立运行的插件。不要在原定义之外再声明同名常量；替换对应定义或在原变量链内以等价函数表达式接入。

## A：已安装局部删除线——完整功能代码

```javascript
// Only decorate the generated label; never change the editor's heading DOM.
function officeOutlineStrike(heading, label) {
  if (!heading || !label) return;
  const doc = label.ownerDocument;
  const source = doc.createTreeWalker(heading, 4);
  const spans = [];
  let text = '', node;
  while ((node = source.nextNode())) {
    const start = text.length;
    text += node.data.replace(/\u200b/g, '');
    if (node.parentElement.closest('s, del, strike')) spans.push([start, text.length]);
  }
  // Fail closed for unsupported transformations, instead of striking wrong text.
  if (!spans.length || text !== label.textContent.replace(/\u200b/g, '')) return;
  const target = doc.createTreeWalker(label, 4);
  const nodes = [];
  let offset = 0;
  while ((node = target.nextNode())) {
    const positions = [];
    for (let i = 0; i < node.length; i++) if (node.data[i] !== '\u200b') positions.push(i);
    nodes.push([node, offset, positions]);
    offset += positions.length;
  }
  for (const [leaf, start, positions] of nodes) {
    const cuts = spans.map(([a,b]) => [Math.max(0,a-start),Math.min(positions.length,b-start)])
      .filter(([a,b]) => a < b).map(([a,b]) => [positions[a],positions[b-1]+1]);
    for (const [a,b] of cuts.reverse()) {
      const part = leaf.splitText(a);
      part.splitText(b-a);
      if (part.parentElement.closest('s, del, strike')) continue;
      const mark = doc.createElement('s');
      mark.style.textDecoration = 'line-through';
      part.replaceWith(mark);
      mark.append(part);
    }
  }
}
```

## A：完整目录副本、标题收集与标签应用接入

下列定义与上面的函数处于同一作用域。`T_e`删除IR标记，`D_e`只处理目录副本；`i$`保留原目录生成、折叠及跳转逻辑。完整列出这条接入链，方便未来AI在符号改名后按行为迁移。

```javascript
const T_e=e=>{let t=e.cloneNode(!0);return t.querySelectorAll(`.vditor-ir__marker, wbr`).forEach(e=>{e.remove()}),t},E_e=e=>(e.querySelectorAll(`code`).forEach(e=>{e.innerHTML=e.innerHTML.replace(/&/g,`&amp;`)}),e),D_e=(e,t)=>{let n=(t==null?void 0:t.currentMode)===`ir`?T_e(e):e.cloneNode(!0);return n.querySelectorAll(`wbr`).forEach(e=>{e.remove()}),E_e(n),t==null||t.currentMode,n.outerHTML},O_e=120,k_e=.25,A_e=(e,t)=>{let n=t.getBoundingClientRect(),r=n.top,i=n.bottom;e.options.height===`auto`&&(i=window.innerHeight,e.options.toolbarConfig.pin&&(r=Math.max(r,e.toolbar.element.getBoundingClientRect().bottom)));let a=Math.max(0,i-r),o=Math.max(15,Math.min(O_e,a*k_e));return r+o},r$=(e,t)=>{let n=e.getBoundingClientRect(),r=t.getBoundingClientRect();e.scrollTop+=r.top-n.top-15},i$=(e,t,n)=>{var r,i;let a=``,o=[],strikeHeadings=new Map;if(Array.from(e.children).forEach((e,t)=>{if(GZ(e)){if(n)if(!e.id)e.id=`vditor-outline-target-${t}`;else{let n=e.id.lastIndexOf(`_`);e.id=e.id.substring(0,n===-1?void 0:n)+`_`+t}o.push(e.id),e.querySelector(`s,del,strike`)&&strikeHeadings.set(e.id,T_e(e)),a+=D_e(e,n)}}),a===``)return t.innerHTML=``,``;let s=document.createElement(`div`);if(n)n.lute.SetToC(!0),n.currentMode===`wysiwyg`?s.innerHTML=n.lute.SpinVditorDOM(`<p>[ToC]</p>`+a):s.innerHTML=n.lute.HTML2VditorDOM(`<p>[ToC]</p>`+a),n.lute.SetToC(n.options.preview.markdown.toc);else{t.classList.add(`vditor-outline`);let e=Lute.New();e.SetToC(!0),s.innerHTML=e.HTML2VditorDOM(`<p>[ToC]</p>`+a)}let c=s.firstElementChild;if(!c)return t.innerHTML=``,``;let u=c.querySelectorAll(`li > span[data-target-id]`);if(u.forEach((e,t)=>{e.nextElementSibling&&e.nextElementSibling.tagName===`UL`?e.innerHTML=`${l(`chevron-down`,`vditor-outline__action`)}<span>${e.innerHTML}</span>`:e.innerHTML=`<span class="vditor-outline__placeholder" aria-hidden="true"></span><span>${e.innerHTML}</span>`,e.setAttribute(`data-target-id`,o[t]),officeOutlineStrike(strikeHeadings.get(o[t]),e.lastElementChild)}),a=c.innerHTML,u.length===0)return t.innerHTML=``,a;t.innerHTML=a,n&&n$(t,{cdn:n.options.cdn,math:n.options.preview.math});let d=n==null||(r=n.options)==null||(r=r.cache)==null?void 0:r.id,f=d?`vditor-outline-state:${d}`:null,p=()=>{if(!f)return new Set;try{let e=localStorage.getItem(f);return e?new Set(JSON.parse(e)):new Set}catch(e){return new Set}},m=()=>{if(!f)return;let e=[];t.querySelectorAll(`.vditor-outline__action--close`).forEach(t=>{var n;let r=(n=t.parentElement)==null?void 0:n.getAttribute(`data-target-id`);r&&e.push(r)}),localStorage.setItem(f,JSON.stringify(e))},h=p();return h.size>0&&t.querySelectorAll(`li > span[data-target-id]`).forEach(e=>{var t;let n=e.getAttribute(`data-target-id`);if(!n||!h.has(n))return;let r=e.querySelector(`.vditor-outline__action`),i=(t=e.parentElement)==null?void 0:t.querySelector(`ul`);r&&i&&(r.classList.add(`vditor-outline__action--close`),i.style.display=`none`)}),(i=t.firstElementChild)==null||i.addEventListener(`click`,r=>{let i=r.target;for(;i&&!i.isEqualNode(t);){if(i.classList.contains(`vditor-outline__action`)){i.classList.contains(`vditor-outline__action--close`)?(i.classList.remove(`vditor-outline__action--close`),i.parentElement.nextElementSibling.setAttribute(`style`,`display:block`)):(i.classList.add(`vditor-outline__action--close`),i.parentElement.nextElementSibling.setAttribute(`style`,`display:none`)),m(),r.preventDefault(),r.stopPropagation();break}else if(i.getAttribute(`data-target-id`)){r.preventDefault(),r.stopPropagation();let t=i.getAttribute(`data-target-id`),a=document.getElementById(t);if(!a)return;if(n){if(f$(n,t),n.options.height===`auto`){let e=a.offsetTop+n.element.offsetTop;n.options.toolbarConfig.pin||(e+=n.toolbar.element.offsetHeight),window.scrollTo(window.scrollX,e-15)}else n.element.offsetTop<window.scrollY&&window.scrollTo(window.scrollX,n.element.offsetTop),r$(e,a);GQ(n)&&QQ(n)}else window.scrollTo(window.scrollX,a.offsetTop-15);break}i=i.parentElement}}),a};
```

## A：关键替换位置对照

```diff
- let a=``,o=[];
+ let a=``,o=[],strikeHeadings=new Map;

- o.push(e.id),a+=D_e(e,n)
+ o.push(e.id),e.querySelector(`s,del,strike`)&&strikeHeadings.set(e.id,T_e(e)),a+=D_e(e,n)

- e.setAttribute(`data-target-id`,o[t])
+ e.setAttribute(`data-target-id`,o[t]),officeOutlineStrike(strikeHeadings.get(o[t]),e.lastElementChild)
```

## B：未通过完整原生验收的富文本候选——完整功能代码

若要研究富文本扩展，使用下面两个函数替换A的单个helper；不要叠加执行两个 `officeOutlineStrike`。该候选只提取允许样式，不复制任意HTML属性；颜色值由CSS属性解析器校验。完整HTML元数据、独立起始标记和DOM重排形态均需在新版重新验证。

```javascript
// Normalize Lute HTML-inline wrappers in a detached copy used only by TOC.
function officeOutlineSource(heading) {
  const clone = heading.cloneNode(true), doc = heading.ownerDocument;
  const safeRaw = node => {
    if (node.nodeType === 3) return doc.createTextNode(node.data);
    if (node.nodeType !== 1 || /^(SCRIPT|STYLE|IFRAME|OBJECT)$/.test(node.tagName)) return doc.createTextNode('');
    const el = doc.createElement(/^(B|STRONG|S|DEL|STRIKE|EM|I|CODE)$/.test(node.tagName) ? node.tagName.toLowerCase() : 'span');
    el.style.color = node.style.color || (node.tagName === 'FONT' ? node.getAttribute('color') || '' : '');
    Array.from(node.childNodes).forEach(child => el.append(safeRaw(child)));
    return el;
  };
  // Process children first: nested spans are often reparented inside the
  // opening marker by the HTML parser, whereas font/b become real siblings.
  const normalize = node => {
    Array.from(node.children).forEach(normalize);
    if (!node.matches('[data-type="html-inline"][data-md-source]')) return;
    const template = doc.createElement('template');
    template.innerHTML = node.getAttribute('data-md-source');
    const opener = template.content.firstElementChild;
    const content = Array.from(node.childNodes).filter(child => child.nodeType !== 1 || !child.matches('.vditor-html-inline__display, .vditor-ir__marker'));
    if (content.some(child => child.nodeType === 1 || child.textContent.replace(/\u200b/g, '').length)) {
      const wrapper = opener ? safeRaw(opener) : doc.createElement('span');
      wrapper.replaceChildren(...content);
      node.replaceWith(wrapper);
    } else {
      node.replaceWith(...Array.from(template.content.childNodes).map(safeRaw));
    }
  };
  normalize(clone);
  return clone;
}
// Read a detached heading only. Never copy HTML attributes into the TOC.
function officeOutlineStrike(heading, label) {
  if (!heading || !label) return;
  const doc = label.ownerDocument;
  const runs = [];
  let text = '';
  const clean = value => value.replace(/\u200b/g, '');
  const color = value => {
    const probe = doc.createElement('span');
    probe.style.color = value || '';
    return probe.style.color;
  };
  const styleOf = (el, inherited) => ({
    bold: inherited.bold || /^(B|STRONG)$/.test(el.tagName),
    strike: inherited.strike || /^(S|DEL|STRIKE)$/.test(el.tagName),
    color: color(el.style?.color || (el.tagName === 'FONT' ? el.getAttribute('color') : '')) || inherited.color,
  });
  const append = (value, style) => {
    value = clean(value);
    if (!value) return;
    const start = text.length;
    text += value;
    runs.push({start, end: text.length, ...style});
  };
  const visit = (node, inherited) => {
    if (node.nodeType === 3) return append(node.data, inherited);
    if (node.nodeType !== 1 && node.nodeType !== 11) return;
    if (node.nodeType === 11) return Array.from(node.childNodes).forEach(child => visit(child, inherited));
    if (node.matches('.vditor-ir__marker, .vditor-cm-host, wbr, script, style')) return;
    if (node.tagName === 'IMG') return append(node.getAttribute('alt') || '', inherited);
    const math = node.matches('[data-type="inline-node"], [data-type="math-inline"]') &&
      (node.querySelector('code[data-type="math-inline"]') || (node.matches('code[data-type="math-inline"]') ? node : node.querySelector('.language-math')));
    if (math) return append(math.textContent, inherited);
    let style = styleOf(node, inherited);
    Array.from(node.childNodes).forEach(child => visit(child, style));
  };
  visit(officeOutlineSource(heading), {bold: false, strike: false, color: ''});
  if (text !== clean(label.textContent)) return;
  const walker = doc.createTreeWalker(label, 4);
  const leaves = [];
  let leaf, offset = 0;
  while ((leaf = walker.nextNode())) {
    const positions = [];
    for (let i = 0; i < leaf.length; i++) if (leaf.data[i] !== '\u200b') positions.push(i);
    leaves.push({leaf, start: offset, positions});
    offset += positions.length;
  }
  for (const {leaf, start, positions} of leaves) {
    for (const run of runs.slice().reverse()) {
      const a = Math.max(0, run.start - start), b = Math.min(positions.length, run.end - start);
      if (a >= b || !(run.bold || run.strike || run.color)) continue;
      const parent = leaf.parentElement;
      const bold = run.bold && !parent.closest('b,strong');
      const strike = run.strike && !parent.closest('s,del,strike');
      if (!(bold || strike || run.color)) continue;
      const part = leaf.splitText(positions[a]);
      part.splitText(positions[b - 1] + 1 - positions[a]);
      const mark = doc.createElement(strike ? 's' : 'span');
      if (strike) mark.style.textDecoration = 'line-through';
      if (bold) mark.style.fontWeight = 'bold';
      if (run.color) mark.style.color = run.color;
      part.replaceWith(mark);
      mark.append(part);
    }
  }
}
```

## B：完整目录副本与区间映射接入

与A的区别：收集所有标题副本；在 `D_e` 的目录副本上执行 `officeOutlineSource`，避免后续TOC转换丢掉span中的文字。不是修改实际正文DOM。

```javascript
const T_e=e=>{let t=e.cloneNode(!0);return t.querySelectorAll(`.vditor-ir__marker, wbr`).forEach(e=>{e.remove()}),t},E_e=e=>(e.querySelectorAll(`code`).forEach(e=>{e.innerHTML=e.innerHTML.replace(/&/g,`&amp;`)}),e),D_e=(e,t)=>{let n=(t==null?void 0:t.currentMode)===`ir`?T_e(e):e.cloneNode(!0);return n=officeOutlineSource(n),n.querySelectorAll(`wbr`).forEach(e=>{e.remove()}),E_e(n),t==null||t.currentMode,n.outerHTML},O_e=120,k_e=.25,A_e=(e,t)=>{let n=t.getBoundingClientRect(),r=n.top,i=n.bottom;e.options.height===`auto`&&(i=window.innerHeight,e.options.toolbarConfig.pin&&(r=Math.max(r,e.toolbar.element.getBoundingClientRect().bottom)));let a=Math.max(0,i-r),o=Math.max(15,Math.min(O_e,a*k_e));return r+o},r$=(e,t)=>{let n=e.getBoundingClientRect(),r=t.getBoundingClientRect();e.scrollTop+=r.top-n.top-15},i$=(e,t,n)=>{var r,i;let a=``,o=[],strikeHeadings=new Map;if(Array.from(e.children).forEach((e,t)=>{if(GZ(e)){if(n)if(!e.id)e.id=`vditor-outline-target-${t}`;else{let n=e.id.lastIndexOf(`_`);e.id=e.id.substring(0,n===-1?void 0:n)+`_`+t}o.push(e.id),strikeHeadings.set(e.id,e.cloneNode(!0)),a+=D_e(e,n)}}),a===``)return t.innerHTML=``,``;let s=document.createElement(`div`);if(n)n.lute.SetToC(!0),n.currentMode===`wysiwyg`?s.innerHTML=n.lute.SpinVditorDOM(`<p>[ToC]</p>`+a):s.innerHTML=n.lute.HTML2VditorDOM(`<p>[ToC]</p>`+a),n.lute.SetToC(n.options.preview.markdown.toc);else{t.classList.add(`vditor-outline`);let e=Lute.New();e.SetToC(!0),s.innerHTML=e.HTML2VditorDOM(`<p>[ToC]</p>`+a)}let c=s.firstElementChild;if(!c)return t.innerHTML=``,``;let u=c.querySelectorAll(`li > span[data-target-id]`);if(u.forEach((e,t)=>{e.nextElementSibling&&e.nextElementSibling.tagName===`UL`?e.innerHTML=`${l(`chevron-down`,`vditor-outline__action`)}<span>${e.innerHTML}</span>`:e.innerHTML=`<span class="vditor-outline__placeholder" aria-hidden="true"></span><span>${e.innerHTML}</span>`,e.setAttribute(`data-target-id`,o[t]),officeOutlineStrike(strikeHeadings.get(o[t]),e.lastElementChild)}),a=c.innerHTML,u.length===0)return t.innerHTML=``,a;t.innerHTML=a,n&&n$(t,{cdn:n.options.cdn,math:n.options.preview.math});let d=n==null||(r=n.options)==null||(r=r.cache)==null?void 0:r.id,f=d?`vditor-outline-state:${d}`:null,p=()=>{if(!f)return new Set;try{let e=localStorage.getItem(f);return e?new Set(JSON.parse(e)):new Set}catch(e){return new Set}},m=()=>{if(!f)return;let e=[];t.querySelectorAll(`.vditor-outline__action--close`).forEach(t=>{var n;let r=(n=t.parentElement)==null?void 0:n.getAttribute(`data-target-id`);r&&e.push(r)}),localStorage.setItem(f,JSON.stringify(e))},h=p();return h.size>0&&t.querySelectorAll(`li > span[data-target-id]`).forEach(e=>{var t;let n=e.getAttribute(`data-target-id`);if(!n||!h.has(n))return;let r=e.querySelector(`.vditor-outline__action`),i=(t=e.parentElement)==null?void 0:t.querySelector(`ul`);r&&i&&(r.classList.add(`vditor-outline__action--close`),i.style.display=`none`)}),(i=t.firstElementChild)==null||i.addEventListener(`click`,r=>{let i=r.target;for(;i&&!i.isEqualNode(t);){if(i.classList.contains(`vditor-outline__action`)){i.classList.contains(`vditor-outline__action--close`)?(i.classList.remove(`vditor-outline__action--close`),i.parentElement.nextElementSibling.setAttribute(`style`,`display:block`)):(i.classList.add(`vditor-outline__action--close`),i.parentElement.nextElementSibling.setAttribute(`style`,`display:none`)),m(),r.preventDefault(),r.stopPropagation();break}else if(i.getAttribute(`data-target-id`)){r.preventDefault(),r.stopPropagation();let t=i.getAttribute(`data-target-id`),a=document.getElementById(t);if(!a)return;if(n){if(f$(n,t),n.options.height===`auto`){let e=a.offsetTop+n.element.offsetTop;n.options.toolbarConfig.pin||(e+=n.toolbar.element.offsetHeight),window.scrollTo(window.scrollX,e-15)}else n.element.offsetTop<window.scrollY&&window.scrollTo(window.scrollX,n.element.offsetTop),r$(e,a);GQ(n)&&QQ(n)}else window.scrollTo(window.scrollX,a.offsetTop-15);break}i=i.parentElement}}),a};
```

## 验证用例与归档依据

用独立Markdown测试整段/局部/多段删除线、粗体与链接嵌套、中文/emoji、重名标题、新增/删除/移动标题；验证取消格式、撤销/重做、保存重开、IR/WYSIWYG，以及目录折叠/高亮/跳转。验证B时额外覆盖b/strong、font/span前景色、内层颜色优先和三样式叠加；同时核对正文没有先丢字。任何安全跳过都不能算该用例通过。

历史来源（仅供追溯，使用本指南不依赖这些文件仍然存在）：

- A：`/Users/wuhao/Documents/Codex/patches/office-outline-strikethrough/outline-strike.js`、`build-patch.py`、`test-outline.cjs`。
- B：`/Users/wuhao/Documents/Codex/patches/office-outline-richtext-scroll-20260915/outline-richtext.js`、`build-richtext.py`、`test-richtext.cjs`、`README.md`。

### Bug Post-Mortem

- **现象**：正文标题样式经过TOC转换后丢失或范围不一致。
- **根因**：目录转换不会完整保留正文格式；IR编辑标记、零宽占位与HTML-inline元数据让可见文字和DOM文字不同。
- **修复**：A通过副本区间映射同步局部删除线；B尝试统一富文本映射，但原生嵌套正文异常导致候选回滚。
- **Prevention Rule**：区分正文解析与目录装饰，真实编辑器与独立解析器分别验收；不得把候选、跳过映射或程序通过标为完整修复成功。

# 给未来 AI 的 Prompt 指令

> **2026-09-22 起以补丁 C 为准**：颜色/加粗/删除线已由 C 统一实现并安装，下面这段历史指令中「B 只是已回滚候选」的表述已过期；排查新问题时先读文末「2026-09-22 补丁 C」节，以 `outline-color.js` 作为当前可读实现。

> 请根据本指南排查当前实际启用的 Office Viewer 大纲与正文样式不同步。先定位扩展版本、目录生成函数和新版现有能力，确认问题仍存在，再备份目标文件并记录版本与SHA-256。以A的已安装历史修复为默认参考，按标题既有对应关系恢复局部删除线，完整接入helper、标题副本采集和目录标签应用；不要按标题文本匹配。B的加粗/颜色代码只是已回滚候选：可用独立样例验证，但未经重新验证和明确采用，不得直接写入安装版。新版本符号、DOM或接口不同，请按行为适配，不要盲套旧行号或整文件覆盖。保留其他本地修改和正文内容；此任务不要顺带修改刷新逻辑、正文解析或授权。完成程序检查后，使用独立文档验证局部样式、重名、取消、撤销、保存重开、两种模式以及折叠/跳转。原生失败则仅回滚本次目录补丁。最终分别报告代码测试、安装状态、运行中加载、原生验收和独立互审，保存差异、哈希、截图、回滚步骤与Post-Mortem。


# 2026-09-22 补丁 C：目录颜色同步（本次修复）

## Bug 现象

todo.md 原文：「#BUG 修复Markdown文件使用office viewer 渲染后的md文件，没当标题的颜色进行标红等颜色标记操作，左侧渲染出来的大纲没有渲染出红色」。截图：`image/todo/1789544641035.png`（正文标题「3. James-Stein 收缩：让检索最坏等于均值 #TODO」为红色，左侧大纲同条目为黑色）。

实际标题写法（`experiments/I01_patient_retrieval/knowledge/data-analysis-from-grok/1.progress/实验结果分析-grok.md` 第 102 行）：

```markdown
### #TODO-2. <span style="color: #ff0000;">零训练改 key</span>：按模型实际吃的 WSI 检索 #TODO
```

修复前用真实安装版 Lute + jsdom 复现（IR 模式、运行时配置）：大纲标签为 `#TODO-2. <strong>零训练改 key</strong>：按模型实际吃的 WSI 检索 #TODO`——颜色丢失，且带色文字被错误渲染成粗体；WYSIWYG 模式下带 span 的标题文字整段丢失（标签只剩 `. `）。

## 根因

- Lute 把行内 HTML 编码成 `span[data-type="html-inline"][data-md-source]` 包装（显示层 + 元数据），A 的目录副本直接把这个包装交给 `HTML2VditorDOM` / `SpinVditorDOM`，TOC 转换既不保留颜色又会把包装误转成 `**`（IR）或丢字（WYSIWYG）。
- 历史候选 B 已能补回颜色，但因正文嵌套 span 的既有缺陷被整体回滚，单层 span/font 颜色（原生已通过）随之丢失一周。
- 新增发现：Lute 的 obsidian-tag 节点是「display + 隐藏 source」双层 DOM，B 的文本遍历会把 `#TODO` 计两次，导致目录文字比对失败而安全跳过；当前运行时（0911 本地补丁 `this.vditor.lute.SetObsidianTag(!1)`）标签是纯文本，但测试矩阵必须覆盖两种配置。

## 目标文件与当前状态

- 扩展：`cweijan.vscode-office-4.2.0`（`~/.vscode/extensions/`；`rjwang.vscode-office-enhanced`、`imfing.office-viewer-vscode` 已禁用；实际运行的应用是 `/Applications/Visual Studio Code 3.app`）。
- 文件：`resource/markdown/dist/index.min.js`，只改目录生成区（`D_e` / `i$` / `officeOutlineStrike`）。
- 基线（含 A + 阅读位置补丁）SHA-256：`5389639d9e4b44dd9b0abdb462b91e332be29b85f1bd369459b8438d6196d52a`
- 安装后 SHA-256：`9f67af52fda7203f11ea561134694c0aa2d7e2d7ffb604b0f421c81eeea58177`
- 补丁目录：`/Users/wuhao/Documents/Codex/patches/office-outline-color-20260922/`（`backup/`、`candidate/`、`outline-color.js`、`build-color.py`、`manage-patch.py`、`hashes.json`、`office-outline-color.patch`、`manifest-before.json`、`installed-verification.json`、`test-color.cjs`、`test-strike-regression.cjs`、`outline-color-demo.md`、日志）。
- 全量清单核对：1759 个安装文件仅上述 1 个文件变化，新增 0、删除 0。

## 核心逻辑

`officeOutlineSource` 在**仅供目录使用的标题副本**里：① 把 html-inline 包装还原成只带允许样式（b/strong/s/del/strike/em/i/code + 合法 color）的安全节点，不复制事件与任意属性；② 把 obsidian-tag 双层节点归一为其 source 文本一次。`D_e` 生成目录 HTML 前先走该副本，避免 TOC 转换把 span 转成粗体或丢字。`officeOutlineStrike` 在同一副本上按可见文字区间记录 bold / color / strike（内层显式颜色优先），与目录标签文字全等时才按既有标题 ID 对应关系装饰标签文本节点；不等则安全跳过。正文 DOM、序列化、折叠/跳转逻辑未改。

## 关键替换位置对照（由 build-color.py 按锚点执行，不按行号）

```diff
- D_e=(e,t)=>{...;return n.querySelectorAll(`wbr`).forEach(...)...}
+ D_e=(e,t)=>{...;return n=officeOutlineSource(n),n.querySelectorAll(`wbr`).forEach(...)...}

- o.push(e.id),e.querySelector(`s,del,strike`)&&strikeHeadings.set(e.id,T_e(e)),a+=D_e(e,n)
+ o.push(e.id),strikeHeadings.set(e.id,e.cloneNode(!0)),a+=D_e(e,n)

- ,officeOutlineStrike=(heading, label)=> { /* A：仅删除线 */ },O_e=120
+ ,officeOutlineSource=(heading) =>{ /* 目录副本归一化 */ },officeOutlineStrike=(heading, label) =>{ /* bold/color/strike 区间映射 */ },O_e=120
```

## C：完整可读实现（outline-color.js，原样）

```javascript
// Office Viewer (cweijan.vscode-office 4.2.0) outline colour / bold / strike sync.
// Display layer only: decorates the generated TOC label; never edits the editor's heading DOM.
// Derived from candidate B (office-outline-richtext-scroll-20260915/outline-richtext.js)
// plus single-count handling for Lute obsidian-tag nodes (display + hidden source layer).
// These two functions are spliced into the `const T_e=...,D_e=...,officeOutlineStrike=...,O_e=...`
// declaration chain of resource/markdown/dist/index.min.js by build-color.py.

// Normalize Lute HTML-inline wrappers and obsidian-tag nodes in a detached copy used only by TOC.
function officeOutlineSource(heading) {
  const clone = heading.cloneNode(true), doc = heading.ownerDocument;
  const safeRaw = node => {
    if (node.nodeType === 3) return doc.createTextNode(node.data);
    if (node.nodeType !== 1 || /^(SCRIPT|STYLE|IFRAME|OBJECT)$/.test(node.tagName)) return doc.createTextNode('');
    const el = doc.createElement(/^(B|STRONG|S|DEL|STRIKE|EM|I|CODE)$/.test(node.tagName) ? node.tagName.toLowerCase() : 'span');
    el.style.color = node.style.color || (node.tagName === 'FONT' ? node.getAttribute('color') || '' : '');
    Array.from(node.childNodes).forEach(child => el.append(safeRaw(child)));
    return el;
  };
  // Obsidian tags render as display + hidden source layers; keep the source text exactly once.
  const tagText = node => {
    const layer = node.querySelector('.vditor-obsidian-tag__source') || node.querySelector('.vditor-obsidian-tag__display') || node;
    return doc.createTextNode(layer.textContent.replace(/​/g, ''));
  };
  // Process children first: nested spans are often reparented inside the
  // opening marker by the HTML parser, whereas font/b become real siblings.
  const normalize = node => {
    Array.from(node.children).forEach(normalize);
    if (node.matches('.vditor-obsidian-tag')) return node.replaceWith(tagText(node));
    if (!node.matches('[data-type="html-inline"][data-md-source]')) return;
    const template = doc.createElement('template');
    template.innerHTML = node.getAttribute('data-md-source');
    const opener = template.content.firstElementChild;
    const content = Array.from(node.childNodes).filter(child => child.nodeType !== 1 || !child.matches('.vditor-html-inline__display, .vditor-ir__marker'));
    if (content.some(child => child.nodeType === 1 || child.textContent.replace(/​/g, '').length)) {
      const wrapper = opener ? safeRaw(opener) : doc.createElement('span');
      wrapper.replaceChildren(...content);
      node.replaceWith(wrapper);
    } else {
      node.replaceWith(...Array.from(template.content.childNodes).map(safeRaw));
    }
  };
  normalize(clone);
  return clone;
}
// Read a detached heading only. Never copy HTML attributes into the TOC.
function officeOutlineStrike(heading, label) {
  if (!heading || !label) return;
  const doc = label.ownerDocument;
  const runs = [];
  let text = '';
  const clean = value => value.replace(/​/g, '');
  const color = value => {
    const probe = doc.createElement('span');
    probe.style.color = value || '';
    return probe.style.color;
  };
  const styleOf = (el, inherited) => ({
    bold: inherited.bold || /^(B|STRONG)$/.test(el.tagName),
    strike: inherited.strike || /^(S|DEL|STRIKE)$/.test(el.tagName),
    color: color(el.style?.color || (el.tagName === 'FONT' ? el.getAttribute('color') : '')) || inherited.color,
  });
  const append = (value, style) => {
    value = clean(value);
    if (!value) return;
    const start = text.length;
    text += value;
    runs.push({start, end: text.length, ...style});
  };
  const visit = (node, inherited) => {
    if (node.nodeType === 3) return append(node.data, inherited);
    if (node.nodeType !== 1 && node.nodeType !== 11) return;
    if (node.nodeType === 11) return Array.from(node.childNodes).forEach(child => visit(child, inherited));
    if (node.matches('.vditor-ir__marker, .vditor-cm-host, wbr, script, style')) return;
    if (node.tagName === 'IMG') return append(node.getAttribute('alt') || '', inherited);
    const math = node.matches('[data-type="inline-node"], [data-type="math-inline"]') &&
      (node.querySelector('code[data-type="math-inline"]') || (node.matches('code[data-type="math-inline"]') ? node : node.querySelector('.language-math')));
    if (math) return append(math.textContent, inherited);
    let style = styleOf(node, inherited);
    Array.from(node.childNodes).forEach(child => visit(child, style));
  };
  visit(officeOutlineSource(heading), {bold: false, strike: false, color: ''});
  // Fail closed: if the normalized heading text differs from the label, leave the label untouched.
  if (text !== clean(label.textContent)) return;
  const walker = doc.createTreeWalker(label, 4);
  const leaves = [];
  let leaf, offset = 0;
  while ((leaf = walker.nextNode())) {
    const positions = [];
    for (let i = 0; i < leaf.length; i++) if (leaf.data[i] !== '​') positions.push(i);
    leaves.push({leaf, start: offset, positions});
    offset += positions.length;
  }
  for (const {leaf, start, positions} of leaves) {
    for (const run of runs.slice().reverse()) {
      const a = Math.max(0, run.start - start), b = Math.min(positions.length, run.end - start);
      if (a >= b || !(run.bold || run.strike || run.color)) continue;
      const parent = leaf.parentElement;
      const bold = run.bold && !parent.closest('b,strong');
      const strike = run.strike && !parent.closest('s,del,strike');
      if (!(bold || strike || run.color)) continue;
      const part = leaf.splitText(positions[a]);
      part.splitText(positions[b - 1] + 1 - positions[a]);
      const mark = doc.createElement(strike ? 's' : 'span');
      if (strike) mark.style.textDecoration = 'line-through';
      if (bold) mark.style.fontWeight = 'bold';
      if (run.color) mark.style.color = run.color;
      part.replaceWith(mark);
      mark.append(part);
    }
  }
}
```

## 验证

- 程序测试 `test-color.cjs`（真实安装版 Lute + jsdom 26，`OFFICE_JSDOM` 指定 jsdom 路径）：**87 项通过**；矩阵 = B 原 12 例 × IR/WYSIWYG × {Lute 默认, 运行时 obsidian 开+obsidianTag 关} + 用户真实标题 5 例（十六进制颜色、局部/整行 span、`#TODO` 尾标签、`✅`）+ 重名标题/清除样式 + 手工 DOM（html-inline 元数据、嵌套颜色、obsidian-tag 双层单次计数）+ 文字不一致必须安全跳过。修复前基线跑同一脚本在首个颜色用例失败（`test-color-before.log`）。
- Obsidian 标签开启配置（非运行时）：含标签标题因 Lute TOC 自身丢标签文字而安全跳过（不着色、无乱码），不含标签标题正常着色；记录于 `test-color-after.log` 的 `tagOutcome`。
- 删除线旧回归 `test-strike-regression.cjs`：32 项通过；`node --check` 通过；补丁正向/反向往返哈希一致。
- 原生 VS Code（窗口「outline-color-demo.md — 知识库 (工作区)」，IR 模式，通过后台窗口截图放大核对）：`零训练改 key` 红、其余黑且不再粗体；`3. James-Stein …#TODO` 整条红；`交集（可以直接锁定` 红而 `）✅` 黑；`红色` 红；`蓝色` 蓝 + `删除` 删除线 + `粗体` 粗；普通标题无颜色。演示文档：`outline-color-demo.md`。
- 未覆盖：工具栏字体颜色（Pro 授权）编辑路径、撤销/重做后的目录刷新时序只由既有重建机制保证，未逐一原生实点。

## 回滚 / 重新应用

```sh
python3 /Users/wuhao/Documents/Codex/patches/office-outline-color-20260922/manage-patch.py check
python3 /Users/wuhao/Documents/Codex/patches/office-outline-color-20260922/manage-patch.py rollback   # 回到 A + 阅读位置补丁
python3 /Users/wuhao/Documents/Codex/patches/office-outline-color-20260922/manage-patch.py apply
```

版本或哈希不符时脚本拒绝写入；扩展升级后须重新定位锚点并重建，不得强套。应用/回滚后关闭并重开已保存的 Markdown 标签页以加载新 bundle。

### Bug Post-Mortem

- **现象**：标题局部/整行着色，Office Viewer 大纲对应条目无颜色，IR 模式还被误渲染成粗体。
- **根因**：目录副本把 Lute 的 html-inline 包装原样交给 TOC 转换；历史候选 B 因正文既有缺陷整体回滚，已验证的单层颜色也一并丢失；obsidian-tag 双层 DOM 让文本区间双计数。
- **修复**：以当前安装基线重建 B 的目录增量为补丁 C，副本内归一 html-inline 与 obsidian-tag，区间映射 bold/color/strike；RED→GREEN 程序测试 + 原生截图验收后安装。
- **Prevention Rule**：候选按功能粒度拆分验收与回滚，不因正文既有缺陷否定目录增量；目录文本映射的测试矩阵必须包含运行时 Lute 配置（obsidian 开 / obsidianTag 关）与标签开启两种形态，并以用户真实标题作为固定用例。

## 给未来 AI 的补充指令

> 先 `manage-patch.py check` 确认安装态与哈希；新问题先用 `test-color.cjs` 在真实 Lute 上复现（把用户标题原样加入 `userCases`），再改 `outline-color.js` → `build-color.py` → RED/GREEN → `manage-patch.py build/apply` → 原生截图。不要改正文解析、序列化、快捷键或授权；不要按标题文字匹配；不要用整文件覆盖处理版本升级。
