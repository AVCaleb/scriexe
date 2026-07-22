"""Interface internationalization for the exeg TUI.

Two interface languages: English (en) and 中文 (zh). `tr(lang, key, **kw)`
looks up a string; falls back to English then to the key itself.
"""
LANGS = {"en": "English", "zh": "中文"}
DEFAULT_LANG = "en"

S = {
    # status / mode hints
    "nav_hint": {"en": "j/k move · l drill · h up · Enter commit · Esc exit · ? help",
                 "zh": "j/k 移动 · l 下钻 · h 上级 · Enter 选定 · Esc 退出 · ? 帮助"},
    "normal_hint": {"en": "j/k verse · Tab nav · z scope · +/- window · i note · / find · b back · p mark · ? help · o settings · :q quit",
                    "zh": "j/k 经文 · Tab 导航 · z 范围 · +/- 窗口 · i 笔记 · / 查找 · b 返回 · p 书签 · ? 帮助 · o 设置 · :q 退出"},
    "word_hint": {"en": "j/k select · Enter jump · Esc back",
                  "zh": "j/k 选择 · Enter 跳转 · Esc 返回"},
    "result_hint": {"en": "j/k select · Enter jump · Esc back",
                    "zh": "j/k 选择 · Enter 跳转 · Esc 返回"},
    "insert_status": {"en": " INSERT · type to edit · Esc save · Ctrl-C discard · Backspace del ",
                      "zh": " 插入 · 输入编辑 · Esc 保存 · Ctrl-C 放弃 · Backspace 删除 "},
    "pinned_status": {"en": "PINNED — Tab roam · p release · i note",
                      "zh": "已钉住 — Tab 浏览 · p 取消 · i 笔记"},
    # column headers
    "col_books": {"en": "Books", "zh": "书卷"},
    "col_ch": {"en": "Ch", "zh": "章"},
    "col_vs": {"en": "Vs", "zh": "节"},
    "col_words": {"en": "Words", "zh": "词"},
    # title parts
    "focus_mark": {"en": "focus", "zh": "焦点"},
    "bm_mark": {"en": "bm", "zh": "签"},
    "set_mark": {"en": "set", "zh": "选段"},
    # scope names
    "scope_window": {"en": "window", "zh": "窗口"},
    "scope_chapter": {"en": "chapter", "zh": "全章"},
    "scope_verse": {"en": "verse", "zh": "单节"},
    # messages
    "bookmarked": {"en": "bookmarked {ref}", "zh": "已加书签 {ref}"},
    "returned": {"en": "returned to {ref}", "zh": "已返回 {ref}"},
    "no_bookmark": {"en": "no bookmark — press p to set one", "zh": "无书签 — 按 p 设置"},
    "study_set": {"en": "study set: {ref}", "zh": "选段：{ref}"},
    "study_set_cleared": {"en": "study set cleared (chapter scope)", "zh": "已清除选段（回到全章）"},
    "versions_set": {"en": "versions: {vs}", "zh": "译本：{vs}"},
    "no_occurrences": {"en": "no occurrences of {q!r}", "zh": "未找到 {q!r} 的出现"},
    "occurrences_count": {"en": "{n} occurrences", "zh": "{n} 处出现"},
    "no_matches": {"en": "no matches", "zh": "无匹配"},
    "matches_count": {"en": "{n} matches", "zh": "{n} 处匹配"},
    "bad_ref": {"en": "bad reference: {e}", "zh": "无法解析经文：{e}"},
    "bad_scope": {"en": "bad scope '{a}' — try window|chapter|verse", "zh": "范围 '{a}' 无效 — 试试 window|chapter|verse"},
    "exported": {"en": "exported -> {p}", "zh": "已导出 -> {p}"},
    "help_open": {"en": "help — j/k scroll, q to close", "zh": "帮助 — j/k 滚动，q 关闭"},
    "find_hits": {"en": "/{pat}: {n} hits", "zh": "/{pat}：{n} 处命中"},
    "find_cleared": {"en": "find cleared", "zh": "已清除查找"},
    # editor / note
    "note_word": {"en": "note", "zh": "笔记"},
    "note_chapter": {"en": "chapter", "zh": "章"},
    "note_book": {"en": "book", "zh": "书"},
    "esc_save_hint": {"en": "Esc save · Ctrl-C discard", "zh": "Esc 保存 · Ctrl-C 放弃"},
    "note_edit_prompt": {"en": "(i to edit)", "zh": "(i 编辑)"},
    # word study
    "word_study": {"en": "word study", "zh": "字词研究"},
    "gloss": {"en": "gloss", "zh": "释义"},
    "in_corpus": {"en": "in corpus", "zh": "全书出现"},
    "occurrences": {"en": "occurrences ({n})  — j/k select · Enter jump · Esc back",
                    "zh": "出现 ({n})  — j/k 选择 · Enter 跳转 · Esc 返回"},
    # help overlay
    "help_title": {"en": "exeg TUI — help   (j/k scroll · q or Esc to close)",
                   "zh": "exeg 终端释经 — 帮助   (j/k 滚动 · q 或 Esc 关闭)"},
    # settings page
    "settings_title": {"en": "Settings  (j/k move · Enter toggle · Esc back)",
                       "zh": "设置  (j/k 移动 · Enter 切换 · Esc 返回)"},
    "set_iface_lang": {"en": "Interface language", "zh": "界面语言"},
    "set_translations": {"en": "Scripture translations", "zh": "译本选择"},
    "set_orig_auto": {"en": "Greek/Hebrew originals: automatic per testament",
                      "zh": "希腊/希伯来原文：按卷自动"},
    "set_section_zh": {"en": "Chinese", "zh": "中文"},
    "set_section_en": {"en": "English", "zh": "英文"},
    "set_section_la": {"en": "Latin", "zh": "拉丁文"},
    "study_data": {"en": "Optional study data", "zh": "可选研经数据"},
    "download_pack": {"en": "Download all optional study data (~50 MB)",
                      "zh": "下载全部可选研经数据（约 50 MB）"},
    "pack_status_not_installed": {"en": "not installed", "zh": "未安装"},
    "pack_status_partial": {"en": "partially installed", "zh": "部分安装"},
    "pack_status_installed": {"en": "installed", "zh": "已安装"},
}


def tr(lang: str, key: str, **kw) -> str:
    entry = S.get(key)
    if not entry:
        return key
    val = entry.get(lang) or entry.get(DEFAULT_LANG) or key
    try:
        return val.format(**kw)
    except Exception:
        return val


def lang_name(code: str) -> str:
    return LANGS.get(code, code)