import re
from io import BytesIO
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
import pytesseract


def _clean(text: str) -> str:
    text = text.replace("\x0c", " ")
    text = text.replace("“", '"').replace("”", '"').replace("«", '"').replace("»", '"')

    # убрать мусор, который ломает вид
    text = text.replace("\\[", "").replace("\\]", "")
    text = text.replace("\\(", "").replace("\\)", "")
    text = text.replace("\\", "")

    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _score(text: str) -> int:
    """Эвристика качества OCR: больше цифр/мат.символов/букв — лучше, меньше мусора — лучше."""
    if not text:
        return -999
    good = len(re.findall(r"[0-9xXyYzZ=+\-*/^().,]", text))
    letters = len(re.findall(r"[A-Za-zА-Яа-я]", text))
    bad = len(re.findall(r"[{}[\]|~`<>]", text))
    return good + letters - 3 * bad


def _autocrop(img: Image.Image) -> Image.Image:
    """
    Обрезаем поля вокруг текста:
    1) в серый
    2) инвертируем
    3) bbox по "небелому"
    """
    gray = img.convert("L")
    inv = ImageOps.invert(gray)
    bbox = inv.getbbox()
    if not bbox:
        return img

    # padding вокруг текста (чтобы не срезать символы)
    pad = 20
    x0, y0, x1, y1 = bbox
    x0 = max(0, x0 - pad)
    y0 = max(0, y0 - pad)
    x1 = min(img.size[0], x1 + pad)
    y1 = min(img.size[1], y1 + pad)
    return img.crop((x0, y0, x1, y1))


def _prep(img: Image.Image, thr: int) -> Image.Image:
    img = img.convert("L")

    # увеличить (OCR любит крупнее)
    w, h = img.size
    img = img.resize((w * 2, h * 2))

    # контраст + резкость
    img = ImageEnhance.Contrast(img).enhance(2.4)
    img = img.filter(ImageFilter.SHARPEN)

    # бинаризация
    img = img.point(lambda x: 0 if x < thr else 255, "1")
    return img.convert("L")


def _ocr_once(img: Image.Image, psm: int, thr: int) -> str:
    prepared = _prep(img, thr)
    config = f"--oem 3 --psm {psm}"
    raw = pytesseract.image_to_string(prepared, lang="rus+eng", config=config)
    return _clean(raw)


def ocr_image(image_bytes: bytes) -> str:
    img0 = Image.open(BytesIO(image_bytes)).convert("RGB")

    # 1) Автокроп (убираем поля)
    img0 = _autocrop(img0)

    # 2) Автоповорот: перебираем небольшие углы и выбираем лучший OCR-скор
    # (Это и есть лёгкий deskew без OpenCV)
    angles = [-6, -4, -2, 0, 2, 4, 6]
    psms = [6, 4, 11]         # 6 — блок текста, 4 — колонки, 11 — разреженный текст
    thrs = [140, 160, 180]    # разные пороги бинаризации

    best_text = ""
    best_score = -10**9

    for ang in angles:
        # fill белым, чтобы не было чёрных углов
        rotated = img0.rotate(ang, expand=True, fillcolor=(255, 255, 255))
        rotated = _autocrop(rotated)  # ещё раз обрежем после поворота

        for psm in psms:
            for thr in thrs:
                txt = _ocr_once(rotated, psm=psm, thr=thr)
                sc = _score(txt)
                if sc > best_score:
                    best_score = sc
                    best_text = txt

    return best_text
