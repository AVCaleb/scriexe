# exegesis

Terminal Bible-exegesis workspace: parallel multilingual reading, navigation,
notes, search, and optional Greek/Hebrew word studies.

## Install the standalone command

Install Node.js/npm, then:

```bash
npm install -g scriexe
scriexe
```

The command keeps the visible application name `exeg`. The base installation
bundles public-domain CUVS (简体和合本) and ASV, so reading works offline without
Python or an initial download.

During onboarding, choose **Download all optional study data** to add SBLGNT,
WLC, Strong's dictionaries, WEB, KJV, and Vulgate. The same action remains in
Settings and can safely retry an interrupted download.

Runtime data is kept outside the npm installation:

- macOS: `~/Library/Application Support/scriexe`
- Linux: `$XDG_DATA_HOME/scriexe` or `~/.local/share/scriexe`
- Windows: `%LOCALAPPDATA%\scriexe`

API keys and user-licensed translations are never included in release
artifacts. ESV and NASB95 require the user's own API key or imported copy.

All existing one-shot commands remain available through the new executable:

```bash
scriexe passage "1Pet 3:18-22"
scriexe search "living hope"
scriexe word G3958
scriexe fetch
```

## Source development

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/exeg fetch
.venv/bin/exeg
```

Build a local standalone folder after fetching CUVS and ASV:

```bash
.venv/bin/pip install -e '.[distribution]'
.venv/bin/exeg fetch --only ebible --versions cuvs,asv
.venv/bin/python packaging/build_core_data.py --output build/core
.venv/bin/pyinstaller --clean --noconfirm packaging/scriexe.spec
```

See `AGENTS.md` for repository study and copyright rules.
