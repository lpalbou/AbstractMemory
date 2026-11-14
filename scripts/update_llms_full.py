"""Aggregate public documentation with links resolved from repository root."""
from pathlib import Path
import posixpath
import re

ROOT = Path(__file__).resolve().parents[1]
PAGES = ['README.md', 'docs/getting-started.md', 'docs/architecture.md', 'docs/memory-system.md',
         'docs/api.md', 'docs/stores.md', 'docs/operator.md', 'docs/faq.md', 'docs/troubleshooting.md',
         'skills/abstractmemory/SKILL.md']

def render():
    sections = ['# AbstractMemory (llms-full)\n\nSee [llms.txt](llms.txt) for the documentation index.']
    for page in PAGES:
        body = (ROOT/page).read_text()
        def link(match):
            label, target = match.groups()
            if re.match(r'^(?:[a-z]+:|/|#)', target):
                return match.group(0)
            return f'[{label}]({posixpath.normpath(posixpath.join(posixpath.dirname(page), target))})'
        body = re.sub(r'\[([^\]]*)\]\(([^)\s]+)\)', link, body)
        sections.append(f'## {page}\n\n{body.rstrip()}')
    return '\n\n---\n\n'.join(sections)+'\n'

if __name__ == '__main__':
    import sys
    target = ROOT/'llms-full.txt'
    expected = render()
    if '--check' in sys.argv:
        if target.read_text() != expected:
            raise SystemExit('llms-full.txt is stale: run python scripts/update_llms_full.py')
    else:
        target.write_text(expected)
