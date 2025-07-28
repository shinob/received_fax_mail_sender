import smtplib
import time
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path
from typing import Optional, Dict, Any
from .logger import FaxProcessorLogger


class MailSender:
    def __init__(self, config: dict, logger: FaxProcessorLogger):
        self.config = config
        self.logger = logger
        self.smtp_server = config.get('SMTP_SERVER')
        self.smtp_port = int(config.get('SMTP_PORT', 587))
        self.username = config.get('SMTP_USERNAME')
        self.password = config.get('SMTP_PASSWORD')
        self.mail_from = config.get('MAIL_FROM')
        self.mail_to = config.get('MAIL_TO')
        self.retry_count = config.get('retry_count', 3)
        
        self._validate_config()

    def _validate_config(self) -> None:
        required_fields = ['SMTP_SERVER', 'SMTP_USERNAME', 'SMTP_PASSWORD', 'MAIL_FROM', 'MAIL_TO']
        missing_fields = [field for field in required_fields if not self.config.get(field)]
        
        if missing_fields:
            raise ValueError(f"Missing required mail configuration: {', '.join(missing_fields)}")

    def send_fax_notification(self, original_file: Path, extracted_text: str, 
                            ocr_metadata: Optional[Dict[str, Any]] = None) -> bool:
        for attempt in range(self.retry_count):
            try:
                self.logger.info(f"Sending email notification (attempt {attempt + 1}): {original_file.name}")
                
                message = self._create_email_message(original_file, extracted_text, ocr_metadata)
                
                with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                    server.starttls()
                    server.login(self.username, self.password)
                    
                    text = message.as_string()
                    server.sendmail(self.mail_from, self.mail_to.split(','), text)
                
                self.logger.info(f"Email sent successfully to {self.mail_to}")
                return True
                
            except Exception as e:
                self.logger.warning(f"Email sending attempt {attempt + 1} failed: {str(e)}")
                if attempt < self.retry_count - 1:
                    time.sleep(2 ** attempt)
                else:
                    self.logger.error(f"All email sending attempts failed for {original_file.name}")
                    
        return False

    def _create_email_message(self, original_file: Path, extracted_text: str, 
                            ocr_metadata: Optional[Dict[str, Any]] = None) -> MIMEMultipart:
        message = MIMEMultipart()
        
        subject_template = self.config.get('subject_template', 'FAX受信通知 - {filename}')
        message['Subject'] = subject_template.format(filename=original_file.name)
        message['From'] = self.mail_from
        message['To'] = self.mail_to
        message['Date'] = datetime.now().strftime('%a, %d %b %Y %H:%M:%S %z')
        
        body = self._create_email_body(original_file, extracted_text, ocr_metadata)
        message.attach(MIMEText(body, 'plain', 'utf-8'))
        
        return message

    def _create_email_body(self, original_file: Path, extracted_text: str, 
                         ocr_metadata: Optional[Dict[str, Any]] = None) -> str:
        timestamp = datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')
        
        body_lines = [
            "FAX受信通知",
            "=" * 50,
            f"受信日時: {timestamp}",
            f"ファイル名: {original_file.name}",
            f"ファイルパス: {original_file}",
            ""
        ]
        
        if ocr_metadata:
            body_lines.extend([
                "OCR処理情報:",
                f"  文字数: {ocr_metadata.get('char_count', 'N/A')}",
                f"  単語数: {ocr_metadata.get('word_count', 'N/A')}",
                f"  行数: {ocr_metadata.get('line_count', 'N/A')}",
                f"  日本語含有: {'はい' if ocr_metadata.get('has_japanese', False) else 'いいえ'}",
                ""
            ])
        
        body_lines.extend([
            "抽出されたテキスト:",
            "-" * 30,
            extracted_text,
            "",
            "-" * 30,
            "このメールは自動送信されています。"
        ])
        
        return '\n'.join(body_lines)

    def send_error_notification(self, error_message: str, file_path: Optional[Path] = None) -> bool:
        try:
            self.logger.info("Sending error notification email")
            
            message = MIMEMultipart()
            message['Subject'] = "FAX処理エラー通知"
            message['From'] = self.mail_from
            message['To'] = self.mail_to
            message['Date'] = datetime.now().strftime('%a, %d %b %Y %H:%M:%S %z')
            
            timestamp = datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')
            
            body_lines = [
                "FAX処理エラー通知",
                "=" * 50,
                f"エラー発生日時: {timestamp}",
                f"対象ファイル: {file_path if file_path else 'N/A'}",
                "",
                "エラー内容:",
                error_message,
                "",
                "システム管理者にお問い合わせください。"
            ]
            
            body = '\n'.join(body_lines)
            message.attach(MIMEText(body, 'plain', 'utf-8'))
            
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.username, self.password)
                
                text = message.as_string()
                server.sendmail(self.mail_from, self.mail_to.split(','), text)
            
            self.logger.info("Error notification email sent successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to send error notification email: {str(e)}")
            return False

    def test_connection(self) -> bool:
        try:
            self.logger.info("Testing SMTP connection")
            
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.username, self.password)
            
            self.logger.info("SMTP connection test successful")
            return True
            
        except Exception as e:
            self.logger.error(f"SMTP connection test failed: {str(e)}")
            return False