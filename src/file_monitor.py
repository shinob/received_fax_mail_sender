import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Set
from .logger import FaxProcessorLogger


class FileMonitor:
    def __init__(self, config: dict, logger: FaxProcessorLogger):
        self.config = config
        self.logger = logger
        self.watch_directory = config.get('NAS_WATCH_DIRECTORY')
        self.file_extensions = config.get('file_extensions', ['.tif', '.tiff'])
        self.check_interval = config.get('check_interval', 600)
        self.processed_files: Set[str] = set()

    def scan_for_new_files(self, time_threshold_minutes: int = 10) -> List[Path]:
        if not os.path.exists(self.watch_directory):
            self.logger.error(f"Watch directory does not exist: {self.watch_directory}")
            return []

        new_files = []
        current_time = datetime.now()
        threshold_time = current_time - timedelta(minutes=time_threshold_minutes)

        try:
            for root, _, files in os.walk(self.watch_directory):
                for file in files:
                    file_path = Path(root) / file
                    
                    if not self._is_target_file(file_path):
                        continue

                    if str(file_path) in self.processed_files:
                        continue

                    file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                    
                    if file_mtime >= threshold_time:
                        new_files.append(file_path)
                        self.logger.info(f"New FAX file detected: {file_path}")

        except Exception as e:
            self.logger.error(f"Error scanning directory {self.watch_directory}: {str(e)}")
            return []

        return new_files

    def _is_target_file(self, file_path: Path) -> bool:
        return file_path.suffix.lower() in self.file_extensions

    def mark_as_processed(self, file_path: Path) -> None:
        self.processed_files.add(str(file_path))
        self.logger.debug(f"Marked file as processed: {file_path}")

    def is_file_ready(self, file_path: Path, stability_check_seconds: int = 5) -> bool:
        try:
            initial_size = file_path.stat().st_size
            initial_mtime = file_path.stat().st_mtime
            
            time.sleep(stability_check_seconds)
            
            current_size = file_path.stat().st_size
            current_mtime = file_path.stat().st_mtime
            
            if initial_size == current_size and initial_mtime == current_mtime:
                return True
            else:
                self.logger.debug(f"File still being written: {file_path}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error checking file stability {file_path}: {str(e)}")
            return False

    def cleanup_processed_files_cache(self, max_age_hours: int = 24) -> None:
        current_files = set()
        
        try:
            for root, _, files in os.walk(self.watch_directory):
                for file in files:
                    file_path = Path(root) / file
                    if self._is_target_file(file_path):
                        current_files.add(str(file_path))
        except Exception as e:
            self.logger.error(f"Error during cache cleanup: {str(e)}")
            return

        removed_count = len(self.processed_files) - len(self.processed_files & current_files)
        self.processed_files &= current_files
        
        if removed_count > 0:
            self.logger.info(f"Cleaned up {removed_count} entries from processed files cache")