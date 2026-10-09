"""Render original, explicitly labeled project diagrams and a synthetic-data plot."""

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-dir', type=Path, required=True, help='Non-C temporary/cache directory.')
    args = parser.parse_args()
    work = args.work_dir.expanduser().resolve()
    if os.name == 'nt' and work.drive.upper() == 'C:':
        parser.error('Use a non-C work directory on Windows.')
    work.mkdir(parents=True, exist_ok=True)
    for name in ('TEMP', 'TMP', 'TMPDIR'):
        os.environ[name] = str(work)
    os.environ['MPLCONFIGDIR'] = str(work / 'matplotlib-cache')

    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont

    output = ROOT / 'docs/images'
    output.mkdir(parents=True, exist_ok=True)
    font_dir = Path(matplotlib.get_data_path()) / 'fonts/ttf'
    colors = ['#137f67', '#2974a3', '#ba4554', '#af8120', '#5f5aa3', '#48766c']
    ink, muted, line = '#172124', '#56666b', '#d8e1e3'

    def font(size, bold=False):
        name = 'DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf'
        return ImageFont.truetype(str(font_dir / name), size)

    def text(draw, xy, value, size=26, fill=ink, bold=False):
        draw.text(xy, value, font=font(size, bold), fill=fill)

    def canvas(title, subtitle, height):
        im = Image.new('RGB', (1600, height), '#fbfcfc')
        d = ImageDraw.Draw(im)
        d.rectangle((60, 62, 72, 123), fill=colors[0])
        text(d, (94, 57), title, 50, bold=True)
        text(d, (94, 128), subtitle, 25, muted)
        return im, d

    im, draw = canvas('Research Starter Skills', 'Your materials. Relevant guidance. Traceable writing.', 960)
    draw.rectangle((60, 200, 1540, 312), fill='#edf4f2', outline=line, width=2)
    text(draw, (90, 220), '$research-starter-paper', 36, bold=True)
    text(draw, (90, 270), 'Routes to the modules your task needs; not every module on every request.', 25, muted)
    modules = [
        ('Research design', '$rsk-research-design', 'Question / hypothesis / minimum test'),
        ('Literature', '$rsk-literature', 'Reading cards / citation verification'),
        ('Paper writing', '$rsk-paper-writing', 'Argument / introduction / abstract'),
        ('Experiments & figures', '$rsk-experiments-figures', 'Fair comparisons / captions / limits'),
        ('Rebuttal', '$rsk-rebuttal', 'Comment coverage / real changes'),
        ('Research workflow', '$rsk-research-workflow', 'Meetings / conferences / research logs'),
    ]
    for index, (title, name, purpose) in enumerate(modules):
        col, row = index % 2, index // 2
        x, y = 60 + 755 * col, 346 + 158 * row
        draw.rectangle((x, y, x + 725, y + 132), fill='white', outline=line, width=2)
        draw.rectangle((x, y, x + 8, y + 132), fill=colors[index])
        text(draw, (x + 26, y + 16), title, 29, bold=True)
        text(draw, (x + 26, y + 58), name, 24, colors[index])
        text(draw, (x + 26, y + 94), purpose, 22, muted)
    text(draw, (60, 846), 'Evidence check: observed / inferred / planned / missing', 31, bold=True)
    text(draw, (60, 900), 'Independent adaptation of Research-Starter-Kit. Original visualization, not an official graphic.', 22, muted)
    im.save(output / 'workflow.png', optimize=True)

    im, draw = canvas('A claim should have somewhere to point', 'Illustrative output structure; not a model run or a real experimental result.', 900)
    headers = ['CLAIM', 'EVIDENCE / STATUS', 'WRITING DECISION']
    columns = [60, 540, 1040]
    for x, header in zip(columns, headers):
        text(draw, (x + 20, 212), header, 26, muted, bold=True)
    rows = [
        (['The toy curves differ.'], ['thermal-demo.csv', 'Synthetic, descriptive only'], ['Describe the visible shape.', 'Keep the teaching-data label.']),
        (['The treatment is', 'statistically significant.'], ['No independent repeats', 'No statistical test'], ['Do not make this claim.', 'Record the missing evidence.']),
        (['The mechanism', 'has been proven.'], ['No mechanism evidence'], ['State an untested hypothesis', 'or leave it out.']),
    ]
    for index, cells in enumerate(rows):
        y = 265 + index * 162
        draw.line((60, y - 15, 1540, y - 15), fill=line, width=2)
        for column, values in enumerate(cells):
            for row, value in enumerate(values):
                text(draw, (columns[column] + 20, y + row * 40), value, 26,
                     colors[0] if index == 0 and column == 2 else ink)
    draw.rectangle((60, 773, 1540, 842), fill='#edf4f2')
    text(draw, (82, 791), 'Useful output = a draft + locatable evidence + honest unfinished work.', 28, bold=True)
    im.save(output / 'evidence-check.png', optimize=True)

    with (ROOT / 'examples/demo-materials/thermal-demo.csv').open(newline='', encoding='utf-8') as handle:
        data = list(csv.DictReader(handle))
    temperature = np.array([float(row['temperature_C']) for row in data])
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 12, 'axes.spines.top': False,
                         'axes.spines.right': False, 'axes.labelcolor': ink, 'text.color': ink})
    fig, axes = plt.subplots(1, 2, figsize=(12, 5.4), dpi=150)
    for key, label, color, style in [('mass_A_pct', 'Toy curve A', colors[0], '-'),
                                     ('mass_B_pct', 'Toy curve B', colors[1], '--')]:
        mass = np.array([float(row[key]) for row in data])
        axes[0].plot(temperature, mass, label=label, color=color, linestyle=style, linewidth=2.5)
        axes[1].plot(temperature, -np.gradient(mass, temperature), label=label,
                     color=color, linestyle=style, linewidth=2.5)
    for axis in axes:
        axis.set_xlabel('Temperature (C)')
        axis.grid(alpha=0.15)
        axis.legend(frameon=False)
    axes[0].set(title='TG: supplied toy values', ylabel='Mass (%)')
    axes[1].set(title='DTG: numerical derivative', ylabel='-d(mass%)/dT (%/C)')
    fig.suptitle('SYNTHETIC TEACHING DATA - NOT MEASURED RESULTS', fontsize=15, fontweight='bold', y=0.97)
    fig.text(0.06, 0.045, 'Hand-constructed curves; no repeats, error bars, statistical tests, or mechanism evidence.', fontsize=11)
    fig.subplots_adjust(left=0.07, right=0.98, top=0.83, bottom=0.18, wspace=0.3)
    fig.savefig(output / 'thermal-demo.png', metadata={'Software': 'Research Starter Skills original demo'})
    plt.close(fig)

    images = []
    for name, kind, description in [
        ('workflow.png', 'original-diagram', 'Original map of the router and six focused skills.'),
        ('evidence-check.png', 'illustrative-output', 'Manually authored claim/evidence illustration, not a recorded model response.'),
        ('thermal-demo.png', 'synthetic-data-plot', 'Reproducible plot of hand-constructed teaching curves; not a real experiment.'),
    ]:
        path = output / name
        with Image.open(path) as image:
            width, height = image.size
            image.verify()
        entry = {'path': 'docs/images/' + name, 'kind': kind, 'creator': 'YCC-Lover with Codex',
                 'description': description, 'source': 'scripts/render_showcase.py',
                 'width': width, 'height': height, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
        if kind == 'synthetic-data-plot':
            entry['data_source'] = 'examples/demo-materials/thermal-demo.csv'
        images.append(entry)
    manifest_path = output / 'manifest.json'
    if manifest_path.is_file():
        existing = json.loads(manifest_path.read_text(encoding='utf-8'))['images']
        rendered_paths = {entry['path'] for entry in images}
        images.extend(entry for entry in existing if entry['path'] not in rendered_paths)
    manifest_path.write_text(json.dumps({'images': images}, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'images': [entry['path'] for entry in images], 'cache_dir': str(work)}))


if __name__ == '__main__':
    main()
