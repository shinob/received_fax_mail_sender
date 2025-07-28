import logging
import logging.handlers
import os
from typing import Optional


class FaxProcessorLogger:
    def __init__(self, config: dict, log_file: Optional[str] = None):
        self.config = config
        self.log_file = log_file or config.get('LOG_FILE', './logs/fax_processor.log')
        self.log_level = config.get('LOG_LEVEL', 'INFO')
        self.logger = self._setup_logger()

    def _setup_logger(self) -> logging.Logger:
        logger = logging.getLogger('fax_processor')
        logger.setLevel(getattr(logging, self.log_level))
        
        if logger.handlers:
            return logger

        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

        os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
        
        file_handler = logging.handlers.RotatingFileHandler(
            self.log_file,
            maxBytes=self.config.get('max_bytes', 10485760),
            backupCount=self.config.get('backup_count', 5)
        )
        file_handler.setLevel(getattr(logging, self.log_level))
        file_handler.setFormatter(formatter)
        
        console_handler = logging.StreamHandler()
        console_handler.setLevel(getattr(logging, self.log_level))
        console_handler.setFormatter(formatter)
        
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
        return logger

    def info(self, message: str) -> None:
        self.logger.info(message)

    def warning(self, message: str) -> None:
        self.logger.warning(message)

    def error(self, message: str) -> None:
        self.logger.error(message)

    def debug(self, message: str) -> None:
        self.logger.debug(message)

    def exception(self, message: str) -> None:
        self.logger.exception(message)