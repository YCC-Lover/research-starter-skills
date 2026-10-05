# 参与完善

欢迎贡献真实场景、清晰的任务提示词、维护脚本和有依据的纠错。不要求先参与整套科研流程。

## 提交方式

1. Fork 或 clone 仓库，读取 [AGENTS.md](AGENTS.md) 及相关技能入口。
2. 将改动限定在对应场景、模块或工具；保留用户选择、证据边界与来源关系。
3. 执行下方校验，提交 Pull Request，说明输入、预期交付、实际变更及未验证部分。

~~~text
python -m pip install -r requirements-dev.txt
python scripts/validate_skills.py
python -O scripts/validate_skills.py
python -m unittest discover -s tests -v
~~~

本维护者的 Windows 中间产物与缓存按 AGENTS.md 放在 D/E，不批量删除。其他环境遵循其用户指令和允许的工作目录。新增图像需更新 docs/images/manifest.json，使用原创或明确有权公开的素材；不要复制原教程图片。

## 一个好的示例包含什么

- 具体任务、可公开的输入材料与工具条件。
- 可改写提示词和交付目标，或明确标注的手工输出示意。
- 数值、引用、读取范围、修改状态与权限方面的检查点。
- 合成数据、虚构意见、真实匿名案例与实际模型运行记录的明确区分。

真实案例只提交有权公开且充分脱敏的材料。不要上传未发表稿件、实验原始数据、个人信息、凭证或聊天日志。不能证明已运行的案例，不标为实测效果。

## 修改来源

方法论来源为 [Research-Starter-Kit](https://github.com/LAMDA-NeSy/Research-Starter-Kit)。修改提炼时记录教程、实际阅读范围和定位；新增来源未读全文时不得更新为已读。不把原创补充归因于原作者。

本仓库尚未增加整体许可或原创素材许可；公开可读不等于已经授予任意再分发权限。贡献前确认自己有权提交材料，发布范围见 [NOTICE.md](NOTICE.md)。不为 Star 数要求夸大效果、刷量、伪造案例或进行骚扰式推广。
