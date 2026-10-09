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

## Application examples

After installation, attach the relevant materials and adapt a prompt below. These are task examples and expected deliverables, not completed research or guaranteed outputs. Share only materials you are authorized to share.

### 1. Find a starting point as a beginner

**Bring:** Your discipline, stage, current difficulty and any existing materials. Papers or data are not prerequisites.

~~~text
Use $research-starter-paper. I am new to research in [discipline] and stuck on [difficulty].
Explain this step, point me to the relevant original tutorial, and give a labeled teaching example with optional practice.
Suggest a next step based on my materials; do not invent papers or results I do not have.
~~~

**Expected:** A focused diagnosis, tutorial link, practice task and actionable next step.

### 2. Narrow a broad direction into a research question

**Bring:** Your research object, observed phenomenon, literature leads and available instruments, data or time.

~~~text
Use $rsk-research-design. My direction is "swelling conditions and material thermal behavior"; see my object and resources in the attachments.
Separate known facts from candidate hypotheses, narrow the question and propose a minimum test.
Specify controls, measurements and falsifying outcomes; unperformed experiments must remain plans.
~~~

**Expected:** A question, candidate hypotheses, a minimum test plan and key risks, not a premature conclusion.

### 3. Connect the papers you have read

**Bring:** Readable PDFs or paper text, plus the question you want to answer.

~~~text
Use $rsk-literature to read the three supplied papers around [my research question].
Create a reading card for each and compare their problems, methods, evidence and limitations with page or figure locations.
Separate author claims from my inferences; if only abstracts are readable, say so without guessing the body.
~~~

**Expected:** Three reading cards, a literature comparison and questions requiring further verification.

### 4. Make an abstract specific without overstating results

**Bring:** Your abstract draft, actual result tables, method description and word limit.

~~~text
Use $rsk-paper-writing to revise my abstract from the supplied methods and actual results within [word limit].
Make the question, method, findings and scope explicit; preserve numbers, units and terminology.
Revise only the abstract; mark missing evidence as [Needed: specific information] without exaggerating contributions.
~~~

**Expected:** A revised abstract, brief change notes and concrete missing items.

### 5. Check what differing TG/DTG curves support

**Bring:** Exported CSV/XLSX data, curve images, sample details, atmosphere, heating rate and repeat-measurement records.

~~~text
Use $rsk-experiments-figures to review the supplied TG/DTG data, measurement conditions and analysis draft.
Check comparability first, then identify supported observations and mechanism claims lacking evidence.
Review only: do not edit data, replot or rewrite the text; list missing conditions.
~~~

**Expected:** Comparability findings, evidence boundaries and a verification checklist, not causal claims from curve differences alone.

### 6. Organize a point-by-point reviewer response

**Bring:** Actual reviewer comments, the manuscript, completed changes and actual new results; label unfinished work separately.

~~~text
Use $rsk-rebuttal to draft replies from the actual comments and revision records.
Keep comment IDs, identify evidence and manuscript locations, and list the status of each issue.
Do not describe unfinished experiments as completed; draft only, without submission or contacting anyone.
~~~

**Expected:** A reply draft and a comment/evidence/revision-location/status coverage table.

### 7. Prepare for your first academic conference

**Bring:** A research summary approved for public sharing, attendance goals and talks of interest; label unproduced results as plans.

~~~text
Use $rsk-research-workflow to prepare a short research introduction and discussion questions for my first conference.
Distinguish actual progress, difficulties and plans from the attachments, then draft a follow-up email template.
Keep placeholders for conversations that have not happened; do not invent collaborations, send emails or register me.
~~~

**Expected:** An introduction, question list and a follow-up template to fill after an actual conversation.

See [19 detailed scenarios](examples/README.md) for more inputs and prompts, or try the [first introduction exercise](examples/first-run/README.md) with public teaching materials.

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
