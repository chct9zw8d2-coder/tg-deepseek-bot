import re
from PIL import Image, ImageEnhance, ImageFilter
import pytesseract

def _preprocess(img: Image.Image) -> Image.Image:
    # grayscale
    img = img.convert("L")

    # увеличить изображение (OCR любит крупнее)
    w, h = img.size
    img = img.resize((w * 2, h * 2))

    # контраст + резкость
    img = ImageEnhance.Contrast(img).enhance(2.2)
    img = img.filter(ImageFilter.SHARPEN)

    # простая бинаризация
    img = img.point(lambda x: 0 if x < 160 else 255, "1")
    return img.convert("L")

def _clean_ocr_text(text: str) -> str:
    text = text.replace("\x0c", " ")
    text = text.replace("“", '"').replace("”", '"').replace("«", '"').replace("»", '"')
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    # убрать мусорные слеши/латех-скобки, которые портят вид
    text = text.replace("\\[", "").replace("\\]", "")
    text = text.replace("\\(", "").replace("\\)", "")
    text = text.replace("\\", "")
    return text.strip()

def ocr_image(image_bytes: bytes) -> str:
    img = Image.open(__import__("io").BytesIO(image_bytes))
    img = _preprocess(img)

    config = r"--oem 3 --psm 6"
    raw = pytesseract.image_to_string(img, lang="rus+eng", config=config)

    return _clean_ocr_text(raw)
