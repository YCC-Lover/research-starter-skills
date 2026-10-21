# 进阶文献与筛选

先读 [共享执行规则](../../research-starter-paper/references/advanced-research.md)。
完整模式入口位于总入口的 `resources/research-engine/`。

## 调研与综合

读取 `deep-research/WORKFLOW.md` 并保持用户选定模式：`full` 深度报告、`quick`
短简报、`review` 评读材料、`lit-review` 注释书目与综合、`three-way-scan`
WHY/HOW/WHAT 对照、`fact-check` 逐条核查、`systematic-review` 系统综述。
`socratic` 交由研究设计处理。报告长度服从任务预算，不机械套用默认字数。

实际加载该阶段的 bibliography、source verification、synthesis 和必要的批判角色。
保留检索式、检索日期、来源版本、阅读范围、纳入排除理由、主张定位及矛盾证据。
只有摘要时不得填成全文阅读；题名相似、DOI 前缀陌生或检索未命中不自动证明造假。
证据不足或不能访问时保持未核验，不用模型记忆补齐引用字段。

系统综述先确认问题与协议，再做检索、选择、提取、偏倚评价及综合。读取
`deep-research/references/systematic_review_protocol.md` 及相应 risk-of-bias / meta-analysis
角色。只有可比的真实效应量和不确定性才计算合并效应；异质性、设计差异、偏倚和
缺失报告可使定量合并不适当。此时交付有依据的叙述性综合，不伪造森林图或统计量。
PRISMA 数字应能回溯记录，遵循实际完成程度，不声称自动满足所有报告准则。

## 明确要求筛选时

读取 `sr-screener/WORKFLOW.md` 与对应指南。已有记录或说“系统综述”本身不等于
要求启动筛选。八种模式是 `protocol`、`quick`、`pilot`、`ta-screen`、`ft-screen`、
`adjudicate`、`audit`、`report`，分别完成协议、单人初筛、试筛、题摘筛选、全文筛选、
冲突裁决、排除质控和可追溯报告。

从 RIS、MEDLINE、WoS 或 CSV 导入时保留原始条目和去重关系，稳定 ID 一旦产生
不能静默重排。先确认纳排规则、固定排除码、试筛参考标签、双盲机制和实际预算。
按源脚本依次准备记录、生成隔离角色输入、收集真实输出、合并决定、质控及导出。
前置条件不满足时保留待办，不能为运行脚本虚构人工标签或协议确认。

全文排除保留一个主要理由与可读的页码/章节依据；缺全文属于待取得或未能取得，
不能编造已阅读全文的排除理由。裁决和 senior exclusion QC 是不同步骤。
一致性指标、PRISMA 计数、RIS 分组与 `literature_corpus` 是实际记录的派生产物，
高一致性不证明正确性。协议改变须保留旧版本，并在新版本重新筛选受影响条目。

引用核验、阅读标记、缓存失效及导入适配器位于资源根的 `scripts/`。运行前看
具体 CLI 帮助和读写/网络边界；导入成功不等于文献存在或内容得到核验。
