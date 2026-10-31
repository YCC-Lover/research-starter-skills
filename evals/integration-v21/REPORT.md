# 2.1.0 独立合成回归审阅

日期：2026-10-31。运行标识：`2026-10-31-v2.1.0-guided-regression`。

这是无对照组、每例一次的小规模合成回归记录，不代表普遍效率或真实科研准确率。独立模型 worker 审阅，非人类专家评审；未宣称跨模型家族盲评。本次整理没有重跑模型，也没有读取旧答案或旧 judgments 作为新结果。

## 范围与结论

以 `evals/guided/cases.json` 的 8 例、56 项为固定检查表，逐项对照当前 `behavior-v21` 的真实模型回答、合成源输入和实际 `artifacts-final`。归档共 15 个回答轮次、11 个执行上下文、38 个最终项目文件。

| Case | 检查项 | 通过 | 不通过 | 无法确认 | 最终项目文件 |
| --- | ---: | ---: | ---: | ---: | ---: |
| G01 历史学起步与恢复 | 4 | 4 | 0 | 0 | 8 |
| G02 教育学起步与恢复 | 4 | 4 | 0 | 0 | 9 |
| G03 TG 输入变化与恢复 | 4 | 4 | 0 | 0 | 20 |
| G04 26 段表达编辑 | 28 | 27 | 0 | 1 | 0 |
| G05 指定文件编辑 | 4 | 4 | 0 | 0 | 1 |
| G06 审稿回复 | 4 | 4 | 0 | 0 | 0 |
| G07 文献片段综合 | 4 | 4 | 0 | 0 | 0 |
| G08 学生答问演练 | 4 | 4 | 0 | 0 | 0 |
| 合计 | 56 | 55 | 0 | 1 | 38 |

状态：`reviewed-with-unconfirmed-check`，不是全通过。56 项内没有判为“不通过”的项目，但有以下明确未满足及失败记录：

- G04 第 12 项（P12）“无法确认”：回答为“本研究分析了复杂交互，强调记录条件的重要性。”仍未说明交互的对象和关系，残留空泛表达。合成输入没有足够细节，不能补造具体机制后宣称通过。
- 检查表外 `thermal-checker-help`“不通过”：只读执行热分析脚本的 `--help`，在 Python 3.13.13 下退出码为 1，错误为 `ValueError: unsupported format character ')' (0x29) at index 29`。当前帮助文字中的 `%` 触发格式化错误。G03 捕获笔记提到 Python 3.14，本次复现仅声称实际记录的 3.13.13 环境，不据此推定所有版本。未修改生产脚本。

每项判断、原检查文本、回答中的真实子串引文和理由见 [CHECKS.md](CHECKS.md)；机器记录见 [results.json](results.json)。工具失败没有计入或冲淡固定 56 项，也没有被完整性校验成功掩盖。

## 实际文件与上下文

- G01/G02/G03 的 initial 与 followup 分别复用各自同一上下文，resume 均使用不同的实际 `agent_id`；各 case 之间没有复用上下文。G08 学生回答与首轮保持同一实际上下文。
- 15 份当前 raw-envelope 的 `raw_response` 解码后均与 `response` 相等。归档轮次保留真实上下文 ID，而非另造 fresh/resume 标签代替执行记录。
- G01/G02 实际检查点、进度索引和讨论稿保存了已知事实、未知项、已答/待答问题、产物与下一步，恢复后没有重复索要已答背景。
- G03 当前实际 CSV 与 `thermal-updated.csv` 相等。恢复后 T2 为 29%，处理组均值为 27%，相对未处理组为 7 个百分点；300/400 摄氏度的反向观察和技术复测边界保留。当前稿为 `mentor-update-20261031.md`，最终 revision 10 与之对应。
- G03 的旧稿、旧核对笔记和旧 JSON 仍保留 27%/26%/6 个百分点等旧值。没有重写这些文件；当前稿及进度明确标注它们不是当前数值依据，不能把旧 JSON 当作已更新结果。
- G05 用当前 `check_prose_edit.py` 比较实际源 draft 与实际目标 draft，结果 `protected_spans_unchanged=true`、`changes=[]`、退出码 0；执行保留的 `before.md` 与源输入文本相同，候选稿与实际目标文本相同。语义复核确认不确定性、否定、交联未验证和全称量词均保留。
- G05 实际项目只有 `inbox/draft.md`，没有进度目录或第二份交付稿。保护备份和候选稿保存在已授权的项目外中间位置，不算用户项目中的新增文件。
- G06/G08 的最终项目文件清单为空。G08 的 n=41 检验有效：1763=41×43；这是独立算术核对，不是将该分解式伪装成模型原回答。

38 个最终项目文件的实际字节数和原始 SHA-256 均与捕获相等；公开捕获文本另有归一化后的文本 hash。详见 [artifacts](artifacts)、[execution-manifest.json](execution-manifest.json) 和 [deterministic-checks.json](deterministic-checks.json)。

## 冻结来源

[sources.json](sources.json) 的 104 份 skill 文本直接取自 `behavior-v21/pre-run-skill-snapshot.json`，逐份验证原有 SHA-256，未用当前源码重抓或刷新旧 hash。当前固定合成输入归档为独立 `inputs`；首轮请求与 `prepared.json` 相等，实际请求仅替换了项目占位符。

8 例实际报告读取的 skill 引用与 `case.dependencies` 的并集为 26 个文件，均与当前源码文本逐字相等。读取列表来自当前模型 envelope 的自报引用，不是独立完整工具轨迹；依赖列入核对不表示模型实际读取了每个依赖。

执行后有以下 5 份冻结来源发生变化，冻结文本及旧 hash 原样保留，当前 hash 与受影响 case 列表另记于 [source-audit.json](source-audit.json)：

- `skills/rsk-research-workflow/references/ppt-master-notices.md`
- `skills/rsk-research-workflow/references/presentation-tools.md`
- `skills/rsk-research-workflow/scripts/presentation_retention.py`
- `skills/rsk-research-workflow/scripts/presentation_source.py`
- `skills/rsk-research-workflow/scripts/research_presentations.py`

这些变化不在 8 例实际读取引用或依赖中，受影响的已选 case 数为 0。该事实不表示这些新版演示代码已经被本轮验证；八例也不覆盖 PPTX 导出、复杂演示交互或资源归档引擎行为。冻结快照本身不包含 resource archives。

## 溯源与公开边界

原始 raw-envelope 本地留存，不放入公开仓库。公开记录只含当前回答的路径归一化版本、上下文 ID 和原始 envelope 字节 hash。本机项目、仓库与辅助目录前缀统一替换为 `{{project}}`、`{{package}}`、`{{run}}`、`{{work}}`，包含嵌套 JSON 中转义的 Windows 路径；没有将 hash 改算成归一化正文的 hash。

`AGENTS.md`、`catalog.json` 的读取自报保留在执行清单，不能放进校验器仅接受 `skills/` 的 `references_read`。二者未被执行前 skill 快照冻结，执行时文本是否与当前相同无法追溯确认，不以当前 hash 冒充执行前证据。G04/G06 的非 skill 输入引用可与已归档合成输入核对。没有引入用户私材或非正式聊天笔记正文。

初始用户请求有 `prepared.json` 可核对；followup/resume/学生请求按固定 fixture 归档以符合校验 schema。当前 raw-envelope 没有独立保存派发的用户消息或完整工具调用轨迹，因此不能将 schema 一致性扩张为对此类缺失轨迹的独立证明。

## 索引与校验

旧 6 个 run 全部标为 historical，唯一 current 为本轮运行；旧 12 份 report/sources 以字节 hash 核验未改。未读取旧判断用于本轮评分。

`scripts/validate_behavior_eval.py` 普通模式及 `-O` 模式均退出码 0：当前 8 例齐全、无缺项、受影响 case 为 0；包含历史的全索引为 46 个 case 记录、80 份 response 记录，数量均与预期相等。`validate_skills.py` 普通模式及 `-O` 模式也均退出码 0。完整输出和独立复核见 [validation.json](validation.json)。

额外独立复核确认 56 项 evidence 均直接出现在各自当前 raw 回答中，15 份 raw-envelope、38 个实际文件、104 份冻结源码及历史 12 份归档的 hash 均对应。公开文件扫描未发现本机项目或仓库前缀泄漏。

完整性校验检查证据子串、上下文形状、来源快照及当前依赖影响，不评定模型准确率。通过不消除 P12 的无法确认或辅助 CLI 的失败；资源引擎内容校验也不等于执行验证。

本次只整理获准的评测归档和索引，未改生产代码、测试或 README；未运行会重跑模型的流程，也未运行整个生产测试套件。
