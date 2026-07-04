import os
import base64
import tempfile
import logging
import fitz
from PIL import Image
from ..config import settings

logger = logging.getLogger("visibility-docs")


class OCRService:
    def __init__(self):
        self._paddle = None
        self._lock = __import__("threading").Lock()
        self.use_gpu = settings.USE_GPU
        self._warmed = False

    def _get_paddle(self):
        if self._paddle is None:
            with self._lock:
                if self._paddle is None:
                    try:
                        from paddleocr import PaddleOCR
                        self._paddle = PaddleOCR(use_angle_cls=True, lang='en', use_gpu=self.use_gpu, show_log=False)
                        logger.info("PaddleOCR initialized")
                    except Exception as e:
                        logger.error(f"PaddleOCR init failed: {e}")
                        return None
        return self._paddle

    def _fresh_paddle(self):
        try:
            from paddleocr import PaddleOCR
            ocr = PaddleOCR(use_angle_cls=True, lang='en', use_gpu=self.use_gpu, show_log=False)
            logger.info("Fresh PaddleOCR instance created")
            return ocr
        except Exception as e:
            logger.error(f"Fresh PaddleOCR init failed: {e}")
            return None

    def warm(self):
        """Pre-warm PaddleOCR on startup so first doc inference is fast (avoids HTTP timeout)."""
        logger.info("Pre-warming PaddleOCR (JIT compilation may take a minute)...")
        import numpy as np
        ocr = self._get_paddle()
        if ocr:
            try:
                dummy = np.zeros((100, 300, 3), dtype=np.uint8)
                ocr.ocr(dummy, cls=True)
                logger.info("PaddleOCR warm-up complete")
            except Exception as e:
                logger.warning(f"PaddleOCR warm-up failed (non-fatal): {e}")

    def pdf_to_images(self, pdf_path: str, dpi: int = 150) -> list[str]:
        doc = fitz.open(pdf_path)
        tmp_dir = tempfile.mkdtemp(prefix="ocr_")
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        paths = []
        for i, page in enumerate(doc):
            out = os.path.join(tmp_dir, f"page_{i+1:04d}.png")
            pix = page.get_pixmap(matrix=mat)
            pix.save(out)
            paths.append(out)
        doc.close()
        return paths

    def _extract_pymupdf_text(self, file_path: str) -> tuple[str, int]:
        try:
            doc = fitz.open(file_path)
            page_count = doc.page_count
            text = ""
            for page in doc:
                text += page.get_text()
            doc.close()
            return text, page_count
        except Exception:
            return "", 0

    def _is_text_sufficient(self, text: str, page_count: int) -> bool:
        if page_count == 0:
            return False
        return len(text.strip()) / page_count > 50

    def _image_to_base64(self, image_path: str) -> str:
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    def _groq_ocr(self, image_paths: list[str]) -> str:
        from .groq_service import groq_service

        if not groq_service.available:
            return ""

        texts = []
        for img_path in image_paths:
            b64 = self._image_to_base64(img_path)
            ext = os.path.splitext(img_path)[1].lower().lstrip(".")
            mime = "image/jpeg" if ext in ("jpg", "jpeg") else f"image/{ext}"

            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Extract ALL text from this document image exactly as it appears. Return the complete text content."},
                        {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                    ],
                }
            ]

            try:
                result = groq_service.chat_vision(messages, temperature=0.05, max_tokens=4096)

                if ("does not support image" in result.lower() or
                    "cannot read" in result.lower() or
                    "not configured" in result.lower()):
                    return ""

                if result and not result.startswith("[Groq"):
                    texts.append(result)
                else:
                    return ""
            except Exception:
                return ""

        return "\n\n--- Page Break ---\n\n".join(texts)

    def _paddle_ocr(self, image_paths: list[str]) -> str:
        texts = []
        errors = []
        # Use a fresh PaddleOCR instance each time to avoid state corruption
        ocr = self._fresh_paddle()
        if ocr is None:
            return ""

        for img_path in image_paths:
            try:
                result = ocr.ocr(img_path, cls=True)
                if result and result[0]:
                    page_text = []
                    for line in result[0]:
                        text = line[1][0] if len(line) > 1 and line[1] else ""
                        if text.strip():
                            page_text.append(text.strip())
                    texts.append("\n".join(page_text))
                else:
                    texts.append("")
            except Exception as e:
                err = str(e)
                logger.error(f"PaddleOCR error on {img_path}: {err}")
                errors.append(err)
                texts.append("")

        if errors:
            # Log summary but continue with whatever text we got
            logger.warning(f"PaddleOCR had {len(errors)}/{len(image_paths)} page errors")

        return "\n\n--- Page Break ---\n\n".join(texts)

    def _tesseract_ocr(self, image_paths: list[str]) -> str:
        import pytesseract
        texts = []
        for img_path in image_paths:
            try:
                img = Image.open(img_path)
                text = pytesseract.image_to_string(img)
                texts.append(text)
            except Exception:
                texts.append("")
        return "\n\n--- Page Break ---\n\n".join(texts)

    def process_document(self, file_path: str) -> dict:
        print(f"\n[OCR] Processing document: {file_path}")
        ext = os.path.splitext(file_path)[1].lower()

        # Fast path: try direct text extraction for PDFs
        if ext == ".pdf":
            direct_text, page_count = self._extract_pymupdf_text(file_path)
            print(f"[OCR] PyMuPDF text extraction: {len(direct_text)} chars, {page_count} pages")
            if self._is_text_sufficient(direct_text, page_count):
                print(f"[OCR] Direct text is sufficient ({len(direct_text.strip())//max(page_count,1)} chars/page > 50) - skipping OCR")
                return {"text": direct_text, "page_count": page_count, "images": [], "source": "direct"}
            print(f"[OCR] Direct text insufficient ({len(direct_text.strip())//max(page_count,1)} chars/page <= 50) - falling back to image OCR")

        print(f"[OCR] Converting to images...")
        if ext == ".pdf":
            image_paths = self.pdf_to_images(file_path)
        elif ext in (".jpg", ".jpeg", ".png", ".tiff", ".tif"):
            image_paths = [file_path]
        else:
            raise ValueError(f"Unsupported file type: {ext}")
        print(f"[OCR] Generated {len(image_paths)} page images")

        text = ""
        print(f"[OCR] Running PaddleOCR...")
        if image_paths:
            t0 = __import__("time").time()
            text = self._paddle_ocr(image_paths)
            print(f"[OCR] PaddleOCR done: {len(text)} chars in {__import__('time').time()-t0:.1f}s")

        if not text.strip():
            print(f"[OCR] PaddleOCR empty, trying Groq vision...")
            t0 = __import__("time").time()
            text = self._groq_ocr(image_paths)
            print(f"[OCR] Groq OCR done: {len(text)} chars in {__import__('time').time()-t0:.1f}s")

        if not text.strip():
            print(f"[OCR] Groq empty, trying Tesseract...")
            t0 = __import__("time").time()
            text = self._tesseract_ocr(image_paths)
            print(f"[OCR] Tesseract done: {len(text)} chars in {__import__('time').time()-t0:.1f}s")

        if not text.strip():
            text = "[OCR failed - no text could be extracted from this document]"
            print(f"[OCR] ALL OCR METHODS FAILED")

        print(f"[OCR] Done: {len(text)} chars, {len(image_paths)} pages")
        return {"text": text, "page_count": len(image_paths), "images": image_paths}


ocr_service = OCRService()
