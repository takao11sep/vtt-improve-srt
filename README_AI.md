# VTT to SRT Converter - Claude AI 高精度校正版

Claude API（Sonnet 4）を使用して、歯科・矯正歯科の専門用語を高精度で校正します。

## 🎯 特徴

- ✅ **Claude Sonnet 4** による高精度AI校正
- ✅ **歯科・矯正専門用語** の正確な変換
- ✅ **フィラー完全除去**（えー、あのー等）
- ✅ **自然な日本語** への修正
- ✅ **発話者名保持**
- ✅ **タイムコード完全保持**

## 📋 必要な準備

### 1. Anthropic APIキーの取得

1. [Anthropic Console](https://console.anthropic.com/) にアクセス
2. APIキーを作成
3. APIキーをコピー

### 2. APIキーの設定

ターミナルで以下を実行：

```bash
export ANTHROPIC_API_KEY="your-api-key-here"
```

**永続的に設定する場合**（推奨）:

```bash
# ~/.zshrc または ~/.bash_profile に追加
echo 'export ANTHROPIC_API_KEY="your-api-key-here"' >> ~/.zshrc
source ~/.zshrc
```

## 🚀 使い方

### 方法1: コマンドライン

```bash
python3 process_vtt_ai.py /path/to/your/file.vtt
```

### 方法2: ドラッグ&ドロップ（推奨）

1. ターミナルで以下を入力（最後にスペース）:
```bash
python3 /Users/takao11sep/claude-project/vtt-improve-srt/process_vtt_ai.py
```

2. VTTファイルをターミナルにドラッグ&ドロップ

3. Enterキーを押す

## 📊 処理フロー

```
VTTファイル読み込み
    ↓
100エントリずつバッチに分割
    ↓
各バッチをClaude API に送信
    ↓
AI校正結果を取得
    ↓
SRTファイルとして保存
    ↓
全バッチを結合
    ↓
final_output_corrected.srt 完成！
```

## 🔧 校正ルール

### 1. フィラー除去
- えー、あのー、えっと、その、まあ、なんか
- 意味のない繰り返し（「そうそうそう」→「そう」）

### 2. 歯科・矯正専門用語の正確な変換
- **補綴**: ほてつ → 補綴
- **矯正装置**: インビザライン、アライナー、ブラケット、ワイヤー
- **解剖学用語**: 咬合、舌側、頬側、近心、遠心
- **治療用語**: IPR、アタッチメント、エラスティック

### 3. 自然な日本語への修正
- 口語表現の修正（「なんすか」→「なんですか」）
- 不自然な助詞の修正
- 文章の区切りを自然に

## 💰 料金について

Claude API（Sonnet 4）の料金：
- Input: $3.00 / 1M tokens
- Output: $15.00 / 1M tokens

**概算**: 1000エントリの処理で約$0.20～0.50程度

## ⚠️ 注意事項

- API呼び出しに時間がかかります（100エントリで約10-15秒）
- レート制限対策として各バッチ間に3秒の待機時間あり
- インターネット接続が必要です

## 🆚 従来版との比較

| 項目 | 従来版 (process_vtt.py) | AI版 (process_vtt_ai.py) |
|------|-------------------------|--------------------------|
| 校正精度 | 低（文字列置換のみ） | 高（AI理解） |
| 専門用語 | 固定パターンのみ | 文脈理解して変換 |
| 処理速度 | 速い（1秒以下） | 遅い（バッチあたり10-15秒） |
| コスト | 無料 | 有料（APIコスト） |
| ネット接続 | 不要 | 必要 |

## 📁 出力ファイル

```
work_YYYYMMDD_HHMMSS/
├── 20260113_orthoelite.vtt          # 元ファイル
├── output_batch_1.srt                # バッチ1
├── output_batch_2.srt                # バッチ2
├── ...
└── final_output_corrected.srt        # ★最終ファイル★
```

## 🐛 トラブルシューティング

### エラー: ANTHROPIC_API_KEY が設定されていません

```bash
export ANTHROPIC_API_KEY="your-api-key-here"
```

### エラー: anthropic パッケージがない

```bash
pip install anthropic
```

### API呼び出しが失敗する

- APIキーが正しいか確認
- インターネット接続を確認
- [Anthropic Status](https://status.anthropic.com/) でサービス状況を確認
