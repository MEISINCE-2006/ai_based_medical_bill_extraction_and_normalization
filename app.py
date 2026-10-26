import json
import re
from datetime import datetime
from io import BytesIO
from pathlib import Path

import pandas as pd
import pytesseract
import streamlit as st
from PIL import Image

pytesseract.pytesseract.tesseract_cmd = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)

st.set_page_config(
    page_title="AI Medical Bill Extractor",
    page_icon="🏥",
    layout="wide"
)

SAMPLE_PATH = Path(__file__).parent / "sample_medical_bill.png"

if "page" not in st.session_state:
    st.session_state.page = 1

if "bill_bytes" not in st.session_state:
    st.session_state.bill_bytes = None

if "bill_name" not in st.session_state:
    st.session_state.bill_name = ""

if "raw_text" not in st.session_state:
    st.session_state.raw_text = ""

if "normalized" not in st.session_state:
    st.session_state.normalized = None


def go_to(page):
    st.session_state.page = page


def extract_text(image_bytes):
    image = Image.open(BytesIO(image_bytes)).convert("RGB")
    return pytesseract.image_to_string(image, config="--psm 6")


def find_value(pattern, text):
    match = re.search(
        pattern, text, re.IGNORECASE | re.MULTILINE
    )
    return match.group(1).strip() if match else "Not found"


def normalize_date(value):
    if value == "Not found":
        return value

    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass

    return value


def normalize_bill(text):
    hospital = find_value(
        r"([A-Z][A-Z ]+COMMUNITY HOSPITAL)", text
    )

    patient = find_value(
        r"Patient Name\s*:?\s*([A-Za-z][A-Za-z .'-]+)",
        text
    )

    bill_number = find_value(
        r"(?:Bill Number|Bill No\.?)\s*:?\s*([A-Z0-9/-]+)",
        text
    )

    patient_id = find_value(
        r"Patient ID\s*:?\s*([A-Z0-9-]+)", text
    )

    bill_date = find_value(
        r"Bill Date\s*:?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{4}|\d{4}-\d{2}-\d{2})",
        text
    )

    total = find_value(
        r"(?:GRAND TOTAL|Grand Total)\s*(?:INR)?\s*:?\s*([\d,]+\.\d{2})",
        text
    )

    if total == "Not found":
        total = find_value(
            r"(?:Total Amount|Total)\s*:?\s*(?:INR|Rs\.?|₹)?\s*([\d,]+(?:\.\d{1,2})?)",
            text
        )

    amount = None

    if total != "Not found":
        try:
            amount = round(float(total.replace(",", "")), 2)
        except ValueError:
            pass

    return {
        "hospital_name": hospital,
        "patient_name": patient,
        "patient_id": patient_id,
        "bill_number": bill_number,
        "bill_date": normalize_date(bill_date),
        "currency": "INR",
        "total_amount": amount
    }


def show_progress():
    steps = ["1. Upload", "2. Extraction", "3. Normalization"]
    cols = st.columns(3)

    for index, label in enumerate(steps, start=1):
        if st.session_state.page == index:
            cols[index - 1].info("● " + label)
        elif st.session_state.page > index:
            cols[index - 1].success("✓ " + label)
        else:
            cols[index - 1].markdown("**" + label + "**")


with st.sidebar:
    st.title("🏥 Medical Bill AI")
    st.caption("Extract • Review • Normalize")
    st.divider()

    if st.button("🏠 Home / Upload", use_container_width=True):
        go_to(1)
        st.rerun()

    if st.button("🔎 Extraction", use_container_width=True):
        if st.session_state.bill_bytes:
            go_to(2)
            st.rerun()
        else:
            st.warning("Upload a bill first.")

    if st.button("📋 Normalization", use_container_width=True):
        if st.session_state.normalized:
            go_to(3)
            st.rerun()
        else:
            st.warning("Extract a bill first.")

    st.divider()
    st.caption("Demo application using OCR")


st.title("AI-Powered Medical Bill Extraction")
st.write(
    "Upload a medical bill and follow each stage to extract "
    "and normalize its information."
)

show_progress()
st.divider()


if st.session_state.page == 1:

    st.header("Step 1: Upload Medical Bill")
    st.write("Choose an image of a medical bill to get started.")

    uploaded = st.file_uploader(
        "Upload your bill",
        type=["png", "jpg", "jpeg", "tif", "tiff"],
        key="bill_upload"
    )

    use_sample = st.checkbox("Use the sample medical bill")

    if uploaded is not None:
        new_bytes = uploaded.getvalue()

        if new_bytes != st.session_state.bill_bytes:
            st.session_state.bill_bytes = new_bytes
            st.session_state.bill_name = uploaded.name
            st.session_state.raw_text = ""
            st.session_state.normalized = None

    elif use_sample:
        if SAMPLE_PATH.exists():
            sample_bytes = SAMPLE_PATH.read_bytes()

            if sample_bytes != st.session_state.bill_bytes:
                st.session_state.bill_bytes = sample_bytes
                st.session_state.bill_name = SAMPLE_PATH.name
                st.session_state.raw_text = ""
                st.session_state.normalized = None
        else:
            st.error("sample_medical_bill.png was not found.")

    if st.session_state.bill_bytes:
        st.success("Selected file: " + st.session_state.bill_name)

        preview = Image.open(
            BytesIO(st.session_state.bill_bytes)
        ).convert("RGB")

        st.image(
            preview,
            caption="Medical Bill Preview",
            use_container_width=True
        )

        if st.button("Next: Extract Bill →", type="primary"):
            go_to(2)
            st.rerun()

    else:
        st.info("Upload a bill or select the sample bill to continue.")


elif st.session_state.page == 2:

    st.header("Step 2: Extract Bill Information")
    st.write(
        "OCR reads the text from your uploaded medical bill. "
        "Review the extracted text before normalization."
    )

    if not st.session_state.bill_bytes:
        st.warning("Please upload a bill first.")
        if st.button("← Back to Upload"):
            go_to(1)
            st.rerun()

    else:
        st.caption("File: " + st.session_state.bill_name)

        if st.button("▶ Start Text Extraction", type="primary"):
            try:
                with st.spinner("Extracting text using Tesseract OCR..."):
                    st.session_state.raw_text = extract_text(
                        st.session_state.bill_bytes
                    )
                    st.session_state.normalized = None

            except Exception as error:
                st.error("Text extraction failed.")
                st.code(str(error))

        if st.session_state.raw_text:
            st.success("Text extraction completed.")

            st.subheader("Extracted Raw Text")
            edited_text = st.text_area(
                "Review or correct OCR text before normalization",
                value=st.session_state.raw_text,
                height=300,
                key="reviewed_ocr_text"
            )

            if st.button("Next: Normalize Data →", type="primary"):
                st.session_state.raw_text = edited_text
                st.session_state.normalized = normalize_bill(edited_text)
                go_to(3)
                st.rerun()

        col1, col2 = st.columns(2)

        with col1:
            if st.button("← Back to Upload"):
                go_to(1)
                st.rerun()

        with col2:
            if st.session_state.raw_text and st.button(
                "Re-extract Text"
            ):
                st.session_state.raw_text = extract_text(
                    st.session_state.bill_bytes
                )
                st.rerun()


elif st.session_state.page == 3:

    st.header("Step 3: Normalize and Review")
    st.write(
        "Convert the extracted fields into a consistent structured format."
    )

    if not st.session_state.raw_text:
        st.warning("Complete text extraction before continuing.")

        if st.button("← Back to Extraction"):
            go_to(2)
            st.rerun()

    else:
        if st.session_state.normalized is None:
            st.session_state.normalized = normalize_bill(
                st.session_state.raw_text
            )

        result = st.session_state.normalized

        st.subheader("Normalized Bill Fields")

        edited = {}

        for key, value in result.items():
            label = key.replace("_", " ").title()

            if key == "total_amount":
                initial = "" if value is None else str(value)
                entered = st.text_input(label, value=initial)
                try:
                    edited[key] = round(float(entered), 2) if entered.strip() else None
                except ValueError:
                    edited[key] = None
                    st.warning("Enter a valid numeric total amount.")
            else:
                edited[key] = st.text_input(
                    label,
                    value="" if value is None else str(value),
                    key="normalized_" + key
                )

        st.info(
            "Review and correct the fields if OCR misread any information."
        )

        if st.button("Save Normalized Data", type="primary"):
            st.session_state.normalized = edited
            st.success("Normalized data updated.")

        st.subheader("Structured JSON Output")

        json_text = json.dumps(
            edited, indent=4, ensure_ascii=False
        )

        st.code(json_text, language="json")

        c1, c2 = st.columns(2)

        with c1:
            st.download_button(
                "⬇ Download JSON",
                data=json_text,
                file_name="normalized_medical_bill.json",
                mime="application/json",
                use_container_width=True
            )

        with c2:
            csv_text = pd.DataFrame([edited]).to_csv(index=False)

            st.download_button(
                "⬇ Download CSV",
                data=csv_text,
                file_name="normalized_medical_bill.csv",
                mime="text/csv",
                use_container_width=True
            )

        st.divider()

        if st.button("← Back to Extraction"):
            go_to(2)
            st.rerun()

        if st.button("Start New Bill"):
            st.session_state.page = 1
            st.session_state.bill_bytes = None
            st.session_state.bill_name = ""
            st.session_state.raw_text = ""
            st.session_state.normalized = None
            st.rerun()

st.divider()
st.caption(
    "Educational prototype: OCR and rule-based normalization. "
    "Use fictional bills and verify extracted data."
)
