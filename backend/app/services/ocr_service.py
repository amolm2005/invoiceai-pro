"""

OCR service for invoice PDFs/images.



Uses a small Tesseract ensemble instead of relying on one page segmentation

mode. Invoice layouts vary a lot: some are table-like, while others have

small labels and sparse text. Running both normal and sparse-text modes and

merging their output gives the extraction layer more complete OCR text.

"""



import io

import logging

import re

from difflib import SequenceMatcher

from collections import OrderedDict

from typing import Tuple



import pytesseract

from PIL import Image, ImageOps, ImageFilter

from pdf2image import convert_from_bytes



from app.core.config import settings



logger = logging.getLogger(__name__)



_easyocr_reader = None





def _get_easyocr_reader():

    global _easyocr_reader



    if _easyocr_reader is None:

        import easyocr



        _easyocr_reader = easyocr.Reader(

            settings.OCR_LANGUAGES,

            gpu=False,

        )



    return _easyocr_reader





def _preprocess_image(img: Image.Image) -> Image.Image:

    """Create a high-contrast, sharpened grayscale image for OCR."""

    img = img.convert("L")



    # Upscaling helps Tesseract read small invoice labels.

    img = img.resize(

        (img.width * 2, img.height * 2),

        Image.Resampling.LANCZOS,

    )



    img = ImageOps.autocontrast(img)

    img = img.filter(ImageFilter.SHARPEN)



    return img





def _load_pages(file_bytes: bytes, file_ext: str) -> list:
    """Return one PIL image per PDF page, or one image for image uploads."""
    if file_ext.lower() == ".pdf":
        return convert_from_bytes(
            file_bytes,
            dpi=300,
        )

    return [Image.open(io.BytesIO(file_bytes))]





def _ocr_pass(

    img: Image.Image,

    psm: int,

) -> Tuple[str, float]:

    """

    Run one Tesseract pass and reconstruct text by OCR lines.



    Keeping line boundaries is important for invoice fields such as:

    'Invoice Number: ...' and 'Due Date: ...'.

    """

    data = pytesseract.image_to_data(

        img,

        output_type=pytesseract.Output.DICT,

        config=f"--oem 3 --psm {psm}",

    )



    lines = OrderedDict()

    confidences = []



    count = len(data.get("text", []))



    for i in range(count):

        word = (data["text"][i] or "").strip()



        if not word:

            continue



        conf_raw = data["conf"][i]



        try:

            conf = float(conf_raw)

        except (TypeError, ValueError):

            conf = -1.0



        if conf >= 0:

            confidences.append(conf)



        # Tesseract's block/paragraph/line identifiers let us reconstruct

        # the original visual lines instead of flattening everything.

        key = (

            data["block_num"][i],

            data["par_num"][i],

            data["line_num"][i],

        )



        lines.setdefault(key, []).append(word)



    text = "\n".join(

        " ".join(words)

        for words in lines.values()

        if words

    )



    avg_conf = (

        sum(confidences) / len(confidences) / 100.0

        if confidences

        else 0.0

    )



    return text, avg_conf





# ============================================================

# GST-SPECIFIC OCR

# ============================================================



GSTIN_OCR_REGEX = re.compile(

    r"\d{2}[A-Z]{5}\d{4}[A-Z][A-Z0-9]Z[A-Z0-9]",

    re.IGNORECASE,

)





def _find_gstin_label_box(img: Image.Image):

    """

    Locate the GSTIN label using Tesseract word-level OCR.



    We specifically look for GSTIN/GSTN rather than generic GST so

    that CGST and SGST labels are not accidentally selected.

    """

    data = pytesseract.image_to_data(

        img,

        output_type=pytesseract.Output.DICT,

        config="--oem 3 --psm 11",

    )



    best = None



    for i, raw in enumerate(data.get("text", [])):

        word = re.sub(

            r"[^A-Za-z]",

            "",

            raw or "",

        ).upper()



        if word not in {"GSTIN", "GSTN"}:

            continue



        try:

            confidence = float(data["conf"][i])

        except (TypeError, ValueError):

            confidence = 0.0



        if confidence < 20:

            continue



        candidate = (

            confidence,

            int(data["left"][i]),

            int(data["top"][i]),

            int(data["width"][i]),

            int(data["height"][i]),

        )



        if best is None or confidence > best[0]:

            best = candidate



    if best is None:

        return None



    return best[1:]





def _extract_gstin_from_image(img: Image.Image):

    """

    Perform targeted OCR on the row containing GSTIN.



    This is separate from normal invoice OCR because GSTIN is a structured

    15-character identifier and can easily be misread during full-page OCR.

    """

    box = _find_gstin_label_box(img)



    if not box:

        logger.warning("GSTIN label was not detected by targeted OCR.")

        return None



    x, y, w, h = box



    # Capture the complete horizontal row containing GSTIN.

    pad_y = max(25, int(h * 3))



    top = max(0, y - pad_y)

    bottom = min(img.height, y + h + pad_y)



    crop = img.crop(

        (

            0,

            top,

            img.width,

            bottom,

        )

    )



    # Convert and improve the GST row.

    crop = crop.convert("L")

    crop = ImageOps.autocontrast(crop)



    # Larger upscale specifically for the GST identifier.

    crop = crop.resize(

        (

            crop.width * 3,

            crop.height * 3,

        ),

        Image.Resampling.LANCZOS,

    )



    # Second preprocessing variant.

    threshold = crop.point(

        lambda p: 0 if p < 180 else 255

    )



    variants = [

        crop,

        threshold,

    ]



    # GSTIN contains only letters and numbers.

    whitelist = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"



    for variant in variants:



        for psm in (6, 7, 11):



            try:

                text = pytesseract.image_to_string(

                    variant,

                    config=(

                        f"--oem 3 --psm {psm} "

                        f"-c tessedit_char_whitelist={whitelist}"

                    ),

                )

            except Exception as exc:

                logger.warning(

                    "GST-specific Tesseract PSM %s failed: %s",

                    psm,

                    exc,

                )

                continue



            # Remove OCR punctuation/noise.

            normalized = re.sub(

                r"[^A-Za-z0-9]",

                "",

                text,

            ).upper()



            match = GSTIN_OCR_REGEX.search(normalized)



            if match:

                gstin = match.group(0).upper()



                logger.info(

                    "GSTIN successfully detected by targeted OCR: %s",

                    gstin,

                )



                return gstin



    logger.warning(

        "GSTIN label was found, but no valid 15-character GSTIN "

        "could be recognized."

    )



    return None



def _merge_ocr_texts(texts) -> str:

    """

    Merge OCR passes while removing exact duplicate lines.



    This deliberately keeps different lines found by different PSM modes,

    because a label missed by PSM 6 may be detected by PSM 11.

    """

    seen = set()

    merged = []



    for text in texts:

        for raw_line in (text or "").splitlines():

            line = " ".join(raw_line.split()).strip()



            if not line:

                continue



            key = line.lower()



            if key not in seen:

                seen.add(key)

                merged.append(line)



    return "\n".join(merged)





def _ocr_pass_with_boxes(img: Image.Image, psm: int):

    """Return OCR lines with bounding boxes so separate passes can be merged in page order."""

    data = pytesseract.image_to_data(

        img,

        output_type=pytesseract.Output.DICT,

        config=f"--oem 3 --psm {psm}",

    )

    grouped = OrderedDict()

    confidences = []



    for i, raw_word in enumerate(data.get("text", [])):

        word = (raw_word or "").strip()

        if not word:

            continue

        try:

            conf = float(data["conf"][i]) / 100.0

        except (TypeError, ValueError):

            conf = -1.0

        if conf < 0:

            continue

        confidences.append(conf)

        key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])

        left, top = int(data["left"][i]), int(data["top"][i])

        width, height = int(data["width"][i]), int(data["height"][i])

        if key not in grouped:

            grouped[key] = {

                "words": [], "left": left, "top": top,

                "right": left + width, "bottom": top + height,

                "confs": [],

            }

        line = grouped[key]

        line["words"].append((left, word))

        line["left"] = min(line["left"], left)

        line["top"] = min(line["top"], top)

        line["right"] = max(line["right"], left + width)

        line["bottom"] = max(line["bottom"], top + height)

        line["confs"].append(conf)



    lines = []

    for item in grouped.values():

        line_text = " ".join(word for _, word in sorted(item["words"]))

        if not line_text.strip():

            continue

        lines.append({

            "text": line_text.strip(),

            "left": item["left"], "top": item["top"],

            "right": item["right"], "bottom": item["bottom"],

            "height": max(1, item["bottom"] - item["top"]),

            "confidence": sum(item["confs"]) / len(item["confs"]),

        })



    average = sum(confidences) / len(confidences) if confidences else 0.0

    return lines, average





def _line_similarity(a: str, b: str) -> float:

    clean = lambda value: re.sub(r"[^a-z0-9]", "", value.lower())

    left, right = clean(a), clean(b)

    if not left or not right:

        return 0.0

    if left in right or right in left:

        return 1.0

    return SequenceMatcher(None, left, right).ratio()





def _merge_spatial_ocr_passes(passes):

    """Deduplicate repeated OCR lines by text and vertical position, then sort by page position."""

    merged = []

    for lines in passes:

        for candidate in lines:

            duplicate = None

            for index, existing in enumerate(merged):

                overlap = max(0, min(existing["bottom"], candidate["bottom"]) - max(existing["top"], candidate["top"]))

                overlap_ratio = overlap / max(1, min(existing["height"], candidate["height"]))

                if overlap_ratio >= 0.55 and _line_similarity(existing["text"], candidate["text"]) >= 0.70:

                    duplicate = index

                    break

            if duplicate is None:

                merged.append(candidate)

            else:

                old = merged[duplicate]

                old_norm = re.sub(r"[^a-z0-9]", "", old["text"].lower())

                new_norm = re.sub(r"[^a-z0-9]", "", candidate["text"].lower())

                # Prefer a more complete line; otherwise prefer higher confidence.

                if (old_norm in new_norm and len(new_norm) > len(old_norm)) or (

                    len(new_norm) >= len(old_norm) and candidate["confidence"] > old["confidence"] + 0.05

                ):

                    merged[duplicate] = candidate



    merged.sort(key=lambda line: (line["top"], line["left"]))

    text = "\n".join(line["text"] for line in merged if line["text"].strip())

    confidence = sum(line["confidence"] for line in merged) / len(merged) if merged else 0.0

    return text, confidence





def _ocr_with_tesseract(

    img: Image.Image,

) -> Tuple[str, float]:

    """Run multiple layouts, merge duplicate lines by position, and retain reading order."""

    passes = []

    pass_confidences = []

    for psm in (6, 11, 4):

        try:

            lines, confidence = _ocr_pass_with_boxes(img, psm)

            if lines:

                passes.append(lines)

                pass_confidences.append(confidence)

        except Exception as exc:

            logger.warning("Tesseract PSM %s failed: %s", psm, exc)



    if not passes:

        return "", 0.0

    text, confidence = _merge_spatial_ocr_passes(passes)

    if not text and pass_confidences:

        confidence = sum(pass_confidences) / len(pass_confidences)

    return text, confidence





def _ocr_with_easyocr(

    img: Image.Image,

) -> Tuple[str, float]:



    import numpy as np



    reader = _get_easyocr_reader()



    results = reader.readtext(

        np.array(img)

    )



    if not results:

        return "", 0.0



    texts = [

        r[1]

        for r in results

    ]



    confs = [

        r[2]

        for r in results

    ]



    return (

        "\n".join(texts),

        sum(confs) / len(confs),

    )






def _extract_embedded_pdf_text(
    file_bytes: bytes,
) -> Tuple[str, float]:
    """
    Extract the native text layer from a PDF when one exists.

    Many invoices are digitally generated PDFs. Their text is already
    machine-readable, so raster OCR can be less accurate than reading the
    embedded text directly. Scanned/image-only PDFs return no text and
    continue through the normal OCR pipeline.
    """
    try:
        import fitz  # PyMuPDF

        document = fitz.open(stream=file_bytes, filetype="pdf")
        page_texts = []

        try:
            for page in document:
                page_text = page.get_text("text", sort=True) or ""
                if page_text.strip():
                    page_texts.append(page_text.strip())
        finally:
            document.close()

        text = "\n".join(page_texts).strip()

        if text:
            return text, 1.0

    except Exception as exc:
        logger.warning(
            "Embedded PDF text extraction failed; falling back to OCR: %s",
            exc,
        )

    return "", 0.0


def extract_text(

    file_bytes: bytes,

    file_ext: str,

    low_confidence_threshold: float = 0.55,

) -> Tuple[str, float]:

    """

    OCR every page and return complete text plus average confidence.



    Unlike the previous implementation, EasyOCR is not allowed to replace

    good Tesseract text merely because its confidence is slightly higher.

    Tesseract's multiple layouts are merged first so important invoice

    labels are less likely to disappear.



    GSTIN receives an additional field-specific OCR pass.

    """

    # Prefer the native PDF text layer when it exists. This is especially
    # important for digitally generated invoices with tables, where OCR can
    # drop labels, dates, invoice numbers, and numeric totals.
    embedded_text = ""
    embedded_conf = 0.0

    if file_ext.lower() == ".pdf":
        embedded_text, embedded_conf = _extract_embedded_pdf_text(
            file_bytes
        )

    pages = _load_pages(

        file_bytes,

        file_ext,

    )



    page_texts = []

    page_confs = []



    for page_number, page_img in enumerate(

        pages,

        start=1,

    ):



        processed = _preprocess_image(

            page_img

        )



        # --------------------------------------------------------

        # Normal Tesseract OCR

        # --------------------------------------------------------

        text, conf = _ocr_with_tesseract(

            processed

        )



        # --------------------------------------------------------

        # GST-specific OCR

        # --------------------------------------------------------

        # First try the enhanced/preprocessed image.

        gstin = _extract_gstin_from_image(

            processed

        )



        # If that fails, try the original 300-DPI page.

        if not gstin:

            gstin = _extract_gstin_from_image(

                page_img

            )



        # Only add GSTIN if it passed the strict 15-character

        # GSTIN pattern. We never invent or "correct" a value.

        if gstin:

            text = _merge_ocr_texts(

                [

                    text,

                    f"GSTIN {gstin}",

                ]

            )



        # --------------------------------------------------------

        # EasyOCR fallback

        # --------------------------------------------------------

        # If Tesseract is genuinely weak, add EasyOCR text instead

        # of throwing away the useful Tesseract output.

        if conf < low_confidence_threshold:



            try:

                fallback_text, fallback_conf = _ocr_with_easyocr(

                    page_img

                )



                if fallback_text.strip():

                    primary_count = sum(bool(line.strip()) for line in text.splitlines())

                    fallback_count = sum(bool(line.strip()) for line in fallback_text.splitlines())

                    # Keep one coherent page transcript. Appending EasyOCR's full

                    # transcript can duplicate labels and detach them from values.

                    if not text.strip() or (

                        fallback_conf > conf and fallback_count >= primary_count

                    ):

                        text = fallback_text

                    conf = max(conf, fallback_conf)



            except Exception as exc:

                logger.warning(

                    "EasyOCR fallback failed on page %s: %s",

                    page_number,

                    exc,

                )



        page_texts.append(text)

        page_confs.append(conf)



    full_text = "\n".join(
        page_texts
    )

    # For digitally generated PDFs, native text is the most reliable source.
    # OCR is still retained so scanned/image-only content is not lost.
    if embedded_text.strip():
        full_text = _merge_ocr_texts(
            [
                embedded_text,
                full_text,
            ]
        )

    avg_confidence = (
        sum(page_confs) / len(page_confs)
        if page_confs
        else 0.0
    )

    avg_confidence = max(avg_confidence, embedded_conf)

    return (
        full_text,
        avg_confidence,
    )
