"""Minimal USFM parser: extracts \\c/\\v verse text, strips notes and char markup."""
import re

from exeg.corpus import Verse

_ID = re.compile(r"\\id\s+([A-Z0-9]{3})")
_V = re.compile(r"\\v\s+(\d+)(?:[-–]\d+)?[ab]?\s*(.*)")
_MARKER_LINE = re.compile(r"\\\+?([a-z0-9]+)\s*(.*)")
# markers whose line content is NOT verse text
_SKIP = {
    "id", "ide", "usfm", "sts", "rem", "h", "toc1", "toc2", "toc3",
    "mt", "mt1", "mt2", "mt3", "ms", "ms1", "mr", "s", "s1", "s2", "s3",
    "r", "d", "sp", "cl", "cp", "cd", "b", "ib", "periph",
}
_NOTES = re.compile(r"\\[fx]\s.*?\\[fx]\*", re.S)
_W = re.compile(r"\\\+?w\s+([^|\\]*?)(?:\|[^\\]*?)?\\\+?w\*")
_RESIDUAL = re.compile(r"\\\+?[a-zA-Z0-9]+\*?")


def _clean(text: str) -> str:
    text = _NOTES.sub("", text)
    text = _W.sub(r"\1", text)
    text = _RESIDUAL.sub("", text)
    return re.sub(r"\s+", " ", text).strip()


def parse_usfm(text: str) -> tuple[str, list[Verse]]:
    m = _ID.search(text)
    if not m:
        raise ValueError("USFM input has no \\id line")
    code = m.group(1)
    chapter = 0
    verses: list[Verse] = []
    cur: list | None = None  # [chapter, verse, [raw parts]]

    def flush():
        nonlocal cur
        if cur is not None:
            cleaned = _clean(" ".join(cur[2]))
            if cleaned:
                verses.append(Verse(cur[0], cur[1], cleaned))
        cur = None

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("\\c "):
            flush()
            chapter = int(line.split()[1])
            continue
        vm = _V.match(line)
        if vm:
            flush()
            cur = [chapter, int(vm.group(1)), [vm.group(2)]]
            continue
        mm = _MARKER_LINE.match(line)
        if mm:
            if mm.group(1) in _SKIP or cur is None:
                continue
            if mm.group(2):
                cur[2].append(mm.group(2))
            continue
        if cur is not None:
            cur[2].append(line)
    flush()
    return code, verses
