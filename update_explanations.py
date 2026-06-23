"""
asitahe_cache.json の内容を参考に data.json の解説を AI で改善するスクリプト。

使い方:
  export ANTHROPIC_API_KEY=sk-ant-...
  python3 update_explanations.py [--batch 20] [--dry-run]

オプション:
  --batch N     1回に処理する問題数（デフォルト: 20）
  --dry-run     data.json を書き換えずに結果を表示するだけ
  --id ID       特定の問題IDのみ処理（例: --id 58A-87）
  --min-gain N  キャッシュが現在より N 文字以上長い問題のみ対象（デフォルト: 50）

復元方法:
  git checkout before-explanation-update -- data.json
"""

import argparse
import json
import os
import sys
import time
import shutil
from datetime import datetime

try:
    import anthropic
except ImportError:
    print("anthropic パッケージが必要です: pip3 install anthropic")
    sys.exit(1)

MODEL = "claude-haiku-4-5-20251001"

REWRITE_PROMPT = """あなたはPT（理学療法士）国家試験の解説を作成するアシスタントです。

以下の参考解説を元に、以下のルールでオリジナルの解説を書いてください：
- 参考解説の内容・医学的事実は正確に踏襲する
- 表現・文体・文の並び順は完全に書き直す（直接の引用はしない）
- 日本語で書く（です・ます調は不要、体言止め・箇条書きも可）
- 正答の根拠を最初に明示する
- 各選択肢の正誤理由がわかるようにする
- 200〜400文字程度を目安にする（長すぎず短すぎず）
- 余計な前置き・挨拶は不要

問題文: {question}
選択肢: {choices}
正答: {answer}番（{answer_text}）

参考解説:
{reference}

上記参考解説を元に、オリジナルの解説文のみを出力してください（前置き不要）:"""


def build_priority_list(data, cache, min_gain=50):
    """優先度順の問題リストを返す。"""
    q_dict = {q["id"]: q for q in data if q.get("id")}
    priority_list = []

    for q_id, ref_text in cache.items():
        if q_id not in q_dict:
            continue
        q = q_dict[q_id]
        cur_len = len(q.get("explanation", ""))
        ref_len = len(ref_text)
        gain = ref_len - cur_len
        if gain < min_gain:
            continue
        acc = q.get("accuracyRate", 50) or 50
        # 優先度: 正答率低い × 改善量大きい
        score = (100 - acc) * (gain / 100)
        priority_list.append((score, q_id))

    priority_list.sort(reverse=True)
    return [q_id for _, q_id in priority_list]


def rewrite_explanation(client, q, ref_text):
    """Claude API で解説を書き直す。"""
    choices = q.get("choices", [])
    answer_idx = int(q.get("answer", 1)) - 1
    answer_text = choices[answer_idx] if 0 <= answer_idx < len(choices) else "?"
    choices_str = "\n".join(f"{i+1}. {c}" for i, c in enumerate(choices))

    prompt = REWRITE_PROMPT.format(
        question=q.get("text", ""),
        choices=choices_str,
        answer=q.get("answer", "?"),
        answer_text=answer_text,
        reference=ref_text[:2000],  # 長すぎる参考はカット
    )

    response = client.messages.create(
        model=MODEL,
        max_tokens=600,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()


def save_data(data, path):
    """data.json を保存（書き込み前にバックアップ）。"""
    backup_path = path + ".bak"
    shutil.copy2(path, backup_path)
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp_path, path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", type=int, default=20)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--id", type=str, default=None)
    parser.add_argument("--min-gain", type=int, default=50)
    args = parser.parse_args()

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("エラー: ANTHROPIC_API_KEY 環境変数を設定してください。")
        print("  export ANTHROPIC_API_KEY=sk-ant-...")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    with open("data.json", encoding="utf-8") as f:
        data = json.load(f)
    with open("asitahe_cache.json", encoding="utf-8") as f:
        cache = json.load(f)

    q_dict = {q["id"]: i for i, q in enumerate(data) if q.get("id")}

    if args.id:
        target_ids = [args.id]
    else:
        target_ids = build_priority_list(data, cache, args.min_gain)
        target_ids = target_ids[: args.batch]

    print(f"処理対象: {len(target_ids)} 問")
    if not target_ids:
        print("改善候補がありません。--min-gain を下げてみてください。")
        return

    updated = 0
    errors = 0

    for i, q_id in enumerate(target_ids, 1):
        if q_id not in q_dict:
            print(f"  [{i}/{len(target_ids)}] {q_id}: data.json に見つからず スキップ")
            continue
        if q_id not in cache:
            print(f"  [{i}/{len(target_ids)}] {q_id}: キャッシュなし スキップ")
            continue

        idx = q_dict[q_id]
        q = data[idx]
        ref_text = cache[q_id]
        cur_exp = q.get("explanation", "")

        print(f"  [{i}/{len(target_ids)}] {q_id} 正答率{q.get('accuracyRate','?')}%"
              f"  現在{len(cur_exp)}字 → 参考{len(ref_text)}字", end=" ", flush=True)

        if args.dry_run:
            print("(dry-run スキップ)")
            continue

        try:
            new_exp = rewrite_explanation(client, q, ref_text)
            data[idx]["explanation"] = new_exp
            data[idx]["explanationCreatedAt"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
            updated += 1
            print(f"→ {len(new_exp)}字 ✓")
        except Exception as e:
            errors += 1
            print(f"× エラー: {e}")

        # 5問ごとに中間保存
        if updated % 5 == 0:
            save_data(data, "data.json")

        time.sleep(0.5)  # レート制限対策

    if not args.dry_run and updated > 0:
        save_data(data, "data.json")
        print()
        print(f"=== 完了 ===")
        print(f"更新: {updated} 問 / エラー: {errors} 問")
        print(f"data.json を保存しました。")
        print()
        print("復元方法（万が一の場合）:")
        print("  git checkout before-explanation-update -- data.json")


if __name__ == "__main__":
    main()
