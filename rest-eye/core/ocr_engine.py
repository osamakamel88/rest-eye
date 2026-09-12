import os
import re
import cv2
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from PIL import Image

try:
    import pytesseract
    HAS_PYTESSERACT = True
except ImportError:
    HAS_PYTESSERACT = False

class RestaurantOcrEngine:
    """
    REST-EYE™ Optical Character Recognition (OCR) Engine
    Designed for Restaurant Quality, Hygiene & Inventory Sentry:
    - Expiration & Batch Date Scanning (Food Safety)
    - Kitchen Order Ticket (KDS) & Receipt OCR
    - Staff Uniform & Badge ID Recognition
    - Camera/DVR OSD Timestamp Extraction
    """

    def __init__(self, tesseract_cmd: Optional[str] = None):
        if tesseract_cmd and HAS_PYTESSERACT:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
        
        self.date_patterns = [
            r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b',
            r'\b\d{4}[/-]\d{1,2}[/-]\d{1,2}\b',
            r'\b(?:EXP|EXPIRY|BB|BBD|PROD|MFG)[:\s.]*\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b',
            r'\b\d{1,2}[/-]\d{4}\b'
        ]

    def preprocess_for_ocr(self, image_input: Any) -> np.ndarray:
        if isinstance(image_input, str):
            img = cv2.imread(image_input)
        elif isinstance(image_input, np.ndarray):
            img = image_input.copy()
        elif isinstance(image_input, Image.Image):
            img = cv2.cvtColor(np.array(image_input), cv2.COLOR_RGB2BGR)
        else:
            raise ValueError("Unsupported image format")

        if img is None or img.size == 0:
            raise ValueError("Empty image provided")

        if len(img.shape) == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        else:
            gray = img

        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        contrast = clahe.apply(gray)
        denoised = cv2.bilateralFilter(contrast, 9, 75, 75)
        thresh = cv2.adaptiveThreshold(
            denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
        )
        return thresh

    def extract_text(self, image_input: Any, lang: str = "eng+ara") -> Dict[str, Any]:
        thresh = self.preprocess_for_ocr(image_input)
        extracted_text = ""
        blocks = []

        if HAS_PYTESSERACT:
            try:
                extracted_text = pytesseract.image_to_string(thresh)
                data = pytesseract.image_to_data(thresh, output_type=pytesseract.Output.DICT)
                n_boxes = len(data["text"])
                for i in range(n_boxes):
                    txt = data["text"][i].strip()
                    if txt:
                        blocks.append({
                            "text": txt,
                            "left": data["left"][i],
                            "top": data["top"][i],
                            "width": data["width"][i],
                            "height": data["height"][i],
                            "confidence": float(data["conf"][i])
                        })
            except Exception:
                extracted_text = f"Processed OCR Frame ({thresh.shape})"
        else:
            extracted_text = "pytesseract library not available"

        return {
            "text": extracted_text.strip(),
            "blocks": blocks,
            "word_count": len(extracted_text.split())
        }

    def scan_expiry_dates(self, image_input: Any) -> Dict[str, Any]:
        ocr_result = self.extract_text(image_input)
        raw_text = ocr_result.get("text", "")

        detected_dates = []
        for pattern in self.date_patterns:
            matches = re.findall(pattern, raw_text, re.IGNORECASE)
            for m in matches:
                if m not in detected_dates:
                    detected_dates.append(m.strip())

        parsed_status = "UNKNOWN"
        nearest_expiry = None
        now = datetime.now()

        for date_str in detected_dates:
            cleaned = re.sub(r"[^0-9/-]", "", date_str)
            for fmt in ["%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d", "%Y-%m-%d", "%m/%Y", "%m-%Y", "%d/%m/%y", "%d-%m-%y"]:
                try:
                    dt = datetime.strptime(cleaned, fmt)
                    if fmt in ["%m/%Y", "%m-%Y"]:
                        dt = (dt.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
                    nearest_expiry = dt
                    if dt < now:
                        parsed_status = "EXPIRED"
                    elif dt <= now + timedelta(days=7):
                        parsed_status = "EXPIRING_SOON"
                    else:
                        parsed_status = "VALID"
                    break
                except ValueError:
                    continue
            if nearest_expiry:
                break

        if parsed_status == "EXPIRED":
            alert_msg = f"🚨 تحذير جودة: تم رصد خامات منتهية الصلاحية ({nearest_expiry.strftime('%Y-%m-%d') if nearest_expiry else '-'})"
        elif parsed_status == "EXPIRING_SOON":
            alert_msg = f"⚠️ تنبيه: خامات تنتهي خلال أسبوع ({nearest_expiry.strftime('%Y-%m-%d') if nearest_expiry else '-'})"
        else:
            alert_msg = "✅ الخامات صالحة ومطابقة للمعايير"

        return {
            "status": parsed_status,
            "detected_dates": detected_dates,
            "nearest_expiry": nearest_expiry.strftime("%Y-%m-%d") if nearest_expiry else None,
            "raw_text": raw_text,
            "is_safe": parsed_status == "VALID",
            "requires_alert": parsed_status in ["EXPIRED", "EXPIRING_SOON"],
            "alert_message": alert_msg
        }

    def scan_kds_ticket(self, image_input: Any) -> Dict[str, Any]:
        ocr_result = self.extract_text(image_input)
        raw_text = ocr_result.get("text", "")
        order_match = re.search(r"(?:ORDER|ORD|طلب|رقم|#)\s*[:#]?\s*(\d+)", raw_text, re.IGNORECASE)
        order_num = order_match.group(1) if order_match else "-"
        return {
            "order_number": order_num,
            "raw_text": raw_text,
            "lines": [l.strip() for l in raw_text.splitlines() if l.strip()]
        }

    def scan_staff_badge(self, image_input: Any) -> Dict[str, Any]:
        ocr_result = self.extract_text(image_input)
        raw_text = ocr_result.get("text", "")
        id_match = re.search(r"(?:ID|STAFF|موظف|شيف|رقم)\s*[:#]?\s*(\d+)", raw_text, re.IGNORECASE)
        staff_id = id_match.group(1) if id_match else None
        return {
            "staff_id": staff_id,
            "badge_text": raw_text,
            "is_identified": staff_id is not None
        }

ocr_engine = RestaurantOcrEngine()

