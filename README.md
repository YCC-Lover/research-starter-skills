# Research Starter Skills

用于 Codex 的科研与论文写作技能包。独立提炼 [LAMDA-NeSy/Research-Starter-Kit](https://github.com/LAMDA-NeSy/Research-Starter-Kit) 固定版本的 README 与全部 19 篇教程，提供一个总入口和六个可独立调用的小 skill。

这是非官方整理版，不包含原始 PDF、飞书登录信息、用户论文或实验数据。来源、适用性改写与逐篇映射保存在各 skill 的 `references/` 中。

## 技能目录

| Skill | 用途 | 原教程 |
| --- | --- | --- |
| [research-starter-paper](skills/research-starter-paper/SKILL.md) | 跨阶段科研与论文任务的总入口 | 01-19 |
| [rsk-research-design](skills/rsk-research-design/SKILL.md) | 选题、问题、Idea、最小验证 | 01、04 |
| [rsk-literature](skills/rsk-literature/SKILL.md) | 找论文、读论文、引用与 BibTeX | 02、03、15 |
| [rsk-paper-writing](skills/rsk-paper-writing/SKILL.md) | 大纲、摘要、引言、相关工作、方法 | 08、10-13 |
| [rsk-experiments-figures](skills/rsk-experiments-figures/SKILL.md) | 实验设计、结果分析、论文图表 | 09、14 |
| [rsk-rebuttal](skills/rsk-rebuttal/SKILL.md) | 审稿回复与返修 | 16 |
| [rsk-research-workflow](skills/rsk-research-workflow/SKILL.md) | 汇报、meeting、参会、日志、资助、AI 协作 | 05-07、17-19 |

## 安装

本地安装仅需 Python 3.10 或更新版本，不需要额外 Python 包。

```text
git clone https://github.com/YCC-Lover/research-starter-skills.git
cd research-starter-skills
python scripts/install_skills.py
```

默认安装到 `$CODEX_HOME/skills`；未设置 `CODEX_HOME` 时使用 `~/.codex/skills`。可用 `--dest <完整目录>` 指定另一个 Codex 用户目录。安装后在后续 Codex 对话中使用技能名称。

也可以在支持内置 `skill-installer` 的 Codex 中提出：

```text
请从 https://github.com/YCC-Lover/research-starter-skills 安装 skills/ 下全部七个 skill。
```

总入口需要六个小 skill 位于同级目录；建议一起安装。已有同名目录时，默认拒绝覆盖，不会删除任何文件。

## 使用

```text
使用 $research-starter-paper，根据我的研究材料整理论文论证和写作计划。
使用 $rsk-paper-writing，修改我的引言，不改变事实和引用。
使用 $rsk-experiments-figures，根据真实数据检查实验分析和图表。
使用 $rsk-research-workflow，准备会议介绍、提问和会后跟进草稿。
```

技能区分已完成结果、假设和计划，不编造数据、引用、机制、审稿意见或已完成修改。原文中 AI 领域案例、句数、介绍时长、旧工具命令和资助条件都有适用说明，不能覆盖当前用户指令或投稿规范。

## 不同 Codex 账号

技能是文件，不绑定某个 Codex 账号。同机同一用户目录可继续使用；不同机器或用户目录需要重新安装。公开仓库可以直接读取，也可以 fork 或 clone 后让另一个 Codex 账号打开项目并按 [AGENTS.md](AGENTS.md) 修改。

Codex 登录与 GitHub 写入权限是两回事。推送到本仓库需要 GitHub 仓库的写权限；没有写权限时，可在自己的 fork 中修改并提交 Pull Request。不会把本机凭证、账号会话或 Codex 聊天随仓库发布。

## 修改与更新

修改 `skills/<名称>/SKILL.md` 和对应参考文件。来源变化时更新提炼位置与真实阅读状态，不能只改变覆盖数字。开发验证：

```text
python -m pip install -r requirements-dev.txt
python scripts/validate_skills.py
python -m unittest discover -s tests -v
```

自动检查覆盖格式、链接、映射、安装行为和隐私，不替代原文人工核对。安装更新需要显式指定备份目录：

```text
python scripts/install_skills.py --update --backup-dir D:\Codex\work\research-starter-skills-backups
```

该操作备份将被覆盖的文件，保留目标目录中的其他文件，不批量删除旧文件。Git 更新或 skill 修改不会自动同步已安装副本，验证后重新执行安装更新。

## 版本与来源

首版为 `v1.0.0`；以 [catalog.json](catalog.json) 中的版本为准。可在 GitHub Releases 下载技能包或选择对应 tag，以固定版本安装。

覆盖对应上游提交 `36ba390d153f5289308ec833e2b633c26b304a7b`。外部致谢资料仅保留出处关系，未声称阅读其中的整本书。[完整来源表](skills/research-starter-paper/references/sources.md) 与 [NOTICE.md](NOTICE.md) 说明作者归属和发布范围。

上游固定版本没有 LICENSE/COPYING 文件。此仓库不将上游标为 MIT 等许可，也不授予原教程、图片或品牌资产的转载权。
