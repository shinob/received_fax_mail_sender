import os
import tempfile
from pathlib import Path
from typing import Optional
import img2pdf
from PIL import Image
from .logger import FaxProcessorLogger


class PDFConverter:
    def __init__(self, config: dict, logger: FaxProcessorLogger):
        self.config = config
        self.logger = logger
        self.temp_directory = config.get('TEMP_DIRECTORY', './temp')
        os.makedirs(self.temp_directory, exist_ok=True)

    def convert_tif_to_pdf(self, tif_path: Path) -> Optional[Path]:
        try:
            self.logger.info(f"Converting TIF to PDF: {tif_path}")
            
            if not tif_path.exists():
                self.logger.error(f"TIF file does not exist: {tif_path}")
                return None

            pdf_filename = f"{tif_path.stem}.pdf"
            pdf_path = Path(self.temp_directory) / pdf_filename

            if self._is_multipage_tif(tif_path):
                return self._convert_multipage_tif(tif_path, pdf_path)
            else:
                return self._convert_single_page_tif(tif_path, pdf_path)

        except Exception as e:
            self.logger.error(f"Error converting TIF to PDF {tif_path}: {str(e)}")
            return None

    def _is_multipage_tif(self, tif_path: Path) -> bool:
        try:
            with Image.open(tif_path) as img:
                img.seek(1)
                return True
        except (EOFError, AttributeError):
            return False

    def _convert_single_page_tif(self, tif_path: Path, pdf_path: Path) -> Optional[Path]:
        try:
            with open(tif_path, 'rb') as tif_file:
                pdf_bytes = img2pdf.convert(tif_file.read())
            
            with open(pdf_path, 'wb') as pdf_file:
                pdf_file.write(pdf_bytes)
            
            self.logger.info(f"Successfully converted single-page TIF to PDF: {pdf_path}")
            return pdf_path

        except Exception as e:
            self.logger.error(f"Error converting single-page TIF: {str(e)}")
            return None

    def _convert_multipage_tif(self, tif_path: Path, pdf_path: Path) -> Optional[Path]:
        try:
            temp_images = []
            
            with Image.open(tif_path) as img:
                page_count = 0
                while True:
                    try:
                        img.seek(page_count)
                        
                        temp_image_path = Path(self.temp_directory) / f"temp_page_{page_count}.png"
                        
                        page_img = img.copy()
                        if page_img.mode != 'RGB':
                            page_img = page_img.convert('RGB')
                        
                        page_img.save(temp_image_path, 'PNG')
                        temp_images.append(temp_image_path)
                        page_count += 1
                        
                    except EOFError:
                        break

            if temp_images:
                pdf_bytes = img2pdf.convert([str(img) for img in temp_images])
                with open(pdf_path, 'wb') as pdf_file:
                    pdf_file.write(pdf_bytes)
                
                for temp_img in temp_images:
                    try:
                        temp_img.unlink()
                    except Exception as e:
                        self.logger.warning(f"Could not delete temp image {temp_img}: {str(e)}")
                
                self.logger.info(f"Successfully converted multi-page TIF ({page_count} pages) to PDF: {pdf_path}")
                return pdf_path
            else:
                self.logger.error("No pages found in multi-page TIF")
                return None

        except Exception as e:
            self.logger.error(f"Error converting multi-page TIF: {str(e)}")
            return None

    def cleanup_pdf(self, pdf_path: Path) -> None:
        try:
            if pdf_path.exists():
                pdf_path.unlink()
                self.logger.debug(f"Cleaned up PDF file: {pdf_path}")
        except Exception as e:
            self.logger.warning(f"Could not cleanup PDF file {pdf_path}: {str(e)}")

    def validate_pdf(self, pdf_path: Path) -> bool:
        try:
            if not pdf_path.exists():
                return False
            
            if pdf_path.stat().st_size == 0:
                self.logger.error(f"PDF file is empty: {pdf_path}")
                return False
            
            with open(pdf_path, 'rb') as pdf_file:
                header = pdf_file.read(4)
                if header != b'%PDF':
                    self.logger.error(f"Invalid PDF header: {pdf_path}")
                    return False
            
            return True

        except Exception as e:
            self.logger.error(f"Error validating PDF {pdf_path}: {str(e)}")
            return False