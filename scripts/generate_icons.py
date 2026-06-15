#!/usr/bin/env python3
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "voice_input" / "static"

BASE = '''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" width="48" height="48">
  <rect x="14" y="6" width="20" height="20" rx="4" ry="4" fill="{COLOR}"/>
  <line x1="17" y1="11" x2="31" y2="11" stroke="rgba(255,255,255,0.5)" stroke-width="1"/>
  <line x1="17" y1="15" x2="31" y2="15" stroke="rgba(255,255,255,0.5)" stroke-width="1"/>
  <line x1="17" y1="19" x2="31" y2="19" stroke="rgba(255,255,255,0.5)" stroke-width="1"/>
  <rect x="22" y="26" width="4" height="8" fill="{COLOR}"/>
  <rect x="16" y="33" width="16" height="2" fill="{COLOR}"/>
</svg>'''

OUT.mkdir(parents=True, exist_ok=True)

(OUT / "idle.svg").write_text(BASE.replace("{COLOR}", "#888888"))

recording_svg = BASE.replace("{COLOR}", "#E53935")
recording_svg = recording_svg.replace(
    '</svg>',
    '  <ellipse cx="33" cy="33" rx="5" ry="5" fill="#E53935"/>\n</svg>'
)
(OUT / "recording.svg").write_text(recording_svg)

transcribing_svg = BASE.replace("{COLOR}", "#1976D2")
transcribing_svg = transcribing_svg.replace(
    '</svg>',
    '  <ellipse cx="34" cy="36" rx="2" ry="2" fill="#1976D2"/>\n'
    '  <ellipse cx="37" cy="36" rx="2" ry="2" fill="#1976D2"/>\n'
    '  <ellipse cx="40" cy="36" rx="2" ry="2" fill="#1976D2"/>\n</svg>'
)
(OUT / "transcribing.svg").write_text(transcribing_svg)
