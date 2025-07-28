#!/usr/bin/env python3
import os
import sys
import time
import signal
import yaml
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, Any, List
from dotenv import load_dotenv

from .logger import FaxProcessorLogger
from .file_monitor import FileMonitor
from .pdf_converter import PDFConverter
from .ocr_client import OCRClient
from .mail_sender import MailSender


class FaxProcessor:
    def __init__(self, config_path: str = None, env_path: str = None):
        self.config_path = config_path or './config/config.yaml'
        self.env_path = env_path or '.env'
        self.running = True
        
        self._load_configuration()
        self._setup_components()
        self._setup_signal_handlers()

    def _load_configuration(self) -> None:
        load_dotenv(self.env_path)
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            self.yaml_config = yaml.safe_load(f)
        
        self.env_config = dict(os.environ)
        
        self.config = {**self.yaml_config.get('fax', {}), **self.env_config}
        self.config.update(self.yaml_config.get('ocr', {}))
        self.config.update(self.yaml_config.get('mail', {}))
        self.config.update(self.yaml_config.get('logging', {}))
        self.config.update(self.yaml_config.get('processing', {}))

    def _setup_components(self) -> None:
        self.logger = FaxProcessorLogger(self.config)
        self.logger.info("FAX Processor starting up")
        
        try:
            self.file_monitor = FileMonitor(self.config, self.logger)
            self.pdf_converter = PDFConverter(self.config, self.logger)
            self.ocr_client = OCRClient(self.config, self.logger)
            self.mail_sender = MailSender(self.config, self.logger)
            
            self.max_concurrent_files = self.config.get('max_concurrent_files', 3)
            
            if not self.mail_sender.test_connection():
                raise Exception("SMTP connection test failed")
                
            self.logger.info("All components initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize components: {str(e)}")
            sys.exit(1)

    def _setup_signal_handlers(self) -> None:
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

    def _signal_handler(self, signum, frame) -> None:
        self.logger.info(f"Received signal {signum}, shutting down gracefully")
        self.running = False

    def process_single_file(self, tif_file: Path) -> bool:
        try:
            self.logger.info(f"Processing file: {tif_file}")
            
            if not self.file_monitor.is_file_ready(tif_file):
                self.logger.warning(f"File not ready for processing: {tif_file}")
                return False

            pdf_file = self.pdf_converter.convert_tif_to_pdf(tif_file)
            if not pdf_file:
                self.logger.error(f"PDF conversion failed: {tif_file}")
                return False

            if not self.pdf_converter.validate_pdf(pdf_file):
                self.logger.error(f"PDF validation failed: {pdf_file}")
                self.pdf_converter.cleanup_pdf(pdf_file)
                return False

            extracted_text = self.ocr_client.extract_text_from_pdf(pdf_file)
            if not extracted_text:
                self.logger.error(f"OCR text extraction failed: {pdf_file}")
                self.pdf_converter.cleanup_pdf(pdf_file)
                return False

            validation_result = self.ocr_client.validate_extracted_text(extracted_text)
            if not validation_result['is_valid']:
                self.logger.warning(f"Extracted text validation failed: {validation_result.get('reason', 'Unknown')}")

            success = self.mail_sender.send_fax_notification(
                tif_file, extracted_text, validation_result
            )
            
            if self.config.get('temp_file_cleanup', True):
                self.pdf_converter.cleanup_pdf(pdf_file)

            if success:
                self.file_monitor.mark_as_processed(tif_file)
                self.logger.info(f"Successfully processed file: {tif_file}")
                return True
            else:
                self.logger.error(f"Email sending failed: {tif_file}")
                return False

        except Exception as e:
            self.logger.error(f"Error processing file {tif_file}: {str(e)}")
            self.mail_sender.send_error_notification(f"Processing error: {str(e)}", tif_file)
            return False

    def run_single_scan(self) -> None:
        try:
            new_files = self.file_monitor.scan_for_new_files()
            if not new_files:
                self.logger.debug("No new files found")
                return

            self.logger.info(f"Found {len(new_files)} new files to process")

            with ThreadPoolExecutor(max_workers=self.max_concurrent_files) as executor:
                future_to_file = {
                    executor.submit(self.process_single_file, file_path): file_path 
                    for file_path in new_files
                }

                for future in as_completed(future_to_file):
                    file_path = future_to_file[future]
                    try:
                        success = future.result()
                        if success:
                            self.logger.info(f"File processed successfully: {file_path}")
                        else:
                            self.logger.error(f"File processing failed: {file_path}")
                    except Exception as e:
                        self.logger.error(f"Unexpected error processing {file_path}: {str(e)}")

        except Exception as e:
            self.logger.error(f"Error during scan cycle: {str(e)}")
            self.mail_sender.send_error_notification(f"Scan cycle error: {str(e)}")

    def run_continuous(self) -> None:
        self.logger.info("Starting continuous monitoring mode")
        check_interval = self.config.get('check_interval', 600)
        
        try:
            while self.running:
                self.run_single_scan()
                
                self.file_monitor.cleanup_processed_files_cache()
                
                if self.running:
                    self.logger.debug(f"Sleeping for {check_interval} seconds")
                    time.sleep(check_interval)
                    
        except KeyboardInterrupt:
            self.logger.info("Keyboard interrupt received")
        except Exception as e:
            self.logger.error(f"Unexpected error in continuous mode: {str(e)}")
            self.mail_sender.send_error_notification(f"System error: {str(e)}")
        finally:
            self.logger.info("FAX Processor shutting down")

    def health_check(self) -> Dict[str, Any]:
        health_status = {
            'timestamp': time.time(),
            'status': 'healthy',
            'components': {}
        }

        try:
            if os.path.exists(self.config.get('NAS_WATCH_DIRECTORY', '')):
                health_status['components']['file_monitor'] = 'ok'
            else:
                health_status['components']['file_monitor'] = 'error: directory not accessible'
                health_status['status'] = 'unhealthy'

            if self.mail_sender.test_connection():
                health_status['components']['mail_sender'] = 'ok'
            else:
                health_status['components']['mail_sender'] = 'error: smtp connection failed'
                health_status['status'] = 'unhealthy'

            health_status['components']['ocr_client'] = 'ok'
            health_status['components']['pdf_converter'] = 'ok'

        except Exception as e:
            health_status['status'] = 'unhealthy'
            health_status['error'] = str(e)

        return health_status


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='FAX Processor - Automated FAX to Email System')
    parser.add_argument('--config', '-c', default='./config/config.yaml', 
                       help='Path to configuration file')
    parser.add_argument('--env', '-e', default='.env', 
                       help='Path to environment file')
    parser.add_argument('--once', action='store_true', 
                       help='Run once and exit (instead of continuous monitoring)')
    parser.add_argument('--health-check', action='store_true', 
                       help='Perform health check and exit')
    
    args = parser.parse_args()
    
    try:
        processor = FaxProcessor(args.config, args.env)
        
        if args.health_check:
            health = processor.health_check()
            print(f"Health Status: {health['status']}")
            for component, status in health['components'].items():
                print(f"  {component}: {status}")
            sys.exit(0 if health['status'] == 'healthy' else 1)
        
        if args.once:
            processor.run_single_scan()
        else:
            processor.run_continuous()
            
    except Exception as e:
        print(f"Fatal error: {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()