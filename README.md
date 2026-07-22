<div align="center">

# scriexe

### Read deeply. Study in context. Stay in flow.

A keyboard-first Bible study TUI for immersive Scripture reading, original-language research, and personal exegesis.

[![npm](https://img.shields.io/npm/v/scriexe?color=cb3837&label=npm)](https://www.npmjs.com/package/scriexe)
[![Platforms](https://img.shields.io/badge/platform-macOS%20%7C%20Linux%20%7C%20Windows-64748b)](#platform-support)
[![Release](https://github.com/AVCaleb/scriexe/actions/workflows/release-scriexe.yml/badge.svg)](https://github.com/AVCaleb/scriexe/actions/workflows/release-scriexe.yml)

**English** | [中文](README_ZH.md)

```bash
npm install -g scriexe
scriexe
```

</div>

---

## Why scriexe?

Serious Bible study is often fragmented across translation websites, lexicons, search tools, note files, and browser tabs. Every switch breaks the reading context: the passage moves out of sight, observations become scattered, and the work of interpretation becomes separated from the text that prompted it.

**scriexe brings that workflow back into one focused terminal workspace.** Move naturally from book to chapter, verse, and original-language word; compare translations without leaving the passage; examine morphology and occurrences; search the corpus; record notes; bookmark a location; and return to the text without losing your place.

scriexe is not designed to flood the screen with information. It is designed to keep the right information close to the passage—so reading, observation, word study, and note-taking remain part of one continuous process.

## One workspace, one continuous study flow

- **Contextual Reading** — Conventional study tools separate passage navigation, translation comparison, and surrounding context across different pages or tabs, forcing you to find your place repeatedly. scriexe keeps the four-level navigator, parallel translations, and adjustable reading scope together, so the passage remains visible while the depth of view changes.

- **Original-Language Study** — A normal lexicon lookup pulls you away from the verse and leaves you to reconstruct its context afterward. scriexe continues directly from verse to Greek or Hebrew word, bringing lemmas, Strong’s numbers, morphology, and corpus occurrences into the same reading path—and preserving a bookmark for the way back.

- **Local Study Notes** — When observations live in unrelated documents, the connection between a note and the text that prompted it gradually disappears. scriexe attaches plain Markdown notes directly to verses and word occurrences, marks passages you have studied, and keeps every note portable, searchable, and under your control.

- **Keyboard-First Flow** — Repeated mouse movement and window switching interrupt the rhythm of close reading. scriexe keeps navigation, scope changes, search, notes, bookmarks, and occurrence jumps on the keyboard, while Unicode-aware wrapping keeps multilingual passages aligned and readable.

## What is included?

The base installation is useful immediately. It bundles two public-domain translations and does not require Python or a first-launch download:

| Included offline | Purpose |
| --- | --- |
| CUVS / 简体和合本 | Chinese reading and parallel comparison |
| ASV (1901) | A highly literal English translation in the lineage later continued by NASB/NASB95; its close attention to wording and sentence structure makes it especially useful for detailed study alongside CUVS. |

During onboarding, you may choose **Download all optional study data**. The same action remains available in Settings, and interrupted downloads can be retried without discarding completed datasets.

| Optional public data | What it adds |
| --- | --- |
| SBLGNT | Greek New Testament forms, lemmas, and morphology |
| WLC | Hebrew Old Testament forms, lemmas, and morphology |
| Strong’s dictionaries | Strong’s lookup and lexical connections |
| WEB and KJV | Additional English comparison texts |
| Vulgate | Latin comparison text |

ESV and NASB95 are not redistributed with scriexe. They can be accessed only through the user’s own API key or a locally imported copy where supported. User-licensed translations are kept outside the installed package and are never included in release artifacts.

## Quick start

### 1. Install

Node.js 18 or later is required for installation. Python is not required.

```bash
npm install -g scriexe
```

npm selects the native package for your operating system and architecture. The same command name works on macOS, Linux, and Windows:

```bash
scriexe
```

### 2. Complete onboarding

On first launch, choose the interface language and the translations you want visible by default. You can begin immediately with CUVS and ASV, or download the complete public study dataset before entering the workspace.

API keys are optional. They can be added later from Settings without affecting offline reading.

### 3. Start reading

The TUI opens directly into the reading workspace. A typical study session can remain entirely inside scriexe:

1. Open the navigator and select a passage.
2. Choose window, chapter, or verse scope.
3. Compare the visible translations.
4. Drill into a Greek or Hebrew word when study data is available.
5. Follow occurrences while preserving a bookmark.
6. Record observations beside the verse or word.
7. Search and revisit earlier observations without leaving the workspace.

## Essential keys

| Context | Keys | Action |
| --- | --- | --- |
| Anywhere | `Tab` | Open or close the navigator |
| Navigator | `j` / `k` | Move through items |
| Navigator | `h` / `l` | Move up or drill down a column |
| Navigator | `Enter` | Open the selected verse or word |
| Reading | `j` / `k` | Move between verses |
| Reading | `z` | Cycle window, chapter, and verse scope |
| Reading | `+` / `-` | Resize the context window |
| Reading | `p` / `b` | Set and return to a bookmark |
| Reading | `i` | Edit a note |
| Reading | `/` | Find text in the current verse preview |
| Find active | `j` / `k` | Move between matches |
| Find active | `Enter` / `Esc` | Accept the viewport / clear find |
| Reading | `o` | Open Settings |
| Word/results | `Enter` | Jump to the selected occurrence |
| Anywhere | `?` | Open help |

## Command-line tools

The interactive workspace is the main experience, but the same installation also provides one-shot commands for scripts and quick lookups:

```bash
# Display a passage in selected versions
scriexe passage "1Pet 3:18-22" --versions cuvs,asv

# Search the local corpus
scriexe search "living hope"

# Study a Strong’s number or lemma after installing study data
scriexe word G3958

# Download or refresh public datasets
scriexe fetch

# Import a user-provided translation
scriexe import ./translation.usfm --version mytranslation

# Generate a bilingual Markdown study file
scriexe scaffold "1Pet 3:18-22"
```

English and Chinese reference forms are accepted by passage-oriented commands.

## Local-first by design

scriexe separates the installed application from your personal workspace. Bundled resources are read-only; notes, settings, API keys, imports, caches, and downloaded datasets are written to a user-data directory:

| Platform | User-data location |
| --- | --- |
| macOS | `~/Library/Application Support/scriexe` |
| Linux | `$XDG_DATA_HOME/scriexe` or `~/.local/share/scriexe` |
| Windows | `%LOCALAPPDATA%\scriexe` |

Study exports and scaffolded Markdown files go into the `studies` subdirectory of that user-data location. Every successful export reports the complete absolute path, so the destination is never implicit.

A downloaded or imported corpus file takes precedence over the bundled fallback without modifying the npm installation. This keeps upgrades separate from personal work and makes a damaged installation easier to replace.

Release builds exclude `.env`, notes, studies, caches, source downloads, and imported translations. Network access occurs only when you request a download or use a configured online translation API.

## Planned AI-assisted exegesis

AI assistance is on the roadmap, but it is not presented as a substitute for reading or judgment.

The planned direction is a context-aware assistant that works from the current passage, nearby context, original-language data, and the user’s own notes. It may help organize observations, surface questions worth investigating, compare existing material, and identify places where an argument needs closer textual support.

The intended boundary is equally important: generated suggestions should remain distinguishable from the biblical text and from the user’s own conclusions. The user remains responsible for interpretation; AI should make careful study easier to organize, not make interpretive authority disappear behind a generated answer.

## Platform support

The npm launcher installs one matching native build:

- macOS — Apple Silicon and Intel
- Linux — ARM64 and x64
- Windows — x64

If npm optional dependencies are disabled, the native package will not be installed. Reinstall with optional dependencies enabled if scriexe reports that its platform package is missing.

## Project status

scriexe is an early release. The core reading, navigation, search, note, word-study, and import workflows are implemented and tested, while packaging and interface details may continue to evolve as the project is used on more terminals and operating systems.

The project deliberately favors a small, understandable local workspace over accounts, synchronization services, or hidden background processes.

## Development

Clone the repository and prepare a local Python environment:

```bash
git clone https://github.com/AVCaleb/scriexe.git
cd scriexe
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/exeg fetch
.venv/bin/pytest -q
.venv/bin/exeg
```

Run the JavaScript launcher tests:

```bash
node --test npm/scriexe/test/*.test.js
```

Build a local standalone folder:

```bash
.venv/bin/pip install -e '.[distribution]'
.venv/bin/exeg fetch --only ebible --versions cuvs,asv
.venv/bin/python packaging/build_core_data.py --output build/core
.venv/bin/pyinstaller --clean --noconfirm packaging/scriexe.spec
```

## Data and attribution

CUVS and ASV are packaged from public-domain distributions provided by [eBible.org](https://ebible.org/). Attribution files are included with every native package. Optional datasets retain their respective upstream source information.

Licensed translations remain subject to their providers’ terms and are not redistributed by this project.

## Contributing

Bug reports, terminal compatibility reports, documentation improvements, and focused feature proposals are welcome through GitHub Issues. When reporting a display issue, include the operating system, terminal application, terminal width, and a screenshot when possible.

---

<div align="center">

**A quieter interface for deeper reading.**

[Install](#quick-start) · [Features](#one-workspace-one-continuous-study-flow) · [Privacy](#local-first-by-design) · [Roadmap](#planned-ai-assisted-exegesis)

</div>
