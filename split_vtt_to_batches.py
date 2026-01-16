#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VTTファイルを100エントリずつのバッチJSONに分割するスクリプト
使い方: python3 split_vtt_to_batches.py <vttファイルのパス>
"""

import os
import sys
import re
import json
from datetime import datetime
from pathlib import Path
import shutil


def read_vtt_file(vtt_path):
    """VTTファイルを読み込んでエントリのリストを返す"""
    print(f"  [LOG] ファイル読み込み: {vtt_path.name}")
    with open(vtt_path, 'r', encoding='utf-8') as f:
        content = f.read()

    pattern = r'(\d{2}:\d{2}:\d{2}\.\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}\.\d{3}).*?\n((?:.*(?:\n|$))+?)(?=\n\d{2}:\d{2}:\d{2}\.\d{3}|$)'
    matches = re.findall(pattern, content, re.MULTILINE)

    entries = []
    for i, (start, end, text) in enumerate(matches, 1):
        text = text.strip()
        if text:
            entries.append({
                'index': i,
                'start': start,
                'end': end,
                'text': text
            })

    print(f"  ✓ 総エントリ数: {len(entries)}")
    return entries


def split_into_batches(entries, batch_size=100):
    """エントリをバッチに分割"""
    batches = []
    for i in range(0, len(entries), batch_size):
        batches.append(entries[i:i + batch_size])
    return batches


def main():
    """メイン処理"""
    print("=" * 60)
    print("VTT Batch Splitter - Claude 内部完結型")
    print("=" * 60)

    # コマンドライン引数からVTTファイルのパスを取得
    if len(sys.argv) < 2:
        print("\n使い方: python3 split_vtt_to_batches.py <vttファイルのパス>")
        print("または: VTTファイルをこのスクリプトにドラッグ&ドロップ")
        sys.exit(1)

    vtt_file_path = sys.argv[1]
    vtt_file = Path(vtt_file_path)

    if not vtt_file.exists():
        print(f"エラー: ファイルが見つかりません: {vtt_file_path}")
        sys.exit(1)

    if not vtt_file.suffix.lower() == '.vtt':
        print(f"エラー: VTTファイルを指定してください: {vtt_file_path}")
        sys.exit(1)

    print(f"\n入力ファイル: {vtt_file.name}")

    # タイムスタンプでフォルダ名を生成
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    work_folder_name = f"work_{timestamp}"
    work_folder = Path.cwd() / work_folder_name
    work_folder.mkdir(exist_ok=True)

    print(f"作業フォルダ: {work_folder_name}")

    # VTTファイルを作業フォルダにコピー
    work_vtt_file = work_folder / vtt_file.name
    shutil.copy2(vtt_file, work_vtt_file)
    print(f"✓ VTTファイルをコピーしました")

    # VTTファイルを読み込む
    print(f"\nVTTファイルを読み込んでいます...")
    entries = read_vtt_file(work_vtt_file)

    # バッチに分割
    batch_size = 100
    batches = split_into_batches(entries, batch_size)
    total_batches = len(batches)

    print(f"\nバッチ分割を開始します（{batch_size}エントリ/バッチ）")
    print(f"総バッチ数: {total_batches}")

    # 各バッチをJSONファイルとして保存
    for i, batch in enumerate(batches, 1):
        batch_file = work_folder / f"batch_{i}.json"
        with open(batch_file, 'w', encoding='utf-8') as f:
            json.dump(batch, f, ensure_ascii=False, indent=2)
        print(f"  ✓ 保存: batch_{i}.json ({len(batch)} エントリ)")

    # 次の手順を説明するREADMEを作成
    readme_content = f"""# 校正手順

## 1. 準備完了

- 作業フォルダ: {work_folder_name}
- 総バッチ数: {total_batches}
- 各バッチファイル: batch_1.json ~ batch_{total_batches}.json

## 2. Claudeに校正を依頼

以下のメッセージをClaude（このチャット）に送信してください：

---

{work_folder_name}/batch_1.json を読み込んで、歯科・矯正歯科の専門家として高精度に校正してください。

【校正ルール】
1. フィラー完全除去（えー、あのー、えっと、その、まあ、なんか等）
2. 歯科・矯正専門用語の正確な変換
   - 音声認識の誤変換を正しい専門用語に修正
   - 例：「ほてつ」→「補綴」、「インビザライン」等の固有名詞を正確に
   - 「咬合」「舌側」「頬側」「近心」「遠心」等の解剖学用語
   - 「IPR」「アタッチメント」「エラスティック」等の治療用語
3. 自然な日本語への修正（口語表現を適切に修正）
4. 発話者名は絶対に保持
5. タイムコードは変更しない

校正結果を {work_folder_name}/output_batch_1.srt として保存してください。

---

## 3. 全バッチを処理

batch_1.json → output_batch_1.srt
batch_2.json → output_batch_2.srt
...
batch_{total_batches}.json → output_batch_{total_batches}.srt

全て完了したら、Claudeに「すべてのバッチを結合して final_output_corrected.srt を作成してください」と依頼してください。

## 4. 完成！

{work_folder_name}/final_output_corrected.srt が最終ファイルです。
"""

    readme_file = work_folder / "README_WORKFLOW.txt"
    with open(readme_file, 'w', encoding='utf-8') as f:
        f.write(readme_content)

    print("\n" + "=" * 60)
    print("バッチ分割完了！")
    print("=" * 60)
    print(f"作業フォルダ: {work_folder}")
    print(f"総バッチ数: {total_batches}")
    print("\n次のステップ:")
    print(f"1. Claudeに以下のメッセージを送信:")
    print(f"\n   {work_folder_name}/batch_1.json を読み込んで校正してください")
    print(f"\n2. 詳細は {work_folder_name}/README_WORKFLOW.txt を参照")
    print("=" * 60)


if __name__ == "__main__":
    main()
