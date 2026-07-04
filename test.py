"""Quick PaddleOCR test"""
from paddleocr import PaddleOCR
ocr = PaddleOCR(use_angle_cls=True, lang='en', use_gpu=False, show_log=False)
result = ocr.ocr('uploads/table.pdf', cls=True)
if result and result[0]:
    for line in result[0]:
        print(line[1][0])
