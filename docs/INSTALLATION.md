# 安装、检查与安全更新

[返回首页](../README.md)

安装脚本仅需 Python 3.10 或更新版本，使用标准库。开发校验才需要 requirements-dev.txt；可选展示作图才需要 requirements-showcase.txt。

## 安装七个同级技能

~~~text
python scripts/install_skills.py
~~~

默认位置为 CODEX_HOME/skills，未设置时为用户目录下的 .codex/skills。也可以显式指定：

~~~text
python scripts/install_skills.py --dest D:\Codex\profiles\another\skills
~~~

总入口通过同级路径读取六个模块，建议整个技能包一起安装。公开仓库中的 AGENTS.md 是维护指南，不会自动变成本机所有科研项目的全局指令。

## 先预览，再写入

~~~text
python scripts/install_skills.py --dry-run
~~~

预览也执行源目录、目标路径与冲突检查，但不创建目录、不复制文件、不创建备份。已有同名目录时，应先检查现状或使用明确的更新选项。

## 对比已安装内容

~~~text
python scripts/install_skills.py --check
~~~

该命令只读取文件，报告缺失、修改和与当前技能包一致的状态。检查的是文件内容，不把“目录存在”当作版本一致；用户附加文件不视为错误。缺失或修改时返回非零退出码，便于脚本使用。本地自定义也会列为修改，不代表它一定有问题。

## 更新与备份

~~~text
python scripts/install_skills.py --update --backup-dir D:\Codex\work\rsk-backups --dry-run
python scripts/install_skills.py --update --backup-dir D:\Codex\work\rsk-backups
~~~

将被覆盖的文件先复制到独立快照，用户额外文件保留，不自动删除旧文件。备份目录不能与源仓库或安装目录重叠；Windows 备份不能放在 C 盘。链接目录、重解析点以及待覆盖的硬链接文件会被拒绝，防止意外写入别处。

安装不宣称跨多个文件的原子事务。若磁盘、权限或文件在复制中改变而失败，应先用 --check 定位状态，保留已有备份，不自动删除或回滚用户文件。不要同时修改目标目录。

## 换 Codex 账号

技能是本地文件，不绑定 Codex 账号。同机同一技能目录可继续使用；另一台机器或不同用户目录需重新安装。安装后在新对话中直接点名技能；若没有发现，重开对话或重启 Codex，并核对当前 CODEX_HOME 与 --dest 是否一致。

GitHub 的写入权限单独管理。没有本仓库写权限时，可以在自己的 fork 修改并提交 Pull Request，不应共享密码、token 或聊天会话。
