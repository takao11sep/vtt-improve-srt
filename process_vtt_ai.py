#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VTTファイルをClaude APIで高精度校正してSRTに変換するスクリプト
使い方: python3 process_vtt_ai.py <vttファイルのパス>
環境変数: ANTHROPIC_API_KEY にAPIキーを設定
"""

import os
import sys
import re
import json
import time
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


def vtt_time_to_srt_time(vtt_time):
    """VTT形式の時間をSRT形式に変換"""
    return vtt_time.replace('.', ',')


def call_claude_api(entries_batch, api_key):
    """Claude APIを呼び出してバッチを校正"""
    try:
        import anthropic
    except ImportError:
        print("\nエラー: anthropic パッケージがインストールされていません。")
        print("以下のコマンドでインストールしてください:")
        print("  pip install anthropic")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    # エントリをJSON形式に変換
    entries_json = json.dumps(entries_batch, ensure_ascii=False, indent=2)

    prompt = f"""以下の字幕テキストを、歯科医療・矯正歯科の専門家として校正してください。

【校正ルール】
1. フィラーを完全除去
   - えー、あのー、えっと、その、まあ、なんか、等
   - 意味のない繰り返し（「そうそうそう」→「そう」）

2. 歯科・矯正専門用語の正確な変換
   - 音声認識の誤変換を正しい専門用語に修正
   - 例：「ほてつ」→「補綴」、「きょうせい」→「矯正」
   - 「インビザライン」「アライナー」「ブラケット」「ワイヤー」等の固有名詞を正確に
   - 「咬合」「舌側」「頬側」「近心」「遠心」等の解剖学用語
   - 「IPR」「アタッチメント」「エラスティック」等の治療用語

3. 自然な日本語への修正
   - 口語表現を適切に修正（「なんすか」→「なんですか」）
   - 不自然な助詞を修正
   - 文章の区切りを自然に

4. 発話者名は絶対に保持
   - 「minamidate:」「Asano:」等の発話者名は削除しない

5. タイムコードは変更しない

【入力データ】
{entries_json}

【出力形式】
以下のJSON形式で出力してください。```json記号は不要です。
[
  {{"index": 1, "text": "校正後のテキスト"}},
  {{"index": 2, "text": "校正後のテキスト"}},
  ...
]
"""

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=8000,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    response_text = message.content[0].text

    # JSONブロックを抽出
    json_match = re.search(r'```json\s*(.*?)\s*```', response_text, re.DOTALL)
    if json_match:
        json_str = json_match.group(1)
    else:
        json_str = response_text

    try:
        corrected = json.loads(json_str)
        return corrected
    except json.JSONDecodeError as e:
        print(f"  ⚠ JSON解析エラー: {e}")
        print(f"  元のテキストを使用します")
        return [{'index': e['index'], 'text': e['text']} for e in entries_batch]


def process_batch(entries, batch_num, output_dir, api_key):
    """バッチを処理してSRTファイルを作成"""
    print(f"\n[バッチ {batch_num}] {len(entries)} エントリを処理中...")
    print(f"  → Claude API 呼び出し中...")

    # Claude APIで校正
    corrected = call_claude_api(entries, api_key)

    # 校正結果を反映
    corrected_dict = {item['index']: item['text'] for item in corrected}
    for entry in entries:
        if entry['index'] in corrected_dict:
            entry['text'] = corrected_dict[entry['index']]

    # SRTファイルに保存
    output_path = output_dir / f"output_batch_{batch_num}.srt"
    with open(output_path, 'w', encoding='utf-8') as f:
        for entry in entries:
            f.write(f"{entry['index']}\n")
            f.write(f"{vtt_time_to_srt_time(entry['start'])} --> {vtt_time_to_srt_time(entry['end'])}\n")
            f.write(f"{entry['text']}\n\n")

    print(f"  ✓ 保存完了: output_batch_{batch_num}.srt")
    return output_path


def merge_batch_files(output_dir, total_batches, final_output_path):
    """中間ファイルを結合して最終的なSRTファイルを作成"""
    print("\n最終ファイルを結合しています...")
    with open(final_output_path, 'w', encoding='utf-8') as final:
        for batch_num in range(1, total_batches + 1):
            batch_file = output_dir / f"output_batch_{batch_num}.srt"
            if batch_file.exists():
                with open(batch_file, 'r', encoding='utf-8') as f:
                    final.write(f.read())
    print(f"✓ 完成: {final_output_path}")


def main():
    """メイン処理"""
    print("=" * 60)
    print("VTT to SRT Converter - Claude AI 高精度校正版")
    print("=" * 60)

    # APIキーの確認
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("\nエラー: 環境変数 ANTHROPIC_API_KEY が設定されていません。")
        print("以下のコマンドで設定してください:")
        print('  export ANTHROPIC_API_KEY="your-api-key-here"')
        sys.exit(1)

    # コマンドライン引数からVTTファイルのパスを取得
    if len(sys.argv) < 2:
        print("\n使い方: python3 process_vtt_ai.py <vttファイルのパス>")
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

    # バッチ処理
    batch_size = 100
    total_batches = (len(entries) + batch_size - 1) // batch_size

    print(f"\nClaude API バッチ処理を開始します（{batch_size}エントリ/バッチ）")
    print(f"総バッチ数: {total_batches}")
    print(f"使用モデル: claude-sonnet-4-20250514")

    for batch_num in range(1, total_batches + 1):
        start_idx = (batch_num - 1) * batch_size
        end_idx = min(start_idx + batch_size, len(entries))
        batch_entries = entries[start_idx:end_idx]

        process_batch(batch_entries, batch_num, work_folder, api_key)

        # レート制限対策（最後のバッチ以外は3秒待機）
        if batch_num < total_batches:
            print(f"  ⏳ 3秒待機...")
            time.sleep(3)

    # 最終ファイルの結合
    final_output_path = work_folder / "final_output_corrected.srt"
    merge_batch_files(work_folder, total_batches, final_output_path)

    print("\n" + "=" * 60)
    print("処理完了！")
    print("=" * 60)
    print(f"作業フォルダ: {work_folder}")
    print(f"最終ファイル: {final_output_path.name}")
    print(f"サイズ: {final_output_path.stat().st_size / 1024:.1f} KB")
    print("=" * 60)


if __name__ == "__main__":
    main()
