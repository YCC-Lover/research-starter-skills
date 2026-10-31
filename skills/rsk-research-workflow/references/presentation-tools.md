# 制作工具与执行边界

## 依赖与资源

核心依赖见 [requirements-presentations.txt](../assets/requirements-presentations.txt)，安装
到用户选定的独立环境，不在 skill 载入时自动安装。PDF、EPUB、Notebook、网页、
图片生成、TTS 与视频的附加依赖按对应源工具帮助检查；完整上游依赖表保存在运行时的
`requirements.txt`。不要为了一个普通 PPT 任务安装所有供应商 SDK 或修改全局环境。

准备工具将固定版本的完整 skill 资源展开到任务目录；不会复制仓库的展示工程，也不会
增加额外技能注册。资源包是可复现的压缩 JSON 源清单，逐文件保留原始 Git blob、
字节数和 SHA-256，包括图标/声音的第三方说明；打包不意味着已阅读或测试每一个资源。
重建命令为仓库 `scripts/vendor_presentation_engine.py --source PINNED_CHECKOUT`。

`verify` 检查包内容，`doctor` 只探测依赖，`prepare` 展开资源并运行原始署名检查；
三者都不运行模型、不生成汇报。准备收据记录实际路径、原始/适配后哈希与清理改动。
启动器为本次子进程配置运行时根目录和脚本导入路径，嵌套的来源转换工具不要求用户
手动设置 `PYTHONPATH`；用户已有的进程导入路径保留在其后，不修改系统变量。
若运行时被修改或不完整，保留原目录并选择新的任务目录，不自动覆盖或强行修复署名门。
版本更新需要沿用原科研项目时，可显式执行 `prepare --work-dir ABSOLUTE_WORK --refresh`：
重新从固定源包准备运行时，旧运行时不删除，旧收据归档；原项目和制稿材料不重置。

首次展开及显式 `prepare` 复查全部资源；连续工具调用重查代码、契约和署名文件，
不重复扫描上万张图标与媒体。需要确认完整素材未变时再次运行 `prepare`；源包完整性、
运行时代码检查和实际采用素材的视觉/来源核对是不同检查范围。

## 常用调用

先阅读选中工作流，从 `--help` 获取当前固定版本的准确参数；不要凭下表推断已经执行。
所有命令通过 `research_presentations.py run --work-dir ABSOLUTE_WORK TOOL -- ARGS`
调用，`TOOL` 是相对 `scripts/` 的路径。脚本输出的实际路径为准。

| 任务 | 工具 |
| --- | --- |
| 初始化、复制导入、来源转换 | `project_manager.py`、`source_to_md.py`、`source_to_md/ppt_to_md.py` |
| SVG 质量、原生数据基线、最终化 | `svg_quality_checker.py`、`stamp_native_fallbacks.py`、`finalize_svg.py` |
| 原生 PPTX 导出 | `svg_to_pptx.py`；数据级图表/表格加 `--native-charts-and-tables` |
| 保留原稿的 round-trip 导入/导出 | `pptx_to_svg.py SOURCE -o WORKSPACE --inheritance-mode both --roundtrip`，再 `svg_to_pptx.py WORKSPACE --roundtrip` |
| 模板分析、导入、预览、应用 | `pptx_intake.py`、`pptx_template_import.py`、`template_preview_pptx.py`、`apply_template.py` |
| 图表/图标及本地图片 | `visualization_recall.py`、`icon_sync.py`、`analyze_images.py`、`slice_images.py` |
| 公式、形状与布尔几何 | `latex_render.py`、`preset_shape_svg.py`、`shape_boolean_svg.py` |
| 讲稿拆分、效果与媒体整合 | `total_md_split.py`、`animation_config.py`、`narration_sync.py`、`video_subtitles.py`、`video_sound_mix.py` |
| 导出后包检查与正文回读 | `pptx_delivery_check.py OUTPUT.pptx`、`source_to_md/ppt_to_md.py OUTPUT.pptx -o NEW_READBACK.md` |

模板是“原稿保留编辑”还是“可复用模板创建”，由实际请求决定；导入脚本成功不代表
已经完成设计决定、结构声明或模板验证。`beautify_identity.py` 可核对逐页美化的不变量，
检查结果须与实际修改范围一致。

显式快速生成使用 `project_manager.py init NAME --quick-generate --dir BASE`。
普通流程的设计确认、spec/lock 与结构契约继续由原工作流管理；不能拿 Quick 的无锁
结果冒充完成了普通流程的门。创建模板同样保留其具体 Brand/Style/Layout/Deck 契约。

## 外部能力

`image_search.py`、`image_gen.py`、`notes_to_audio.py` 和网页转换要求本次任务有对应
授权，并加 `--allow-network`。联网许可不是服务可用性或费用保证；宿主原生图片工具
可优先使用。API 失败时保留实际状态与材料，不虚构已生成资源，不主动推荐赞助商。

交互式确认、设计复核或 SVG 预览服务只有任务确需时使用 `--allow-server`，限定本机
访问并管理实际进程。普通聊天确认可替代原宿主的专用确认页面，但不能伪造 UI 收据。
启动器本身不为任意脚本建立沙箱，尤其需核对输出路径、网页地址和外部媒体。

旁白可由用户提供音频，或在明确允许的服务上生成。`powerpoint_video.py` 的原生视频
导出需要实际 PowerPoint/平台支持；FFmpeg、字幕与声音合成也需要对应程序。未运行的
步骤明确未验证，不因为可执行帮助存在就保证服务、动画播放或最终 MP4 成功。

## 保留策略

源码打包字节不修改；展开时将可定位的 Python 文件清理调用替换为保留操作，并记录
每个改动文件的前后哈希。临时目录不会自动递归删除；被替换的中间文件/目录移入该
任务的 `.rsk-retained/`，原始路径和保留名称另存。原始署名、许可和执行门不被移除。
这不是对全部依赖副作用的审计或 OS 沙箱；运行时仍须执行当前用户的权限和文件约束。
不执行上游自更新器，不自动整理或清理用户项目，导入原件使用复制。

Windows 启动器只在当前 Python 进程中使用标准库的本地平台探测回退，避免不可达的
WMI 服务阻塞依赖导入；不修改系统服务、注册表或全局 Python。

镜像模板复用只改标题时，完全未变的公式模块不应因导入预览估宽被当成新增溢出。
对应适配绑定源检查器的准确字节，只在原型及依赖哈希全部吻合、根属性与全局样式/定义未变、模块的
全部文本/属性/结构与原型一致时保留其来源几何归属；改过的文字、公式或上下文仍检查。
这不证明原稿排版本来正确，也不豁免包结构、资源或新溢出，实际渲染仍须核对。

新稿未选择转场或动画配置时使用无转场；显式效果配置和原生往返稿件继续保留所选
运动。讲稿、旁白与视频各自按任务开启，不因安装工具就自动生成媒体。

保持已安装技能只读，最终文件保存到用户指定位置。只需要原始 PPTX 的只读诊断时，
不要擅自重建、填入模板、联网或覆盖原件。来源和各部分许可见 [说明](ppt-master-notices.md)。
