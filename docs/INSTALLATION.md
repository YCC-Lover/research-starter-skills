# 安装与更新

[首页](../README.md) · [首次练习](../examples/first-run/README.md) · [完整任务包](../examples/worked/README.md)

## 首次安装

准备 Python 3.10 或更新版本，下载并解压 [最新技能包](https://github.com/YCC-Lover/research-starter-skills/releases/latest)。在包含 `catalog.json` 的目录运行：

~~~text
python scripts/install_skills.py --dry-run
python scripts/install_skills.py
~~~

第一条预览路径与复制计划，第二条安装七个同级技能目录。安装脚本使用 Python 标准库。使用 Git 时：

~~~text
git clone https://github.com/YCC-Lover/research-starter-skills.git
cd research-starter-skills
python scripts/install_skills.py
~~~

默认目标为 `$CODEX_HOME/skills`；未设置 `CODEX_HOME` 时为 `~/.codex/skills`。也可用 `--dest <完整路径>` 选择其他用户目录。总入口通过相对路径选择六个模块，完整安装便于协作。

## 查看安装状态

~~~text
python scripts/install_skills.py --check
python scripts/install_skills.py --doctor
~~~

`--check` 比较实际文件，列出缺失、与当前包的差异及安装后的本地修改。缺失或修改时返回非零退出码，便于脚本判断。

| 字段 | 含义 |
| --- | --- |
| version | 当前来源包的版本 |
| installed_version | 安装收据记录的版本；旧安装未记录时为null |
| current | 包内文件与已安装副本的逐文件比较 |
| local_changes_since_install | 文件相对该次安装收据的变化 |
| receipt_status | 安装收据的记录状态 |

收据位于目标目录的 `.research-starter-skills-install.json`，保存版本和源文件哈希。用户附加文件保留。`--doctor` 在此基础上只读发现可选命令与Python模块，输出工具准备情况。

## 带备份更新

先获取新包或执行Git更新，再用 `--check` 查看差异。若自己改过同名技能文件，先比较并保留需要的自定义内容，然后运行：

~~~text
python scripts/install_skills.py --update --backup-dir D:\Codex\work\research-starter-skills-backups
~~~

更新前将所有待覆盖文件及安装收据复制到唯一的snapshot目录，随后复制包内同名文件；额外文件继续保留。更新是文件替换，自定义内容由使用者先比较并合并。

备份位置遵循自己的存储约定，保持与来源仓库、安装目标分开。本维护者使用D/E工作目录。安装器预检已有目录、路径链接、重解析点和待覆盖硬链接，遇到冲突给出错误。

复制涉及多个文件。遇到磁盘、权限或并发修改错误时，保留快照，先运行 `--check` 定位现状，再根据具体差异处理。更新期间保持目标目录稳定。

## 安装后验收

1. 查看安装输出，确认总入口与六个小skill已复制。
2. 运行 `--check` 核对版本和实际内容。
3. 新开Codex对话，选择 `$research-starter-paper` 或一个小模块。
4. 用 [首次引言练习](../examples/first-run/README.md) 或 [完整任务包](../examples/worked/README.md) 完成一个任务，按输入核对数字、来源、范围与交付。
5. 检查本次任务所需的文献读取、作图或文档工具，按实际结果继续。

同一用户目录中更换Codex账号后可继续使用已安装文件。换机器或用户目录时重新安装。GitHub读取公开仓库、Codex登录与仓库写入各自按对应权限工作；贡献可通过fork和Pull Request完成。

## 从输入到成果

v2.0.0 的进阶资源随七个技能一起复制，不再单独注册内部工作流。执行 Python 研究
辅助工具时，可在用户选定的环境中使用已安装总入口内的
`assets/requirements-research.txt`；发行仓库根目录的 `requirements-research.txt`
指向同一份依赖清单。普通文字指导不需要安装这些包。Windows 的研究事务和文件
绑定工具目前按 Python 3.13 验证，安装器仍只需 Python 3.10+。

代理按 [运行工具](../skills/research-starter-paper/references/runtime-helpers.md) 设置
任务内临时目录与缓存，按需运行本地检查或明确授权的联网核验。Pandoc、TeX、PDF
内容分类器与其他可选工具使用当前环境实际可用的版本，不在安装技能时自动下载安装。

学习与文字分析可以直接从提供的材料开始。按任务需要启用可用的检索、PDF读取、科学作图或Word/LaTeX导出工具。TG/DTG只读CSV检查提供显式的 `--derive` 导数计算选项，使用环境中已有的NumPy；Origin项目可经可用接口读取，或导出CSV/XLSX后分析。

[学习路径](LEARNING_PATH.md)连接原教程与实践；[对照实测](../evals/utility/REPORT.md)提供相同材料下两组实际交付，方便选择自己的第一个任务。

## 给项目贡献修改

修改 `skills/<名称>/SKILL.md` 及相关参考，保持来源映射和七模块布局。验证后更新已安装副本：

~~~text
python -m pip install -r requirements-dev.txt
python scripts/validate_skills.py
python -O scripts/validate_skills.py
python scripts/validate_behavior_eval.py
python -m unittest discover -s tests -v
~~~

工程检查验证包结构、来源映射、链接、安装和记录完整性；实际任务表现见相应评测轮次。[协作规则](../AGENTS.md)
