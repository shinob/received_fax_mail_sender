import time
from pathlib import Path
from typing import Optional, Dict, Any
import requests
from .logger import FaxProcessorLogger

try:
    from google.cloud import vision
    GOOGLE_VISION_AVAILABLE = True
except ImportError:
    GOOGLE_VISION_AVAILABLE = False

try:
    from azure.cognitiveservices.vision.computervision import ComputerVisionClient
    from azure.cognitiveservices.vision.computervision.models import OperationStatusCodes
    from msrest.authentication import CognitiveServicesCredentials
    AZURE_VISION_AVAILABLE = True
except ImportError:
    AZURE_VISION_AVAILABLE = False


class OCRClient:
    def __init__(self, config: dict, logger: FaxProcessorLogger):
        self.config = config
        self.logger = logger
        self.api_type = config.get('OCR_API_TYPE', 'custom_api').lower()
        self.retry_count = config.get('retry_count', 3)
        self.retry_delay = config.get('retry_delay', 2)
        self.confidence_threshold = config.get('confidence_threshold', 0.7)
        
        self._setup_client()

    def _setup_client(self) -> None:
        if self.api_type == 'custom_api':
            self._setup_custom_api()
        elif self.api_type == 'google_vision':
            self._setup_google_vision()
        elif self.api_type == 'azure_vision':
            self._setup_azure_vision()
        else:
            raise ValueError(f"Unsupported OCR API type: {self.api_type}")

    def _setup_custom_api(self) -> None:
        self.api_base_url = self.config.get('OCR_API_BASE_URL')
        self.email = self.config.get('OCR_API_EMAIL')
        self.max_retries = int(self.config.get('OCR_MAX_RETRIES', 30))
        self.retry_interval = int(self.config.get('OCR_RETRY_INTERVAL', 10))
        
        if not self.api_base_url:
            raise ValueError("OCR API base URL not provided")
        if not self.email:
            raise ValueError("OCR API email not provided")
            
        self.logger.info("Custom OCR API client initialized")

    def _setup_google_vision(self) -> None:
        if not GOOGLE_VISION_AVAILABLE:
            raise ImportError("Google Cloud Vision library not available")
        
        api_key = self.config.get('GOOGLE_VISION_API_KEY')
        if not api_key:
            raise ValueError("Google Vision API key not provided")
        
        self.client = vision.ImageAnnotatorClient()
        self.logger.info("Google Vision OCR client initialized")

    def _setup_azure_vision(self) -> None:
        if not AZURE_VISION_AVAILABLE:
            raise ImportError("Azure Computer Vision library not available")
        
        endpoint = self.config.get('AZURE_VISION_ENDPOINT')
        key = self.config.get('AZURE_VISION_KEY')
        
        if not endpoint or not key:
            raise ValueError("Azure Vision endpoint or key not provided")
        
        self.client = ComputerVisionClient(endpoint, CognitiveServicesCredentials(key))
        self.logger.info("Azure Vision OCR client initialized")

    def extract_text_from_pdf(self, pdf_path: Path) -> Optional[str]:
        for attempt in range(self.retry_count):
            try:
                self.logger.info(f"Extracting text from PDF (attempt {attempt + 1}): {pdf_path}")
                
                if self.api_type == 'custom_api':
                    return self._extract_text_custom_api(pdf_path)
                elif self.api_type == 'google_vision':
                    return self._extract_text_google_vision(pdf_path)
                elif self.api_type == 'azure_vision':
                    return self._extract_text_azure_vision(pdf_path)
                    
            except Exception as e:
                self.logger.warning(f"OCR attempt {attempt + 1} failed: {str(e)}")
                if attempt < self.retry_count - 1:
                    time.sleep(self.retry_delay * (2 ** attempt))
                else:
                    self.logger.error(f"All OCR attempts failed for {pdf_path}")
                    
        return None

    def _extract_text_custom_api(self, pdf_path: Path) -> Optional[str]:
        temp_file = self._upload_pdf(pdf_path)
        if not temp_file:
            return None
            
        return self._fetch_ocr_result(temp_file)

    def _upload_pdf(self, pdf_path: Path) -> Optional[str]:
        try:
            upload_url = f"{self.api_base_url}/upload"
            
            with open(pdf_path, 'rb') as pdf_file:
                files = {
                    'file': (pdf_path.name, pdf_file, 'application/pdf')
                }
                data = {
                    'email': self.email
                }
                
                self.logger.info(f"Uploading {pdf_path.name} to OCR API...")
                
                response = requests.post(upload_url, files=files, data=data, timeout=30)
                
                if response.status_code == 200:
                    response_data = response.json()
                    temp_file = response_data.get('tempfile')
                    if temp_file:
                        self.logger.info(f"Upload successful. Temp file: {temp_file}")
                        return temp_file
                    else:
                        self.logger.error("Upload response missing tempfile")
                        return None
                else:
                    self.logger.error(f"Upload failed. Status: {response.status_code}, Body: {response.text}")
                    return None
                    
        except Exception as e:
            self.logger.error(f"Upload exception: {str(e)}")
            return None

    def _fetch_ocr_result(self, temp_file: str) -> Optional[str]:
        result_url = f"{self.api_base_url}/result"
        
        for attempt in range(self.max_retries):
            try:
                self.logger.info(f"Fetching OCR result for {temp_file} (attempt {attempt + 1})")
                
                response = requests.post(
                    result_url, 
                    data={'tempfile': temp_file}, 
                    timeout=30
                )
                
                if response.status_code == 200:
                    result_text = response.text
                    
                    if result_text == 'working':
                        self.logger.debug(f"OCR still processing, waiting {self.retry_interval} seconds...")
                        time.sleep(self.retry_interval)
                        continue
                    elif result_text == 'false':
                        self.logger.error("File not found on server or already processed")
                        return None
                    else:
                        self.logger.info("OCR result retrieved successfully")
                        return result_text
                else:
                    self.logger.error(f"Failed to fetch result. Status: {response.status_code}")
                    return None
                    
            except Exception as e:
                self.logger.error(f"Fetch result exception: {str(e)}")
                return None
        
        self.logger.error("Timed out waiting for OCR result")
        return None

    def _extract_text_google_vision(self, pdf_path: Path) -> Optional[str]:
        with open(pdf_path, 'rb') as pdf_file:
            content = pdf_file.read()

        image = vision.Image(content=content)
        response = self.client.document_text_detection(image=image)
        
        if response.error.message:
            raise Exception(f"Google Vision API error: {response.error.message}")

        if response.full_text_annotation:
            extracted_text = response.full_text_annotation.text
            confidence = self._calculate_google_confidence(response)
            
            self.logger.info(f"Google Vision extraction completed. Confidence: {confidence:.2f}")
            
            if confidence >= self.confidence_threshold:
                return extracted_text
            else:
                self.logger.warning(f"OCR confidence {confidence:.2f} below threshold {self.confidence_threshold}")
                return extracted_text
        
        return None

    def _extract_text_azure_vision(self, pdf_path: Path) -> Optional[str]:
        with open(pdf_path, 'rb') as pdf_file:
            read_response = self.client.read_in_stream(pdf_file, raw=True)

        operation_location = read_response.headers["Operation-Location"]
        operation_id = operation_location.split("/")[-1]

        while True:
            read_result = self.client.get_read_result(operation_id)
            if read_result.status not in ['notStarted', 'running']:
                break
            time.sleep(1)

        if read_result.status == OperationStatusCodes.succeeded:
            extracted_text = ""
            for text_result in read_result.analyze_result.read_results:
                for line in text_result.lines:
                    extracted_text += line.text + "\n"
            
            self.logger.info("Azure Vision extraction completed")
            return extracted_text.strip()
        else:
            raise Exception(f"Azure Vision OCR failed with status: {read_result.status}")

    def _calculate_google_confidence(self, response) -> float:
        if not response.full_text_annotation or not response.full_text_annotation.pages:
            return 0.0
        
        total_confidence = 0.0
        word_count = 0
        
        for page in response.full_text_annotation.pages:
            for block in page.blocks:
                for paragraph in block.paragraphs:
                    for word in paragraph.words:
                        if hasattr(word, 'confidence'):
                            total_confidence += word.confidence
                            word_count += 1
        
        return total_confidence / word_count if word_count > 0 else 0.0

    def validate_extracted_text(self, text: str) -> Dict[str, Any]:
        if not text or not text.strip():
            return {"is_valid": False, "reason": "Empty text"}
        
        text = text.strip()
        char_count = len(text)
        word_count = len(text.split())
        line_count = len(text.split('\n'))
        
        japanese_char_count = sum(1 for char in text if '\u3040' <= char <= '\u309F' or '\u30A0' <= char <= '\u30FF' or '\u4E00' <= char <= '\u9FAF')
        has_japanese = japanese_char_count > 0
        
        validation_result = {
            "is_valid": True,
            "char_count": char_count,
            "word_count": word_count,
            "line_count": line_count,
            "has_japanese": has_japanese,
            "japanese_ratio": japanese_char_count / char_count if char_count > 0 else 0
        }
        
        if char_count < 5:
            validation_result["is_valid"] = False
            validation_result["reason"] = "Text too short"
        
        return validation_result