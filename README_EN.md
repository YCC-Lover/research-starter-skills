# Research Starter Skills

[中文](README.md) · [English](README_EN.md) · [Changelog](CHANGELOG.md)

**Research guidance for Codex, from a focused question to evidence-grounded writing.**

Start with the step that is blocking you: a broad topic, a dense introduction, an unclear figure caption, or a reviewer comment. Bring your actual materials; choose one focused skill or let the router select relevant modules.

**[Download](https://github.com/YCC-Lover/research-starter-skills/releases/latest) · [Learning path](docs/LEARNING_PATH.md) · [First exercise](examples/first-run/README.md) · [19 task examples](examples/README.md) · [Contribute](CONTRIBUTING.md)**

## Origin first

This is an **unofficial independent adaptation** of [LAMDA-NeSy/Research-Starter-Kit](https://github.com/LAMDA-NeSy/Research-Starter-Kit), based on its README at revision 36ba390d153f5289308ec833e2b633c26b304a7b and all 19 exported tutorials. The upstream README is introduced by Guo Lanzhe and acknowledges Chen Yuyang, Ge Lingyue, Zhang Yikai, and others. YCC-Lover maintains this Codex adaptation; no upstream endorsement is implied.

[Tutorial-by-tutorial mapping](skills/research-starter-paper/references/sources.md) · [Attribution and publication scope](NOTICE.md) · [Citation metadata](CITATION.cff)

![Original diagram of one router and six focused skills](docs/images/workflow.png)

The diagram is original to this repository, not a tutorial screenshot. The detailed skills and examples are primarily in Chinese; prompt the skills in your preferred language and supply your discipline and target requirements.

## Choose a task

All seven skills distinguish learning, execution and review. Ask to learn for an explanation, optional practice and feedback; ask for a deliverable to work directly on it; ask for review only to receive findings without file edits. No complete course or prerequisite paper collection is mandatory. Beginners without a supervisor's seed papers can start with their object, phenomenon and resources.

| Skill | Focus |
| --- | --- |
| [research-starter-paper](skills/research-starter-paper/SKILL.md) | Router for cross-stage requests |
| [rsk-research-design](skills/rsk-research-design/SKILL.md) | Questions, hypotheses, minimum tests |
| [rsk-literature](skills/rsk-literature/SKILL.md) | Search, reading cards, citation verification |
| [rsk-paper-writing](skills/rsk-paper-writing/SKILL.md) | Arguments, outlines, introductions, abstracts, methods |
| [rsk-experiments-figures](skills/rsk-experiments-figures/SKILL.md) | Comparisons, descriptive analysis, figures and captions |
| [rsk-rebuttal](skills/rsk-rebuttal/SKILL.md) | Evidence-linked replies and revision status |
| [rsk-research-workflow](skills/rsk-research-workflow/SKILL.md) | Meetings, conferences, logs and bounded AI collaboration |

## Install

Requires Python 3.10+. Installation uses only the standard library.

~~~text
git clone https://github.com/YCC-Lover/research-starter-skills.git
cd research-starter-skills
python scripts/install_skills.py --dry-run
python scripts/install_skills.py
~~~

Without Git, download the ZIP from Releases, extract it, and run the installer from the directory containing catalog.json. Install all seven folders as siblings. The default is CODEX_HOME/skills, or ~/.codex/skills when unset. Use --dest to specify another profile. See the [installation guide](docs/INSTALLATION.md) for read-only checks and explicit backup updates.

Then try:

~~~text
Use $rsk-paper-writing to revise the supplied introduction only.
Check the problem, prior work, concrete gap, response, and evidence.
Preserve citations, numbers, units, and terminology.
Mark missing evidence explicitly; do not invent results or references.
~~~

No suitable public material yet? Start with the [first introduction exercise](examples/first-run/README.md), then the [included teaching fixtures](examples/demo-materials/README.md). Numbers, citations and reviewer comments are explicitly synthetic or fictional, never actual research. Separately recorded model outputs and their limitations belong to the [behavior evaluation](evals/README.md).

For long projects, optionally reuse the [handoff template](skills/research-starter-paper/assets/project-state.md). A new chat must read it and check the current source materials; chat history is not automatic persistent project memory. Discussion/submission, measurement checks and responsible AI guidance are connected to their focused modules.

## What it does not promise

Skills are instructions, not standalone research engines. Search, proprietary file parsing, plotting, and document export depend on available tools. An Origin .opju file still requires a supported interface or readable export. Validation tests do not establish model accuracy, publication success, or time savings. Authors remain responsible for checking sources and conclusions.

No raw tutorials, upstream figures, private research, credentials, or account sessions are published. This repository has not adopted a general license, and does not grant redistribution rights to upstream tutorials. Public visibility and attribution are not substitutes for permission; see [NOTICE.md](NOTICE.md).

## Help improve a real workflow

Star to find the project again, report a sanitized issue, or propose a concrete example. Contributions should preserve evidence, provenance, user scope, and the distinction between completed work and plans. See [CONTRIBUTING.md](CONTRIBUTING.md) and the [audit record](docs/PROJECT_AUDIT.md).
