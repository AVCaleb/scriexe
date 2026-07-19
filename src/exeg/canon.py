"""Canonical book table: OSIS/USFM ids, English and Chinese names, chapter counts."""
import difflib
from dataclasses import dataclass


@dataclass(frozen=True)
class Book:
    osis: str
    usfm: str
    en: str
    chapters: int
    zh_abbr: str
    zh: str
    nt: bool


def _b(osis, usfm, en, ch, zh_abbr, zh, nt=False):
    return Book(osis, usfm, en, ch, zh_abbr, zh, nt)


BOOKS = [
    _b("Gen", "GEN", "Genesis", 50, "创", "创世记"),
    _b("Exod", "EXO", "Exodus", 40, "出", "出埃及记"),
    _b("Lev", "LEV", "Leviticus", 27, "利", "利未记"),
    _b("Num", "NUM", "Numbers", 36, "民", "民数记"),
    _b("Deut", "DEU", "Deuteronomy", 34, "申", "申命记"),
    _b("Josh", "JOS", "Joshua", 24, "书", "约书亚记"),
    _b("Judg", "JDG", "Judges", 21, "士", "士师记"),
    _b("Ruth", "RUT", "Ruth", 4, "得", "路得记"),
    _b("1Sam", "1SA", "1 Samuel", 31, "撒上", "撒母耳记上"),
    _b("2Sam", "2SA", "2 Samuel", 24, "撒下", "撒母耳记下"),
    _b("1Kgs", "1KI", "1 Kings", 22, "王上", "列王纪上"),
    _b("2Kgs", "2KI", "2 Kings", 25, "王下", "列王纪下"),
    _b("1Chr", "1CH", "1 Chronicles", 29, "代上", "历代志上"),
    _b("2Chr", "2CH", "2 Chronicles", 36, "代下", "历代志下"),
    _b("Ezra", "EZR", "Ezra", 10, "拉", "以斯拉记"),
    _b("Neh", "NEH", "Nehemiah", 13, "尼", "尼希米记"),
    _b("Esth", "EST", "Esther", 10, "斯", "以斯帖记"),
    _b("Job", "JOB", "Job", 42, "伯", "约伯记"),
    _b("Ps", "PSA", "Psalms", 150, "诗", "诗篇"),
    _b("Prov", "PRO", "Proverbs", 31, "箴", "箴言"),
    _b("Eccl", "ECC", "Ecclesiastes", 12, "传", "传道书"),
    _b("Song", "SNG", "Song of Solomon", 8, "歌", "雅歌"),
    _b("Isa", "ISA", "Isaiah", 66, "赛", "以赛亚书"),
    _b("Jer", "JER", "Jeremiah", 52, "耶", "耶利米书"),
    _b("Lam", "LAM", "Lamentations", 5, "哀", "耶利米哀歌"),
    _b("Ezek", "EZK", "Ezekiel", 48, "结", "以西结书"),
    _b("Dan", "DAN", "Daniel", 12, "但", "但以理书"),
    _b("Hos", "HOS", "Hosea", 14, "何", "何西阿书"),
    _b("Joel", "JOL", "Joel", 3, "珥", "约珥书"),
    _b("Amos", "AMO", "Amos", 9, "摩", "阿摩司书"),
    _b("Obad", "OBA", "Obadiah", 1, "俄", "俄巴底亚书"),
    _b("Jonah", "JON", "Jonah", 4, "拿", "约拿书"),
    _b("Mic", "MIC", "Micah", 7, "弥", "弥迦书"),
    _b("Nah", "NAM", "Nahum", 3, "鸿", "那鸿书"),
    _b("Hab", "HAB", "Habakkuk", 3, "哈", "哈巴谷书"),
    _b("Zeph", "ZEP", "Zephaniah", 3, "番", "西番雅书"),
    _b("Hag", "HAG", "Haggai", 2, "该", "哈该书"),
    _b("Zech", "ZEC", "Zechariah", 14, "亚", "撒迦利亚书"),
    _b("Mal", "MAL", "Malachi", 4, "玛", "玛拉基书"),
    _b("Matt", "MAT", "Matthew", 28, "太", "马太福音", True),
    _b("Mark", "MRK", "Mark", 16, "可", "马可福音", True),
    _b("Luke", "LUK", "Luke", 24, "路", "路加福音", True),
    _b("John", "JHN", "John", 21, "约", "约翰福音", True),
    _b("Acts", "ACT", "Acts", 28, "徒", "使徒行传", True),
    _b("Rom", "ROM", "Romans", 16, "罗", "罗马书", True),
    _b("1Cor", "1CO", "1 Corinthians", 16, "林前", "哥林多前书", True),
    _b("2Cor", "2CO", "2 Corinthians", 13, "林后", "哥林多后书", True),
    _b("Gal", "GAL", "Galatians", 6, "加", "加拉太书", True),
    _b("Eph", "EPH", "Ephesians", 6, "弗", "以弗所书", True),
    _b("Phil", "PHP", "Philippians", 4, "腓", "腓立比书", True),
    _b("Col", "COL", "Colossians", 4, "西", "歌罗西书", True),
    _b("1Thess", "1TH", "1 Thessalonians", 5, "帖前", "帖撒罗尼迦前书", True),
    _b("2Thess", "2TH", "2 Thessalonians", 3, "帖后", "帖撒罗尼迦后书", True),
    _b("1Tim", "1TI", "1 Timothy", 6, "提前", "提摩太前书", True),
    _b("2Tim", "2TI", "2 Timothy", 4, "提后", "提摩太后书", True),
    _b("Titus", "TIT", "Titus", 3, "多", "提多书", True),
    _b("Phlm", "PHM", "Philemon", 1, "门", "腓利门书", True),
    _b("Heb", "HEB", "Hebrews", 13, "来", "希伯来书", True),
    _b("Jas", "JAS", "James", 5, "雅", "雅各书", True),
    _b("1Pet", "1PE", "1 Peter", 5, "彼前", "彼得前书", True),
    _b("2Pet", "2PE", "2 Peter", 3, "彼后", "彼得后书", True),
    _b("1John", "1JN", "1 John", 5, "约一", "约翰一书", True),
    _b("2John", "2JN", "2 John", 1, "约二", "约翰二书", True),
    _b("3John", "3JN", "3 John", 1, "约三", "约翰三书", True),
    _b("Jude", "JUD", "Jude", 1, "犹", "犹大书", True),
    _b("Rev", "REV", "Revelation", 22, "启", "启示录", True),
]

BY_OSIS = {b.osis: b for b in BOOKS}
NT_BOOKS = [b for b in BOOKS if b.nt]
USFM_TO_OSIS = {b.usfm: b.osis for b in BOOKS}
# Masoretic-text chapter counts where they differ from English versification
WLC_CHAPTERS = {"Joel": 4, "Mal": 3}
# common abbreviations that are not prefixes of the English name
EXTRA_ALIASES = {
    "mt": "Matt", "mk": "Mark", "lk": "Luke", "jn": "John", "jhn": "John",
    "php": "Phil", "phm": "Phlm", "sos": "Song", "sng": "Song", "jas": "Jas",
    "1jn": "1John", "2jn": "2John", "3jn": "3John", "rv": "Rev",
}


class UnknownBook(ValueError):
    def __init__(self, query: str, suggestions: list[str]):
        self.query, self.suggestions = query, suggestions
        hint = f" Did you mean: {', '.join(suggestions)}?" if suggestions else ""
        super().__init__(f"Unknown book: {query!r}.{hint}")


def max_chapters(book: Book) -> int:
    return max(book.chapters, WLC_CHAPTERS.get(book.osis, 0))


def _norm(s: str) -> str:
    return s.replace(" ", "").replace("　", "").replace(".", "").lower()


def find_book(name: str) -> Book:
    q = _norm(name)
    if not q:
        raise UnknownBook(name, [])
    for b in BOOKS:
        if q in (_norm(b.osis), _norm(b.usfm), _norm(b.en)) or q in (b.zh_abbr, b.zh):
            return b
    if q in EXTRA_ALIASES:
        return BY_OSIS[EXTRA_ALIASES[q]]
    hits = [b for b in BOOKS if _norm(b.en).startswith(q) or _norm(b.osis).startswith(q)]
    uniq = {b.osis: b for b in hits}
    if len(uniq) == 1:
        return next(iter(uniq.values()))
    if uniq:
        raise UnknownBook(name, sorted(uniq))
    names = {_norm(b.en): b.osis for b in BOOKS}
    close = difflib.get_close_matches(q, names, n=3, cutoff=0.6)
    raise UnknownBook(name, [names[c] for c in close])
