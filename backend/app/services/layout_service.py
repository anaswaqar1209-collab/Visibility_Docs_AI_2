import json
import logging
from PIL import Image

logger = logging.getLogger("visibility-docs")


class LayoutService:
    def detect_regions(self, image_path: str) -> list[dict]:
        try:
            import cv2
            import numpy as np
            img = cv2.imread(image_path)
            if img is None:
                return []
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
            dilated = cv2.dilate(binary, kernel, iterations=3)

            contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            regions = []
            for i, cnt in enumerate(contours):
                x, y, w, h = cv2.boundingRect(cnt)
                area = w * h
                img_area = img.shape[0] * img.shape[1]
                if area < img_area * 0.005 or area > img_area * 0.95:
                    continue
                roi = gray[y:y + h, x:x + w]
                text_density = cv2.countNonZero(cv2.threshold(roi, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]) / (w * h) if w * h > 0 else 0
                region_type = self._classify_region(x, y, w, h, img.shape[1], img.shape[0], text_density)
                regions.append({
                    "region_id": i,
                    "type": region_type,
                    "bbox": {"x": int(x), "y": int(y), "width": int(w), "height": int(h)},
                    "text_density": round(float(text_density), 3),
                    "area_ratio": round(area / img_area, 4),
                })
            regions.sort(key=lambda r: (r["bbox"]["y"], r["bbox"]["x"]))
            return regions
        except ImportError:
            logger.warning("OpenCV not available for layout detection")
            return []
        except Exception as e:
            logger.error(f"Layout detection error: {e}")
            return []

    def _classify_region(self, x: int, y: int, w: int, h: int, img_w: int, img_h: int, density: float) -> str:
        aspect = w / h if h > 0 else 0
        y_ratio = y / img_h if img_h > 0 else 0

        if y_ratio < 0.08 and h < img_h * 0.15:
            return "header"
        if y_ratio > 0.85 and h < img_h * 0.12:
            return "footer"
        if aspect > 3 and h < img_h * 0.1:
            return "separator"
        if aspect > 1.5 and density > 0.3:
            return "table"
        if density > 0.15:
            return "text_block"
        if aspect > 2 and w < img_w * 0.5:
            return "sidebar"
        return "figure"

    def extract_tables(self, image_path: str) -> list[list[list[str]]]:
        try:
            import cv2
            import numpy as np
            img = cv2.imread(image_path)
            if img is None:
                return []
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            _, binary = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY_INV)

            horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (40, 1))
            horizontal_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, horizontal_kernel)

            vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 40))
            vertical_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, vertical_kernel)

            table_structure = cv2.add(horizontal_lines, vertical_lines)
            contours, _ = cv2.findContours(table_structure, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            cells = []
            for cnt in contours:
                x, y, w, h = cv2.boundingRect(cnt)
                area = w * h
                if area > 500 and w > 20 and h > 20:
                    cells.append((x, y, w, h))

            if not cells:
                return []

            cells.sort(key=lambda c: (c[1], c[0]))
            rows = {}
            for cell in cells:
                x, y, w, h = cell
                row_key = y // (h if h > 0 else 10)
                if row_key not in rows:
                    rows[row_key] = []
                rows[row_key].append(cell)

            table = []
            for row_key in sorted(rows.keys()):
                row_cells = sorted(rows[row_key], key=lambda c: c[0])
                row_data = []
                for cell in row_cells:
                    x, y, w, h = cell
                    cell_img = gray[y:y + h, x:x + w]
                    try:
                        import pytesseract
                        text = pytesseract.image_to_string(cell_img, config='--psm 6').strip()
                    except Exception:
                        text = ""
                    row_data.append(text)
                if any(c.strip() for c in row_data):
                    table.append(row_data)

            return table
        except ImportError:
            return []
        except Exception as e:
            logger.error(f"Table extraction error: {e}")
            return []

    def analyze_layout(self, image_path: str) -> dict:
        regions = self.detect_regions(image_path)
        tables = self.extract_tables(image_path)

        text_regions = [r for r in regions if r["type"] == "text_block"]
        table_regions = [r for r in regions if r["type"] == "table"]
        reading_order = [r for r in regions if r["type"] in ("header", "text_block", "table", "footer")]

        return {
            "regions": regions,
            "tables": tables,
            "text_region_count": len(text_regions),
            "table_region_count": len(table_regions),
            "has_header": any(r["type"] == "header" for r in regions),
            "has_footer": any(r["type"] == "footer" for r in regions),
            "reading_order": [r["region_id"] for r in reading_order],
        }


layout_service = LayoutService()
