#!/usr/bin/env python3
"""Build the single-file PDF manual from the Markdown topics in this folder.

    ../.venv/bin/python build_pdf.py

The Markdown files are the source of truth -- they are what people read on
GitHub, with working links between topics. This script stitches them into one
printable document for sharing with people who will not clone the repository.

Requires `weasyprint` and `markdown` (both pip-installable). WeasyPrint is used
rather than pandoc because the diagrams are SVG, and it rasterises them properly
without needing a LaTeX toolchain or an SVG converter in between.
"""

import io
import os
import re
import sys

import markdown
from weasyprint import HTML

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'E6-Exhibition-Manual.pdf')

TOPICS = [
    ('01-safety', 'Safety and the emergency stop'),
    ('02-status-lights', 'Status lights'),
    ('03-setup', 'Unpacking, packing and connecting'),
    ('04-running', 'Running and stopping the program'),
    ('05-joystick', 'Joystick controls'),
    ('06-scanning', 'The probe: payload and contact force'),
    ('07-limits', 'Joint limits and singularities'),
    ('08-troubleshooting', 'Troubleshooting'),
    ('09-windows', 'Running on Windows'),
    ('10-reference', 'Reference'),
]

# Colour emoji need a colour-emoji font that print backends rarely have, and a
# missing glyph in the status-light table would destroy the one thing that table
# exists to convey. Swap them for markup that carries the same meaning.
LED = {'\U0001F535': 'blue', '\U0001F7E2': 'green',
       '\U0001F7E1': 'yellow', '\U0001F534': 'red'}
GLYPH = {'⚠️': '⚠', '✅': '✔', '\U0001F4C4': ''}


def is_nav(line):
    """Prev/next/contents strips are navigation for the website, noise in print."""
    s = line.strip()
    return (s.startswith('[') and '](' in s
            and ('←' in s or '→' in s or 'Contents](' in s))


def prepare(name):
    """Read one topic, strip its navigation, and retarget cross-links."""
    text = io.open(os.path.join(HERE, name + '.md'), encoding='utf-8').read()
    text = '\n'.join(l for l in text.split('\n') if not is_nav(l))

    # Cross-topic links become internal PDF jumps rather than dead .md paths.
    text = re.sub(r'\]\((\d\d-[a-z-]+)\.md(?:#[^)]*)?\)', r'](#\1)', text)
    text = text.replace('](README.md)', '](#contents)')

    for emoji, cls in LED.items():
        text = text.replace(emoji, f'<span class="led {cls}"></span>')
    for emoji, repl in GLYPH.items():
        text = text.replace(emoji, repl)

    html = markdown.markdown(text, extensions=['tables', 'attr_list', 'sane_lists'])
    # Drop the leading <h1>; the section header below carries the title.
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

.cover { page-break-after: always; padding-top: 42mm; }
.cover .kicker { font-family: "DejaVu Sans Mono", monospace; font-size: 9pt;
                 letter-spacing: 1.6pt; text-transform: uppercase; color: #0C6B74;
                 margin-bottom: 6mm; }
.cover h1 { font-size: 27pt; line-height: 1.1; margin: 0 0 6mm; letter-spacing: -0.5pt; }
.cover .sub { font-size: 11.5pt; color: #44585E; max-width: 125mm; line-height: 1.5; }
.cover .meta { margin-top: 14mm; font-family: "DejaVu Sans Mono", monospace;
               font-size: 8.5pt; color: #5E7177; line-height: 1.9;
               border-top: 0.4mm solid #16242A; padding-top: 4mm; }
.cover .warn { margin-top: 10mm; padding: 4mm; background: #FBE7E4;
               border-left: 1mm solid #A81F14; font-size: 9.5pt; }

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


def main():
    parts = [f'<style>{CSS}</style>']

    parts.append(
        '<div class="cover">'
        '<div class="kicker">Exhibition operating manual</div>'
        '<h1>Dobot Magician E6<br>ultrasound teleoperation</h1>'
        '<div class="sub">How to connect, run, drive and pack down the arm for '
        'live probe-on-phantom demonstrations. Written for engineers who have not '
        'worked with a robot arm before.</div>'
        '<div class="warn"><b>The arm is position controlled and does not feel you.</b> '
        'It will not stop for your hand, the bench, or the phantom. Keep the '
        'emergency stop within reach and read section 1 first.</div>'
        '<div class="meta">'
        'Robot &nbsp;Dobot Magician E6<br>'
        'Controller &nbsp;PS5 DualSense<br>'
        'Stack &nbsp;ROS 2 Humble + MoveIt Servo<br>'
        'Arm address &nbsp;192.168.5.1<br>'
        'Revision &nbsp;2026-10-04'
        '</div></div>')

    toc = ['<div class="toc" id="contents"><h2>Contents</h2><ol>']
    for i, (_, title) in enumerate(TOPICS, 1):
        toc.append(f'<li><span class="n">{i:02d}</span>{title}</li>')
    toc.append('</ol></div>')
    parts.append(''.join(toc))

    for i, (name, title) in enumerate(TOPICS, 1):
        parts.append(
            f'<section id="{name}">'
            f'<div class="shead"><span class="n">SECTION {i:02d}</span>'
            f'<h2>{title}</h2></div>{prepare(name)}</section>')

    HTML(string=''.join(parts), base_url=HERE).write_pdf(OUT)
    size = os.path.getsize(OUT)
    print(f'wrote {OUT}  ({size/1024:.0f} kB)')


if __name__ == '__main__':
    sys.exit(main())
