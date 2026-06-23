#!/usr/bin/env python3
"""
教科書高精度検索ツール v2
使い方:
  python3 ~/textbook-chatbot/search.py "キーワード1 キーワード2"
  python3 ~/textbook-chatbot/search.py "腰椎前弯 原因" --book 義肢装具学
  python3 ~/textbook-chatbot/search.py "ROM制限" --full
  python3 ~/textbook-chatbot/search.py "スカルパ三角" --semantic
"""

import json, os, sys, re, argparse
from pathlib import Path

CACHE_DIR = Path.home() / "textbook-chatbot" / "ocr_cache"

# ── 書誌メタデータ ──────────────────────────────────────────────
BOOK_META = {
    "理学療法概説":          {"series": "標準理学療法学",              "publisher": "医学書院", "year": "2018"},
    "神経理学療法学":         {"series": "標準理学療法学",              "publisher": "医学書院", "year": "2018"},
    "運動療法学各論":         {"series": "標準理学療法学",              "publisher": "医学書院", "year": "2018"},
    "運動療法学総論":         {"series": "標準理学療法学",              "publisher": "医学書院", "year": "2018"},
    "骨関節理学療法学":       {"series": "標準理学療法学",              "publisher": "医学書院", "year": "2018"},
    "内部疾患理学療法学":     {"series": "標準理学療法学",              "publisher": "医学書院", "year": "2018"},
    "地域理学療法学":         {"series": "標準理学療法学",              "publisher": "医学書院", "year": "2018"},
    "日常生活活動学・生活環境学": {"series": "標準理学療法学",          "publisher": "医学書院", "year": "2018"},
    "物理療法学":             {"series": "標準理学療法学",              "publisher": "医学書院", "year": "2018"},
    "理学療法研究法":         {"series": "標準理学療法学",              "publisher": "医学書院", "year": "2018"},
    "病態運動学":             {"series": "標準理学療法学",              "publisher": "医学書院", "year": "2018"},
    "臨床実習とケーススタディ": {"series": "標準理学療法学",            "publisher": "医学書院", "year": "2018"},
    "がんのリハビリテーション": {"series": "標準理学療法学・作業療法学", "publisher": "医学書院", "year": "2018"},
    "リハビリテーション管理学": {"series": "標準理学療法学・作業療法学", "publisher": "医学書院", "year": "2018"},
    "内科学":                 {"series": "標準理学療法学・作業療法学", "publisher": "医学書院", "year": "2018"},
    "精神医学":               {"series": "標準理学療法学・作業療法学", "publisher": "医学書院", "year": "2018"},
    "脳画像":                 {"series": "標準理学療法学・作業療法学", "publisher": "医学書院", "year": "2018"},
    "人間発達学":             {"series": "標準理学療法学・作業療法学", "publisher": "医学書院", "year": "2018"},
    "小児科学":               {"series": "標準理学療法学・作業療法学", "publisher": "医学書院", "year": "2018"},
    "整形外科学":             {"series": "標準理学療法学・作業療法学", "publisher": "医学書院", "year": "2018"},
    "生理学":                 {"series": "標準理学療法学・作業療法学", "publisher": "医学書院", "year": "2018"},
    "病理学":                 {"series": "標準理学療法学・作業療法学", "publisher": "医学書院", "year": "2018"},
    "神経内科":               {"series": "標準理学療法学・作業療法学", "publisher": "医学書院", "year": "2018"},
    "義肢装具学":             {"series": "標準理学療法学・作業療法学", "publisher": "医学書院", "year": "2018"},
    "老年学":                 {"series": "標準理学療法学・作業療法学", "publisher": "医学書院", "year": "2018"},
    "解剖学":                 {"series": "標準理学療法学・作業療法学", "publisher": "医学書院", "year": "2018"},
    "運動学":                 {"series": "標準理学療法学・作業療法学", "publisher": "医学書院", "year": "2018"},
    "解剖生理学":             {"series": "系統看護学講座",              "publisher": "医学書院", "year": "2018"},
}

def book_display_name(filename: str) -> str:
    """ファイル名 → 書籍表示名"""
    name = filename.replace(".pdf.json", "")
    for prefix in [
        "標準理学療法学作業療法学__",
        "標準理学療法学作業療法学_",
        "標準理学療法学__",
        "標準理学療法学_",
        "系統看護学講座_",
    ]:
        name = name.replace(prefix, "")
    return name.strip().rstrip("_").strip()

def get_citation(book_name: str, page: str) -> str:
    """参考文献形式の文字列を返す"""
    meta = BOOK_META.get(book_name, {})
    series  = meta.get("series", "標準理学療法学・作業療法学")
    pub     = meta.get("publisher", "医学書院")
    year    = meta.get("year", "2018")
    return f"{series}『{book_name}』{pub}（{year}）p.{page}"

def extract_snippets(text: str, keywords: list, context: int = 150) -> list:
    """キーワード周辺のスニペットを抽出"""
    snippets = []
    seen_ranges = []
    for kw in keywords:
        idx = 0
        while True:
            idx = text.find(kw, idx)
            if idx == -1:
                break
            start = max(0, idx - context)
            end   = min(len(text), idx + len(kw) + context)
            # 重複範囲はスキップ
            overlap = any(s <= idx <= e for s, e in seen_ranges)
            if not overlap:
                snippet = text[start:end].replace("\n", " ").strip()
                # キーワードをハイライト
                for k in keywords:
                    snippet = snippet.replace(k, f"【{k}】")
                snippets.append(snippet)
                seen_ranges.append((start, end))
            idx += len(kw)
            if len(snippets) >= 3:
                break
        if len(snippets) >= 3:
            break
    return snippets

def score_page(text: str, keywords: list, phrase: str = "") -> float:
    """ページのスコアを計算"""
    score = 0.0

    # フレーズ完全一致（最高優先）
    if phrase and phrase in text:
        score += 20.0

    # 全キーワードヒット
    hit_kws = [kw for kw in keywords if kw in text]
    score += len(hit_kws) * 5.0

    # 頻度ボーナス（1キーワードあたり最大+3）
    for kw in hit_kws:
        freq = text.count(kw)
        score += min(freq - 1, 3) * 1.0

    # 冒頭200文字にキーワードがある（見出し・タイトル）
    head = text[:200]
    for kw in keywords:
        if kw in head:
            score += 3.0

    return score

def search_all(
    keywords:    list,
    phrase:      str  = "",
    book_filter: str  = "",
    max_results: int  = 10,
    use_semantic:bool = False,
) -> list:
    """全教科書をキーワード検索"""
    results = []
    files = sorted(CACHE_DIR.glob("*.json"))

    for f in files:
        book_name = book_display_name(f.name)
        if book_filter and book_filter.lower() not in book_name.lower():
            continue

        with open(f, encoding="utf-8") as fh:
            data = json.load(fh)

        pages = data.get("pages", {})
        for page_num, text in pages.items():
            if not text.strip():
                continue
            # 最低1キーワードはヒットが必要
            if not any(kw in text for kw in keywords):
                continue

            sc = score_page(text, keywords, phrase)
            if sc <= 0:
                continue

            snippets = extract_snippets(text, keywords)
            results.append({
                "book":      book_name,
                "page":      page_num,
                "score":     sc,
                "hit_count": sum(1 for kw in keywords if kw in text),
                "total_kw":  len(keywords),
                "snippets":  snippets,
                "full_text": text,
                "citation":  get_citation(book_name, page_num),
            })

    # 意味検索（オプション）
    if use_semantic:
        try:
            import chromadb
            from sentence_transformers import SentenceTransformer
            client = chromadb.PersistentClient(
                path=str(Path.home() / "textbook-chatbot" / "chroma_db"))
            col   = client.get_collection("textbooks")
            model = SentenceTransformer("paraphrase-multilingual-mpnet-base-v2")
            query = phrase or " ".join(keywords)
            vec   = model.encode([query]).tolist()
            where = {"source": {"$contains": book_filter}} if book_filter else None
            kw    = {"query_embeddings": vec, "n_results": 10,
                     "include": ["documents", "metadatas", "distances"]}
            if where:
                kw["where"] = where
            res = col.query(**kw)
            seen = {f"{r['book']}_{r['page']}" for r in results}
            for doc, meta, dist in zip(
                    res["documents"][0], res["metadatas"][0], res["distances"][0]):
                bn = meta.get("source", "")
                pg = str(meta.get("page", "?"))
                uid = f"{bn}_{pg}"
                if uid in seen:
                    continue
                sc = round((1 - dist) * 8, 2)   # 意味スコアはやや低め
                results.append({
                    "book":      bn,
                    "page":      pg,
                    "score":     sc,
                    "hit_count": 0,
                    "total_kw":  len(keywords),
                    "snippets":  [doc[:300]],
                    "full_text": doc,
                    "citation":  get_citation(bn, pg),
                    "match":     "意味検索",
                })
                seen.add(uid)
        except Exception as e:
            print(f"  ※意味検索エラー: {e}", file=sys.stderr)

    results.sort(key=lambda x: (-x["score"], x["book"], int(x["page"]) if x["page"].isdigit() else 0))
    return results[:max_results]


def format_results(results: list, full: bool = False) -> str:
    """検索結果を整形して返す（Claude が読みやすい形式）"""
    if not results:
        return "❌ 該当なし。キーワードを変えてみてください。"

    lines = [f"✅ {len(results)}件ヒット\n", "=" * 60]
    refs  = []

    for i, r in enumerate(results, 1):
        kw_info = f"{r['hit_count']}/{r['total_kw']}語" if r["hit_count"] > 0 else "意味"
        lines.append(f"\n[{i}] 📚 {r['book']}　p.{r['page']}　(スコア:{r['score']:.1f} / {kw_info}ヒット)")
        lines.append("-" * 50)

        if full:
            lines.append(r["full_text"])
        else:
            for s in r["snippets"]:
                lines.append(f"  …{s}…")

        lines.append(f"\n  📎 {r['citation']}")
        refs.append(r["citation"])

    lines.append("\n" + "=" * 60)
    lines.append("\n【参考文献】")
    seen_refs = []
    for ref in refs:
        if ref not in seen_refs:
            lines.append(f"  ・{ref}")
            seen_refs.append(ref)

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="教科書全文検索 v2")
    parser.add_argument("query",   help='検索語（スペース区切りでAND）例: "前壁 腰椎"')
    parser.add_argument("--book",  "-b", default="", help="書籍名フィルター")
    parser.add_argument("--max",   "-n", type=int, default=8, help="最大件数（デフォルト8）")
    parser.add_argument("--full",  "-f", action="store_true", help="全文表示")
    parser.add_argument("--semantic", "-s", action="store_true", help="意味検索も使用")
    args = parser.parse_args()

    # フレーズ検索（""で囲まれた部分）
    phrase_match = re.findall(r'"([^"]+)"', args.query)
    phrase = phrase_match[0] if phrase_match else ""
    # キーワード抽出（"" を除去してスペース分割）
    clean_query = re.sub(r'"[^"]+"', "", args.query)
    keywords = [kw for kw in clean_query.split() if kw]
    if phrase:
        keywords = list(set(keywords + phrase.split()))

    if not keywords and not phrase:
        print("キーワードを入力してください")
        sys.exit(1)

    label = f'"{phrase}" + {keywords}' if phrase else " AND ".join(keywords)
    print(f"\n🔍 検索: {label}", end="")
    if args.book:
        print(f"  ［{args.book}］", end="")
    if args.semantic:
        print("  ＋意味検索", end="")
    print()

    results = search_all(
        keywords=keywords,
        phrase=phrase,
        book_filter=args.book,
        max_results=args.max,
        use_semantic=args.semantic,
    )
    print(format_results(results, full=args.full))


if __name__ == "__main__":
    main()
