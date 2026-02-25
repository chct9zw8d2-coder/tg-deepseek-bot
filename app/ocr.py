import pytesseract
from PIL import Image

def image_to_text(path: str) -> str:
    img = Image.open(path)
    # rus+eng — чтобы и русский и английский нормально
    text = pytesseract.image_to_string(img, lang="rus+eng")
    return (text or "").strip()
