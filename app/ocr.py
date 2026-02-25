import re
from io import BytesIO
from PIL import Image, ImageEnhance, ImageFilter
import pytesseract


def _prep(img: Image.Image, thr: int) -> Image.Image:
    img = img.convert("L")
    w, h = img.size
    img = img.resize((w * 2, h * 2))

    img = ImageEnhance.Contrast(img).enhance(2.4)
    img = img.filter(ImageFilter.SHARPEN)

    # бинаризация
    img = img.point(lambda x: 0 if x < thr else 255, "1")
    return img.convert("L")


def _clean(text: str) -> str:
    text = text.replace("\x0c", " ")
    text = text.replace("“", '"').replace("”", '"').replace("«", '"').replace("»", '"')

    # уберём совсем мусор
    text = text.replace("\\[", "").replace("\\]", "")
    text = text.replace("\\(", "").replace("\\)", "")
    text = text.replace("\\", "")

    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def _score(text: str) -> int:
    """
    Простая эвристика:
    - больше цифр/мат.символов -> лучше
    - меньше странных символов -> лучше
    """
    if not text:
        return -999

    good = len(re.findall(r"[0-9xXyY=+\-*/^().]", text))
    bad = len(re.findall(r"[{}[\]|~`]", text))
    letters = len(re.findall(r"[A-Za-zА-Яа-я]", text))
    return good + letters - 3 * bad


def ocr_image(image_bytes: bytes) -> str:
    img0 = Image.open(BytesIO(image_bytes))

    # пробуем разные режимы разметки + разные пороги
    candidates = []
    for psm in (6, 4, 11):
        for thr in (140, 160, 180):
            img = _prep(img0, thr)
            config = f"--oem 3 --psm {psm}"
            raw = pytesseract.image_to_string(img, lang="rus+eng", config=config)
            cleaned = _clean(raw)
            candidates.append((cleaned, _score(cleaned)))

    # лучший по скору
    candidates.sort(key=lambda x: x[1], reverse=True)
    best = candidates[0][0] if candidates else ""
    return best
