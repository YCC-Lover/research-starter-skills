# 进阶实验、图表与证据

先读 [共享执行规则](../../research-starter-paper/references/advanced-research.md)。
以下角色与脚本位于总入口的 `resources/research-engine/`。

需要方法学论证时使用 `deep-research/agents/research_architect_agent.md`。
为每项主张建立实验来源：数据或材料身份、条件、过程、输出、分析方法、局限。
`planned_experiment_ids` 只表示计划，不能当作完成证据；`experiment_provenance`
中的路径与记录应能定位真实产物。对应完整性检查区分 aligned、overstated、
unsupported 和 insufficient，而不是把结构合格写成实验可信。

图表任务读取 `academic-paper/agents/visualization_agent.md` 与其相关指南。
真实数据图使用用户数据和可复现脚本；概念示意与真实测量区分。
可用图像理解工具时做可见内容和图注核对，未看图时不能声称 VLM 已验证。
元分析图来自实际效应量和计算结果，不由图像模型生成数值内容。

对代码实验使用明确获准的环境和数据，记录实际运行命令、依赖、随机性及输出。
完整运行的配置可用 repro_lock 描述，配置一致不保证逐位复现；只有实际重跑
才能报告重跑结果。不能因原工作流提到外部 experiment-agent，就假装已安装或已运行。

人体研究/敏感数据需要按当前机构与适用要求核验权限，研究伦理与数据保护分开。
模板、风险分析和机构导航不是伦理批准，也不能替代合法授权。
本模块已有 TG/DTG、材料表征和重复性检查继续使用，不被通用流程覆盖。
