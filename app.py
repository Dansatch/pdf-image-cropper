from fastapi import FastAPI, UploadFile, File
from fastapi.responses import FileResponse
from PIL import Image
import fitz
import shutil
import zipfile
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

# Coordinates based on a rendered page size of 1190 x 1684
CROPS = [
    (447, 267, 1060, 1085),  # Page 1 - Carton ID
    (447, 145, 1060, 962),   # Page 2 - Parcel Label
    (447, 145, 1060, 962),   # Page 3 - Damage 1
    (447, 145, 1060, 962),   # Page 4 - Damage 2
]


@app.post("/process")
async def process_pdf(file: UploadFile = File(...)):

    # Save uploaded PDF
    pdf_path = TEMP_DIR / file.filename

    with pdf_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    doc = fitz.open(pdf_path)

    output_files = []

    for page_index in range(min(len(doc), 4)):

        page = doc[page_index]

        # Render at 2x resolution
        pix = page.get_pixmap(
            matrix=fitz.Matrix(2, 2),
            alpha=False
        )

        # Save temporary full page
        full_path = TEMP_DIR / f"page_{page_index + 1}.jpg"
        pix.save(full_path)

        # Open rendered page
        image = Image.open(full_path)

        print(
            f"Page {page_index + 1}: "
            f"{image.width} x {image.height}"
        )

        # Get crop coordinates
        crop_box = CROPS[page_index]

        # Crop out the PDF template
        cropped = image.crop(crop_box)

        # Save using required name
        output_path = TEMP_DIR / IMAGE_NAMES[page_index]

        cropped.save(
            output_path,
            "JPEG",
            quality=95
        )

        output_files.append(output_path)

    doc.close()

    # Create ZIP
    zip_path = TEMP_DIR / "images.zip"

    with zipfile.ZipFile(
        zip_path,
        "w",
        zipfile.ZIP_DEFLATED
    ) as zip_file:

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