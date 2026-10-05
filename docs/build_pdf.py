#!/usr/bin/env python3
"""Build the PDF handouts from the Markdown topics in this folder.

    ../.venv/bin/python build_pdf.py

The Markdown files are the source of truth -- they are what people read on
GitHub, with working links between topics. This script stitches selections of
them into printable documents for people who will not clone the repository.

Two outputs:

  E6-Exhibition-Manual.pdf   sections 1-7, the full operating manual
  E6-Quick-Guide.pdf         power on, run, drive -- for the operator on the day

Sections 8 (Running on Windows) and 9 (Reference) are in neither. They are
developer material, they change far more often than the operating procedure, and
a printed handout that has gone stale is worse than one that is honestly scoped.
They stay in the repository as Markdown.

Requires `weasyprint` and `markdown` (both pip-installable). WeasyPrint rather
than pandoc because the diagrams are SVG and it renders them as vectors without
needing a LaTeX toolchain or an SVG converter in between.
"""

import io
import os
import re
import sys

import markdown
from weasyprint import HTML

HERE = os.path.dirname(os.path.abspath(__file__))

# Every section, in order. The builds below select from these.
ALL_TOPICS = [
    ('01-safety', 'Safety and the emergency stop'),
    ('02-status-lights', 'Status lights'),
    ('03-setup', 'Unpacking, packing and connecting'),
    ('04-running', 'Running and stopping the program'),
    ('05-joystick', 'Joystick controls'),
    ('06-scanning', 'The probe: payload and contact force'),
    ('07-troubleshooting', 'Limits, faults and recovery'),
    ('08-windows', 'Running on Windows'),
    ('09-reference', 'Reference'),
]

# The full manual: the seven operating sections, whole.
FULL = [(name, title, {}) for name, title in ALL_TOPICS[:7]]

# The quick guide: just enough to switch the arm on, start it and drive it.
# `only` keeps named H2 blocks, `drop` removes them -- so the quick guide reuses
# the same source text instead of duplicating it and drifting out of step.
QUICK = [
    ('03-setup', 'Powering the arm on', {'only': ['Powering the arm on']}),
    ('04-running', 'Running and stopping', {}),
    # The operator-frame diagram is cut: the control table already says "your
    # left" and "away from you", so on a short handout the picture restates it
    # rather than adding anything. Re-mapping is a developer concern.
    ('05-joystick', 'Joystick controls',
     {'drop': ['Directions are from where you stand', 'Re-mapping']}),
]

# Colour emoji need a colour-emoji font that print backends rarely have, and a
# missing glyph in the status-light table would destroy the one thing that table
# exists to convey. Swap them for markup that carries the same meaning.
LED = {'\U0001F535': 'blue', '\U0001F7E2': 'green',
       '\U0001F7E1': 'yellow', '\U0001F534': 'red'}
GLYPH = {'⚠️': '⚠', '✅': '✔', '\U0001F4C4': '', '⬇': ''}


def is_nav(line):
    """Prev/next/contents strips are navigation for the website, noise in print."""
    s = line.strip()
    return (s.startswith('[') and '](' in s
            and ('←' in s or '→' in s or 'Contents](' in s))


def select(text, only=None, drop=None):
    """Keep or remove whole `## ` blocks of a topic."""
    if not only and not drop:
        return text
    parts = re.split(r'(?m)^(## .*)$', text)
    # With `only`, the preamble introduces the whole topic, so it goes too.
    out = [] if only else [parts[0]]
    for i in range(1, len(parts) - 1, 2):
        head, body = parts[i], parts[i + 1]
        name = head[3:].strip()
        if only is not None and name not in only:
            continue
        if drop and name in drop:
            continue
        out.append(head + body)
    return '\n'.join(out)


def prepare(name, included, only=None, drop=None):
    """Read one topic, strip navigation, select blocks, retarget cross-links."""
    text = io.open(os.path.join(HERE, name + '.md'), encoding='utf-8').read()
    text = '\n'.join(l for l in text.split('\n') if not is_nav(l))
    text = select(text, only, drop)

    # Links to a section that IS in this PDF become internal jumps. Links to one
    # that is not would be dead anchors, so unwrap them and mark them.
    def unwrap(m):
        label, target = m.group(1), m.group(2)
        return m.group(0) if target in included else f'{label} (online)'
    text = re.sub(r'\[([^\]]+)\]\((\d\d-[a-z-]+)\.md(?:#[^)]*)?\)', unwrap, text)
    text = re.sub(r'\]\((\d\d-[a-z-]+)\.md(?:#[^)]*)?\)', r'](#\1)', text)
    text = text.replace('](README.md)', '](#contents)')

    for emoji, cls in LED.items():
        text = text.replace(emoji, f'<span class="led {cls}"></span>')
    for emoji, repl in GLYPH.items():
        text = text.replace(emoji, repl)

    html = markdown.markdown(text, extensions=['tables', 'attr_list', 'sane_lists'])
    html = re.sub(r'^<h1>.*?</h1>', '', html, count=1, flags=re.S)
    return html


CSS = """
@page {
  size: A4; margin: 17mm 16mm 18mm 16mm;
  @bottom-center {
    content: counter(page); font-family: monospace; font-size: 8.5pt; color: #7A8C92;
  }
  @bottom-right {
    content: "Dobot Magician E6 \\2014 ultrasound teleoperation";
    font-family: sans-serif; font-size: 7.5pt; color: #9AA9AE;
  }
}
@page :first { @bottom-center { content: ""; } @bottom-right { content: ""; } }

body { font-family: "DejaVu Sans", sans-serif; font-size: 9.6pt; line-height: 1.5;
       color: #16242A; }
h1, h2, h3, h4 { color: #0B2B30; line-height: 1.22; }
h2 { font-size: 15pt; margin: 0 0 3mm; }
h3 { font-size: 11.5pt; margin: 6mm 0 2mm; }
h4 { font-size: 9.8pt; margin: 5mm 0 1.5mm; }
p, li { orphans: 2; widows: 2; }
ul, ol { padding-left: 5mm; }
li { margin: 0.6mm 0; }
code, pre { font-family: "DejaVu Sans Mono", monospace; }
code { font-size: 8.6pt; background: #EDF2F3; padding: 0.3mm 1mm; border-radius: 1mm; }
pre { background: #F4F7F8; border: 0.3mm solid #D3DEE1; border-left: 1mm solid #0C6B74;
      border-radius: 1mm; padding: 2.5mm 3mm; font-size: 8.3pt; line-height: 1.45;
      white-space: pre-wrap; page-break-inside: avoid; }
pre code { background: none; padding: 0; font-size: inherit; }
blockquote { margin: 3mm 0; padding: 2.5mm 3.5mm; background: #FBF0DC;
             border-left: 1mm solid #8A5D00; border-radius: 1mm;
             page-break-inside: avoid; }
blockquote p { margin: 0 0 1.5mm; } blockquote p:last-child { margin: 0; }
table { border-collapse: collapse; width: 100%; margin: 3mm 0; font-size: 8.6pt;
        page-break-inside: avoid; }
th { text-align: left; background: #EDF2F3; border-bottom: 0.4mm solid #B4C3C7;
     padding: 1.6mm 2mm; font-size: 7.8pt; text-transform: uppercase;
     letter-spacing: 0.3pt; color: #44585E; }
td { border-bottom: 0.2mm solid #DDE5E7; padding: 1.6mm 2mm; vertical-align: top; }
img { max-width: 100%; display: block; margin: 3mm auto; page-break-inside: avoid; }
hr { border: none; border-top: 0.2mm solid #D3DEE1; margin: 5mm 0; }
a { color: #0C6B74; text-decoration: none; }
.led { display: inline-block; width: 2.6mm; height: 2.6mm; border-radius: 50%;
       margin-right: 1.5mm; }
.led.blue { background: #2E7CF6; } .led.green { background: #22B467; }
.led.yellow { background: #E0B400; } .led.red { background: #D6301F; }

.cover { page-break-after: always; padding-top: 34mm; }
.cover .kicker { font-family: "DejaVu Sans Mono", monospace; font-size: 9pt;
                 letter-spacing: 1.6pt; text-transform: uppercase; color: #0C6B74;
                 margin-bottom: 6mm; }
.cover h1 { font-size: 27pt; line-height: 1.1; margin: 0 0 6mm; letter-spacing: -0.5pt; }
.cover .sub { font-size: 11.5pt; color: #44585E; max-width: 125mm; line-height: 1.5; }
.cover .meta { margin-top: 11mm; font-family: "DejaVu Sans Mono", monospace;
               font-size: 8.5pt; color: #5E7177; line-height: 1.9;
               border-top: 0.4mm solid #16242A; padding-top: 4mm; }
.cover .warn { margin-top: 9mm; padding: 4mm; background: #FBE7E4;
               border-left: 1mm solid #A81F14; font-size: 9.5pt; }
.cover .warn ul { margin: 2mm 0 0; padding-left: 4.5mm; }
.cover .tail { margin-top: 7mm; font-size: 8.3pt; color: #7A8C92; line-height: 1.5; }

.toc { page-break-after: always; }
.toc h2 { border-bottom: 0.4mm solid #16242A; padding-bottom: 2mm; }
.toc ol { list-style: none; padding: 0; margin: 4mm 0 0; }
.toc li { margin: 0 0 2.6mm; font-size: 10.5pt; }
.toc .n { font-family: "DejaVu Sans Mono", monospace; color: #0C6B74;
          font-size: 8.5pt; margin-right: 3mm; }

section { page-break-before: always; }
section > .shead { border-top: 0.6mm solid #16242A; padding-top: 3mm; margin-bottom: 4mm; }
section > .shead .n { font-family: "DejaVu Sans Mono", monospace; font-size: 8.5pt;
                      color: #0C6B74; letter-spacing: 1pt; }
section > .shead h2 { margin: 1mm 0 0; }
"""

# The quick guide omits the safety section, so the essentials ride on its cover.
# A handout that explains how to move a robot arm and nothing about stopping it
# is not a shorter document, it is an incomplete one.
SAFETY_BOX = (
    '<div class="warn"><b>The arm is position controlled and does not feel you.</b> '
    'It will not stop for your hand, the bench, or the phantom.'
    '<ul>'
    '<li>Hold <b>L1</b> or nothing moves. Release it and the arm stops &mdash; '
    'that is your first reflex, not the emergency stop.</li>'
    '<li>Keep the <b>red emergency stop</b> on the base within reach. Press to '
    'stop, rotate to release.</li>'
    '<li>The <b>robot base is the centre</b> of the workspace: the arm reaches '
    '450&nbsp;mm in every direction, <b>front and back</b>. Nobody puts a hand '
    'inside it while it is running.</li>'
    '</ul></div>')


def build(spec, out_name, kicker, title, subtitle, tail):
    included = {name for name, _, _ in spec}
    parts = [f'<style>{CSS}</style>']

    parts.append(
        '<div class="cover">'
        f'<div class="kicker">{kicker}</div>'
        f'<h1>{title}</h1>'
        f'<div class="sub">{subtitle}</div>'
        f'{SAFETY_BOX}'
        '<div class="meta">'
        'Robot &nbsp;Dobot Magician E6<br>'
        'Controller &nbsp;PS5 DualSense<br>'
        'Arm address &nbsp;192.168.5.1<br>'
        'Revision &nbsp;2026-10-04'
        '</div>'
        f'<div class="tail">{tail}</div>'
        '</div>')

    toc = ['<div class="toc" id="contents"><h2>Contents</h2><ol>']
    for i, (_, title_i, _) in enumerate(spec, 1):
        toc.append(f'<li><span class="n">{i:02d}</span>{title_i}</li>')
    toc.append('</ol></div>')
    parts.append(''.join(toc))

    for i, (name, title_i, opts) in enumerate(spec, 1):
        body = prepare(name, included, opts.get('only'), opts.get('drop'))
        parts.append(
            f'<section id="{name}">'
            f'<div class="shead"><span class="n">SECTION {i:02d}</span>'
            f'<h2>{title_i}</h2></div>{body}</section>')

    out = os.path.join(HERE, out_name)
    HTML(string=''.join(parts), base_url=HERE).write_pdf(out)
    print(f'wrote {out_name}  ({os.path.getsize(out)/1024:.0f} kB)')


def main():
    build(FULL, 'E6-Exhibition-Manual.pdf',
          'Exhibition operating manual &nbsp;&middot;&nbsp; sections 1-7',
          'Dobot Magician E6<br>ultrasound teleoperation',
          'How to connect, run, drive and pack down the arm for live '
          'probe-on-phantom demonstrations. Written for engineers who have not '
          'worked with a robot arm before.',
          'Sections 8 (Running on Windows) and 9 (Reference) are developer '
          'material and are kept in the repository rather than here: '
          'github.com/k211/DOBOT-NSL')

    build(QUICK, 'E6-Quick-Guide.pdf',
          'Quick guide &nbsp;&middot;&nbsp; power on, run, drive',
          'Dobot Magician E6<br>quick guide',
          'The short version: switch the arm on, start the program, and drive it. '
          'For the operator on the day.',
          'Unpacking and packing, the status lights, scanning with the probe and '
          'troubleshooting are in the full manual: github.com/k211/DOBOT-NSL')

    build_checklist()


def build_checklist():
    """One A4 page: compact type, no cover, no footer, tables only.

    It is a sheet to tick on a clipboard, so it must not spill onto a second
    page -- a missed page is a missed e-stop.
    """
    body = prepare('hardware-checklist', set())
    body = body.replace('<hr />', '')
    css = CSS + """
      @page { size: A4; margin: 8mm 10mm 7mm 10mm;
              @bottom-center { content: ""; } @bottom-right { content: ""; } }
      body { font-size: 7.3pt; line-height: 1.2; }
      h1 { font-size: 14pt; margin: 0 0 1.5mm; }
      h2 { font-size: 9.5pt; margin: 1.8mm 0 0.5mm; }
      p { margin: 0 0 1.2mm; }
      table { margin: 0; font-size: 7.2pt; page-break-inside: auto; }
      th { padding: 0.6mm 1.4mm; font-size: 6.4pt; }
      td { padding: 0.35mm 1.4mm; }
      /* tick columns: the first cell always, the second only in Out/Back
         tables -- in the two-column check tables it holds the text */
      td:first-child, th:first-child,
      td:nth-child(2):not(:last-child), th:nth-child(2):not(:last-child)
        { width: 8mm; text-align: center; font-size: 8.5pt; padding: 0 1mm; }
      td:last-child, th:last-child { text-align: left; }
      /* fixed columns so every Out/Back table lines up down the page */
      table { table-layout: fixed; width: 100%; }
      td:nth-child(3):not(:last-child), th:nth-child(3):not(:last-child) { width: 36%; }
      td:nth-child(4):not(:last-child), th:nth-child(4):not(:last-child)
        { width: 9%; text-align: center; }
      code { font-size: 6.8pt; padding: 0 0.6mm; }
    """
    html = f'<style>{css}</style><h1>NSL Dobot \u2014 hardware checklist</h1>{body}'
    out = os.path.join(HERE, 'NSL-Hardware-Checklist.pdf')
    doc = HTML(string=html, base_url=HERE).render()
    pages = len(doc.pages)
    doc.write_pdf(out)
    print(f'wrote NSL-Hardware-Checklist.pdf  ({os.path.getsize(out)/1024:.0f} kB, '
          f'{pages} page{"s" if pages != 1 else ""})')
    if pages != 1:
        print('  WARNING: checklist no longer fits on one page')


if __name__ == '__main__':
    sys.exit(main())
