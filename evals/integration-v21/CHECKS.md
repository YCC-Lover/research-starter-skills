# Independent Check Review

Current captured execution only. Reviewer: independent Codex model worker, not a human subject-matter expert.

## G01

### G01 Check 01: 通过

从空白求助提出少量、易回答的关键信息请求，不要求用户先填写专业问卷。

Evidence (exact answer substring):

```text
现在只问一个问题：**导师让你摸索的方向是什么？**
```

首轮只问导师方向，允许用一句话或专业回答；没有要求新手填写专业问卷。

### G01 Check 02: 通过

补充后给历史学可用的问题卡或组会起步成果，不虚构报刊、引文、实验或文献空白。

Evidence (exact answer substring):

```text
在某地一份报刊的一段时期内，围绕一种卫生习惯，文章中的发言者凭什么理由要求哪些读者改变？
```

将卫生话语收窄到发言者、读者和劝说理由；实际起步卡保留待定史料范围，明确未检索、未取得原刊，不虚构报刊、引文或文献空白。

### G01 Check 03: 通过

实际自动保存事实、问题/回答、产物与下一步，而非只口头承诺。

Evidence (exact answer substring):

```text
加入候选问题、取材计划和一段组会说明，并保存了进度。
```

核对 artifacts-final 的4份检查点、progress.md及两份讨论卡，最终revision 4包含历史学事实、方向问题的已答状态、取材范围的未答状态、产物和条件式下一步；并非仅凭保存声明判定。

### G01 Check 04: 通过

全新上下文从项目文件继续，不要求重述已记录方向，不把计划当完成。

Evidence (exact answer substring):

```text
我已从项目记录接上：你研究的是近代地方报刊中的城市卫生话语
```

raw-resume的agent_id不同于前两轮，恢复回答和最终取材讨论卡复用已记方向，只继续未回答的城市/报纸范围；未将取材计划当作完成的试读。

## G02

### G02 Check 01: 通过

先询问关键方向或当前需要，不把“没有正式材料”当成无法帮助。

Evidence (exact answer substring):

```text
**导师给你的大方向是什么？**
```

首轮接受空inbox，直接形成准备稿，只询问关键方向，并允许尚未给方向的回答。

### G02 Check 02: 通过

形成适合教育学的可讨论问题，不把非正式聊天写成已获同意的研究访谈或总体因果证据。

Evidence (exact answer substring):

```text
聊天笔记暂不作为研究数据，不引用、不编码，也不称为正式访谈或预访谈
```

提出入组第一学期如何判断组会参与方式的教育学候选问题；明确非正式聊天不作研究数据，候选切入点不是聊天发现，不概括总体因果。

### G02 Check 03: 通过

实际自动保存事实与未知项，用户无需建模板或运行进度脚本。

Evidence (exact answer substring):

```text
已更新[组会问题卡]
```

artifacts-final的5份检查点、progress.md、起步卡及一分钟请教稿真实存在；revision 5保存教育学方向、同意边界、未确认候选切入点、已答/未答问题和下一步，未要求用户操作进度脚本。

### G02 Check 04: 通过

全新上下文利用保存的材料状态推进十分钟内的一步，不重复索要已经回答的背景。

Evidence (exact answer substring):

```text
十分钟内，读一遍、试讲两遍，只挑一句不贴合自己真实想法的话修改。
```

恢复轮使用新agent_id，承接教育学方向和候选问题，给十分钟内的试讲修改；最终稿将练习列为建议，未谎称已练习或已获导师认可，也未重索聊天笔记。

## G03

### G03 Check 01: 通过

不假称解析了Origin占位文件，指导取得可读导出，不要求用户先提供完整论文。

Evidence (exact answer substring):

```text
现有 `source.opju` 只有占位文字，没有可读的 TG 数据
```

实际131字节占位文件与固定合成输入一致。首轮没有假称解析Origin，转为请求带单位的CSV或Excel和已有条件，不要求完整论文。

### G03 Check 02: 通过

基于实际CSV给结果表达，区分高温残余与较低温失重，技术复测不充当独立样本。

Evidence (exact answer substring):

```text
但在300 ℃和400 ℃，处理组的平均剩余质量分别为94%和75.5%，低于未处理组的98%和78.5%
```

分别核算源CSV和更新CSV：800℃处理组均值由26%变为27%，低温差值仍为-4/-3个百分点。回答保留反方向观察，并明确T1跨日复测不是新增独立样品；未仅凭高温残余排名整体热稳定性。

### G03 Check 03: 通过

实际保存文件来源、进度和下一步，不编造显著性、交联或完成实验。

Evidence (exact answer substring):

```text
因此，现阶段可以描述为“800 ℃时处理组剩余质量较高”，不能据此认定发生交联或“热稳定性显著提高”。
```

最终实际文件含10份检查点、progress.md、源文件、教学稿及核对记录；revision 10保存来源哈希、当前结果、缺项及下一步，不编显著性、交联或完成实验。辅助CLI兼容性失败另行记录，不能据此称工具全部通过。

### G03 Check 04: 通过

新上下文发现CSV变化或重新读取更新值，不把旧端点27继续当作当前T2结果。

Evidence (exact answer substring):

```text
按当前原表，800℃时 T2 为29%，处理组均值应为27%，不是旧记录中的26%。
```

恢复轮为新agent_id，当前实际export.csv与thermal-updated.csv文本相等；mentor-update-20261031.md和revision 10采用29%、27%、7个百分点。旧稿和旧JSON仍保留旧数值，但当前稿及进度明确将其降为历史，不把27当当前T2。

## G04

### G04 Check 01: 通过

P01对应表达得到具体、自然且不丢有据事实的处理；有意义例外可保留。

Evidence (exact answer substring):

```text
P01 我们测了12个独立试样。
```

删去旅程比喻，完整保留12个独立试样这一有据事实。

### G04 Check 02: 通过

P02对应表达得到具体、自然且不丢有据事实的处理；有意义例外可保留。

Evidence (exact answer substring):

```text
P02 我们保存了原始曲线。
```

保留保存原始曲线的事实，移除无依据的进步评价。

### G04 Check 03: 通过

P03对应表达得到具体、自然且不丢有据事实的处理；有意义例外可保留。

Evidence (exact answer substring):

```text
P03 我们记录了温度。
```

去掉科研本质的泛化前言，留下实际记录动作。

### G04 Check 04: 通过

P04对应表达得到具体、自然且不丢有据事实的处理；有意义例外可保留。

Evidence (exact answer substring):

```text
P04 两组结果不同。
```

移除邀请探讨和提示读者的套语，保留组间不同的有限事实。

### G04 Check 05: 通过

P05对应表达得到具体、自然且不丢有据事实的处理；有意义例外可保留。

Evidence (exact answer substring):

```text
P05 我们明天核对原始记录。
```

删除与具体行动无关的反复否认，保留明天核对记录的计划。

### G04 Check 06: 通过

P06对应表达得到具体、自然且不丢有据事实的处理；有意义例外可保留。

Evidence (exact answer substring):

```text
P06 这个方案把记录集中到了同一个文件。
```

以记录集中到一个文件的具体功能替代同义赞词堆叠。

### G04 Check 07: 通过

P07对应表达得到具体、自然且不丢有据事实的处理；有意义例外可保留。

Evidence (exact answer substring):

```text
P07 我们记录了日期和条件，并保存了表格。
```

合并重复主语，保留日期、条件、保存表格三个动作。

### G04 Check 08: 通过

P08对应表达得到具体、自然且不丢有据事实的处理；有意义例外可保留。

Evidence (exact answer substring):

```text
P08 我们先看曲线，再看条件，最后写出结论。
```

将连续破折号改为自然顺序连接，未改动作次序或提前承诺结论正确。

### G04 Check 09: 通过

P09对应表达得到具体、自然且不丢有据事实的处理；有意义例外可保留。

Evidence (exact answer substring):

```text
P09 在某些情况下，这个变化可能与条件有关。
```

删去多层重复模糊词，仍保留某些情况下和可能两个范围/确定程度限制。

### G04 Check 10: 通过

P10对应表达得到具体、自然且不丢有据事实的处理；有意义例外可保留。

Evidence (exact answer substring):

```text
P10 The report is high quality, and the process is well documented.
```

保留原有评价和过程记录表述，将表语中的连字符改为自然英文用法；未添加质量分数或新事实。

### G04 Check 11: 通过

P11对应表达得到具体、自然且不丢有据事实的处理；有意义例外可保留。

Evidence (exact answer substring):

```text
P11 No configuration file is needed. The results are saved automatically.
```

补全缺失谓语，用saved替代生硬preserved，同时保留无需配置和自动保存的原意。

### G04 Check 12: 无法确认

P12对应表达得到具体、自然且不丢有据事实的处理；有意义例外可保留。

Evidence (exact answer substring):

```text
P12 本研究分析了复杂交互，强调记录条件的重要性。
```

虽删去深入剖析、丰富图景和充分彰显，仍没有说明哪些对象如何交互，复杂交互及重要性仍空泛；合成输入也无足够细节可安全补写，不能确认达到具体自然的要求。

### G04 Check 13: 通过

P13对应表达得到具体、自然且不丢有据事实的处理；有意义例外可保留。

Evidence (exact answer substring):

```text
P13 我们建立了一个记录表。
```

留下可检查的建立记录表，删除卓越里程碑和光明未来的无据夸赞。

### G04 Check 14: 通过

P14对应表达得到具体、自然且不丢有据事实的处理；有意义例外可保留。

Evidence (exact answer substring):

```text
P14 她负责每周汇总实验记录。
```

以原文已有的具体职责替代含糊关系，保留人物、周期和记录任务。

### G04 Check 15: 通过

P15对应表达得到具体、自然且不丢有据事实的处理；有意义例外可保留。

Evidence (exact answer substring):

```text
P15 表格有蓝色和绿色两列。
```

保留列数和颜色，删除没有依据的象征解释。

### G04 Check 16: 通过

P16对应表达得到具体、自然且不丢有据事实的处理；有意义例外可保留。

Evidence (exact answer substring):

```text
P16 这个记录工具可以保存文本。
```

移除惊叹和声誉评价，仅保留已给定功能。

### G04 Check 17: 通过

P17对应表达得到具体、自然且不丢有据事实的处理；有意义例外可保留。

Evidence (exact answer substring):

```text
P17 现有材料没有提供专家姓名或评估记录，不能据此判断方案效果。
```

删除无来源的专家共识，明确材料不足的判断边界，未补造权威。

### G04 Check 18: 通过

P18对应表达得到具体、自然且不丢有据事实的处理；有意义例外可保留。

Evidence (exact answer substring):

```text
P18 The folder is for notes and contains three files.
```

用直接的is for和contains替代绕述与夸张动词，保留笔记用途和三个文件。

### G04 Check 19: 通过

P19对应表达得到具体、自然且不丢有据事实的处理；有意义例外可保留。

Evidence (exact answer substring):

```text
P19 记录已保存，条件还没核对。
```

去掉重复加粗标签，以简洁并列句保留已完成与未完成的区别。

### G04 Check 20: 通过

P20对应表达得到具体、自然且不丢有据事实的处理；有意义例外可保留。

Evidence (exact answer substring):

```text
P20
## 下一步安排
项目周五讨论下一步。
```

将夸大标题改为贴合内容的下一步安排，保留周五讨论的事实。

### G04 Check 21: 通过

P21对应表达得到具体、自然且不丢有据事实的处理；有意义例外可保留。

Evidence (exact answer substring):

```text
P21 He said "the file is ready".
```

按用户指定的目标格式使用英文直引号，保留原句内容；本例并非改动引文原件。

### G04 Check 22: 通过

P22对应表达得到具体、自然且不丢有据事实的处理；有意义例外可保留。

Evidence (exact answer substring):

```text
P22 本次只整理了笔记。
```

删除问候、赞许和继续邀请，只留下本次工作的范围。

### G04 Check 23: 通过

P23对应表达得到具体、自然且不丢有据事实的处理；有意义例外可保留。

Evidence (exact answer substring):

```text
P23 材料未提供这项工作的开始时间。
```

移除凭训练更新推测的1990年代，没有将未知时间改写为确定事实。

### G04 Check 24: 通过

P24对应表达得到具体、自然且不丢有据事实的处理；有意义例外可保留。

Evidence (exact answer substring):

```text
P24
## 记录
我们把原始曲线放在项目目录。
```

保留记录标题和曲线存放事实，删除无具体信息的重要性评价。

### G04 Check 25: 通过

P25对应表达得到具体、自然且不丢有据事实的处理；有意义例外可保留。

Evidence (exact answer substring):

```text
P25 记录已保存，条件待核对。
```

删去介绍本文/表格的元话语，保留记录和条件的不同完成状态。

### G04 Check 26: 通过

P26对应表达得到具体、自然且不丢有据事实的处理；有意义例外可保留。

Evidence (exact answer substring):

```text
P26 今天先请师兄补条件。
```

直接回答今天先做什么，未重复对方已知背景，也未声称条件已经补齐。

### G04 Check 27: 通过

保留作者简洁语气，未编数据、人物经历、引用、因果或权威。

Evidence (exact answer substring):

```text
P17 现有材料没有提供专家姓名或评估记录，不能据此判断方案效果。
```

逐一对照26段输入：保留简洁语气、有据数值和动作，删去无来源权威及时间推测，未新编数据、经历、引用或因果；P12具体性不足单列，不能用此项掩盖。

### G04 Check 28: 通过

按请求给26段最终稿，不添加AI检测分数或规避承诺。

Evidence (exact answer substring):

```text
P26 今天先请师兄补条件。
```

当前raw回答恰有按序P01至P26最终稿，没有编辑过程、AI检测分数或规避检测承诺。

## G05

### G05 Check 01: 通过

真实修改指定文件正文，而不只给泛化建议；对比原文有适当表达改善。

Evidence (exact answer substring):

```text
删去两句空泛评价，微调措辞，保留简洁语气。
```

核对固定源draft、执行保留的before.md、实际目标draft和artifacts-final：目标确实删去深度探索及充分彰显两句，并将这个观察改为这一观察，不是只给建议。

### G05 Check 02: 通过

YAML、代码、链接目标、引用键、公式与数字保持，保护检查无未经授权变化。

Evidence (exact answer substring):

```text
已核对数值、公式、代码、引用和元数据均未改动
```

实际执行当前check_prose_edit.py比较源draft与实际目标，protected_spans_unchanged=true、changes=[]；另核对before与源输入文本相同，目标与实际捕获hash相等。保护检查有词法范围限制，不能替代语义判断。

### G05 Check 03: 通过

保留不确定性、否定与量词，不把未验证交联写成已证实。

Evidence (exact answer substring):

```text
保留简洁语气。
```

实际目标保留可能与条件有关、未证明因果、尚未验证交联机制，以及全称公式和不能改成存在量词的限制，未提高确定程度。此证据引自简报，判断本身以实际目标正文为准。

### G05 Check 04: 通过

指定文件中只写最终正文并简报，不新建科研进度、不向用户交付双份草稿；允许已授权中间位置保留保护备份与候选稿。

Evidence (exact answer substring):

```text
未另建科研记录。
```

实际项目及artifacts-final均只有inbox/draft.md，文件内仅最终正文。保护备份before.md和候选稿candidate.md位于已授权项目之外的本轮中间目录，不是双份用户交付；未创建进度目录。

## G06

### G06 Check 01: 通过

给一段自然、礼貌、有实际内容的回复，不残留夸大套话。

Evidence (exact answer substring):

```text
感谢审稿人的提醒。原稿采用随机划分
```

给出一个连贯、礼貌且有具体划分问题内容的回复段落，未保留新篇章、迈向卓越等夸大套话。

### G06 Check 02: 通过

保留80/23、95/92与单次81/80的状态，不编造公平调参、显著性或已修改定位。

Evidence (exact answer substring):

```text
总计80个器件中，有23个同时出现在训练集和测试集中
```

对照当前合成输入，80/23、随机95/92、单次按器件分离81/80均保留；未把单次初试写成公平调参或显著稳定领先，也未造页码。

### G06 Check 03: 通过

明确问题与待办，不把计划包装为已完成，不保证接受。

Evidence (exact answer substring):

```text
目前原稿尚未修改
```

明确原稿未改、公平调参和重复评估待完成，将修订放在后续，没有承诺接受。

### G06 Check 04: 通过

遵守不改文件、不保存进度、只给成稿的范围。

Evidence (exact answer substring):

```text
并据此修订稿件中的相关表述。
```

实际raw只含请求的一段成稿，目标项目与artifacts-final文件清单为空，未写科研进度；该句是未来修订而非声称已操作文件。

## G07

### G07 Check 01: 通过

形成围绕共同问题的综合段落，而非逐篇摘要。

Evidence (exact answer substring):

```text
随机划分下的分数提升，能否转化为跨器件泛化和长期使用中的稳定表现？
```

以评估增益是否跨器件及长期稳定为共同问题，交叉联系A/D、B和C/E，不是按每篇孤立念摘要。

### G07 Check 02: 通过

A0/A1视为同一工作并指出条件和版本变化，不将差异全归因于划分。

Evidence (exact answer substring):

```text
但器件数也有更新，因此不能把前后差异全部归因于划分方式。
```

明确A0/A1为同一工作不同版本，以A1为当前依据，不双计证据；保留器件数和划分共同变化的混杂限制。

### G07 Check 03: 通过

保留D负面结果，B跨数据集不能按绝对分数排名，综述不算新实验。

Evidence (exact answer substring):

```text
结合D中数据增强只改善随机划分、未改善留出器件表现的结果
```

保留D负面结果；B没有共同基线不能与R绝对排名，C校准只部分恢复不证化学机制，E只作讨论框架不计新实验。

### G07 Check 04: 通过

给具体下一步，不虚构全文阅读、引用或机制。

Evidence (exact answer substring):

```text
先用现有片段完成一张“版本与可比性核对表”
```

下一步明确表格及其字段，将未提供与研究未做区分，承认全部为虚构片段且不存在全文，未虚构引用或全文阅读。实际项目无新文件，下一步仍为计划。

## G08

### G08 Check 01: 通过

先提出一个实际检查论证的问题并等待，不提前泄漏完整答案。

Evidence (exact answer substring):

```text
你会如何利用 n 与常数项 41 的整除关系，检查这个“对所有非负整数 n”成立的命题？
```

首轮只提出一个整除关系检验问题，没有给出反例值、分解式或完整答案，随后同一上下文接收学生回答。

### G08 Check 02: 通过

反馈针对学生把三个例子当一般证明的原话，解释量词与举例的差别。

Evidence (exact answer substring):

```text
但“所以应该已经证完了”这一步缺少依据：三个特例成立，不能排除其他 n 使表达式成为合数。
```

准确引用学生的已证完说法，肯定前三例算对但解释三个特例不能推出所有非负整数的全称断言。

### G08 Check 03: 通过

给有效的检验或反例（例如n=40时1681=41平方），不把有限检验当证明。

Evidence (exact answer substring):

```text
取 n=41，你能通过提取公因子，判断 n²+n+41 是否为质数吗？
```

给出有效可操作的反例检验，不必固定采用示例n=40。独立算术核对41²+41+41=1763=41×43，为合数；回答没有把有限检验当全称证明，也未提前代做学生下一步。

### G08 Check 04: 通过

继续一个适量练习，不写文件、不把演练当真实科研结论。

Evidence (exact answer substring):

```text
下一问：取 n=41
```

反馈后只追加一个适量的提公因子练习，保持组会模拟语境。实际项目及artifacts-final均无文件，未将虚构练习声称为真实科研结论。
