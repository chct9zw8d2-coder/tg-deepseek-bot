import pytesseract
from PIL import Image
import io

def ocr_image_bytes(b):
    img = Image.open(io.BytesIO(b))
    return pytesseract.image_to_string(img, lang="eng+rus")
