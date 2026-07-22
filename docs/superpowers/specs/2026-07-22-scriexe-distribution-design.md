# scriexe Standalone Distribution Design

## Summary

Distribute the existing Python `exeg` terminal application as a standalone,
cross-platform npm-installed command named `scriexe`:

```bash
npm install -g scriexe
scriexe
```

The internal Python package and all user-facing TUI branding remain `exeg`.
Recipients need Node/npm to install the command, but do not need Python.

The base installation works offline with CUVS and ASV. A single optional
download action in onboarding and Settings installs all public study datasets.

## Goals

- Support macOS, Linux, and Windows.
- Make `scriexe` the exact shell command on every platform; npm supplies the
  `.cmd`/PowerShell shims on Windows.
- Require no recipient-side Python installation.
- Bundle CUVS and ASV for immediate offline reading.
- Keep notes, settings, imports, caches, API keys, and downloads writable and
  outside the installed package.
- Preserve all existing `exeg` subcommands behind the new command, such as
  `scriexe passage`, `scriexe fetch`, and `scriexe import`.
- Let users install all optional public datasets from either first-run
  onboarding or Settings.

## Non-goals

- Do not rewrite the Python application in JavaScript.
- Do not rename the internal `exeg` package or the visible `exeg` TUI.
- Do not bundle ESV, NASB95, user imports, API keys, notes, or caches.
- Do not bundle original-language/Strong's datasets in the base npm install.
- Do not provide native MSI, PKG, DMG, DEB, or RPM installers in this phase.

## Distribution Architecture

### npm package topology

The public package `scriexe` is a small JavaScript launcher. It declares all
native packages as `optionalDependencies`; each native package declares npm
`os` and `cpu` constraints, so npm installs only the compatible artifact.

Initial packages:

- `scriexe`
- `scriexe-darwin-arm64`
- `scriexe-darwin-x64`
- `scriexe-linux-arm64`
- `scriexe-linux-x64`
- `scriexe-win32-x64`

The unscoped `scriexe` name was unclaimed in the npm registry when this design
was written. All package names must be reserved before the first public
release.

The main package exposes `bin/scriexe.js` through its `bin.scriexe` field. The
launcher maps `process.platform` and `process.arch` to one native package,
resolves its executable, runs it with inherited stdin/stdout/stderr, forwards
all arguments, and exits with the same status or signal result.

Unsupported platform/architecture combinations produce an actionable error
listing supported targets. A missing native optional dependency produces a
reinstall message rather than a JavaScript stack trace.

### Native application packages

GitHub Actions builds each native package on its corresponding operating
system using PyInstaller one-folder mode. One-folder mode is preferred over
one-file mode because it avoids extracting CUVS/ASV on every startup and makes
resource lookup predictable.

Each native package contains:

- `scriexe` (`scriexe.exe` on Windows)
- PyInstaller runtime files
- Bundled CUVS corpus
- Bundled ASV corpus
- Public-domain/source attribution for both corpora

Windows builds install and freeze `windows-curses`. macOS and Linux use their
native Python curses support.

## Runtime Storage and Corpus Overlay

Installed npm package contents are immutable resources. Runtime writes use a
platform user-data root:

- macOS: `~/Library/Application Support/scriexe`
- Linux: `$XDG_DATA_HOME/scriexe`, falling back to
  `~/.local/share/scriexe`
- Windows: `%LOCALAPPDATA%\scriexe`

The existing `EXEG_ROOT` override remains supported for development, testing,
and portable/custom installations.

The corpus module separates two concepts:

1. **Resource root** — packaged, read-only CUVS/ASV (or the repository root in
   source-checkout mode).
2. **User root** — writable downloads, imports, notes, settings, `.env`, cache,
   sources, and exports.

Verse reads check paths in this order:

1. User corpus (`<user-root>/data/corpus/...`)
2. Bundled corpus (`<resource-root>/data/corpus/...`)

This lets a user download or import a replacement without mutating the npm
installation. All corpus writes target the user corpus. Notes, setup metadata,
API-key storage, studies, caches, and source downloads also target the user
root.

Packaged first-run translation defaults are CUVS and ASV. Original-language
versions are not selected until their data exists. Before the optional pack is
installed, reading remains fully functional while word navigation/search
shows a concise prompt to download study data instead of failing.

## Bundled Core Corpora

The release workflow fetches and normalizes only:

- CUVS (`cmn-cu89s`)
- ASV (`eng-asv`)

The source distributions currently identify both as public domain. Release
artifacts retain their attribution metadata. Corpus files remain generated
build inputs and are not committed under `data/`, preserving the repository's
existing data policy.

A packaging manifest enumerates required books and validates that both
translations are complete before PyInstaller runs. A missing/incomplete core
corpus fails the build instead of publishing a partially functional package.

## Optional Study Data

One optional pack includes all of the following:

- SBLGNT
- WLC
- Strong's Greek and Hebrew dictionaries
- WEB
- KJV
- Vulgate

SBLGNT, WLC, and Strong's enable the Words column, lemma/Strong's lookup,
morphology, and occurrence lists. WEB, KJV, and Vulgate add public translation
choices. CUVS and ASV are not downloaded again because they already exist in
the resource bundle unless the user explicitly requests a writable refresh.

Fetching is dependency-aware: Strong's is prepared before SBLGNT so Greek
Strong's mappings are available during normalization. Each dataset is
idempotent and independently detectable. A retry skips complete datasets and
continues incomplete ones.

## Onboarding and Settings UX

Both first-run onboarding and Settings include this action:

> Download all optional study data (~50 MB)

### Onboarding

The action appears before the final Begin action. Users may:

- Download the pack and then begin; or
- Skip downloading and begin immediately with CUVS/ASV.

### Settings

The same action remains available later. Its status is one of:

- Not installed
- Partially installed
- Installed

Selecting an installed action is a safe no-op unless datasets are incomplete.

### Progress and errors

The curses screen temporarily switches to a progress view listing each
dataset. Completed datasets receive a success marker. Network or parse failure
identifies the dataset, preserves all completed work, and offers retry or
return. Returning never prevents use of bundled CUVS/ASV.

No download runs silently during npm installation or ordinary startup.

## Build and Release Pipeline

A tagged release runs these stages:

1. Run the complete Python test suite.
2. Fetch and validate core CUVS/ASV build resources.
3. Build PyInstaller artifacts on native runners for each supported target.
4. Smoke-test each binary with `scriexe --version` and verify bundled CUVS/ASV
   discovery without network access.
5. Pack each native npm package and inspect its file list.
6. Test the main JavaScript launcher against platform mappings and argument,
   terminal-I/O, signal, and exit-code forwarding.
7. Publish all native packages at the same version.
8. Publish the main `scriexe` package only after every required native package
   succeeds.

Publishing requires an npm automation token stored as a GitHub Actions secret.
A failed platform build or native-package publish prevents publishing the main
package, avoiding a release that installs but cannot launch.

## Error Handling

- Unsupported platform: state the detected platform/architecture and supported
  targets.
- Missing native package: recommend reinstalling with optional dependencies
  enabled.
- Missing bundled corpus: fail the release smoke test; at runtime show a clear
  installation-corruption message.
- Unwritable user-data directory: show its path and the OS error without
  writing into the npm package.
- Interrupted optional download: preserve completed datasets and permit an
  idempotent retry.
- Offline first launch: continue with bundled CUVS/ASV.
- Windows terminal without usable curses initialization: retain the existing
  one-shot-command fallback message.

## Testing Strategy

### Python unit and integration tests

- Frozen/source resource-root selection
- Platform user-data paths and `EXEG_ROOT` override
- User corpus precedence over bundled corpus
- Writes never target bundled resources
- CUVS/ASV packaged defaults
- Missing optional datasets degrade cleanly
- Optional-pack manifest and dependency order
- Installed/partial/not-installed detection
- Onboarding and Settings pending download actions
- Retry skips complete datasets

### JavaScript tests

- Every supported `platform/arch` mapping
- Unsupported target error
- Missing optional dependency error
- Argument forwarding
- Inherited terminal I/O
- Exit-code and signal forwarding

### Release smoke tests

On every native runner:

- Executable starts without system Python
- `--version` succeeds
- Bundled CUVS and ASV are discoverable offline
- Writable user data is created outside the package
- Existing Python tests pass before packaging
- `npm pack` contains only intended runtime files

## Privacy and Release Safety

Build inputs and npm artifacts are scanned to exclude:

- `.env` and API keys
- `notes/`
- `studies/`
- caches
- user-imported/licensed translations
- local source-download directories except required attribution files

Only public application code, runtime dependencies, CUVS, ASV, and their
attribution are distributable artifacts.

## Acceptance Criteria

A new user on a supported macOS, Linux, or Windows target can run:

```bash
npm install -g scriexe
scriexe
```

The TUI starts without Python, displays its existing `exeg` branding, reads
CUVS and ASV offline, and stores all personal/runtime data outside the npm
installation. The user can skip the optional pack during onboarding or install
all optional study data from onboarding or Settings. The same command exposes
all existing CLI subcommands.
