# 运行工具

本页供执行任务的 Codex 按需读取。路径 `ENGINE` 指本 skill 的
`resources/research-engine/`；`ADAPTER` 指本 skill 的 `scripts/`。
先读取相应工作流和契约，再按其字段调用工具；不要求使用者手动维护这些记录。

## 环境与启动

普通指导、文字编辑和原生子代理不依赖额外 Python 包。运行研究检查脚本时，
使用发行包的 `requirements-research.txt`，或已安装总入口内的
`assets/requirements-research.txt`，安装到用户指定的环境。通用检查使用 Python 3.10+；
Windows 研究事务、条件绑定、投稿清单和活动记录工具使用已验证的 Python 3.13+。
若七个技能的父目录中有 `.research-starter-skills-runtime.json`，先读取其中的
`python` 字段，优先用已配置的专用解释器运行本页工具；这是本机配置，不写入论文。
没有该配置时使用当前可用环境并检查依赖。调用 Python 时加 `-B`，临时目录和缓存
仍随本次任务选择，专用环境只用于保存依赖。
PDF 内容分类器、NumPy、绘图、Pandoc、TeX 和其他外部工具按当前任务单独探测。
不在技能载入或安装时自动联网安装依赖。

```text
python ADAPTER/research_engine.py doctor
python ADAPTER/research_engine.py run-local --work-dir ABSOLUTE_WORK SCRIPT -- ARGUMENTS
```

启动器设置任务内临时目录、缓存和导入路径。源协议中的根相对路径以 ENGINE 为根。
源命令示例若带 POSIX 语法，按当前 shell 改写调用方式，保留 JSON 中规范化的 `/` 路径。
本用户的 Windows 中间文件使用 D/E 盘；其他平台使用任务明确选择的绝对目录。
保留失败产物，不运行递归清理。命令帮助和资源完整性检查不代表研究任务已执行。

## PDF 读取预检

```text
python ADAPTER/research_pdf_preflight.py --help
```

该适配器调用实际结构检查，再把结果写入明确选择的工作目录。核对输入 PDF 的字节
指纹，保留 PASS、FAIL、UNAVAILABLE。结构可解析不等于正文已阅读，缺少内容分类器
不伪造分类结果。侧车采用独占新建，不能覆盖旧结果；目录应由当前用户信任和控制。

## 引用元数据核验

`research_citations.py` 把真实稿件中的 `<!--ref:slug-->` 与 corpus 的 citation_key
显式对应，不使用诊断命令把 citation_key 假装成正文引用。代理先根据稿件建立：

```json
{
  "schema": "rsk.citation-join.v1",
  "manuscript_sha256": "SHA256_OF_EXACT_MANUSCRIPT_BYTES",
  "ref_slug_by_key": {"example2024": "paper-one"}
}
```

```text
python ADAPTER/research_citations.py --passport PASSPORT --manuscript MANUSCRIPT --join JOIN --work-dir ABSOLUTE_WORK --allow-metadata-network --output NEW_JSON_IN_WORK
```

只有任务允许向 Crossref、OpenAlex、Semantic Scholar、arXiv 查询元数据时才加网络选项。
核验前检查 corpus、稿件指纹和实际引用标记；缓存位于该工作目录。报告分别保留查到、
未匹配和无法解析的状态。该命令不核验正文内容支持、作者实际阅读或撤稿状态，也不
根据存在一个定位标记宣称已核对定位内容。需要这些检查时按相应源角色指导实际读取。
`--no-cache` 才绕过缓存；缺少真实正文映射不能改用 synthetic-ref-slug 作为正式证据。

## 研究与返修产物

原生筛选返回先用 `research_screening.py` 收集，再累计合并：

```text
python ADAPTER/research_screening.py collect --plan PLAN_JSON --label EXACT_PLANNED_LABEL --response ACTUAL_WORKER_JSON --actor-context-id ACTUAL_CONTEXT_ID
python ADAPTER/research_screening.py merge --work-dir SCREENING_WORK --stage ta --config SCREENING_CONFIG
```

上下文 ID 从真实子代理工具返回取得，不能让摘要内容或模型自述充当身份。该工具核对
提示词哈希，保留每轮实际返回、来源与字节校验，并把历史 A/B、裁决和 QC 输入共同
交给原合并器重建。不能只把最新 QC 文件传给原合并器，否则旧 A/B 结果不会出现在
重建快照里。收集器本身不调用模型，记录的调用方身份声明也不等于独立执行认证。

通过 run-local 使用下列已打包脚本，并从其 `--help` 取得准确参数：

| 任务 | ENGINE 内的入口 |
| --- | --- |
| 运行记录、阅读标记、主张与证据行 | `scripts/run_ledger.py`、`scripts/ars_mark_read.py`、`scripts/evidence_rows.py` |
| 结构锚点、作者决定、修改回放 | `scripts/ars_anchorize_draft.py`、`scripts/revision_roadmap.py`、`scripts/ars_apply_revision_patch.py` |
| 数值及引用保护、实验来源、复现选择 | `scripts/check_revision_token_conservation.py`、`scripts/check_experiment_provenance.py`、`scripts/check_repro_lock.py` |
| 多视角审稿记录与合成检查 | `scripts/review_panel_provenance.py`、`scripts/check_panel_synthesis.py` |
| 复审、委员会意见与论证变化处理 | `scripts/check_re_review_synthesis.py`、`scripts/check_committee_correspondence.py`、`scripts/claim_strength_drift_disposition.py` |
| 投稿包实际内容与当前策略核对 | `scripts/verify_submission_package.py` |
| 筛选导入、原生调度计划、合并及导出 | `sr-screener/scripts/prepare_records.py`、`build_workflow.py`、`merge_decisions.py`、`build_outputs.py` |

库接口和原生代理共同完成依赖模型判断的任务。`claim_audit_pipeline.py` 的检索与
判断回调要接入实际读取与判断，不能把空回调当作通过；claim-standing 的源 CLI
尚未接入实时 stance provider。当前模型审稿始终保持 NOT_CALIBRATED；校准研究可
运行，但源项目尚未接通的“将校准结果应用到实时审稿”不作为已实现能力。

跨模型核验按共享协议记录真实接收方、范围、模型和结果，使用当前可用的原生接口。
同一模型换角色不算跨模型。原平台钩子、启动器和实验执行器不是复制资源后就会
自动存在；按实际环境执行和报告。外部传输沿用本次有效授权，不重复询问已确认事项。
