# exegesis

Terminal Bible-exegesis workspace: a local multilingual corpus (SBLGNT, WLC,
WEB, KJV, 和合本, Strong's) + `exeg`, a CLI that prints parallel passages,
does word studies, and scaffolds bilingual (EN/中文) study files. ESV and
NASB95 display via licensed APIs (`ESV_API_KEY`, `API_BIBLE_KEY` in `.env`)
or `exeg import` of your own licensed copy.

## Setup

    python3 -m venv .venv
    .venv/bin/pip install -e '.[dev]'
    .venv/bin/exeg fetch

## Use

    .venv/bin/exeg passage "1Pet 3:18-22"      # or 彼前3:18-22
    .venv/bin/exeg word G3958
    .venv/bin/exeg search "living hope"
    .venv/bin/exeg scaffold "1Pet 3:18-22"     # → studies/1pet_3.18-22.md

See AGENTS.md for the rules assisting agents must follow.
