"""
data.json の参考文献を ★教科書/ocr_cache の29冊から再生成するスクリプト。
各問題の分野・問題文キーワードで各教科書を全文検索し、最もヒットしたページを参照ページとして設定する。
"""

import json, os, re, sys
from collections import defaultdict

OCR_DIR  = '/Users/miyazakiyuuji/Library/CloudStorage/GoogleDrive-y.miyazaki@kyoju.ac.jp/マイドライブ/★ドキュメント/★★★クロードコード/★教科書/ocr_cache'
DATA_FILE = '/Users/miyazakiyuuji/Library/CloudStorage/GoogleDrive-y.miyazaki@kyoju.ac.jp/マイドライブ/★ドキュメント/★★★クロードコード/国家試験作成アプリ/data.json'

# ── 教科書メタ情報 ─────────────────────────────────────────────────────────
BOOKS = {
    '理学療法評価学':         {'series':'標準理学療法学',          'publisher':'医学書院', 'file':'標準理学療法学__理学療法評価学.pdf.json'},
    '神経理学療法学':         {'series':'標準理学療法学',          'publisher':'医学書院', 'file':'標準理学療法学__神経理学療法学.pdf.json'},
    '運動療法学各論':         {'series':'標準理学療法学',          'publisher':'医学書院', 'file':'標準理学療法学__運動療法学各論.pdf.json'},
    '運動療法学総論':         {'series':'標準理学療法学',          'publisher':'医学書院', 'file':'標準理学療法学__運動療法学総論.pdf.json'},
    '骨関節理学療法学':       {'series':'標準理学療法学',          'publisher':'医学書院', 'file':'標準理学療法学__骨関節理学療法学.pdf.json'},
    '理学療法概説':           {'series':'標準理学療法学',          'publisher':'医学書院', 'file':'標準理学療法学__理学療法概説.pdf.json'},
    '内部疾患理学療法学':     {'series':'標準理学療法学',          'publisher':'医学書院', 'file':'標準理学療法学_内部疾患理学療法学.pdf.json'},
    '地域理学療法学':         {'series':'標準理学療法学',          'publisher':'医学書院', 'file':'標準理学療法学_地域理学療法学.pdf.json'},
    '日常生活活動学':         {'series':'標準理学療法学',          'publisher':'医学書院', 'file':'標準理学療法学_日常生活活動学・生活環境学.pdf.json'},
    '物理療法学':             {'series':'標準理学療法学',          'publisher':'医学書院', 'file':'標準理学療法学_物理療法学.pdf.json'},
    '理学療法研究法':         {'series':'標準理学療法学',          'publisher':'医学書院', 'file':'標準理学療法学_理学療法研究法.pdf.json'},
    '病態運動学':             {'series':'標準理学療法学',          'publisher':'医学書院', 'file':'標準理学療法学_病態運動学_.pdf.json'},
    '臨床実習とケーススタディ':{'series':'標準理学療法学',         'publisher':'医学書院', 'file':'標準理学療法学_臨床実習とケーススタディ.pdf.json'},
    'がんのリハビリテーション':{'series':'標準理学療法学・作業療法学','publisher':'医学書院', 'file':'標準理学療法学作業療法学__がんのリハビリテーション.pdf.json'},
    'リハビリテーション管理学':{'series':'標準理学療法学・作業療法学','publisher':'医学書院', 'file':'標準理学療法学作業療法学__リハビリテーション管理学.pdf.json'},
    '内科学':                 {'series':'標準理学療法学・作業療法学','publisher':'医学書院', 'file':'標準理学療法学作業療法学__内科学.pdf.json'},
    '精神医学':               {'series':'標準理学療法学・作業療法学','publisher':'医学書院', 'file':'標準理学療法学作業療法学__精神医学.pdf.json'},
    '脳画像':                 {'series':'標準理学療法学・作業療法学','publisher':'医学書院', 'file':'標準理学療法学作業療法学__脳画像.pdf.json'},
    '人間発達学':             {'series':'標準理学療法学・作業療法学','publisher':'医学書院', 'file':'標準理学療法学作業療法学_人間発達学.pdf.json'},
    '小児科学':               {'series':'標準理学療法学・作業療法学','publisher':'医学書院', 'file':'標準理学療法学作業療法学_小児科学.pdf.json'},
    '整形外科学':             {'series':'標準理学療法学・作業療法学','publisher':'医学書院', 'file':'標準理学療法学作業療法学_整形外科学.pdf.json'},
    '生理学':                 {'series':'標準理学療法学・作業療法学','publisher':'医学書院', 'file':'標準理学療法学作業療法学_生理学.pdf.json'},
    '病理学':                 {'series':'標準理学療法学・作業療法学','publisher':'医学書院', 'file':'標準理学療法学作業療法学_病理学.pdf.json'},
    '神経内科学':             {'series':'標準理学療法学・作業療法学','publisher':'医学書院', 'file':'標準理学療法学作業療法学_神経内科.pdf.json'},
    '義肢装具学':             {'series':'標準理学療法学・作業療法学','publisher':'医学書院', 'file':'標準理学療法学作業療法学_義肢装具学.pdf.json'},
    '老年学':                 {'series':'標準理学療法学・作業療法学','publisher':'医学書院', 'file':'標準理学療法学作業療法学_老年学.pdf.json'},
    '解剖学':                 {'series':'標準理学療法学・作業療法学','publisher':'医学書院', 'file':'標準理学療法学作業療法学_解剖学.pdf.json'},
    '運動学':                 {'series':'標準理学療法学・作業療法学','publisher':'医学書院', 'file':'標準理学療法学作業療法学_運動学.pdf.json'},
    '解剖生理学':             {'series':'系統看護学講座',           'publisher':'医学書院', 'file':'系統看護学講座_解剖生理学.pdf.json'},
}

# ── 分野 → 優先教科書（2〜3冊）─────────────────────────────────────────────
FIELD_BOOKS = {
    '評価':   ['理学療法評価学', '病態運動学', '運動学'],
    '内部':   ['内部疾患理学療法学', '内科学', '運動療法学各論'],
    '中枢':   ['神経理学療法学', '神経内科学', '脳画像'],
    '運動学': ['運動学', '解剖学', '生理学'],
    '運動器': ['骨関節理学療法学', '整形外科学', '運動療法学各論'],
    '基礎':   ['解剖学', '生理学', '病理学'],
    'リハ概': ['理学療法概説', 'リハビリテーション管理学', '地域理学療法学'],
    '精神':   ['精神医学', '神経内科学', '理学療法概説'],
    '小児':   ['小児科学', '人間発達学', '神経理学療法学'],
    '義肢装具':['義肢装具学', '骨関節理学療法学', '日常生活活動学'],
    'ADL':    ['日常生活活動学', '理学療法評価学', '運動療法学各論'],
    '解剖':   ['解剖学', '運動学', '解剖生理学'],
    '心理':   ['精神医学', '理学療法概説', '老年学'],
    '病理':   ['病理学', '内科学', '生理学'],
    '人発':   ['人間発達学', '小児科学', '老年学'],
    '物療':   ['物理療法学', '内部疾患理学療法学', '理学療法評価学'],
    '生理':   ['生理学', '解剖学', '解剖生理学'],
}
DEFAULT_BOOKS = ['理学療法評価学', '理学療法概説', '運動学']

# ── OCR 全ページ読み込み ──────────────────────────────────────────────────────
print('教科書データ読み込み中…', flush=True)
book_pages = {}  # book_name -> {page_str -> text}
for book_name, meta in BOOKS.items():
    fpath = os.path.join(OCR_DIR, meta['file'])
    if not os.path.exists(fpath):
        print(f'  ★ファイル未発見: {meta["file"]}')
        book_pages[book_name] = {}
        continue
    with open(fpath, encoding='utf-8') as f:
        d = json.load(f)
    pages = d.get('pages', d) if isinstance(d, dict) else {}
    if isinstance(pages, list):
        pages = {str(i): p for i, p in enumerate(pages)}
    book_pages[book_name] = pages
    print(f'  読込完了: {book_name} ({len(pages)}p)')

# ── キーワード抽出（漢字・かな混じり2文字以上） ──────────────────────────────
def extract_keywords(text: str) -> list[str]:
    # 漢字を含む2文字以上の語を抽出
    words = re.findall(r'[一-龥ぁ-んァ-ンa-zA-Zａ-ｚＡ-Ｚ][一-龥ぁ-んァ-ン一-龥]{1,}', text)
    # 3文字以上を優先、ただし重複削除
    seen = set()
    result = []
    for w in words:
        if w not in seen:
            seen.add(w)
            result.append(w)
    return result

# ── OCRテキストから印刷ページ番号を抽出（年号などを除外） ────────────────────
def _extract_print_page(page_text: str, fallback_ocr_num: str) -> str:
    # テキスト末尾200文字から1〜3桁の独立した数字を探す（年号4桁は除外）
    nums = re.findall(r'(?:^|\n)\s*(\d{1,3})\s*(?:\n|$)', page_text[-300:])
    if nums:
        n = int(nums[-1])
        if 1 <= n <= 999:
            return str(n)
    # フォールバック: OCRインデックス0始まり→1始まり補正
    try:
        return str(int(fallback_ocr_num) + 1)
    except ValueError:
        return ''

# ── 1冊の中でキーワードが最もヒットしたページを返す ─────────────────────────
def find_best_page(book_name: str, keywords: list[str]) -> str:
    pages = book_pages.get(book_name, {})
    if not pages:
        return ''
    best_page, best_score = '', 0
    # まず3文字以上で検索
    for page_num, text in pages.items():
        score = sum(text.count(kw) for kw in keywords if len(kw) >= 3)
        if score > best_score:
            best_score, best_page = score, page_num
    # スコア0なら2文字キーワードでリトライ
    if best_score == 0:
        for page_num, text in pages.items():
            score = sum(text.count(kw) for kw in keywords if len(kw) >= 2)
            if score > best_score:
                best_score, best_page = score, page_num
    # それでも0なら先頭付近の代表ページを返す（p.1）
    if best_score == 0 or not best_page:
        # ページ総数の1/4あたりを返す（前書き除いた本文開始目安）
        sorted_keys = sorted(pages.keys(), key=lambda x: int(x) if x.isdigit() else 0)
        if sorted_keys:
            quarter = max(0, len(sorted_keys) // 4)
            best_page = sorted_keys[quarter]
            return _extract_print_page(pages[best_page], best_page)
        return ''
    page_text = pages.get(best_page, '')
    return _extract_print_page(page_text, best_page)

# ── 分野文字列から書籍リストを取得 ──────────────────────────────────────────
def get_books_for_field(field: str) -> list[str]:
    parts = [f.strip() for f in field.split(',')]
    books = []
    seen = set()
    for part in parts:
        for b in FIELD_BOOKS.get(part, []):
            if b not in seen:
                seen.add(b)
                books.append(b)
    if not books:
        for b in DEFAULT_BOOKS:
            if b not in seen:
                seen.add(b)
                books.append(b)
    return books[:3]

# ── メイン処理 ──────────────────────────────────────────────────────────────
print('\ndata.json 読み込み中…', flush=True)
with open(DATA_FILE, encoding='utf-8') as f:
    data = json.load(f)
print(f'{len(data)}問 処理開始', flush=True)

for i, q in enumerate(data):
    if i % 200 == 0:
        print(f'  {i}/{len(data)}問処理中…', flush=True)

    field    = q.get('field', '')
    q_text   = q.get('text', '') + ' '.join(q.get('choices', []))
    keywords = extract_keywords(q_text)

    book_names = get_books_for_field(field)
    refs = []
    for bname in book_names:
        meta = BOOKS.get(bname)
        if not meta:
            continue
        page = find_best_page(bname, keywords)
        refs.append({
            'book':      bname,
            'series':    meta['series'],
            'publisher': meta['publisher'],
            'year':      '2023',
            'page':      page,
        })

    q['references'] = refs

print('書き込み中…', flush=True)
with open(DATA_FILE, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print('完了！')
