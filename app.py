from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from PIL import Image
import fitz
import shutil
import zipfile
import re
from pathlib import Path

app = FastAPI()

TEMP_DIR = Path(__file__).parent / "temp"
TEMP_DIR.mkdir(parents=True, exist_ok=True)

IMAGE_NAMES = [
    "Carton ID Picture.jpg",
    "Parcel Label Picture.jpg",
    "Damage Picture 1.jpg",
    "Damage Picture 2.jpg"
]

# Coordinates based on rendered page size of 1190 x 1684
CROPS = [
    (447, 267, 1060, 1085),  # Page 1 - Carton ID
    (447, 145, 1060, 962),   # Page 2 - Parcel Label
    (447, 145, 1060, 962),   # Page 3 - Damage Picture 1
    (447, 145, 1060, 962),   # Page 4 - Damage Picture 2
]


def extract_scan_carton_id(doc):
    """
    Extract Scan Carton ID from the text on page 1.
    """

    first_page = doc[0]
    text = first_page.get_text()

    print("PAGE 1 TEXT:")
    print(text)

    match = re.search(
        r"Scan\s+Carton\s+ID\s+([A-Za-z0-9_-]+)",
        text,
        re.IGNORECASE
    )

    if not match:
        return None

    return match.group(1).strip()


@app.post("/process")
async def process_pdf(file: UploadFile = File(...)):

    # -----------------------------------
    # Save uploaded PDF
    # -----------------------------------

    pdf_path = TEMP_DIR / file.filename

    with pdf_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    doc = fitz.open(pdf_path)

    # -----------------------------------
    # Extract the REAL Scan Carton ID
    # -----------------------------------

    scan_carton_id = extract_scan_carton_id(doc)

    if not scan_carton_id:
        doc.close()

        raise HTTPException(
            status_code=422,
            detail="Could not find Scan Carton ID on page 1"
        )

    print(f"SCAN CARTON ID: {scan_carton_id}")

    # -----------------------------------
    # Crop images
    # -----------------------------------

    output_files = []

    for page_index in range(min(len(doc), 4)):

        page = doc[page_index]

        pix = page.get_pixmap(
            matrix=fitz.Matrix(2, 2),
            alpha=False
        )

        full_path = (
            TEMP_DIR /
            f"page_{page_index + 1}.jpg"
        )

        pix.save(full_path)

        image = Image.open(full_path)

        print(
            f"Page {page_index + 1}: "
            f"{image.width} x {image.height}"
        )

        crop_box = CROPS[page_index]

        cropped = image.crop(crop_box)

        output_path = (
            TEMP_DIR /
            IMAGE_NAMES[page_index]
        )

        cropped.save(
            output_path,
            "JPEG",
            quality=95
        )

        output_files.append(output_path)

    doc.close()

    # -----------------------------------
    # Create Scan Carton ID text file
    # -----------------------------------

    carton_id_path = TEMP_DIR / "scan_carton_id.txt"

    carton_id_path.write_text(
        scan_carton_id,
        encoding="utf-8"
    )

    # -----------------------------------
    # Create ZIP
    # -----------------------------------

    zip_path = TEMP_DIR / "images.zip"

    with zipfile.ZipFile(
        zip_path,
        "w",
        zipfile.ZIP_DEFLATED
    ) as zip_file:

        # Add ID
        zip_file.write(
            carton_id_path,
            "scan_carton_id.txt"
        )

        # Add images
        for output_file in output_files:
            zip_file.write(
                output_file,
                output_file.name
            )

    return FileResponse(
        zip_path,
        media_type="application/zip",
        filename="images.zip"
    )