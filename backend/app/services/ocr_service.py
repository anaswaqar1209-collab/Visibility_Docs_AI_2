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

    def _extract_embedded_images_text(self, file_path: str) -> str:
        try:
            doc = fitz.open(file_path)
        except Exception:
            return ""
        tmp_dir = tempfile.mkdtemp(prefix="embimg_")
        img_paths = []
        try:
            for page_idx, page in enumerate(doc):
                img_list = page.get_images(full=True)
                for img_idx, img_info in enumerate(img_list):
                    xref = img_info[0]
                    try:
                        pix = fitz.Pixmap(doc, xref)
                        if pix.n > 4:
                            pix = fitz.Pixmap(fitz.csRGB, pix)
                        out = os.path.join(tmp_dir, f"p{page_idx+1}_i{img_idx+1}.png")
                        pix.save(out)
                        pix = None
                        img_paths.append(out)
                    except Exception:
                        continue
        except Exception:
            doc.close()
            return ""
        doc.close()
        if not img_paths:
            return ""
        ocr = self._get_paddle()
        if ocr is None:
            ocr = self._fresh_paddle()
        if ocr is None:
            return ""
        texts = []
        for img_path in img_paths:
            try:
                result = ocr.ocr(img_path, cls=True)
                if result and result[0]:
                    page_text = []
                    for line in result[0]:
                        txt = line[1][0] if len(line) > 1 and line[1] else ""
                        if txt.strip():
                            page_text.append(txt.strip())
                    if page_text:
                        texts.append("\n".join(page_text))
            except Exception:
                continue
        if texts:
            return "\n\n".join(texts)
        return ""

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
            ext = os.path.splitext(img_path)[1].lower().lstrip(".")
            if ext not in ("jpg", "jpeg", "png", "tiff", "tif", "bmp"):
                texts.append("")
                continue

            b64 = self._image_to_base64(img_path)
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
                    texts.append("")
                    continue

                if result and not result.startswith("[Groq"):
                    texts.append(result)
                else:
                    texts.append("")
                    continue
            except Exception:
                texts.append("")
                continue

        return "\n\n--- Page Break ---\n\n".join(texts)

    def _detect_regions(self, ocr_result: list) -> list[dict]:
        regions = []
        if not ocr_result or not ocr_result[0]:
            return regions
        for line in ocr_result[0]:
            box = line[0]
            text = line[1][0] if len(line) > 1 and line[1] else ""
            conf = line[1][1] if len(line) > 1 and line[1] else 0
            x0 = min(p[0] for p in box)
            y0 = min(p[1] for p in box)
            x1 = max(p[0] for p in box)
            y1 = max(p[1] for p in box)
            regions.append({"x0": x0, "y0": y0, "x1": x1, "y1": y1, "text": text.strip(), "conf": conf})
        return regions

    def _group_regions(self, regions: list[dict], y_gap: int = 15) -> list[list[dict]]:
        if not regions:
            return []
        sorted_reg = sorted(regions, key=lambda r: (r["y0"], r["x0"]))
        groups = [[sorted_reg[0]]]
        for r in sorted_reg[1:]:
            last = groups[-1][-1]
            if abs(r["y0"] - last["y1"]) <= y_gap and abs(r["x0"] - last["x0"]) <= 50:
                groups[-1].append(r)
            else:
                groups.append([r])
        return groups

    def _paddle_ocr(self, image_paths: list[str]) -> str:
        texts = []
        errors = []
        ocr = self._get_paddle()
        if ocr is None:
            # Fall back to fresh instance if singleton corrupted
            ocr = self._fresh_paddle()
            if ocr is None:
                return ""

        for img_path in image_paths:
            try:
                result = ocr.ocr(img_path, cls=True)
                if result and result[0]:
                    regions = self._detect_regions(result)
                    groups = self._group_regions(regions)
                    page_text = []
                    for group in groups:
                        line_text = " ".join(r["text"] for r in group if r["text"])
                        if line_text:
                            page_text.append(line_text)
                    texts.append("\n".join(page_text))
                else:
                    texts.append("")
            except Exception as e:
                err = str(e)
                if "state corruption" in err.lower() or "cudnn" in err.lower():
                    logger.warning(f"PaddleOCR state corruption on {img_path}, creating fresh instance")
                    ocr = self._fresh_paddle()
                    if ocr:
                        try:
                            result = ocr.ocr(img_path, cls=True)
                            if result and result[0]:
                                regions = self._detect_regions(result)
                                groups = self._group_regions(regions)
                                page_text = []
                                for group in groups:
                                    line_text = " ".join(r["text"] for r in group if r["text"])
                                    if line_text:
                                        page_text.append(line_text)
                                texts.append("\n".join(page_text))
                                continue
                        except Exception:
                            pass
                logger.error(f"PaddleOCR error on {img_path}: {err}")
                errors.append(err)
                texts.append("")

        if errors:
            logger.warning(f"PaddleOCR had {len(errors)}/{len(image_paths)} page errors")

        result = "\n\n--- Page Break ---\n\n".join(texts)
        # If all failed, fall back to direct text
        if not result.strip():
            try:
                import fitz
                doc = fitz.open(image_paths[0].rsplit("_", 1)[0] + ".pdf" if "_" in image_paths[0] else image_paths[0])
                direct = ""
                for page in doc:
                    direct += page.get_text()
                doc.close()
                if direct.strip():
                    return direct
            except Exception:
                pass
        return result

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

        if ext == ".pdf":
            direct_text, page_count = self._extract_pymupdf_text(file_path)
            print(f"[OCR] PyMuPDF text extraction: {len(direct_text)} chars, {page_count} pages")
            # Extract text from embedded images
            t0 = __import__("time").time()
            embedded_text = self._extract_embedded_images_text(file_path)
            if embedded_text:
                print(f"[OCR] Embedded images OCR: {len(embedded_text)} chars in {__import__('time').time()-t0:.1f}s")
                direct_text = direct_text + "\n\n[Embedded Images]\n" + embedded_text
            if self._is_text_sufficient(direct_text, page_count):
                print(f"[OCR] Direct text + embedded images is sufficient ({len(direct_text.strip())//max(page_count,1)} chars/page > 50) - skipping full page OCR")
                return {"text": direct_text, "page_count": page_count, "images": [], "source": "direct"}
            print(f"[OCR] Direct text insufficient ({len(direct_text.strip())//max(page_count,1)} chars/page <= 50) - falling back to full page image OCR")

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
