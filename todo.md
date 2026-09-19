- [ ]  #BUG 修复Markdown文件使用office viewer 渲染后的md文件，没当标题的颜色进行标红等颜色标记操作，左侧渲染出来的大纲没有渲染出红色

![1789544641035](image/todo/1789544641035.png)

##可参考此版本的MD文件，并且如问题修复了之后，将此问题并同步到这个MD文件中/Users/wuhao/Desktop/TriModalSurv/docs/workflow/office-viewer/outline-sync-fix.md



**② Better Todo Tree 索引：保留，默认 regex 舍弃** #BUG


定位:索引和导航。

证据:v1.3.4 对 `.md` 走专用分支,只认 `<!-- -->` 和任务列表。官方测试(`detection.behavior.test.js:151`)自己断言 `# TODO heading` 被忽略。我的 13 行探针在默认配置下命中 0/13。改成下方 regex 后,10 行探针里 5 行真标签全中、5 行误报探针 0 命中,树节点显示知识点原文。[确定]

警告:README 字面写了 `#` 是前缀,但实现对 `.md` 另走分支。改 regex 后,同一工作区的 `// TODO` 和 `- [ ]` 任务列表都不再被扫,所以配置要放笔记库的 `.vscode/settings.json`。`"[markdown]"` 语言级覆盖读源码不像会生效 [不确定],别依赖
