#!/usr/bin/env python3
"""
教科書PDF → OCR → ChromaDB インデックス化
- macOS Vision Framework (Swift) で高精度日本語OCR
- ページ単位でキャッシュ保存 → 中断・再開に対応
- 既インデックス済みPDFはスキップ
"""
import os, sys, json, time, subprocess, tempfile
import fitz  # PyMuPDF
import chromadb
from sentence_transformers import SentenceTransformer

PDF_DIR    = "/Users/miyazakiyuuji/Library/CloudStorage/GoogleDrive-y.miyazaki@kyoju.ac.jp/マイドライブ/★ドキュメント/★教科書"
DB_DIR     = os.path.expanduser("~/textbook-chatbot/chroma_db")
CACHE_DIR  = os.path.expanduser("~/textbook-chatbot/ocr_cache")
OCR_HELPER = os.path.expanduser("~/textbook-chatbot/ocr_helper")
EMBED_MODEL = "paraphrase-multilingual-mpnet-base-v2"
CHUNK_SIZE    = 600
CHUNK_OVERLAP = 100


# ─── OCR（macOS Vision） ──────────────────────────────────────────────────────

def ocr_image_bytes(img_bytes: bytes) -> str:
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        f.write(img_bytes)
        tmp = f.name
    try:
        r = subprocess.run([OCR_HELPER, tmp], capture_output=True, text=True, timeout=30)
        return r.stdout.strip()
    except subprocess.TimeoutExpired:
        return ""
    finally:
        os.unlink(tmp)


def page_to_image(page) -> bytes:
    mat = fitz.Matrix(2.0, 2.0)
    pix = page.get_pixmap(matrix=mat)
    return pix.tobytes("png")


def extract_page_text(page) -> str:
    text = page.get_text("text").strip()
    if len(text) > 30:
        return text
    return ocr_image_bytes(page_to_image(page))


# ─── キャッシュ（ページ単位） ─────────────────────────────────────────────────

def _cache_file(pdf_name: str) -> str:
    safe = pdf_name.replace("/", "_").replace(" ", "_")
    return os.path.join(CACHE_DIR, safe + ".json")


def load_cache(pdf_name: str) -> dict:
    """{"pages": {str(pg): text, ...}, "done": bool}"""
    p = _cache_file(pdf_name)
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return {"pages": {}, "done": False}


def save_cache(pdf_name: str, cache: dict):
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(_cache_file(pdf_name), "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


# ─── チャンク化 ────────────────────────────────────────────────────────────────

def make_chunks(pages: list[dict], source: str) -> list[dict]:
    full = "".join(p["text"] for p in pages)
    bounds = []
    pos = 0
    for p in pages:
        bounds.append((pos, pos + len(p["text"]), p["page"]))
        pos += len(p["text"])

    def pg(i):
        for s, e, n in bounds:
            if s <= i < e:
                return n
        return 0

    chunks, i = [], 0
    while i < len(full):
        txt = full[i:i + CHUNK_SIZE].strip()
        if len(txt) > 50:
            chunks.append({"text": txt, "source": source, "page": pg(i)})
        i += CHUNK_SIZE - CHUNK_OVERLAP
    return chunks


# ─── メイン ───────────────────────────────────────────────────────────────────

def main():
    print("=" * 65)
    print("  教科書RAGシステム — OCR＋インデックス化")
    print("  ※ 中断（Ctrl+C）しても再開できます")
    print("=" * 65)

    if not os.path.exists(OCR_HELPER):
        print(f"\nエラー: OCRヘルパーが見つかりません")
        print(f"  cd ~/textbook-chatbot && swiftc -O ocr_helper.swift -o ocr_helper")
        sys.exit(1)

    # 埋め込みモデル
    print(f"\n[1/4] 埋め込みモデルをロード中 ...")
    model = SentenceTransformer(EMBED_MODEL)
    print("      完了")

    # ChromaDB
    print(f"\n[2/4] ベクトルDBを初期化中 ...")
    os.makedirs(DB_DIR, exist_ok=True)
    client = chromadb.PersistentClient(path=DB_DIR)
    try:
        collection = client.get_collection("textbooks")
        metas = collection.get(include=["metadatas"])["metadatas"]
        indexed_sources = set(m["source"] for m in metas)
        print(f"      既存: {collection.count()} チャンク / {len(indexed_sources)} 冊")
    except Exception:
        collection = client.create_collection("textbooks", metadata={"hnsw:space": "cosine"})
        indexed_sources = set()
        print("      新規作成")

    chunk_id_base = collection.count()

    # PDF一覧
    pdfs = sorted(f for f in os.listdir(PDF_DIR) if f.endswith(".pdf"))
    total_pdfs = len(pdfs)
    print(f"\n[3/4] {total_pdfs} 冊をOCR処理中 ...\n")

    session_chunks: list[dict] = []
    t_session = time.time()

    for book_idx, pdf_name in enumerate(pdfs, 1):
        short = pdf_name.replace(".pdf", "")
        prefix = f"  [{book_idx:2d}/{total_pdfs}] {short[:40]:40s}"

        if short in indexed_sources:
            print(f"{prefix} → スキップ（インデックス済）")
            continue

        # キャッシュ確認
        cache = load_cache(pdf_name)
        pdf_path = os.path.join(PDF_DIR, pdf_name)

        try:
            doc = fitz.open(pdf_path)
            n_pages = doc.page_count
        except Exception as e:
            print(f"{prefix} → 開けません: {e}")
            continue

        if cache["done"]:
            print(f"{prefix} → キャッシュ使用 ({len(cache['pages'])}p)")
        else:
            print(f"{prefix} p.{n_pages}  OCR中 ...", flush=True)
            t0 = time.time()
            for pg_num in range(n_pages):
                key = str(pg_num)
                if key in cache["pages"]:
                    continue
                try:
                    text = extract_page_text(doc[pg_num])
                    cache["pages"][key] = text
                except Exception:
                    cache["pages"][key] = ""
                # 20ページごとに中間保存
                if (pg_num + 1) % 20 == 0:
                    save_cache(pdf_name, cache)
                    done = pg_num + 1
                    elapsed = time.time() - t0
                    spd = elapsed / done
                    remain = (n_pages - done) * spd
                    print(f"    {done}/{n_pages}p  {elapsed:.0f}s経過  残り約{remain/60:.1f}分", flush=True)

            cache["done"] = True
            save_cache(pdf_name, cache)
            elapsed = time.time() - t0
            print(f"    完了: {n_pages}p / {elapsed:.0f}秒")

        doc.close()

        # チャンク化
        pages = [
            {"page": int(k) + 1, "text": v}
            for k, v in sorted(cache["pages"].items(), key=lambda x: int(x[0]))
            if v.strip()
        ]
        chunks = make_chunks(pages, short)
        session_chunks.extend(chunks)

        # 1冊ごとにDBに追加（途中まで保存）
        if chunks:
            BATCH = 64
            embs = model.encode([c["text"] for c in chunks], show_progress_bar=False).tolist()
            base = chunk_id_base + len(session_chunks) - len(chunks)
            for i in range(0, len(chunks), BATCH):
                b = chunks[i:i + BATCH]
                collection.add(
                    documents=[c["text"] for c in b],
                    embeddings=embs[i:i + BATCH],
                    metadatas=[{"source": c["source"], "page": c["page"]} for c in b],
                    ids=[f"chunk_{base + i + j}" for j in range(len(b))],
                )
            indexed_sources.add(short)
            print(f"    DB追加: {len(chunks)}チャンク（累計 {collection.count()}）")

    # 完了サマリ
    total_time = time.time() - t_session
    print(f"\n{'=' * 65}")
    print(f"  完了！  DB合計: {collection.count()} チャンク")
    print(f"  処理時間: {total_time/60:.1f}分")
    print(f"  DB場所:  {DB_DIR}")
    print(f"\n  チャットボット起動:")
    print(f"  python3 ~/textbook-chatbot/chatbot.py")
    print("=" * 65)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n中断しました。再実行すると続きから処理されます。")
