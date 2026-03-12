from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from io import BytesIO
from pathlib import Path
from typing import Any
import json

from flask import Flask, Response, render_template_string, request
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader, simpleSplit
import qrcode

app = Flask(__name__)

BASE_DIR = Path(__file__).resolve().parent
LOGO_PATH = BASE_DIR / "logo.png"  # Zet hier jouw N4F logo neer
COUNTER_PATH = BASE_DIR / "invoice_counter.json"

# N4F branding
BLACK = colors.HexColor("#000000")
CHAMPAGNE = colors.HexColor("#D4B16A")
CREAM = colors.HexColor("#EFE6D8")
MUTED = colors.HexColor("#CFC6B8")
WHITE = colors.white

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="nl">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>N4F Factuurgenerator</title>
  <style>
    :root {
      --bg: #000000;
      --card: #000000;
      --text: #EFE6D8;
      --muted: #CFC6B8;
      --border: #B49A6C;
      --accent: #D4B16A;
      --white: #FFFFFF;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: Arial, Helvetica, sans-serif;
      background: var(--bg);
      color: var(--text);
    }
    .wrap {
      max-width: 1200px;
      margin: 0 auto;
      padding: 24px;
      display: grid;
      grid-template-columns: 380px 1fr;
      gap: 24px;
    }
    .panel, .invoice {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 20px;
      box-shadow: 0 8px 24px rgba(0,0,0,0.05);
    }
    .panel {
      padding: 20px;
      position: sticky;
      top: 20px;
      height: fit-content;
    }
    .invoice {
      padding: 40px;
    }
    h1, h2, h3 { margin: 0 0 12px; }
    h1 { font-size: 28px; }
    h2 { font-size: 18px; margin-top: 24px; }
    .muted { color: var(--muted); font-size: 14px; }
    .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
    .field { margin-bottom: 12px; }
    label {
      display: block;
      font-size: 13px;
      color: var(--muted);
      margin-bottom: 6px;
      font-weight: 600;
    }
    input, textarea, select {
      width: 100%;
      padding: 12px 14px;
      border-radius: 12px;
      border: 1px solid var(--border);
      font: inherit;
      background: #fff;
      color: #111;
    }
    textarea { min-height: 84px; resize: vertical; }
    .btns { display: flex; gap: 10px; margin-top: 18px; flex-wrap: wrap; }
    button {
      border: 0;
      border-radius: 12px;
      padding: 12px 16px;
      cursor: pointer;
      font-weight: 700;
      font-size: 14px;
    }
    .primary { background: var(--accent); color: white; }
    .secondary { background: #eee7db; color: #8f7750; }
    .logo-wrap {
      text-align: center;
      margin-bottom: 28px;
      padding-bottom: 18px;
      border-bottom: 2px solid var(--accent);
    }
    .logo-wrap img {
      width: 100%;
      max-width: 720px;
      height: auto;
      display: block;
      margin: 0 auto;
    }
    .invoice-head {
      display: flex;
      justify-content: space-between;
      gap: 24px;
      align-items: flex-start;
      border-bottom: 1px solid var(--accent);
      padding-bottom: 18px;
      margin-bottom: 28px;
    }
    .meta, .business, .client { line-height: 1.65; font-size: 14px; }
    .section-title {
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 1.2px;
      color: var(--accent);
      margin-bottom: 8px;
      font-weight: 700;
    }
    table { width: 100%; border-collapse: collapse; margin: 24px 0; }
    th, td {
      border-bottom: 1px solid var(--accent);
      padding: 14px 10px;
      text-align: left;
      vertical-align: top;
      color: var(--text);
    }
    th { color: var(--accent); font-size: 13px; }
    .totals {
      margin-left: auto;
      width: 320px;
      border-top: 2px solid var(--accent);
      padding-top: 12px;
    }
    .totals-row { display: flex; justify-content: space-between; padding: 8px 0; }
    .totals-row.total { font-weight: 800; font-size: 18px; }
    .bottom {
      margin-top: 28px;
      display: flex;
      justify-content: space-between;
      gap: 24px;
      align-items: flex-start;
    }
    .qr-box {
      background: var(--white);
      color: #111;
      border: 2px solid var(--accent);
      border-radius: 16px;
      padding: 18px;
      text-align: center;
      min-width: 220px;
    }
    #qrcode img { width: 160px; height: 160px; display: block; margin: 0 auto 12px; }
    .footnote {
      margin-top: 24px;
      color: var(--muted);
      font-size: 13px;
      border-top: 1px solid var(--accent);
      padding-top: 16px;
    }
    @media (max-width: 960px) {
      .wrap { grid-template-columns: 1fr; }
      .panel { position: static; }
      .invoice-head, .bottom { flex-direction: column; }
      .totals { width: 100%; }
    }
  </style>
</head>
<body>
  <div class="wrap">
    <aside class="panel">
      <h1>N4F factuurgenerator</h1>
      <p class="muted">Vul klant, bedrag en factuurgegevens in. De QR-code wordt automatisch gemaakt met bedrag, IBAN en omschrijving.</p>

      <form method="post" action="/generate-pdf">
        <h2>Jouw gegevens</h2>
        <div class="field"><label>Bedrijfsnaam</label><input name="businessName" value="Nutrition4Fitness" required /></div>
        <div class="field"><label>Rekeninghouder</label><input name="accountName" value="Christiaan Cornet" required /></div>
        <div class="field"><label>IBAN</label><input name="iban" value="ES25 0073 0100 5508 2170 8106" required /></div>
        <div class="grid">
          <div class="field"><label>KvK</label><input name="kvk" value="89592972" /></div>
          <div class="field"><label>BTW-ID</label><input name="btw" value="NL004375229B65" /></div>
        </div>
        <div class="field"><label>Adres</label><textarea name="businessAddress" readonly>P van der Meerschstraat 24&#10;1689XP Zwaag&#10;Nederland</textarea></div>

        <h2>Klant & factuur</h2>
        <div class="field"><label>Klantnaam</label><input name="clientName" placeholder="Naam klant" /></div>
        <div class="field"><label>Klantadres</label><textarea name="clientAddress" placeholder="Straat + huisnummer&#10;Postcode Plaats"></textarea></div>
        <div class="grid">
          <div class="field"><label>Factuurnummer</label><input name="invoiceNumber" value="{{ invoice_number }}" required /></div>
          <div class="field"><label>Factuurdatum</label><input name="invoiceDate" type="date" value="{{ today }}" required /></div>
        </div>
        <div class="grid">
          <div class="field"><label>Betaaltermijn (dagen)</label><input name="paymentDays" type="number" value="14" /></div>
          <div class="field"><label>BTW</label>
            <select name="vatRate">
              <option value="0">0%</option>
              <option value="9">9%</option>
              <option value="21">21%</option>
            </select>
          </div>
        </div>
        <div class="field"><label>Omschrijving</label><input name="description" value="Online coaching Nutrition4Fitness" /></div>
        <div class="grid">
          <div class="field"><label>Aantal</label><input name="quantity" type="number" step="1" value="1" /></div>
          <div class="field"><label>Prijs excl. btw (€)</label><input name="unitPrice" type="number" step="0.01" value="75.00" /></div>
        </div>
        <div class="field"><label>Betaalomschrijving QR</label><input name="paymentReference" value="Coaching Nutrition4Fitness" /></div>
        <div class="field"><label>Extra notitie</label><textarea name="notes">Bedankt voor het vertrouwen in Nutrition4Fitness.</textarea></div>

        <div class="btns">
          <button type="submit" class="primary">Maak PDF</button>
          <button type="button" class="secondary" onclick="this.form.reset()">Leegmaken</button>
        </div>
      </form>
    </aside>

    <main class="invoice">
      <div class="logo-wrap">
        {% if logo_exists %}
          <img src="/logo" alt="Nutrition4Fitness logo" />
        {% else %}
          <div class="muted">Plaats logo.png naast het Python-bestand</div>
        {% endif %}
      </div>
      <div class="invoice-head">
        <div>
          <div class="business">KvK: 89592972<br>BTW-ID: NL004375229B65<br>IBAN: ES25 0073 0100 5508 2170 8106</div>
        </div>
        <div class="meta">
          <div class="section-title">Factuur</div>
          <strong>Factuurnummer:</strong> {{ invoice_number }}<br>
          <strong>Factuurdatum:</strong> {{ today_display }}
        </div>
      </div>
      <div class="section-title">Preview</div>
      <div class="client">Deze preview is alleen voor invullen. De echte PDF wordt server-side gegenereerd met logo, thema en QR-code.</div>
    </main>
  </div>
</body>
</html>
"""


def today_iso() -> str:
    return date.today().isoformat()


def next_invoice_number() -> str:
    year = date.today().year
    if COUNTER_PATH.exists():
        try:
            data = json.loads(COUNTER_PATH.read_text(encoding="utf-8"))
            if data.get("year") == year:
                return f"{year}-{int(data.get('next', 1)):03d}"
        except Exception:
            pass
    return f"{year}-001"

def reserve_invoice_number(invoice_number: str) -> None:
    try:
        year_str, seq_str = invoice_number.split("-", 1)
        year = int(year_str)
        seq = int(seq_str)
    except Exception:
        return
    data = {"year": year, "next": seq + 1}
    COUNTER_PATH.write_text(json.dumps(data), encoding="utf-8")


def parse_decimal(value: str, default: str = "0") -> Decimal:
    raw = (value or default).replace(",", ".").strip()
    try:
        return Decimal(raw).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except Exception:
        return Decimal(default).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def safe_int(value: str, default: int = 0) -> int:
    try:
        return int(str(value).strip())
    except Exception:
        return default


def euro_str(value: Decimal) -> str:
    s = f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"€ {s}"


def clean_iban(value: str) -> str:
    return "".join((value or "").split()).upper()


def format_nl_date(value: str) -> str:
    try:
        return datetime.strptime(value, "%Y-%m-%d").strftime("%d-%m-%Y")
    except Exception:
        return value or ""


def due_date(value: str, days: int) -> str:
    try:
        dt = datetime.strptime(value, "%Y-%m-%d").date() + timedelta(days=days)
        return dt.strftime("%d-%m-%Y")
    except Exception:
        return ""


def build_epc_payload(name: str, iban: str, amount: Decimal, remittance_info: str) -> str:
    return "\n".join([
        "BCD",
        "002",
        "1",
        "SCT",
        "",
        name,
        clean_iban(iban),
        f"EUR{amount:.2f}",
        "",
        "",
        remittance_info,
        "",
    ])


def make_qr_image(payload: str) -> BytesIO:
    qr = qrcode.QRCode(border=2, box_size=8)
    qr.add_data(payload)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    out = BytesIO()
    img.save(out, format="PNG")
    out.seek(0)
    return out


def draw_multiline(c: canvas.Canvas, text: str, x: float, y: float, max_width: float, font_name: str, font_size: int, color: Any, leading: float) -> float:
    c.setFillColor(color)
    c.setFont(font_name, font_size)
    lines = simpleSplit(text or "", font_name, font_size, max_width)
    for line in lines:
        c.drawString(x, y, line)
        y -= leading
    return y


@app.get("/")
def index() -> str:
    return render_template_string(
        HTML_TEMPLATE,
        today=today_iso(),
        today_display=format_nl_date(today_iso()),
        invoice_number=next_invoice_number(),
        logo_exists=LOGO_PATH.exists(),
    )


@app.get("/logo")
def logo() -> Response:
    if not LOGO_PATH.exists():
        return Response(status=404)
    return Response(LOGO_PATH.read_bytes(), mimetype="image/png")


@app.post("/generate-pdf")
def generate_pdf() -> Response:
    business_name = request.form.get("businessName", "Nutrition4Fitness").strip()
    account_name = request.form.get("accountName", "Christiaan Cornet").strip()
    iban = request.form.get("iban", "").strip()
    kvk = request.form.get("kvk", "").strip()
    btw = request.form.get("btw", "").strip()
    business_address = "P van der Meerschstraat 24\n1689XP Zwaag\nNederland"
    client_name = request.form.get("clientName", "").strip()
    client_address = request.form.get("clientAddress", "").strip()
    invoice_number = request.form.get("invoiceNumber", next_invoice_number()).strip()
    invoice_date = request.form.get("invoiceDate", today_iso()).strip()
    payment_days = safe_int(request.form.get("paymentDays", "14"), 14)
    vat_rate = safe_int(request.form.get("vatRate", "0"), 0)
    description = request.form.get("description", "Online coaching Nutrition4Fitness").strip()
    quantity = safe_int(request.form.get("quantity", "1"), 1)
    unit_price = parse_decimal(request.form.get("unitPrice", "75.00"), "75.00")
    payment_reference = request.form.get("paymentReference", "Coaching Nutrition4Fitness").strip()
    notes = request.form.get("notes", "Bedankt voor het vertrouwen in Nutrition4Fitness.").strip()

    subtotal = (unit_price * Decimal(quantity)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    vat_amount = (subtotal * Decimal(vat_rate) / Decimal(100)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    total = subtotal + vat_amount

    remittance = f"Factuur {invoice_number} {payment_reference or description}".strip()
    epc_payload = build_epc_payload(account_name or business_name, iban, total, remittance)
    qr_buffer = make_qr_image(epc_payload)

    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    page_w, page_h = A4

    left = 12 * mm
    right = page_w - 12 * mm
    top = page_h - 12 * mm
    y = top

    # achtergrond
    c.setFillColor(BLACK)
    c.rect(0, 0, page_w, page_h, stroke=0, fill=1)

    # logo
    if LOGO_PATH.exists():
        logo = ImageReader(str(LOGO_PATH))
        iw, ih = logo.getSize()
        max_w = right - left
        draw_w = max_w
        draw_h = draw_w * (ih / iw)
        c.drawImage(logo, left, y - draw_h, width=draw_w, height=draw_h, preserveAspectRatio=True, mask='auto')
        y -= draw_h + 6 * mm
        c.setStrokeColor(CHAMPAGNE)
        c.setLineWidth(0.5)
        c.line(left, y, right, y)
        y -= 8 * mm

    # header blokken
    c.setFillColor(CREAM)
    c.setFont("Helvetica", 10)
    y_left = y
    for line in [
        *([part for part in business_address.splitlines() if part] if business_address else []),
        f"KvK: {kvk}",
        f"BTW-ID: {btw}",
        f"IBAN: {iban}",
        f"Rekeninghouder: {account_name or business_name}",
    ]:
        c.drawString(left, y_left, line)
        y_left -= 6 * mm

    right_x = 135 * mm
    c.setFillColor(CHAMPAGNE)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(right_x, y, "FACTUUR")
    c.setFillColor(CREAM)
    c.setFont("Helvetica", 10)
    y_right = y - 7 * mm
    for line in [
        f"Factuurnummer: {invoice_number}",
        f"Factuurdatum: {format_nl_date(invoice_date)}",
        f"Vervaldatum: {due_date(invoice_date, payment_days)}",
    ]:
        c.drawString(right_x, y_right, line)
        y_right -= 6 * mm

    y = min(y_left, y_right) - 3 * mm
    c.setStrokeColor(CHAMPAGNE)
    c.setLineWidth(0.3)
    c.line(left, y, right, y)
    y -= 8 * mm

    c.setFillColor(CHAMPAGNE)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(left, y, "FACTUUR AAN")
    y -= 7 * mm

    c.setFillColor(CREAM)
    c.setFont("Helvetica", 10)
    client_lines = [client_name] + ([part for part in client_address.splitlines() if part] if client_address else []) if client_name else ["Nog geen klant ingevuld."]
    for line in client_lines:
        c.drawString(left, y, line)
        y -= 6 * mm
    y -= 2 * mm

    # tabelkop
    cols = [left, 92 * mm, 118 * mm, 150 * mm, 198 * mm]
    c.setFillColor(CHAMPAGNE)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(cols[0], y, "Omschrijving")
    c.drawString(cols[1], y, "Aantal")
    c.drawString(cols[2], y, "Prijs excl.")
    c.drawString(cols[3], y, "BTW")
    c.drawRightString(cols[4], y, "Totaal")
    y -= 3 * mm
    c.line(left, y, right, y)
    y -= 7 * mm

    c.setFillColor(CREAM)
    c.setFont("Helvetica", 10)
    desc_lines = simpleSplit(description, "Helvetica", 10, 72 * mm)
    yy = y
    for line in desc_lines:
        c.drawString(cols[0], yy, line)
        yy -= 5 * mm
    c.drawString(cols[1], y, str(quantity))
    c.drawString(cols[2], y, euro_str(unit_price))
    c.drawString(cols[3], y, f"{vat_rate}%")
    c.drawRightString(cols[4], y, euro_str(subtotal))
    y -= max(8 * mm, len(desc_lines) * 5 * mm + 2 * mm)
    c.line(left, y, right, y)
    y -= 10 * mm

    # totaalblok
    total_x = 122 * mm
    c.setStrokeColor(CHAMPAGNE)
    c.line(total_x, y, right, y)
    y -= 6 * mm
    c.setFont("Helvetica", 10)
    c.setFillColor(CREAM)
    c.drawString(total_x, y, "Subtotaal")
    c.drawRightString(right, y, euro_str(subtotal))
    y -= 7 * mm
    c.drawString(total_x, y, "BTW")
    c.drawRightString(right, y, euro_str(vat_amount))
    y -= 9 * mm
    c.setFont("Helvetica-Bold", 12)
    c.drawString(total_x, y, "Totaal")
    c.drawRightString(right, y, euro_str(total))
    y -= 14 * mm

    # betalen + QR
    c.setFillColor(CHAMPAGNE)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(left, y, "BETALEN")
    y -= 7 * mm
    payment_text = (
        "Open eerst je bankapp en gebruik daar de QR-scanner om te betalen. "
        "Met een gewone QR-scanner werkt de betaalfunctie meestal niet. "
        "Bedrag, IBAN en omschrijving worden daarna automatisch ingevuld.\n\n"
        "Indien je geen gebruik wilt maken van de QR-code, kan het bedrag ook per overschrijving "
        "worden betaald naar het bovenstaande rekeningnummer met het factuurnummer als omschrijving."
    )
    y = draw_multiline(c, payment_text, left, y, 92 * mm, "Helvetica", 9, MUTED, 5 * mm)
    c.drawString(left, y - 2 * mm, f"Betaaltermijn: {payment_days} dagen")

    qr_x = 138 * mm
    qr_y = y + 4 * mm
    c.setFillColor(WHITE)
    c.setStrokeColor(CHAMPAGNE)
    c.roundRect(qr_x, qr_y - 32 * mm, 58 * mm, 62 * mm, 4 * mm, stroke=1, fill=1)
    qr_image = ImageReader(qr_buffer)
    c.drawImage(qr_image, qr_x + 9 * mm, qr_y - 14 * mm, width=40 * mm, height=40 * mm, mask='auto')
    c.setFillColor(BLACK)
    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(qr_x + 29 * mm, qr_y - 18 * mm, "Scan & betaal")
    c.setFont("Helvetica", 8)
    c.drawCentredString(qr_x + 29 * mm, qr_y - 25 * mm, f"Bedrag: {euro_str(total)}")

    y = min(y - 16 * mm, qr_y - 38 * mm)
    c.setStrokeColor(CHAMPAGNE)
    c.line(left, y, right, y)
    y -= 8 * mm
    draw_multiline(c, notes, left, y, right - left, "Helvetica", 9, MUTED, 5 * mm)

    c.showPage()
    c.save()
    buffer.seek(0)

    reserve_invoice_number(invoice_number)

    filename = f"N4F_factuur_{invoice_number}.pdf"
    return Response(
        buffer.getvalue(),
        mimetype="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
