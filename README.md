# Research Starter Skills

[中文](README.md) · [English](README_EN.md) · [版本记录](CHANGELOG.md)

[![技能校验状态](https://github.com/YCC-Lover/research-starter-skills/actions/workflows/validate.yml/badge.svg)](https://github.com/YCC-Lover/research-starter-skills/actions/workflows/validate.yml)

**不知道从哪开始科研？从你手边的一句话、一份笔记开始。**

刚进课题组，没有系统学过科研，连该准备什么材料都不清楚？Research Starter Skills 会先利用你已有的信息，带你逐步形成研究问题、读懂论文、整理结果、修改章节，自动保存进度。**1 个总入口 + 6 个专业模块**，覆盖从科研起步到论文、返修与学术交流的具体任务。

先读 [Research-Starter-Kit](https://github.com/LAMDA-NeSy/Research-Starter-Kit) 的原创教程理解方法，再用本项目的 skills 处理自己的文献、笔记、数据和草稿：把阅读变成观点，把结果变成论证，把问题变成下一步。

**[下载最新版](https://github.com/YCC-Lover/research-starter-skills/releases/latest) · [开始安装](#三步开始) · [新手从这里开始](docs/BEGINNER.md) · [原教程学习路径](docs/LEARNING_PATH.md) · [看完整任务](examples/worked/README.md)**

**来源与致谢：** 科研方法源自 [LAMDA-NeSy/Research-Starter-Kit](https://github.com/LAMDA-NeSy/Research-Starter-Kit) 的全部 19 篇教程。感谢郭兰哲老师及陈煜旸、葛凌岳、张逸凯等同学的整理与分享；YCC-Lover 负责独立提炼、Codex 适配与扩展维护。[逐篇来源](skills/research-starter-paper/references/sources.md) · [归属与使用范围](NOTICE.md)

![Research Starter Skills：从研究问题到文献、写作、实验图表、审稿回复与学术交流](docs/images/workflow-product.png)

产品概念图由本项目使用 GPT-image 生成。[图像说明](docs/images/workflow-product.prompt.md) · [更多场景](examples/SHOWCASE.md)

## 用一次具体任务，感受它的价值

| 你手里有什么 | skill 帮你推进什么 | 你会拿到什么 |
| --- | --- | --- |
| 不知道提供什么，只有导师一句话 | 从眼前困难开始，只补关键材料，逐步完成一件事 | 问题卡、第一步行动、自动保存的项目进度 |
| 一个宽泛方向、有限时间和设备 | 比较候选问题，找到最有信息价值的验证 | 近期优先建议、研究问题、最小验证计划 |
| 几篇论文和零散阅读笔记 | 比较路线、条件与分歧，形成自己的观点 | 证据综合、可追溯索引、具体研究切口 |
| 一段引言或学位论文章节 | 重建论证，统一术语、数据版本和跨章关系 | 可替换正文、实质修改说明、联动清单 |
| 实验表格、TG/DTG 或表征结果 | 看清关键比较与指标权衡，组织图文表达 | 图方案、图注、结果与讨论、后续验证 |
| 多条审稿意见和修订记录 | 确定返修优先级，把回复对应到实际改稿 | 回复草稿、证据与位置联动表、行动顺序 |
| 开题、组会或答辩准备 | 一问一答地练习，针对你的原话反馈 | 更清楚的研究表达、改述练习、下一问 |

小任务直接给成果，复杂任务先理清材料；学习时讲方法、做练习，执行时处理文本和文件，检查时给出发现与建议。你可以随时切换，按自己的进度推进。

## 三步开始

### 1. 安装七个技能

在 [最新发布页](https://github.com/YCC-Lover/research-starter-skills/releases/latest) 下载 Assets 中的 `research-starter-skills-v<版本>.zip`，解压后在含 `catalog.json` 的目录运行：

~~~text
python scripts/install_skills.py
~~~

也可以使用 Git：

~~~text
git clone https://github.com/YCC-Lover/research-starter-skills.git
cd research-starter-skills
python scripts/install_skills.py
~~~

安装使用 Python 3.10+ 和标准库。技能默认放在 `$CODEX_HOME/skills`，未设置时放在 `~/.codex/skills`。七个目录保持同级，便于总入口协调各模块。[安装、更新与备份](docs/INSTALLATION.md)

### 2. 带上当前材料

新开 Codex 对话，附上一段草稿、一份记录或一篇论文。没有文件也没关系，先用自己的话说方向和眼前困难，不需要自己先整理完。[零材料起步](docs/BEGINNER.md) · [七套教学任务](examples/worked/README.md)

### 3. 说出你想完成的事

~~~text
使用 $research-starter-paper。
我刚读研，没系统学过科研，不知道该提供什么材料。
导师说先看看【用自己的话写方向】，带我做出下次组会能用的东西。
工作目录是【我的项目目录】，请自动保存进度。
~~~

~~~text
使用 $rsk-paper-writing。
请修改附件中的3.4讨论，先给可替换正文，
再列出需要联动修改的位置和关键依据。
~~~

~~~text
使用 $rsk-research-workflow，陪我练习开题问答。
根据我的回答给简短反馈，再追问一个问题。
~~~

已明确任务时可以直接点名小模块；希望先梳理方向时交给总入口。[19 个可直接改用的提示词](examples/README.md)

## 从自学到写作

**从方法走到实践。** 学习路径把原教程、具体任务、练习产出与自查连在一起。刚入门时，可以从对象、现象和可用资源开始；已有结果时，可以直接进入写作与分析。

**把零散材料连成论证。** 文献综合关注路线之间的关系，长文修改关注章节之间的依赖，返修关注意见、证据和稿件之间的对应。交付围绕你当前需要使用的成果展开。

**让下一步更明确。** 候选问题比较会解释取舍；实验建议会说明新增信息的价值；学习反馈会回到你的原句，并给一个可以完成的练习。

**进度不用自己反复整理。** 引导任务由代理保存关键回答、实际产物与下一步；新对话先读检查点、核对文件变化，再继续。已有笔记可以复用，只读任务和单段润色不强制建记录。[保存与接续](docs/BEGINNER.md#进度由代理保存)

**自然表达，保留你的声音。** 语言编辑支持作者样例、结构调整和26类表达复核，保护数值、引用、公式与专业含义。不同研究采用相应证据方式，定量实验、定性访谈、历史文本和理论证明不套同一模板。

## 总入口与六个模块

| Skill | 适合的任务 |
| --- | --- |
| [research-starter-paper](skills/research-starter-paper/SKILL.md) | 科研入门、跨阶段协作、材料梳理与接续 |
| [rsk-research-design](skills/rsk-research-design/SKILL.md) | 选题、候选问题比较、Idea、最小验证 |
| [rsk-literature](skills/rsk-literature/SKILL.md) | 检索、批判阅读、多文献综合、引用版本 |
| [rsk-paper-writing](skills/rsk-paper-writing/SKILL.md) | 引言、摘要、方法、结果讨论、学位论文一致性 |
| [rsk-experiments-figures](skills/rsk-experiments-figures/SKILL.md) | 实验比较、材料表征、图注、TG/DTG 数据检查 |
| [rsk-rebuttal](skills/rsk-rebuttal/SKILL.md) | 审稿回复、返修排序、稿件与证据联动 |
| [rsk-research-workflow](skills/rsk-research-workflow/SKILL.md) | 组会、参会交流、科研记录、开题与答辩演练 |

TG/DTG 模块还提供只读 CSV 检查与按实际温度网格计算导数的工具；`--derive` 使用环境中已有的 NumPy。[完整热分析任务](skills/rsk-experiments-figures/references/thermal-task.md)

## 看实际成果

[新手与表达任务验收](evals/guided/REPORT.md)记录从空白起步、跨对话接续、材料变化检查和文字编辑的实际答复；[完整教学任务](examples/worked/README.md)提供可自己练习的合成材料。保存成功、文件可用、事实边界和用户操作分别核对，不用一个总分代替体验。

这些记录是小规模合成任务验证，不承诺录用、通用于所有学科的效果或固定节省时间。自动保存只在当前任务中执行，不是后台监控；新对话仍需定位项目。[工程验收](docs/PROJECT_AUDIT.md)

## 自己使用，也可以继续改进

技能是可读、可编辑的 Markdown 文件。同机同一用户目录可由不同 Codex 账号继续使用；换机器或用户目录后重新安装即可。公开仓库可以 clone 或 fork，修改后通过自己的 GitHub 权限推送或提交 Pull Request。[协作说明](AGENTS.md)

已安装用户可先运行 `python scripts/install_skills.py --check` 查看版本与文件状态，再使用显式备份更新：

~~~text
python scripts/install_skills.py --update --backup-dir D:\Codex\work\research-starter-skills-backups
~~~

安装器保存版本和文件哈希；`--doctor` 提供只读环境诊断。数据解析、作图和 Word/PDF/LaTeX 交付按当前 Codex 环境中的工具完成。[详细验收](docs/INSTALLATION.md#安装后验收)

当前版本为 **v1.5.0**，来源固定于上游提交 `36ba390d153f5289308ec833e2b633c26b304a7b`。原教程归属、独立补充与发布范围见 [NOTICE.md](NOTICE.md)，引用信息见 [CITATION.cff](CITATION.cff)。

## 一起让科研起步更容易

从你正在卡住的一段文字、一张图或一次汇报开始，完成一个任务，再逐步拓展自己的科研方法。

觉得有帮助，欢迎 Star 收藏；也欢迎通过 [Issues](https://github.com/YCC-Lover/research-starter-skills/issues) 分享脱敏后的具体问题，通过 Pull Request 补充真实可复核的场景。[贡献指南](CONTRIBUTING.md)
