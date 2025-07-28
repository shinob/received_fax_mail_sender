# FAX受信メール送信システム 設計資料

## 概要
複合機で受信したFAXのTIFファイルをPDF化し、OCRでテキスト抽出してメール送信する自動化システム。

## システム要件

### 機能要件
- 10分間隔でFAXファイル監視
- TIFファイルのPDF変換
- OCR APIによるテキスト抽出
- 抽出結果のメール送信

### 非機能要件
- 信頼性: ファイル処理失敗時のリトライ機能
- 監査性: 処理ログの記録
- セキュリティ: API認証情報の安全な管理

## システム構成

### アーキテクチャ
```
[複合機] → [NAS] → [監視スクリプト] → [PDF変換] → [OCR API] → [メール送信]
```

### コンポーネント設計

#### 1. ファイル監視モジュール
- **責任**: 新規TIFファイルの検出
- **処理**: 10分間隔で指定ディレクトリをスキャン
- **条件**: 過去10分以内に作成/更新されたTIFファイル

#### 2. PDF変換モジュール
- **責任**: TIFファイルをPDFに変換
- **処理**: 画像品質を保持したPDF生成
- **出力**: OCR処理に適したPDFファイル

#### 3. OCR処理モジュール
- **責任**: PDFからテキスト抽出
- **処理**: OCR APIとの通信
- **エラー処理**: API呼び出し失敗時のリトライ

#### 4. メール送信モジュール
- **責任**: 抽出テキストのメール送信
- **処理**: SMTP経由でのメール配信
- **内容**: 元ファイル情報 + 抽出テキスト

#### 5. ログ管理モジュール
- **責任**: 処理履歴の記録
- **ログレベル**: INFO, WARNING, ERROR
- **ローテーション**: 日次ローテーション

## 技術スタック

### 推奨技術
- **言語**: Python 3.8+
- **PDF変換**: PIL (Pillow) または img2pdf
- **OCR API**: Google Cloud Vision API / Azure Computer Vision
- **メール**: smtplib (標準ライブラリ)
- **スケジューリング**: cron / systemd timer
- **ログ**: Python logging

### 必要ライブラリ
```
pillow>=9.0.0
requests>=2.28.0
python-dotenv>=0.19.0
```

## ディレクトリ構成
```
received_fax_mail_sender/
├── src/
│   ├── __init__.py
│   ├── main.py              # メインスクリプト
│   ├── file_monitor.py      # ファイル監視
│   ├── pdf_converter.py     # PDF変換
│   ├── ocr_client.py        # OCR処理
│   ├── mail_sender.py       # メール送信
│   └── logger.py            # ログ管理
├── config/
│   ├── config.yaml          # 設定ファイル
│   └── .env.example         # 環境変数テンプレート
├── logs/                    # ログディレクトリ
├── temp/                    # 一時ファイル保存
├── requirements.txt
└── README.md
```

## 設定項目

### 環境変数 (.env)
```
# NAS設定
NAS_WATCH_DIRECTORY=/path/to/fax/directory
TEMP_DIRECTORY=./temp

# OCR API設定
OCR_API_TYPE=google_vision  # google_vision, azure_vision
GOOGLE_VISION_API_KEY=your_api_key
AZURE_VISION_ENDPOINT=your_endpoint
AZURE_VISION_KEY=your_key

# メール設定
SMTP_SERVER=smtp.example.com
SMTP_PORT=587
SMTP_USERNAME=your_username
SMTP_PASSWORD=your_password
MAIL_FROM=fax@example.com
MAIL_TO=recipient@example.com

# ログ設定
LOG_LEVEL=INFO
LOG_FILE=./logs/fax_processor.log
```

## 処理フロー

### メイン処理フロー
1. **起動時初期化**
   - 設定ファイル読み込み
   - ログ設定
   - 必要ディレクトリ作成

2. **監視ループ**
   - 10分間隔でファイルスキャン
   - 新規TIFファイル検出
   - 並列処理でファイル処理

3. **ファイル処理**
   ```
   TIFファイル検出
   ↓
   PDF変換
   ↓
   OCR処理
   ↓
   メール送信
   ↓
   一時ファイル削除
   ↓
   処理完了ログ
   ```

### エラーハンドリング
- **ファイル読み取りエラー**: スキップして次回処理
- **PDF変換エラー**: 3回リトライ後にエラーログ
- **OCR APIエラー**: 指数バックオフでリトライ
- **メール送信エラー**: キューに保存して後で再送

## セキュリティ考慮事項
- 環境変数による認証情報管理
- 一時ファイルの適切な削除
- ファイルアクセス権限の制限
- ログファイルの個人情報保護

## 運用考慮事項
- **監視**: ヘルスチェック機能
- **バックアップ**: 処理済みファイルの保管
- **アラート**: 連続エラー時の通知
- **メンテナンス**: ログローテーション

## デプロイメント
- systemdサービスとしての登録
- cronジョブでの定期実行
- Docker化オプション

## 拡張性
- 複数OCR APIの切り替え対応
- 複数宛先メール送信
- ファイル形式拡張 (PDF, JPEGなど)
- Web UI管理画面