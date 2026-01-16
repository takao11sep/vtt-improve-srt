# 使い方ガイド

## クイックスタート

### ターミナルから実行

```bash
# vtt-improve-srt フォルダに移動
cd /Users/takao11sep/claude-project/vtt-improve-srt

# VTTファイルを処理
python3 process_vtt.py /path/to/your/file.vtt
```

### ドラッグ&ドロップで実行（推奨）

1. ターミナルを開く

2. 以下をコピー&ペースト（最後にスペースあり）:
```bash
python3 /Users/takao11sep/claude-project/vtt-improve-srt/process_vtt.py
```

3. VTTファイルをFinderからターミナルにドラッグ&ドロップ

4. Enterキーを押す

## 処理の流れ

```
VTTファイルをドロップ
    ↓
work_YYYYMMDD_HHMMSS フォルダが自動生成
    ↓
VTTファイルがフォルダにコピー
    ↓
バッチ処理開始（100エントリずつ）
    ↓
final_output_corrected.srt が完成！
```

## 出力ファイル

### work_YYYYMMDD_HHMMSS/ フォルダ内

```
├── input.vtt                      # 元のVTTファイル（コピー）
├── output_batch_1.srt             # バッチ1（エントリ1-100）
├── output_batch_2.srt             # バッチ2（エントリ101-200）
├── output_batch_3.srt             # バッチ3（エントリ201-300）
├── output_batch_4.srt             # バッチ4（残り）
└── final_output_corrected.srt     # ★最終ファイル★
```

## 校正例

### Before（VTT）
```
00:03:05.590 --> 00:03:07.899
minamidate: えー、ジャミロックワイ。なんすね。ようは。
```

### After（SRT）
```
3
00:03:05,590 --> 00:03:07,899
minamidate: ジャミロックワイ。なんですね。ようは。
```

変更点：
- フィラー「えー、」を除去
- 「なんすね」→「なんですね」に修正
- タイムコードの `.` を `,` に変換
- 発話者名 `minamidate:` を保持

## よくある質問

### Q: VTTファイル名は何でもいい？
A: はい、任意のファイル名で処理できます。

### Q: 処理にどのくらい時間がかかる？
A: 300エントリで約1-2秒です。

### Q: 複数ファイルを一度に処理できる？
A: 1つずつ処理してください。各ファイルごとに新しい作業フォルダが作られます。

### Q: エラーが出たら？
A: 以下を確認してください：
- VTTファイルが正しい形式か
- ファイルパスに日本語や空白が含まれていないか
- Python 3がインストールされているか（`python3 --version` で確認）
