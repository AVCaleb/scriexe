import json
import pytest
from exeg import corpus, scaffold
from exeg.corpus import Verse, Word
from exeg.refs import parse_ref

def seed(corpus_root):
    corpus.write_words("sblgnt", "1Pet", [
        Word(2, 21, 1, "ἔπαθεν", "πάσχω", "G3958", "V-/3AAI-S--"),
        Word(3, 18, 1, "ὅτι", "ὅτι", "G3754", "C-/--------"),          # conjunction: excluded
        Word(3, 18, 2, "Χριστὸς", "Χριστός", "G5547", "N-/----NSM-"),
        Word(3, 18, 3, "ἔπαθεν", "πάσχω", "G3958", "V-/3AAI-S--"),
        Word(3, 19, 1, "ἐστίν", "εἰμί", "G1510", "V-/3PAI-S--"),        # stoplist: excluded
        Word(3, 19, 2, "Χριστὸς", "Χριστός", "G5547", "N-/----NSM-"),  # dup lemma: excluded
    ])
    corpus.write_verses("cuvs", "1Pet", [Verse(3, 18, "因基督也曾一次为罪受苦"), Verse(3, 19, "他借这灵曾去传道")])
    sdir = corpus.corpus_dir() / "strongs"
    sdir.mkdir(parents=True, exist_ok=True)
    (sdir / "greek.json").write_text(json.dumps({"G3958": {"lemma": "πάσχω", "strongs_def": "to suffer"}}), encoding="utf-8")
    (sdir / "hebrew.json").write_text("{}", encoding="utf-8")
    (sdir / "greek-lemma-map.json").write_text("{}", encoding="utf-8")

def test_pick_words(corpus_root):
    seed(corpus_root)
    picked = scaffold.pick_words(parse_ref("1Pet 3:18-19"))
    assert [w.lemma for w in picked] == ["Χριστός", "πάσχω"]

def test_build_structure(corpus_root, monkeypatch):
    seed(corpus_root)
    monkeypatch.delenv("ESV_API_KEY", raising=False)
    monkeypatch.delenv("API_BIBLE_KEY", raising=False)
    md = scaffold.build(parse_ref("1Pet 3:18-19"), today="2026-07-19")
    assert md.startswith("# 1 Peter 3:18–19 · 彼得前书 3:18–19\n")
    assert "> scaffolded 2026-07-19 · " in md
    for h in ("## Text · 经文对照", "## Word Studies · 字词研究", "## Structure & Context · 结构与背景",
              "## Interpretation · 释经结论", "## Theology & Application · 神学综合与应用"):
        assert h in md
    assert "### πάσχω (ἔπαθεν, v. 18) — G3958 · aorist active indicative 3sg" in md
    assert "gloss: to suffer · in 1 Peter: 2× (2:21, 3:18)" in md
    assert "（your analysis · 你的分析）" in md
    assert "- **和合本** 因基督也曾一次为罪受苦" in md
    assert "> ESV unavailable" in md
    assert "Cross-references · 串珠：" in md

def test_write_and_force(corpus_root):
    seed(corpus_root)
    ref = parse_ref("1Pet 3:18-19")
    path = scaffold.write(ref)
    assert path == corpus.root() / "studies" / "1pet_3.18-19.md"
    assert path.exists()
    with pytest.raises(SystemExit):
        scaffold.write(ref)
    scaffold.write(ref, force=True)

def test_cli(corpus_root, capsys):
    seed(corpus_root)
    from exeg.cli import main
    assert main(["scaffold", "彼前3:18-19"]) == 0
    assert "studies/1pet_3.18-19.md" in capsys.readouterr().out
