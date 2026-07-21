import sys
from PIL import Image

print("=" * 60)
print("STEP 1: Can we even open the image?")
print("=" * 60)

# CHANGE THIS to the actual path of an image you uploaded to test with
IMAGE_PATH = r"C:\Users\kit23\OneDrive\Desktop\idcard.jpeg"

try:
    image = Image.open(IMAGE_PATH)
    print("Image opened OK. Size:", image.size, "Mode:", image.mode)
except Exception as e:
    print("FAILED to open image:", repr(e))
    sys.exit(1)

print()
print("=" * 60)
print("STEP 2: Is easyocr installed and can it load the model?")
print("=" * 60)

try:
    import easyocr
    print("easyocr import OK")
except Exception as e:
    print("easyocr is NOT installed or failed to import:", repr(e))
    easyocr = None

if easyocr:
    try:
        reader = easyocr.Reader(['en', 'ta'], gpu=False)
        print("easyocr.Reader loaded OK (this means model files downloaded fine)")
    except Exception as e:
        print("FAILED to create easyocr.Reader:", repr(e))
        reader = None

    if reader:
        import numpy as np
        image_np = np.array(image.convert("RGB"))
        try:
            result = reader.readtext(image_np)
            print("easyocr.readtext() returned", len(result), "text regions")
            for (_, text, conf) in result[:10]:
                print(f"  - '{text}' (confidence {conf:.2f})")
        except Exception as e:
            print("FAILED during readtext():", repr(e))

print()
print("=" * 60)
print("STEP 3: Is Tesseract installed as a fallback?")
print("=" * 60)

try:
    import pytesseract
    print("pytesseract import OK")
    try:
        version = pytesseract.get_tesseract_version()
        print("Tesseract binary found. Version:", version)
    except Exception as e:
        print("FAILED: pytesseract can't find the Tesseract binary itself.")
        print("This usually means Tesseract-OCR isn't installed at the OS level,")
        print("or it's not on your system PATH.")
        print("Error:", repr(e))
    try:
        langs = pytesseract.get_languages()
        print("Installed Tesseract language packs:", langs)
        if "tam" not in langs:
            print("WARNING: Tamil ('tam') language pack is NOT installed.")
    except Exception as e:
        print("Could not list language packs:", repr(e))
except Exception as e:
    print("pytesseract is NOT installed:", repr(e))
