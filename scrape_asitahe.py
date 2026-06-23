"""
asitahe.com から画像付き問題の解説をスクレイピングしてキャッシュに保存するスクリプト。

使い方:
  python3 scrape_asitahe.py

出力: asitahe_cache.json
  {
    "61A-3": "解説テキスト...",
    "61A-5": "解説テキスト...",
    ...
  }
"""

import json
import math
import re
import time
import urllib.request
import gzip
import warnings

warnings.filterwarnings("ignore")

try:
    from bs4 import BeautifulSoup
except ImportError:
    print("beautifulsoup4 が必要です: pip3 install beautifulsoup4")
    raise

# ── URL パターン ────────────────────────────────────────────────
# AM（全回）: {回}rigaku{start}-{end}national-examanation-am/
# PM（51〜57回）: {回}rigaku{start}-{end}national-examanation-pm/
# PM（58〜61回）: {回}rigaku{start}-{end}national-expmanation-pm/

def build_url_candidates(exam_round: int, session: str, q_num: int):
    """問題IDから試すべきURL候補リストを返す。"""
    start = (q_num - 1) // 5 * 5 + 1
    end   = start + 4

    base_rigaku = f"https://asitahe.com/{exam_round}rigaku{start}-{end}"
    base_ptot   = f"https://asitahe.com/{exam_round}ptot{start}-{end}"

    if session == "AM":
        candidates = [
            f"{base_rigaku}national-examanation-am/",
            f"{base_ptot}national-examanation-am/",
        ]
    else:
        candidates = [
            f"{base_rigaku}national-expmanation-pm/",
            f"{base_rigaku}national-examanation-pm/",
            f"{base_ptot}national-expmanation-pm/",
            f"{base_ptot}national-examanation-pm/",
        ]

    # 53回AM 16-20 ページのタイポ対応
    extras = []
    for c in candidates:
        if "53rigaku16-20" in c:
            extras.append(c.replace("53rigaku16-20", "53rigsku16-20"))

    return candidates + extras


def parse_question_id(q_id: str):
    """'61A-3' → (61, 'AM', 3)"""
    m = re.match(r"(\d+)([AP])-(\d+)", q_id)
    if not m:
        return None
    exam_round = int(m.group(1))
    session    = "AM" if m.group(2) == "A" else "PM"
    q_num      = int(m.group(3))
    return exam_round, session, q_num


# ── ページ取得 ─────────────────────────────────────────────────
_page_cache: dict[str, BeautifulSoup] = {}

def fetch_page(url: str):
    if url in _page_cache:
        return _page_cache[url]
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
                "Accept-Encoding": "gzip",
                "Accept": "text/html",
            },
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read()
            enc = resp.info().get("Content-Encoding", "")
        html = gzip.decompress(raw).decode("utf-8") if enc == "gzip" else raw.decode("utf-8")
        soup = BeautifulSoup(html, "html.parser")
        _page_cache[url] = soup
        time.sleep(1.5)  # サーバー負荷軽減
        return soup
    except Exception as e:
        print(f"  [fetch error] {url}: {e}")
        return None


# ── 解説抽出 ──────────────────────────────────────────────────
def extract_explanation(soup: BeautifulSoup, q_num: int):
    """BeautifulSoup からq_numの解説テキストを抽出。
    「解答」行をアンカーとして、ページ内の問題順序でq_numを特定する。
    """
    all_p = [p.get_text() for p in soup.find_all("p")]

    # 「解答」行のインデックスを全て収集
    ans_indices = [i for i, t in enumerate(all_p) if re.match(r"^解答", t.strip())]
    if not ans_indices:
        return None

    # ページ内の問題順序（0始まり）を計算
    page_start = (q_num - 1) // 5 * 5 + 1  # ページ先頭問題番号: 1, 6, 11, ...
    q_pos = q_num - page_start               # 0〜4

    if q_pos >= len(ans_indices):
        # フォールバック：ページ末尾のコンテンツを使用（不適切問題など解答行がない場合）
        ans_idx = ans_indices[-1] if ans_indices else 0
        # 最後の解答以降のテキストを全て取得
        next_ans_idx = len(all_p)
        skip_patterns2 = [
            r"^スポンサー", r"^この記事には", r"^記事内で", r"^SHARE",
            r"^最新", r"^copyright", r"引用：", r"^類似問題", r"^参考に",
        ]
        parts2 = []
        for i in range(ans_idx + 1, next_ans_idx):
            line = all_p[i].strip()
            if not line or line in ("\xa0", "解説"):
                continue
            if any(re.match(p, line, re.IGNORECASE) for p in skip_patterns2):
                continue
            parts2.append(line)
        return "\n".join(parts2) if parts2 else None

    ans_idx = ans_indices[q_pos]

    # 解答行の次から解説テキストを収集（次の解答行 or ページ末尾まで）
    next_ans_idx = ans_indices[q_pos + 1] if q_pos + 1 < len(ans_indices) else len(all_p)

    skip_patterns = [
        r"^スポンサー", r"^この記事には", r"^記事内で", r"^SHARE",
        r"^最新", r"^copyright", r"引用：", r"^類似問題", r"^参考に",
    ]

    parts = []
    for i in range(ans_idx + 1, next_ans_idx):
        line = all_p[i].strip()
        if not line or line in ("\xa0", "解説"):
            continue
        if any(re.match(p, line, re.IGNORECASE) for p in skip_patterns):
            continue
        parts.append(line)

    return "\n".join(parts) if parts else None


# ── メイン ────────────────────────────────────────────────────
def main():
    # 対象：画像付き問題（data.json から取得）
    with open("data.json", encoding="utf-8") as f:
        data = json.load(f)

    img_questions = [q["id"] for q in data if q["id"]]
    print(f"対象問題: {len(img_questions)} 問")

    # 既存キャッシュを読み込み
    try:
        with open("asitahe_cache.json", encoding="utf-8") as f:
            cache = json.load(f)
        print(f"既存キャッシュ: {len(cache)} 件")
    except FileNotFoundError:
        cache = {}

    skipped_over50 = 0
    not_found = []
    success = 0

    for q_id in img_questions:
        if q_id in cache:
            continue  # 既にキャッシュ済み

        parsed = parse_question_id(q_id)
        if not parsed:
            print(f"  [skip] IDパース失敗: {q_id}")
            continue

        exam_round, session, q_num = parsed
        candidates = build_url_candidates(exam_round, session, q_num)
        if not candidates:
            skipped_over50 += 1
            continue

        soup = None
        used_url = None
        for url in candidates:
            s = fetch_page(url)
            if s is not None:
                soup = s
                used_url = url
                break

        print(f"  取得中: {q_id}  → {used_url or candidates[0]}", end=" ", flush=True)
        if soup is None:
            not_found.append(q_id)
            print("× フェッチ失敗")
            continue

        text = extract_explanation(soup, q_num)
        if text:
            cache[q_id] = text
            success += 1
            print(f"✓ ({len(text)}文字)")
        else:
            not_found.append(q_id)
            print("△ 解説抽出失敗")

    # キャッシュ保存
    with open("asitahe_cache.json", "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

    print()
    print(f"=== 完了 ===")
    print(f"新規取得: {success} 件")
    print(f"問51-100（サイト未掲載）: {skipped_over50} 件")
    print(f"取得失敗・解説なし: {len(not_found)} 件")
    if not_found:
        print(f"  失敗リスト: {not_found}")
    print(f"キャッシュ合計: {len(cache)} 件 → asitahe_cache.json")


if __name__ == "__main__":
    main()
