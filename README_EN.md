# Research Starter Skills

[中文](README.md) · [English](README_EN.md) · [Changelog](CHANGELOG.md)

**Start research with the material you have, even one sentence.**

New to research and unsure what to provide? Start with your supervisor's words, one note, or your current difficulty. One router and six focused skills guide a manageable next step, create a usable deliverable, and save progress in your authorized project. Continue through reading, writing, analysis, revision and academic communication as needed.

Learn the methods from [Research-Starter-Kit](https://github.com/LAMDA-NeSy/Research-Starter-Kit), then apply them to your own project with these skills.

**[Download](https://github.com/YCC-Lover/research-starter-skills/releases/latest) · [Beginner start](docs/BEGINNER.md) · [Learning path](docs/LEARNING_PATH.md) · [Complete task packs](examples/worked/README.md)**

**Origin and thanks:** The methods come from all 19 tutorials in LAMDA-NeSy/Research-Starter-Kit. Thanks to Guo Lanzhe, Chen Yuyang, Ge Lingyue, Zhang Yikai and the other contributors. YCC-Lover independently distills, adapts, extends and maintains this Codex skill bundle. [Sources](skills/research-starter-paper/references/sources.md) · [Attribution and usage scope](NOTICE.md)

![Research Starter Skills: a router and six focused research modules](docs/images/workflow-product.png)

Product concept image generated with GPT-image. [Image notes](docs/images/workflow-product.prompt.md)

## What you can get done

| Bring | Work toward | Take away |
| --- | --- | --- |
| No organized material yet | Identify one useful next step | A question card, minimal material request and saved progress |
| A broad topic and limited resources | Choose a useful research question | A conditional priority and minimum informative test |
| Papers and reading notes | Connect methods, evidence and disagreements | A synthesis, traceable evidence and a concrete research angle |
| An introduction or thesis chapter | Strengthen the argument and align versions | Replacement prose, substantive edits and linked changes |
| Experimental tables and measurements | Explain comparisons and trade-offs | A figure plan, caption, results text and next measurement |
| Reviewer comments and revision records | Prioritize and coordinate revisions | A reply draft, evidence map and actionable sequence |
| A presentation or defense | Practice one question at a time | Feedback on your words and a focused next question |

Ask to learn for an explanation and practice, ask for a deliverable to work directly on it, or request review for findings and recommendations. The detailed guides and examples are primarily in Chinese; supply your preferred language and discipline.

## Start in three steps

**1. Install.** Download the ZIP from [Releases](https://github.com/YCC-Lover/research-starter-skills/releases/latest), extract it, and run the installer beside catalog.json. Or clone:

~~~text
git clone https://github.com/YCC-Lover/research-starter-skills.git
cd research-starter-skills
python scripts/install_skills.py
~~~

Python 3.10+; installation uses the standard library. All seven skill directories are installed together under CODEX_HOME/skills, or ~/.codex/skills by default. [Installation and updates](docs/INSTALLATION.md)

**2. Bring one task.** Open a new Codex chat and attach one item, or describe your direction in everyday words. You do not need a complete proposal or an expert prompt. [Beginner guide](docs/BEGINNER.md) · [Teaching packs](examples/worked/README.md)

**3. Ask for a usable result.**

~~~text
Use $research-starter-paper. I have not had systematic research training.
My supervisor mentioned [direction], but I do not know what material to provide.
Guide me toward something I can discuss at my next meeting.
My authorized project folder is [path]; please save progress there.
~~~

~~~text
Use $rsk-paper-writing to revise the supplied discussion.
Give the replacement prose first, then the substantive edits,
linked chapter changes, and key supporting evidence.
~~~

~~~text
Use $rsk-research-workflow to rehearse my proposal defense.
Give focused feedback on my answer, then ask the next question.
~~~

## Pick a module

| Skill | Focus |
| --- | --- |
| research-starter-paper | Research learning, cross-stage tasks and project handoff |
| rsk-research-design | Questions, decisions, hypotheses and minimum tests |
| rsk-literature | Search, critical reading, synthesis and citation versions |
| rsk-paper-writing | Arguments, sections and thesis consistency |
| rsk-experiments-figures | Comparisons, characterization, figures and TG/DTG checks |
| rsk-rebuttal | Reviewer replies, priorities and revision tracing |
| rsk-research-workflow | Meetings, conferences, research logs and rehearsal |

[19 ready-to-adapt prompts](examples/README.md) · [Stage-by-stage learning](docs/LEARNING_PATH.md)

## Keep moving without rebuilding the context

Guided tasks save confirmed information, hypotheses, answered or unavailable questions, real files and the next step in permanent local checkpoints. A fresh chat can resume from the project and check whether source files changed. This is task-time saving, not background monitoring or automatic memory across unrelated chats.

Prose editing supports author samples, paragraph restructuring and 26 editing patterns while protecting scientific meaning, citations, numbers and formulas. Evidence guidance adapts to quantitative, qualitative, historical and theoretical work; it does not impose one discipline's method on every project.

The [guided-task records](evals/guided/REPORT.md) show actual starts, handoffs, file checks and editing outputs. These are small synthetic-task checks, not proof of universal outcomes, fixed time savings, detector evasion or publication acceptance. [Engineering checks](docs/PROJECT_AUDIT.md)

## Keep your workflow portable

Skills are editable Markdown files. Continue with another Codex account in the same user profile, or reinstall on a different machine. Clone or fork this public repository to adapt it; GitHub write access governs contributions to the original repository.

The installer records versions and file hashes, supports read-only checks and optional-tool discovery, and updates with an explicit backup. Document export, plotting and file parsing use the tools available in your Codex environment.

Version **1.5.0** retains the upstream 19-tutorial mapping at revision 36ba390d153f5289308ec833e2b633c26b304a7b. [Attribution and usage scope](NOTICE.md) · [Citation metadata](CITATION.cff)

Star to find the project again, share a sanitized task in [Issues](https://github.com/YCC-Lover/research-starter-skills/issues), or contribute a concrete example. [Contributing](CONTRIBUTING.md)
