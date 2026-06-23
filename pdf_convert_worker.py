#!/usr/bin/env python3
"""
docx→PDF 変換ワーカー（pdf_server.py から独立サブプロセスとして呼ばれる）
使用方法: python3 pdf_convert_worker.py <docx_path> <pdf_path>

このスクリプトは直接呼び出さないでください。pdf_server.py が自動的に使用します。
"""
import sys
import os


def main() -> None:
    if len(sys.argv) != 3:
        print("Usage: pdf_convert_worker.py <docx_path> <pdf_path>", file=sys.stderr)
        sys.exit(2)

    docx_path = sys.argv[1]
    pdf_path  = sys.argv[2]

    if not os.path.exists(docx_path):
        print(f"入力ファイルが存在しません: {docx_path}", file=sys.stderr)
        sys.exit(1)

    try:
        import docx2pdf
        docx2pdf.convert(docx_path, pdf_path, keep_active=True)
    except ImportError:
        print("docx2pdf がインストールされていません。\n"
              "  pip3 install docx2pdf", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"変換エラー: {e}", file=sys.stderr)
        sys.exit(1)

    if not os.path.exists(pdf_path):
        print("変換後のPDFファイルが見つかりません", file=sys.stderr)
        sys.exit(1)

    # 成功
    sys.exit(0)


if __name__ == "__main__":
    main()
