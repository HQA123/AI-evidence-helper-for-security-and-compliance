import os
import logging
from typing import List, Optional

# try to import pymupdf (fitz)
try:
    import fitz  # PyMuPDF
except Exception:  # pragma: no cover
    fitz = None

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')


def pdf_to_png_file(pdf_path: str, dst_dir: Optional[str] = None, dpi: int = 300, sharpen: bool = True) -> List[str]:
    """Convert a single PDF file to PNG(s).

    Args:
      pdf_path: path to the input PDF file.
      dst_dir: destination directory for PNG files. If None, uses the PDF's directory.
      dpi: render DPI (default 300 for higher-quality output).
      sharpen: whether to apply a Pillow UnsharpMask post-process (default True).

    Returns:
      List of absolute paths to the generated PNG files (one per page).

    Raises:
      FileNotFoundError: if pdf_path does not exist.
      ValueError: if pdf_path does not appear to be a PDF file.
      RuntimeError: for other processing errors.

    Requirements:
      pip install pymupdf Pillow
    """
    if not pdf_path:
        raise ValueError("pdf_path must be provided")

    if not os.path.isfile(pdf_path):
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    if not pdf_path.lower().endswith('.pdf'):
        raise ValueError(f"Input file does not have a .pdf extension: {pdf_path}")

    if fitz is None:
        raise RuntimeError("PyMuPDF (fitz) is not installed. Please install pymupdf")

    # Determine destination dir
    if dst_dir is None:
        dst_dir = os.path.dirname(os.path.abspath(pdf_path)) or os.getcwd()
    else:
        if not os.path.isabs(dst_dir):
            # resolve relative to project root
            base = os.path.dirname(os.path.dirname(__file__))
            dst_dir = os.path.join(base, dst_dir)
    os.makedirs(dst_dir, exist_ok=True)

    outputs: List[str] = []

    name = os.path.splitext(os.path.basename(pdf_path))[0]
    mat = fitz.Matrix(dpi / 72.0, dpi / 72.0)

    with fitz.open(pdf_path) as doc:
        for i in range(doc.page_count):
            page = doc.load_page(i)
            page_number = i + 1
            pix = page.get_pixmap(matrix=mat, alpha=False)
            out_name = f"{name}_page_{page_number}.png"
            out_path = os.path.join(dst_dir, out_name)
            try:
                pix.save(out_path)
            except Exception as e:
                raise RuntimeError(f"Failed to save PNG for {pdf_path} page {page_number}: {e}")

            # Optional Pillow post-process sharpening
            if sharpen:
                try:
                    from PIL import Image, ImageFilter
                    with Image.open(out_path) as im:
                        im = im.filter(ImageFilter.UnsharpMask(radius=1.5, percent=150, threshold=3))
                        im.save(out_path)
                except Exception as e:
                    # Non-fatal: log and continue
                    logger.warning(f"Warning: failed to post-process PNG {out_name}: {e}")

            outputs.append(os.path.abspath(out_path))

    return outputs


if __name__ == '__main__':
    # CLI to convert a single PDF file
    import argparse
    parser = argparse.ArgumentParser(description='Convert a single PDF to PNG files')
    parser.add_argument('--pdf', required=True, help='Path to the input PDF file')
    parser.add_argument('--out', '-o', default=None, help='Destination directory for PNGs (default: same folder as PDF)')
    parser.add_argument('--dpi', type=int, default=300, help='Render DPI for PNGs (higher = higher quality)')
    parser.add_argument('--no-sharpen', action='store_true', help='Disable Pillow post-processing sharpen step')
    args = parser.parse_args()

    try:
        outputs = pdf_to_png_file(args.pdf, args.out, args.dpi, sharpen=not args.no_sharpen)
        print('Generated files:')
        for p in outputs:
            print(p)
    except Exception as e:
        print(f"Error: {e}")
        raise
