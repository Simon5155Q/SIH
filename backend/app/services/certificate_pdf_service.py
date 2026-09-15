import io
import qrcode
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from datetime import datetime, timezone
from app.utils.qr_signing import sign_certificate_payload

def generate_certificate_pdf(
    *,
    certificate_id: int,
    instrument_serial: str,
    instrument_type: str,
    owner_name: str,
    inspection_date: str,
    verification_status: str,
    verify_base_url: str,
) -> bytes:
    issued_at_iso = datetime.now(timezone.utc).isoformat()
    token = sign_certificate_payload(certificate_id, instrument_serial, issued_at_iso)
    verify_url = f"{verify_base_url}/certificates/verify/{token}"

    qr = qrcode.QRCode(box_size=6, border=2)
    qr.add_data(verify_url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")
    qr_buffer = io.BytesIO()
    qr_img.save(qr_buffer, format="PNG")
    qr_buffer.seek(0)

    pdf_buffer = io.BytesIO()
    c = canvas.Canvas(pdf_buffer, pagesize=A4)
    width, height = A4

    c.setFont("Helvetica-Bold", 18)
    c.drawCentredString(width / 2, height - 40 * mm, "LEGAL METROLOGY VERIFICATION CERTIFICATE")

    c.setFont("Helvetica", 11)
    lines = [
        f"Certificate ID: {certificate_id}",
        f"Instrument Serial No.: {instrument_serial}",
        f"Instrument Type: {instrument_type}",
        f"Owner / Trader: {owner_name}",
        f"Inspection Date: {inspection_date}",
        f"Verification Status: {verification_status}",
        f"Issued At (UTC): {issued_at_iso}",
    ]

    y = height - 60 * mm
    for line in lines:
        c.drawString(30 * mm, y, line)
        y -= 8 * mm

    c.drawImage(ImageReader(qr_buffer), width - 70 * mm, 30 * mm, width=40 * mm, height=40 * mm)
    c.setFont("Helvetica-Oblique", 8)
    c.drawString(width - 70 * mm, 25 * mm, "Scan to verify authenticity")

    c.showPage()
    c.save()
    pdf_buffer.seek(0)
    return pdf_buffer.read()
