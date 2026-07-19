"""Scripture reference parsing: '1Pet 3:18-22', '1 Peter 3:18–22', '彼前3：18-22'."""
import re
from dataclasses import dataclass

from exeg import canon


class BadRef(ValueError):
    pass


_TRANSLATE = str.maketrans({"：": ":", "–": "-", "—": "-", "~": "-", "－": "-", "　": " "})
_RANGE = re.compile(
    r"^(?P<book>.+?)\s*(?P<ch>\d+)\s*:\s*(?P<v1>\d+)"
    r"(?:\s*-\s*(?:(?P<ch2>\d+)\s*:\s*)?(?P<v2>\d+))?$"
)
_CHAPTER = re.compile(r"^(?P<book>.+?)\s*(?P<ch>\d+)$")


@dataclass(frozen=True)
class Ref:
    book: canon.Book
    chapter: int
    verse: int | None
    end_chapter: int
    end_verse: int | None

    def contains(self, ch: int, v: int) -> bool:
        if self.verse is None:
            return ch == self.chapter
        return (self.chapter, self.verse) <= (ch, v) <= (self.end_chapter, self.end_verse)

    def _span(self) -> str:
        if self.verse is None:
            return f"{self.chapter}"
        if (self.chapter, self.verse) == (self.end_chapter, self.end_verse):
            return f"{self.chapter}:{self.verse}"
        if self.chapter == self.end_chapter:
            return f"{self.chapter}:{self.verse}–{self.end_verse}"
        return f"{self.chapter}:{self.verse}–{self.end_chapter}:{self.end_verse}"

    def en_label(self) -> str:
        return f"{self.book.en} {self._span()}"

    def zh_label(self, full: bool = False) -> str:
        name = self.book.zh if full else self.book.zh_abbr
        return f"{name} {self._span()}"

    def slug(self) -> str:
        span = self._span().replace(":", ".").replace("–", "-")
        return f"{self.book.osis.lower()}_{span}"


def parse_ref(s: str) -> Ref:
    text = s.translate(_TRANSLATE).strip()
    m = _RANGE.match(text)
    if m:
        book = canon.find_book(m["book"])
        ch, v1 = int(m["ch"]), int(m["v1"])
        ch2 = int(m["ch2"]) if m["ch2"] else ch
        v2 = int(m["v2"]) if m["v2"] else v1
        ref = Ref(book, ch, v1, ch2, v2)
    else:
        m = _CHAPTER.match(text)
        if not m:
            raise BadRef(f"Cannot parse reference: {s!r} (expected forms like '1Pet 3:18-22', '彼前3:18-22', 'Ps 23')")
        book = canon.find_book(m["book"])
        ch = int(m["ch"])
        ref = Ref(book, ch, None, ch, None)
    limit = canon.max_chapters(ref.book)
    if not (1 <= ref.chapter <= limit and 1 <= ref.end_chapter <= limit):
        raise BadRef(f"{ref.book.en} has {limit} chapters; got chapter {max(ref.chapter, ref.end_chapter)}")
    if ref.verse is not None:
        if ref.verse < 1 or ref.end_verse < 1:
            raise BadRef("Verse numbers start at 1")
        if (ref.end_chapter, ref.end_verse) < (ref.chapter, ref.verse):
            raise BadRef(f"Range end {ref.end_chapter}:{ref.end_verse} precedes start {ref.chapter}:{ref.verse}")
    return ref
