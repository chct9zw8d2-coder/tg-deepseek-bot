from __future__ import annotations
from PIL import Image, ImageOps
import pytesseract
import io

def extract_text(image_bytes: bytes) -> str:
    # Basic robust preprocessing for homework photos
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    img = ImageOps.exif_transpose(img)
    # enlarge
    img = img.resize((int(img.width * 1.6), int(img.height * 1.6)))
    # grayscale + autocontrast
    img = ImageOps.grayscale(img)
    img = ImageOps.autocontrast(img)
    # binarize
    img = img.point(lambda x: 0 if x < 165 else 255, mode="1")

    # OCR config: mixed rus+eng, treat as a block of text
    txt = pytesseract.image_to_string(img, lang="rus+eng", config="--oem 1 --psm 6")
    txt = txt.strip()
    # Cleanup common OCR noise
    txt = txt.replace("\x0c", "").strip()
    return txt
