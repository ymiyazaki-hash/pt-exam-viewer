# 理学療法・作業療法 教科書チャットボット

Gemma4（Ollama）+ ChromaDB RAG システム

## セットアップ

### 1. パッケージのインストール

```bash
pip3 install sentence-transformers chromadb gradio ollama
```

### 2. PDFをインデックス化（初回のみ・約10〜30分）

```bash
python3 ~/textbook-chatbot/index_pdfs.py
```

### 3. チャットボットを起動

**Web UI（推奨）:**
```bash
python3 ~/textbook-chatbot/chatbot.py
```
→ ブラウザで http://localhost:7860 を開く

**CLI モード:**
```bash
python3 ~/textbook-chatbot/chatbot.py cli
```

## 対応教科書（28冊）

- 標準理学療法学シリーズ（理学療法概説、神経理学療法学、運動療法学 各論・総論、骨関節、内部疾患、地域、日常生活活動、物理療法、研究法、病態運動学、臨床実習）
- 標準理学療法学・作業療法学（がんのリハビリ、リハビリ管理学、内科学、精神医学、脳画像、人間発達学、小児科学、整形外科学、生理学、病理学、神経内科、義肢装具学、老年学、解剖学、運動学）
- 系統看護学講座 解剖生理学

## 仕組み

1. PDFからテキスト抽出（PyMuPDF）
2. テキストをチャンク分割（600文字）
3. 多言語埋め込みモデルでベクトル化（sentence-transformers）
4. ChromaDB（ローカル）に保存
5. 質問に関連するチャンクを検索 → Gemma4に渡して回答生成
