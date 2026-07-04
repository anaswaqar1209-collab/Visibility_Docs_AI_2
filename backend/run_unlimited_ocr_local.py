import argparse
import os
import sys


def main():
    parser = argparse.ArgumentParser(description="Run PaddleOCR on a PDF or image.")
    parser.add_argument("input_path", help="Path to a PDF or image file")
    parser.add_argument(
        "--output",
        default="",
        help="Optional path to write extracted text to a file",
    )
    args = parser.parse_args()

    backend_dir = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, backend_dir)

    from app.services.ocr_service import ocr_service

    input_path = os.path.abspath(args.input_path)

    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input file not found: {input_path}")

    result = ocr_service.process_document(input_path)
    text = result.get("text", "")

    if not text.strip():
        raise RuntimeError("OCR returned empty text.")

    print(text)

    if args.output:
        output_path = os.path.abspath(args.output)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"\nSaved to: {output_path}")


if __name__ == "__main__":
    main()
