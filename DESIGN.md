# FAX受信メール送信システム 設計資料

## 概要
複合機で受信したFAXのTIFファイルをPDF化し、OCRでテキスト抽出してメール送信する自動化システム。

## システム要件

### 機能要件
- 10分間隔でFAXファイル監視（継続監視モード）
- 単発実行モードによる一回限りの処理
- TIFファイルのPDF変換（単ページ・複数ページ対応）
- 複数OCR API対応（カスタムAPI/Google Vision/Azure Vision）
- 抽出結果のメール送信
- ヘルスチェック機能
- 並行ファイル処理（最大3ファイル同時）

### 非機能要件
- 信頼性: ファイル処理失敗時のリトライ機能、ファイル安定性チェック
- 監査性: 処理ログの記録、日次ローテーション
- セキュリティ: API認証情報の安全な管理
- 拡張性: 複数OCR API切り替え対応

## システム構成

### アーキテクチャ
```
[複合機] → [NAS] → [監視スクリプト] → [PDF変換] → [OCR API] → [メール送信]
                      ↓                              ↓
                 [並行処理対応]                [複数API対応]
                                        (カスタム/Google/Azure)
```

### コンポーネント設計

#### 1. ファイル監視モジュール（FileMonitor）
- **責任**: 新規TIFファイルの検出
- **処理**: 10分間隔で指定ディレクトリをスキャン
- **条件**: 過去10分以内に作成/更新されたTIFファイル
- **機能**: ファイル安定性チェック（書き込み完了確認）、処理済みファイル管理

#### 2. PDF変換モジュール（PDFConverter）
- **責任**: TIFファイルをPDFに変換
- **処理**: 画像品質を保持したPDF生成、単ページ・複数ページ対応
- **出力**: OCR処理に適したPDFファイル
- **機能**: PDF検証、一時ファイル管理

#### 3. OCR処理モジュール（OCRClient）
- **責任**: PDFからテキスト抽出
- **処理**: 複数OCR APIとの通信（カスタム/Google Vision/Azure Vision）
- **エラー処理**: API呼び出し失敗時のリトライ（指数バックオフ）
- **機能**: 信頼度チェック、日本語テキスト検証、非同期処理対応

#### 4. メール送信モジュール（MailSender）
- **責任**: 抽出テキストのメール送信
- **処理**: SMTP経由でのメール配信、接続テスト機能
- **内容**: 元ファイル情報 + 抽出テキスト + OCR検証結果
- **機能**: エラー通知メール送信

#### 5. ログ管理モジュール（FaxProcessorLogger）
- **責任**: 処理履歴の記録
- **ログレベル**: INFO, WARNING, ERROR, DEBUG
- **ローテーション**: サイズベース（10MB毎、5世代保持）

#### 6. メイン処理モジュール（FaxProcessor）
- **責任**: 全体の制御とコーディネーション
- **機能**: 継続監視、単発実行、並行処理管理、ヘルスチェック
- **設定**: YAML + 環境変数のハイブリッド構成

## 技術スタック

### 推奨技術
- **言語**: Python 3.8+
- **PDF変換**: PIL (Pillow) + img2pdf
- **OCR API**: カスタムAPI / Google Cloud Vision API / Azure Computer Vision
- **メール**: smtplib (標準ライブラリ)
- **設定管理**: PyYAML + python-dotenv
- **並行処理**: concurrent.futures.ThreadPoolExecutor
- **スケジューリング**: cron / systemd timer
- **ログ**: Python logging

### 必要ライブラリ
```
pillow>=9.0.0
requests>=2.28.0
python-dotenv>=0.19.0
google-cloud-vision>=3.0.0
azure-cognitiveservices-vision-computervision>=0.9.0
PyYAML>=6.0
img2pdf>=0.4.4
```

## ディレクトリ構成
```
received_fax_mail_sender/
├── src/
│   ├── __init__.py
│   ├── main.py              # メインスクリプト（FaxProcessor）
│   ├── file_monitor.py      # ファイル監視（FileMonitor）
│   ├── pdf_converter.py     # PDF変換（PDFConverter）
│   ├── ocr_client.py        # OCR処理（OCRClient）
│   ├── mail_sender.py       # メール送信（MailSender）
│   └── logger.py            # ログ管理（FaxProcessorLogger）
├── config/
│   ├── config.yaml          # システム設定（YAML）
│   └── .env.example         # 環境変数テンプレート
├── logs/                    # ログディレクトリ
│   └── fax_processor.log    # アプリケーションログ
├── temp/                    # 一時ファイル保存
├── tif/                     # テスト用TIFファイル格納
├── requirements.txt         # Python依存関係
├── README.md               # 使用方法説明
├── DESIGN.md               # 設計文書
└── LICENSE                 # ライセンス
```

## 設定項目

### 環境変数 (.env)
```
# NAS設定
NAS_WATCH_DIRECTORY=/path/to/fax/directory
TEMP_DIRECTORY=./temp

# OCR API設定
OCR_API_TYPE=custom_api   # custom_api, google_vision, azure_vision

# Custom API（推奨）
OCR_API_BASE_URL=https://your-ocr-api.com
OCR_API_EMAIL=your-email@example.com
OCR_MAX_RETRIES=30
OCR_RETRY_INTERVAL=10

# Google Vision API（オプション）
GOOGLE_VISION_API_KEY=your_api_key

# Azure Vision API（オプション）
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

### YAML設定ファイル (config/config.yaml)
```yaml
fax:
  check_interval: 600  # 監視間隔（秒）
  file_extensions: [".tif", ".tiff"]
  
ocr:
  retry_count: 3  # 基本リトライ回数
  retry_delay: 2  # リトライ間隔（秒）
  confidence_threshold: 0.7  # 信頼度閾値
  max_retries: 30  # カスタムAPI用最大リトライ
  retry_interval: 10  # カスタムAPI用リトライ間隔
  
mail:
  subject_template: "FAX受信通知 - {filename}"
  retry_count: 3
  
logging:
  max_bytes: 10485760  # ログファイル最大サイズ（10MB）
  backup_count: 5  # 世代数
  
processing:
  max_concurrent_files: 3  # 並行処理数
  temp_file_cleanup: true  # 一時ファイル自動削除
```

## 処理フロー

### メイン処理フロー

#### 1. 起動時初期化
- 設定ファイル読み込み（YAML + 環境変数）
- ログ設定とコンポーネント初期化
- SMTP接続テスト
- シグナルハンドラー設定

#### 2. 実行モード分岐
- **継続監視モード**: `run_continuous()` - デフォルト
- **単発実行モード**: `run_single_scan()` - `--once`オプション時
- **ヘルスチェックモード**: `health_check()` - `--health-check`オプション時

#### 3. ファイル処理フロー
```
TIFファイル検出（複数）
       ↓
ファイル安定性チェック
       ↓
ThreadPoolExecutor（最大3並行）
       ↓
各ファイルで並行実行:
   TIFファイル → PDF変換 → PDF検証 → OCR処理 → テキスト検証 → メール送信
       ↓
処理済みマーク + 一時ファイル削除
       ↓
処理完了ログ
```

### エラーハンドリング
- **ファイル読み取りエラー**: ファイル安定性チェック後、次回処理でリトライ
- **PDF変換エラー**: 3回リトライ後にエラーログ、一時ファイル削除
- **PDF検証エラー**: 変換失敗として扱い、一時ファイル削除
- **OCR APIエラー**: 指数バックオフでリトライ（最大3回）
  - カスタムAPI: 最大30回（10秒間隔）の非同期処理待機
  - Google/Azure: 即座にレスポンス、信頼度チェック
- **メール送信エラー**: エラー通知メール送信、処理失敗としてマーク
- **システムエラー**: 全般的な例外をキャッチしてログ記録 + エラー通知

## セキュリティ考慮事項
- 環境変数による認証情報管理
- 一時ファイルの適切な削除
- ファイルアクセス権限の制限
- ログファイルの個人情報保護

## 運用考慮事項
- **監視**: ヘルスチェック機能（`--health-check`）
  - ファイル監視ディレクトリアクセス確認
  - SMTP接続テスト
  - コンポーネント状態確認
- **バックアップ**: 処理済みファイルの保管（要手動設定）
- **アラート**: エラー通知メール自動送信
- **メンテナンス**: サイズベースログローテーション（10MB毎、5世代）
- **パフォーマンス**: 並行処理数調整（デフォルト3ファイル同時）

## 実行方法

### コマンドラインオプション
```bash
# 継続監視モード（通常運用）
python -m src.main

# 単発実行モード（テスト・cron用）
python -m src.main --once

# ヘルスチェック
python -m src.main --health-check

# カスタム設定ファイル指定
python -m src.main --config /path/to/config.yaml --env /path/to/.env
```

### デプロイメント
- **systemdサービス**: 継続監視モードで自動起動・再起動
- **cronジョブ**: 単発実行モードで定期実行
- **Docker化**: 対応予定（オプション）

## 拡張性
- **OCR API**: 3種類対応済み（カスタム/Google Vision/Azure Vision）
- **複数宛先**: メール送信機能で対応可能
- **ファイル形式**: TIF/TIFF専用（PDF、JPEG拡張は要開発）
- **Web UI**: 未実装（将来的な拡張予定）
- **ヘルスチェック**: API対応可能な形式で実装済み