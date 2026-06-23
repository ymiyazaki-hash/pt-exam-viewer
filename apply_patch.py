"""
patches/ フォルダ内の JSON パッチを data.json に適用するスクリプト。

使い方:
  python3 apply_patch.py              # patches/*.json を全て適用
  python3 apply_patch.py patch_001.json  # 指定ファイルのみ適用

復元:
  git checkout before-explanation-update -- data.json
"""

import glob
import json
import os
import shutil
import sys
from datetime import datetime

DATA_FILE = "data.json"
PATCH_DIR = "patches"
APPLIED_DIR = "patches/applied"


def main():
    # data.json 読み込み
    with open(DATA_FILE, encoding="utf-8") as f:
        data = json.load(f)
    q_dict = {q["id"]: i for i, q in enumerate(data) if q.get("id")}

    # パッチファイル収集
    if len(sys.argv) > 1:
        patch_files = sys.argv[1:]
    else:
        patch_files = sorted(glob.glob(f"{PATCH_DIR}/patch_*.json"))

    if not patch_files:
        print(f"{PATCH_DIR}/ にパッチファイルがありません。")
        return

    os.makedirs(APPLIED_DIR, exist_ok=True)

    total_updated = 0
    for pf in patch_files:
        with open(pf, encoding="utf-8") as f:
            patch = json.load(f)

        updated = 0
        for q_id, new_exp in patch.items():
            if q_id not in q_dict:
                print(f"  警告: {q_id} が data.json に見つかりません")
                continue
            idx = q_dict[q_id]
            if isinstance(new_exp, list):
                # 新形式: choiceExplanations配列 → explanationはクリア
                data[idx]["choiceExplanations"] = new_exp
                data[idx]["explanation"] = ""
            else:
                # 旧形式: explanationテキスト
                data[idx]["explanation"] = new_exp
            data[idx]["explanationCreatedAt"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
            updated += 1

        total_updated += updated
        print(f"{pf}: {updated} 問 適用")

        # 適用済みに移動
        applied_path = os.path.join(APPLIED_DIR, os.path.basename(pf))
        shutil.move(pf, applied_path)

    # バックアップ → 保存
    shutil.copy2(DATA_FILE, DATA_FILE + ".bak")
    tmp = DATA_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, DATA_FILE)

    print(f"\n合計 {total_updated} 問を更新しました → {DATA_FILE}")
    print("復元: git checkout before-explanation-update -- data.json")


if __name__ == "__main__":
    main()
