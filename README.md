# PT国家試験 問題抽出アプリ 運用マニュアル

## 概要

理学療法士国家試験（第51回〜第61回）の全2,200問を管理・閲覧・出力するWebアプリ。
HTMLファイル1つで完結し、ブラウザで直接開くだけで使える。

---

## ファイル構成

```
国家試験作成アプリ/
├── pt-exam-viewer.html          ← アプリ本体（JSONデータ埋め込み済み・約11MB（画像JPEG圧縮済））
├── pt-exam-full-backup-2026-02-25.json  ← 元データ（バックアップ）
├── tp260424-08seitou.pdf        ← 第61回正答値表（参考）
├── .claude/
│   └── launch.json              ← ローカルサーバー設定
└── README.md                    ← このファイル
```

---

## 基本的な使い方

### アプリを開く

**方法1: ファイルを直接開く（一番簡単）**
- Finderで `pt-exam-viewer.html` をダブルクリック
- JSONデータが埋め込み済みなので、ファイル選択なしで即起動

**方法2: ローカルサーバー経由（iPad等からアクセスする場合）**
```bash
cd "国家試験作成アプリ"
npx serve -p 3456 .
```
- Mac: `http://localhost:3456/pt-exam-viewer.html`
- iPad（同じWiFi）: `http://<MacのIPアドレス>:3456/pt-exam-viewer.html`
  - MacのIPは `ipconfig getifaddr en0` で確認

### 主な機能

| 機能 | 説明 |
|------|------|
| フィルター | カテゴリ（実地・基礎・専門）、分野、試験回、正答率、キーワード |
| 解説モード | 横向き2カラム。左に問題・右に画像。透明キャンバスで直接書き込み可能 |
| Word問題出力 | 表紙付き・2段組・問番号（1問,2問...）付き。解答あり/なし選択可 |
| Word解答一覧 | 5列×20行＝100問/ページ。問番号＋正答＋設問ID |
| PDF問題出力 | ブラウザ印刷ダイアログ経由。表紙付き |
| PDF解答一覧 | 同上 |

---

## 解説モード操作方法

スクリーンに映してタブレットから操作する授業での使用を想定。

| 操作 | 方法 |
|------|------|
| 解答を表示 | ヘッダーの「解答を表示 ▼」ボタン |
| 前後の問題 | ヘッダーの ‹ › ボタン / キーボード ← → |
| 書き込み開始 | ツールバーの「ペン」を選択（操作モードに戻すには「操作」ボタン） |
| 書き込みの色 | 黒・赤・青・緑・オレンジの5色 |
| 書き込みの太さ | スライダーで1〜24px |
| 元に戻す | ↩ ボタン（最大20回） |
| 書き込みクリア | 🗑 ボタン |
| リセット | ツールバー右端の「🔄 リセット」（解答表示＋書き込みを初期化） |
| キーボード | Space/Enter = 解答表示、Esc = 操作モードに戻る |

---

## データ更新手順

### 新しい試験回のデータを追加する場合

#### 1. JSONに問題データを追加
元の `pt-exam-full-backup-*.json` に新しい問題を追加する。
各問題のフォーマット:
```json
{
  "id": "62A-1",
  "category": "実地",
  "examSession": "第62回AM",
  "text": "問題文テキスト",
  "choices": ["選択肢1", "選択肢2", "選択肢3", "選択肢4", "選択肢5"],
  "answer": "3",
  "field": "運動器",
  "keywords": ["キーワード1"],
  "accuracyRate": 75.5,
  "imageData": "data:image/png;base64,...",
  "lastSyncedAt": "2026-06-09T00:00:00.000Z"
}
```

**複数正答の場合**: `"answer": "3,5"` のようにカンマ区切り

#### 2. 正答データの反映（PDFから）

正答値表PDFがある場合、以下のPythonスクリプトで反映:

```python
import json

json_path = '国家試験作成アプリ/pt-exam-full-backup-2026-02-25.json'

with open(json_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

# 正答マッピング（2桁=複数正答: 35→"3,5"）
answers = {
    '62A-1': '5',
    '62A-2': '3,5',  # 複数正答
    # ... 全問分を記載
}

def format_answer(raw):
    if raw is None: return None
    s = str(raw)
    return ','.join(list(s)) if len(s) > 1 else s

for q in data:
    if q['id'] in answers and answers[q['id']]:
        q['answer'] = answers[q['id']]

with open(json_path, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, separators=(',', ':'))
```

#### 3. HTMLにJSONを再埋め込み

```python
import json, os, re, io, base64
from PIL import Image   # pip install Pillow

base = '国家試験作成アプリ'
html_path = f'{base}/pt-exam-viewer.html'
json_path = f'{base}/pt-exam-full-backup-2026-02-25.json'

with open(json_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

# 【重要】画像はJPEG q85に再圧縮してから埋め込む。
# 元はPNG中心で約39MB→約7MBに縮小。HTMLが55MB→約11MBになり、
# モバイル回線でも確実に起動する（巨大ファイルだと読込ループ/メモリ不足の原因）。
for q in data:
    if q.get('imageData'):
        try:
            raw = base64.b64decode(q['imageData'].split(',', 1)[1])
            im = Image.open(io.BytesIO(raw)).convert('RGB')
            buf = io.BytesIO(); im.save(buf, 'JPEG', quality=85, optimize=True)
            q['imageData'] = 'data:image/jpeg;base64,' + base64.b64encode(buf.getvalue()).decode('ascii')
        except Exception as e:
            print('画像スキップ:', e)

minified = json.dumps(data, ensure_ascii=False, separators=(',', ':'))

with open(html_path, 'r', encoding='utf-8') as f:
    html = f.read()

# 既存の埋め込みを削除して再挿入
html = re.sub(
    r'\n?<!-- EXAM_EMBEDDED_START -->.*?<!-- EXAM_EMBEDDED_END -->\n?',
    '', html, flags=re.DOTALL
)
# 【重要】巨大なJS配列リテラル(const EXAM_EMBEDDED=[...])を埋め込むと
# iOS Safari がパース時にメモリ不足でクラッシュ（問題が繰り返し起きました）する。
# 実行されない <script type="application/json"> ブロックとして埋め込み、
# 起動時に JSON.parse する方式にすること（高速・省メモリ）。
embed_block = (
    f'<!-- EXAM_EMBEDDED_START -->\n'
    f'<script type="application/json" id="examData">{minified}</script>\n'
    f'<!-- EXAM_EMBEDDED_END -->\n'
)
html = html.replace(
    '</div><script>\n  let allData',
    embed_block + '</div><script>\n  let allData', 1
)

with open(html_path, 'w', encoding='utf-8') as f:
    f.write(html)

print(f'完了 {os.path.getsize(html_path)/1024/1024:.1f} MB')
```

#### 4. ブラウザで確認

`Cmd+Shift+R`（強制リロード）で最新版を読み込み。

---

## 出力仕様

### Word問題

| 項目 | 設定値 |
|------|--------|
| フォントサイズ | 10.5pt（sz:21） |
| フォント | メイリオ |
| レイアウト | A4・2段組 |
| 表紙 | あり（分類・分野・試験回・問数・出力日） |
| 問番号 | 「1問」「2問」...形式 |
| 画像制限 | 幅58mm以下・高さ44mm以下（両方を超えない） |
| 出力モード | 解答付き / 解答なし（デフォルト: 解答なし） |

### Word解答一覧

| 項目 | 設定値 |
|------|--------|
| レイアウト | 5列 × 20行 = **100問/ページ** |
| 各列 | 問番号(520) + 正答(620) + 設問ID(901) twips |
| 行高 | 600 twips（固定） |
| ヘッダー行高 | 400 twips（固定） |
| タイトル | 1行（sz:24）＋サブタイトル1行（sz:16） |
| 試験回表示 | 「第51回AM〜第61回PM」形式（短縮） |
| 問番号形式 | 数字のみ（「1」「2」...） |

### PDF問題

| 項目 | 設定値 |
|------|--------|
| フォントサイズ | 10.5pt |
| レイアウト | A4・2段組 |
| 表紙 | あり |
| 画像制限 | max-height: 38mm |
| 問番号 | 紺色バーに「N問」形式で大きく表示 |

### PDF解答一覧

| 項目 | 設定値 |
|------|--------|
| レイアウト | 3グループ/行（問番号 + 正答 + 設問ID） |
| 問番号形式 | 「N問」 |

---

## 技術仕様

### アーキテクチャ
- **単一HTMLファイル**（サーバー不要）
- JSONデータは `<script type="application/json" id="examData">...</script>` として埋め込み
- IndexedDBキャッシュにも対応（`file://` ではIndexedDBが使えないため埋め込みが主要手段）
- Word出力: JSZip + OOXML（ブラウザ内でdocxを生成）
- PDF出力: ブラウザの印刷ダイアログ経由

### 外部ライブラリ
- JSZip 3.10.1（CDN: `cdn.jsdelivr.net`）

### 主要な定数（Word出力・OOXML）

| 定数 | 値 | 説明 |
|------|-----|------|
| sz:21 | 10.5pt | デフォルトフォントサイズ（Wordの半ポイント単位） |
| MAX_W | 2,100,000 EMU | 画像最大幅（≈58mm） |
| MAX_H | 1,600,000 EMU | 画像最大高さ（≈44mm） |
| MIN_W | 900,000 EMU | 画像最小幅（≈25mm、縦長画像用） |
| A4サイズ | 11906 × 16838 twips | |
| 余白 | 900 twips（≈16mm） | 上下左右共通 |

### 既知の制限事項

- `file://` でSafariから開くとIndexedDBが使えない → 埋め込みデータで対応済み
- 61A-20は採点除外問題のため解答なし
- HTMLファイルは約11MB（画像はJPEG q85圧縮で埋め込み）

---

## トラブルシューティング

| 問題 | 原因 | 対処 |
|------|------|------|
| 変更が反映されない | ブラウザキャッシュ | `Cmd+Shift+R` で強制リロード |
| IndexedDBエラー | `file://` でのSafari制限 | 正常動作する（埋め込みデータを使用） |
| iPadから開けない | 同じWiFiでない / サーバー未起動 | WiFi確認＋`npx serve -p 3456 .` |
| Word出力で画像が大きすぎる | MAX_W/MAX_H の値 | HTMLの定数を調整 |
| 解答一覧が100問/ページに収まらない | タイトル/行高の合計がA4高さを超過 | 行高・タイトルサイズを調整 |
| ポップアップブロック（PDF出力） | ブラウザ設定 | ポップアップを許可 |

---

## 変更履歴

| 日付 | 内容 |
|------|------|
| 2026-06-09 | 解説モード追加（横向き2カラム・透明キャンバス書き込み） |
| 2026-06-09 | Word/PDF出力改善（10.5pt・表紙・問番号・画像サイズ制限） |
| 2026-06-09 | 解答一覧を問番号順（1問,2問...）＋設問ID形式に変更 |
| 2026-06-09 | 解答一覧を100問/ページに最適化 |
| 2026-06-09 | 第61回（AM/PM）の正答データをPDFから反映（199問） |
| 2026-06-09 | JSONデータをHTMLに埋め込み（ファイル選択不要化） |
| 2026-06-09 | IndexedDBエラー時のフォールバック対応 |
| 2026-06-09 | 出力デフォルトを「解答なし」に変更 |
