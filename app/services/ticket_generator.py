import os
from datetime import datetime

# In-memory ticket store (fast cache, DB is primary storage)
TICKET_STORE = {}


def _save_ticket_to_db(pnr: str, html_content: str):
    """Save ticket HTML to database for persistence across restarts"""
    try:
        from app.db.database import engine
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(
                text("UPDATE trips SET ticket_html = :html WHERE booking_reference = :pnr"),
                {"html": html_content, "pnr": pnr}
            )
            conn.commit()
    except Exception as e:
        print(f"⚠️ Could not save ticket to DB (non-critical): {e}")


def _load_ticket_from_db(pnr: str) -> str:
    """Load ticket HTML from database"""
    try:
        from app.db.database import engine
        from sqlalchemy import text
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT ticket_html FROM trips WHERE booking_reference = :pnr"),
                {"pnr": pnr}
            ).fetchone()
            if row and row[0]:
                return row[0]
    except Exception as e:
        print(f"⚠️ Could not load ticket from DB: {e}")
    return None


class TicketGenerator:
    @staticmethod
    def generate_html_ticket(pnr, passenger_name, flight_data, amount):
        """
        Generates a styled HTML e-ticket and stores in DB + memory.
        Returns the URL path to retrieve it.
        """
        segment = flight_data.get('segments', [{}])[0]
        origin = segment.get('origin', 'UNK')
        destination = segment.get('destination', 'UNK')
        dep_time = segment.get('departure_time', datetime.now().isoformat())
        arr_time = segment.get('arrival_time', datetime.now().isoformat())
        carrier = segment.get('carrier_code', 'XX')
        flight_num = segment.get('number', '0000')

        html_content = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>E-Ticket {pnr}</title>
    <style>
        body {{ font-family: 'Courier New', Courier, monospace; background: #f4f4f4; padding: 20px; }}
        .ticket {{ max-width: 600px; margin: 0 auto; background: white; padding: 30px; border: 1px solid #ddd; box-shadow: 0 4px 20px rgba(0,0,0,0.05); }}
        .header {{ border-bottom: 2px solid #000; padding-bottom: 15px; margin-bottom: 25px; display: flex; justify-content: space-between; align-items: center; }}
        .logo {{ font-weight: bold; font-size: 22px; letter-spacing: -1px; }}
        .pnr {{ font-size: 14px; color: #666; }}
        .route {{ font-size: 42px; font-weight: bold; line-height: 1; margin-bottom: 5px; }}
        .date {{ font-size: 14px; color: #666; margin-top: 8px; margin-bottom: 25px; }}
        .details {{ display: grid; grid-template-columns: 1fr 1fr; gap: 15px; border-top: 1px solid #eee; padding-top: 15px; }}
        .label {{ font-size: 10px; text-transform: uppercase; color: #999; margin-bottom: 3px; }}
        .value {{ font-size: 15px; font-weight: bold; }}
        .footer {{ margin-top: 30px; border-top: 2px solid #000; padding-top: 15px; font-size: 11px; color: #999; text-align: center; }}
        .barcode {{ margin-top: 15px; height: 35px; background: repeating-linear-gradient(90deg, #000, #000 2px, #fff 2px, #fff 4px); width: 100%; opacity: 0.7; }}
    </style>
</head>
<body>
    <div class="ticket">
        <div class="header">
            <div class="logo">Biajez</div>
            <div class="pnr">PNR: {pnr}</div>
        </div>

        <div class="route">{origin} &rarr; {destination}</div>
        <div class="date">{dep_time.split('T')[0]}</div>

        <div class="details">
            <div>
                <div class="label">Pasajero</div>
                <div class="value">{passenger_name}</div>
            </div>
            <div>
                <div class="label">Vuelo</div>
                <div class="value">{carrier} {flight_num}</div>
            </div>
            <div>
                <div class="label">Salida</div>
                <div class="value">{dep_time.split('T')[1][:5]}</div>
            </div>
            <div>
                <div class="label">Llegada</div>
                <div class="value">{arr_time.split('T')[1][:5]}</div>
            </div>
            <div>
                <div class="label">Clase</div>
                <div class="value">Economy</div>
            </div>
            <div>
                <div class="label">Total pagado</div>
                <div class="value">${amount}</div>
            </div>
        </div>

        <div class="barcode"></div>

        <div class="footer">
            Boleto electronico confirmado &bull; Biajez
        </div>
    </div>
</body>
</html>"""

        # Store in memory (fast cache) AND database (persistent)
        TICKET_STORE[pnr] = html_content
        _save_ticket_to_db(pnr, html_content)

        base_url = os.getenv("BASE_URL", "https://biajez-d08x.onrender.com")
        return f"{base_url}/ticket/{pnr}"

    @staticmethod
    def generate_hotel_ticket(pnr, guest_name, hotel_data, amount):
        """
        Generates a Hotel Voucher and stores in DB + memory.
        """
        hotel_name = hotel_data.get('name', 'Hotel')
        address = hotel_data.get('address', {}).get('cityName', '')
        checkin = hotel_data.get('checkin', '')
        checkout = hotel_data.get('checkout', '')

        html_content = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Voucher Hotel {pnr}</title>
    <style>
        body {{ font-family: 'Helvetica', Arial, sans-serif; background: #f4f4f4; padding: 20px; }}
        .voucher {{ max-width: 600px; margin: 0 auto; background: white; padding: 30px; border-top: 5px solid #000; box-shadow: 0 4px 20px rgba(0,0,0,0.05); }}
        .header {{ display: flex; justify-content: space-between; margin-bottom: 30px; }}
        .title {{ font-size: 22px; font-weight: bold; text-transform: uppercase; }}
        .pnr {{ font-size: 14px; color: #666; }}
        .hotel-name {{ font-size: 28px; font-weight: bold; margin-bottom: 8px; }}
        .address {{ font-size: 15px; color: #666; margin-bottom: 25px; }}
        .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 15px; border-top: 1px solid #eee; border-bottom: 1px solid #eee; padding: 15px 0; }}
        .label {{ font-size: 11px; text-transform: uppercase; color: #999; margin-bottom: 4px; }}
        .value {{ font-size: 16px; font-weight: bold; }}
        .footer {{ margin-top: 30px; font-size: 11px; color: #999; text-align: center; }}
    </style>
</head>
<body>
    <div class="voucher">
        <div class="header">
            <div class="title">Voucher de Hotel</div>
            <div class="pnr">CONF: {pnr}</div>
        </div>

        <div class="hotel-name">{hotel_name}</div>
        <div class="address">{address}</div>

        <div class="grid">
            <div>
                <div class="label">Huesped</div>
                <div class="value">{guest_name}</div>
            </div>
            <div>
                <div class="label">Total pagado</div>
                <div class="value">${amount}</div>
            </div>
            <div>
                <div class="label">Check-in</div>
                <div class="value">{checkin}</div>
            </div>
            <div>
                <div class="label">Check-out</div>
                <div class="value">{checkout}</div>
            </div>
        </div>

        <div class="footer">
            Reserva confirmada &bull; Presenta este voucher al llegar &bull; Biajez
        </div>
    </div>
</body>
</html>"""

        # Store in memory (fast cache) AND database (persistent)
        TICKET_STORE[pnr] = html_content
        _save_ticket_to_db(pnr, html_content)

        base_url = os.getenv("BASE_URL", "https://biajez-d08x.onrender.com")
        return f"{base_url}/ticket/{pnr}"
