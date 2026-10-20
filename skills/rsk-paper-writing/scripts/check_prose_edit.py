"""Read-only comparison of common protected spans in Markdown, text and LaTeX."""

import argparse
from collections import Counter
from html.parser import HTMLParser
import json
from pathlib import Path
import re


class LinkTargets(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.targets = []

    def handle_starttag(self, tag, attrs):
        for name, value in attrs:
            if name in {'href', 'src'} and value is not None:
                self.targets.append(value)

    handle_startendtag = handle_starttag


def markdown_targets(text):
    targets = []
    for start in re.finditer(r'(?<!\\)\]\(', text):
        depth, end = 1, start.end()
        while end < len(text) and depth:
            if text[end] == '\\':
                end += 2
                continue
            if text[end] == '(':
                depth += 1
            elif text[end] == ')':
                depth -= 1
            end += 1
        if depth == 0:
            targets.append(text[start.end():end - 1])
    targets.extend(re.findall(r'(?m)^ {0,3}\[[^\]\n]+\]:[ \t]*(.+)$', text))
    return targets


def protected(text):
    result = {'frontmatter': [], 'code': [], 'link_targets': [], 'citations': [], 'math': [], 'numbers': []}
    frontmatter = re.match(r'\A---\n.*?\n(?:---|\.\.\.)\s*(?:\n|$)', text, re.S)
    if frontmatter:
        result['frontmatter'].append(frontmatter.group())
        text = text[frontmatter.end():]
    lines = text.splitlines(keepends=True)
    plain, block, fence = [], [], None
    for line in lines:
        opening = re.match(r'^ {0,3}(`{3,}|~{3,})(.*)', line)
        if fence is None and opening:
            fence = opening.group(1)
            block = [line]
        elif fence is not None:
            block.append(line)
            if re.fullmatch(r' {0,3}' + re.escape(fence[0]) + '{' + str(len(fence)) + r',}[ \t]*(?:\n)?', line):
                result['code'].append(''.join(block))
                block, fence = [], None
        else:
            plain.append(line)
    if fence is not None:
        result['code'].append(''.join(block))
    text = ''.join(plain)
    inline = re.compile(r'(?<!`)(`+)(?!`)(.+?)(?<!`)\1(?!`)', re.S)
    result['code'].extend(match.group() for match in inline.finditer(text))
    text = inline.sub('', text)
    result['link_targets'] = markdown_targets(text)
    html = LinkTargets()
    html.feed(text)
    result['link_targets'].extend(html.targets)
    result['link_targets'].extend(re.findall(r'<((?:https?://|mailto:)[^<>]+)>', text))
    result['citations'] = re.findall(r'\\(?:cite\w*|ref|eqref|label)(?:\[[^\]]*\])*\{[^}]*\}|(?<![\w@])@[A-Za-z][\w:./-]*', text)
    math = re.compile(r'(?s)\\\[.*?\\\]|\\\(.*?\\\)|(?<!\\)\$\$.*?(?<!\\)\$\$|(?<![\\$])\$(?!\$).*?(?<![\\$])\$(?!\$)|\\begin\{(equation\*?|align\*?|gather\*?)\}.*?\\end\{\1\}')
    result['math'] = [match.group() for match in math.finditer(text)]
    result['numbers'] = re.findall(r'(?<![\w])[-+]?\d+(?:[.,]\d+)*(?:[eE][-+]?\d+)?(?:\s*(?:%|\u00b0[CＦF]|[A-Za-z\u03bc]+(?:/[A-Za-z]+)?))?', text)
    return {name: Counter(values) for name, values in result.items()}


def compare(before, after):
    left, right = protected(before), protected(after)
    changes = []
    for kind in left:
        if left[kind] != right[kind]:
            changes.append({'kind': kind, 'removed': list((left[kind] - right[kind]).elements()),
                            'added': list((right[kind] - left[kind]).elements())})
    return {'protected_spans_unchanged': not changes, 'changes': changes,
            'limits': ['Lexical checks cover common Markdown/text/LaTeX forms, not a complete document parser.',
                       'No semantic, authorship, scientific-validity or AI-detection judgment is made.',
                       'Negation, quantifiers, units, scope and author voice also need contextual review.'],
            'files_written': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('before', type=Path)
    parser.add_argument('after', type=Path)
    args = parser.parse_args()
    try:
        if args.before.suffix.lower() not in {'.md', '.txt', '.tex'} or args.after.suffix.lower() not in {'.md', '.txt', '.tex'}:
            raise ValueError('Export prose to MD/TXT/TEX first; this tool does not edit or parse Word/PDF binaries.')
        result = compare(args.before.read_text(encoding='utf-8-sig'), args.after.read_text(encoding='utf-8-sig'))
    except (ValueError, OSError) as error:
        parser.exit(2, 'Prose check failed: ' + str(error) + '\n')
    print(json.dumps(result, ensure_ascii=False))
    if not result['protected_spans_unchanged']:
        parser.exit(1)


if __name__ == '__main__':
    main()
