#!/usr/bin/env python3
"""
PDF変換サーバー: .docx を受け取り Microsoft Word で PDF に変換して返す

【起動方法】
  cd "このファイルがあるフォルダ"
  python3 pdf_server.py

【必要ライブラリ】
  pip3 install flask flask-cors docx2pdf pypdf

【注意】
  - macOS + Microsoft Word が必要です
  - 初回起動時に Word へのアクセス許可を求められる場合があります
"""

import os
import sys
import subprocess
import tempfile
from pathlib import Path

from flask import Flask, request, jsonify, Response
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# このスクリプトと同じディレクトリにあるワーカースクリプト
WORKER_SCRIPT = Path(__file__).parent / "pdf_convert_worker.py"


def convert_docx_to_pdf(docx_path: str, pdf_path: str, timeout: int = 120) -> None:
    """
    独立した Python サブプロセスで docx2pdf を実行。
    Flask のソケットや状態から完全に分離するため subprocess を使用。
    """
    if not WORKER_SCRIPT.exists():
        raise RuntimeError(
            f"ワーカースクリプトが見つかりません: {WORKER_SCRIPT}\n"
            "pdf_convert_worker.py と pdf_server.py は同じフォルダに置いてください。"
        )

    proc = subprocess.Popen(
        [sys.executable, str(WORKER_SCRIPT), docx_path, pdf_path],
        stderr=subprocess.PIPE,
        # stdout は capture しない（プログレスバー表示のため）
    )
    try:
        _, stderr_data = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        raise RuntimeError(f"変換がタイムアウトしました ({timeout}秒)\n"
                           "Word が応答しているか確認してください。")

    if proc.returncode != 0:
        err_msg = stderr_data.decode("utf-8", errors="replace").strip() if stderr_data else "不明なエラー"
        raise RuntimeError(err_msg)

    if not os.path.exists(pdf_path):
        raise RuntimeError("PDF が生成されませんでした")


def count_pdf_pages(pdf_path: str) -> int:
    """pypdf でページ数をカウント"""
    try:
        from pypdf import PdfReader
        reader = PdfReader(pdf_path)
        return len(reader.pages)
    except ImportError:
        return -1  # pypdf 未インストール時はスキップ
    except Exception:
        return -1


@app.route("/convert", methods=["POST"])
def convert():
    if "file" not in request.files:
        return jsonify({"error": "ファイルがアップロードされていません"}), 400

    docx_file = request.files["file"]
    expected_pages = request.form.get("expected_pages", type=int)

    # 一時ファイルを ~/Downloads に保存（Word のサンドボックスがアクセスできる場所）
    suffix = ".docx"
    tmp_dir = Path.home() / "Downloads"
    tmp_dir.mkdir(exist_ok=True)
    fd, docx_path = tempfile.mkstemp(suffix=suffix, dir=str(tmp_dir))
    os.close(fd)
    pdf_path = docx_path[:-len(suffix)] + ".pdf"

    try:
        docx_file.save(docx_path)
        print(f"変換開始: {os.path.basename(docx_path)}", flush=True)

        convert_docx_to_pdf(docx_path, pdf_path)

        actual_pages = count_pdf_pages(pdf_path)
        if actual_pages > 0:
            if expected_pages and actual_pages != expected_pages:
                print(f"⚠️  ページ数不一致: Word={expected_pages}ページ, PDF={actual_pages}ページ", flush=True)
            else:
                print(f"✅ 変換成功: {actual_pages}ページ", flush=True)
        else:
            print("✅ 変換成功", flush=True)

        # PDF をメモリに読み込んでから一時ファイルを削除
        with open(pdf_path, "rb") as f:
            pdf_data = f.read()

        return Response(
            pdf_data,
            mimetype="application/pdf",
            headers={"Content-Disposition": "attachment; filename=output.pdf"},
        )

    except Exception as e:
        print(f"❌ エラー: {e}", flush=True)
        return jsonify({"error": str(e)}), 500

    finally:
        for path in (docx_path, pdf_path):
            try:
                os.unlink(path)
            except Exception:
                pass


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "worker": str(WORKER_SCRIPT)})


if __name__ == "__main__":
    print("=" * 60)
    print("PDF変換サーバー起動中...")
    print("URL: http://localhost:8765")
    print(f"ワーカー: {WORKER_SCRIPT}")
    print("停止するには Ctrl+C")
    print("=" * 60)

    # 依存ライブラリの確認
    missing = []
    try:
        import flask
    except ImportError:
        missing.append("flask")
    try:
        import flask_cors
    except ImportError:
        missing.append("flask-cors")
    try:
        import docx2pdf
    except ImportError:
        missing.append("docx2pdf")
    try:
        import pypdf
    except ImportError:
        missing.append("pypdf  ※ ページ数検証なしで動作します")

    if missing:
        print("\n⚠️  以下のライブラリが不足しています:")
        for m in missing:
            print(f"   pip3 install {m}")
        if any(m in ("flask", "flask-cors", "docx2pdf") for m in missing):
            print("\n必要なライブラリをインストールしてから再起動してください。")
            sys.exit(1)
        print()

    app.run(host="127.0.0.1", port=8765, debug=False, threaded=True)
