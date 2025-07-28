# FAX受信メール送信システム

複合機で受信したFAXのTIFファイルをPDF化し、OCRでテキスト抽出してメール送信する自動化システムです。

## 機能

- 10分間隔でFAXファイル監視
- TIFファイルのPDF変換（単ページ・複数ページ対応）
- OCR APIによるテキスト抽出（カスタムAPI / Google Vision API / Azure Computer Vision）  
- 抽出結果のメール送信
- エラー処理とリトライ機能
- ログ管理とヘルスチェック

## セットアップ

### 1. 依存関係のインストール

```bash
pip install -r requirements.txt
```

### 2. 環境設定

`.env`ファイルを作成：

```bash
cp config/.env.example .env
```

`.env`ファイルを編集して設定値を入力してください。

### 3. OCR API設定

#### カスタムOCR API の場合（推奨）
- OCR APIのベースURLとメールアドレスを`.env`ファイルに設定
- デフォルトで`custom_api`が選択されます

#### Google Vision API の場合
- Google Cloud プロジェクトでVision APIを有効化
- APIキーを取得して`.env`ファイルに設定
- `OCR_API_TYPE=google_vision`に変更

#### Azure Computer Vision の場合  
- Azure Cognitive Servicesリソースを作成
- エンドポイントとキーを`.env`ファイルに設定
- `OCR_API_TYPE=azure_vision`に変更

## 使用方法

### 継続監視モード（通常運用）
```bash
python -m src.main
```

### 単発実行モード
```bash
python -m src.main --once
```

### ヘルスチェック
```bash
python -m src.main --health-check
```

### カスタム設定ファイル使用
```bash
python -m src.main --config /path/to/config.yaml --env /path/to/.env
```

## システム構成

```
src/
├── __init__.py          # パッケージ初期化
├── main.py              # メインスクリプト
├── file_monitor.py      # ファイル監視
├── pdf_converter.py     # PDF変換
├── ocr_client.py        # OCR処理
├── mail_sender.py       # メール送信
└── logger.py            # ログ管理
```

## 設定ファイル

### config/config.yaml
システム動作パラメータの設定

### .env
認証情報や環境固有設定

## 運用

### systemdサービス化

`/etc/systemd/system/fax-processor.service`：

```ini
[Unit]
Description=FAX Processor Service
After=network.target

[Service]
Type=simple
User=faxuser
WorkingDirectory=/path/to/received_fax_mail_sender
ExecStart=/usr/bin/python3 -m src.main
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### cronジョブ設定

単発実行モードでの定期実行：

```bash
# 10分ごとに実行
*/10 * * * * cd /path/to/received_fax_mail_sender && python3 -m src.main --once
```

## ログ

- ファイル: `logs/fax_processor.log`
- ローテーション: 10MB毎、5世代保持
- レベル: INFO, WARNING, ERROR, DEBUG

## トラブルシューティング

### よくある問題

1. **OCR APIエラー**
   - APIキーの確認
   - 課金アカウントの設定確認
   - レート制限の確認

2. **メール送信エラー**
   - SMTP設定の確認
   - 認証情報の確認
   - ファイアウォール設定

3. **ファイル読み込みエラー**
   - NASマウント状態の確認
   - ファイルアクセス権限の確認

### デバッグモード

ログレベルをDEBUGに変更：

```bash
export LOG_LEVEL=DEBUG
python -m src.main --once
```

## セキュリティ

- 環境変数による認証情報管理
- 一時ファイルの自動削除
- ログファイルの個人情報保護

## ライセンス

MIT License