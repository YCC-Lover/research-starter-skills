# Research Starter Skills

[中文](README.md) · [English](README_EN.md) · [Changelog](CHANGELOG.md)

**Turn research guidance into work you can use.**

Starting research on your own? Preparing a thesis chapter, interpreting results, or responding to reviewers? Bring your papers, notes, data and draft to Codex. One router and six focused skills help you move from your current question to a concrete deliverable.

Learn the methods from [Research-Starter-Kit](https://github.com/LAMDA-NeSy/Research-Starter-Kit), then apply them to your own project with these skills.

**[Download](https://github.com/YCC-Lover/research-starter-skills/releases/latest) · [Learning path](docs/LEARNING_PATH.md) · [Complete task packs](examples/worked/README.md) · [Utility comparison](evals/utility/REPORT.md)**

**Origin and thanks:** The methods come from all 19 tutorials in LAMDA-NeSy/Research-Starter-Kit. Thanks to Guo Lanzhe, Chen Yuyang, Ge Lingyue, Zhang Yikai and the other contributors. YCC-Lover independently distills, adapts, extends and maintains this Codex skill bundle. [Sources](skills/research-starter-paper/references/sources.md) · [Attribution and usage scope](NOTICE.md)

![Research Starter Skills: a router and six focused research modules](docs/images/workflow-product.png)

Product concept image generated with GPT-image. [Image notes](docs/images/workflow-product.prompt.md)

## What you can get done

| Bring | Work toward | Take away |
| --- | --- | --- |
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

**2. Bring one task.** Open a new Codex chat and attach your current material. Start with the [first exercise](examples/first-run/README.md) or [included teaching packs](examples/worked/README.md) to explore the workflow.

**3. Ask for a usable result.**

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

## Inspect the actual work

The [utility comparison](evals/utility/REPORT.md) uses six complex tasks with two independent repetitions each. It compares direct Codex use and skill-assisted use on the same materials, scoring research progress, evidence integration, deliverable usability, actionable decisions and collaboration efficiency. Read both sets of answers and their individual judgments.

Both arms averaged 14.96/15, with all twelve pairs in the predefined close range. Inspect the concrete examples of literature synthesis, linked chapter edits and learner-specific feedback to choose a workflow that suits your task.

[Fixed protocol](evals/utility/PROTOCOL.md) · [Evaluation history](evals/README.md) · [Engineering checks](docs/PROJECT_AUDIT.md)

## Keep your workflow portable

Skills are editable Markdown files. Continue with another Codex account in the same user profile, or reinstall on a different machine. Clone or fork this public repository to adapt it; GitHub write access governs contributions to the original repository.

The installer records versions and file hashes, supports read-only checks and optional-tool discovery, and updates with an explicit backup. Document export, plotting and file parsing use the tools available in your Codex environment.

Version **1.4.0** retains the upstream 19-tutorial mapping at revision 36ba390d153f5289308ec833e2b633c26b304a7b. [Attribution and usage scope](NOTICE.md) · [Citation metadata](CITATION.cff)

Star to find the project again, share a sanitized task in [Issues](https://github.com/YCC-Lover/research-starter-skills/issues), or contribute a concrete example. [Contributing](CONTRIBUTING.md)
