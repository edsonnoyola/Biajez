import os
from datetime import datetime

# In-memory ticket store (for serverless/stateless environments)
TICKET_STORE = {}

class TicketGenerator:
    @staticmethod
    def generate_html_ticket(pnr, passenger_name, flight_data, amount):
        """
        Generates a Duffel-style HTML ticket and stores it in memory.
        Returns the URL path to retrieve it.
        """
        # Extract details
        segment = flight_data.get('segments', [{}])[0]
        origin = segment.get('origin', 'UNK')
        destination = segment.get('destination', 'UNK')
        dep_time = segment.get('departure_time', datetime.now().isoformat())
        arr_time = segment.get('arrival_time', datetime.now().isoformat())
        carrier = segment.get('carrier_code', 'XX')
        flight_num = segment.get('number', '0000')
        
        html_content = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>E-Ticket {pnr}</title>
            <style>
                body {{ font-family: 'Courier New', Courier, monospace; background: #f4f4f4; padding: 40px; }}
                .ticket {{ max-width: 600px; margin: 0 auto; background: white; padding: 40px; border: 1px solid #ddd; box-shadow: 0 4px 20px rgba(0,0,0,0.05); }}
                .header {{ border-bottom: 2px solid #000; padding-bottom: 20px; margin-bottom: 30px; display: flex; justify-content: space-between; align-items: center; }}
                .logo {{ font-weight: bold; font-size: 24px; letter-spacing: -1px; }}
                .pnr {{ font-size: 14px; color: #666; }}
                .flight-info {{ display: flex; justify-content: space-between; margin-bottom: 40px; }}
                .route {{ font-size: 48px; font-weight: bold; line-height: 1; }}
                .date {{ font-size: 14px; color: #666; margin-top: 10px; }}
                .details {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; border-top: 1px solid #eee; pt-4; }}
                .label {{ font-size: 10px; text-transform: uppercase; color: #999; margin-bottom: 4px; }}
                .value {{ font-size: 16px; font-weight: bold; }}
                .footer {{ margin-top: 40px; border-top: 2px solid #000; padding-top: 20px; font-size: 12px; color: #999; text-align: center; }}
                .barcode {{ margin-top: 20px; height: 40px; background: repeating-linear-gradient(90deg, #000, #000 2px, #fff 2px, #fff 4px); width: 100%; opacity: 0.7; }}
            </style>
        </head>
        <body>
            <div class="ticket">
                <div class="header">
                    <div class="logo">Biajez / Duffel</div>
                    <div class="pnr">PNR: {pnr}</div>
                </div>
                
                <div class="flight-info">
                    <div>
                        <div class="route">{origin} → {destination}</div>
                        <div class="date">{dep_time.split('T')[0]}</div>
                    </div>
                </div>
                
                <div class="details">
                    <div>
                        <div class="label">Passenger</div>
                        <div class="value">{passenger_name}</div>
                    </div>
                    <div>
                        <div class="label">Flight</div>
                        <div class="value">{carrier} {flight_num}</div>
                    </div>
                    <div>
                        <div class="label">Departure</div>
                        <div class="value">{dep_time.split('T')[1][:5]}</div>
                    </div>
                    <div>
                        <div class="label">Arrival</div>
                        <div class="value">{arr_time.split('T')[1][:5]}</div>
                    </div>
                    <div>
                        <div class="label">Class</div>
                        <div class="value">Economy</div>
                    </div>
                    <div>
                        <div class="label">Total Paid</div>
                        <div class="value">${amount}</div>
                    </div>
                </div>
                
                <div class="barcode"></div>
                
                <div class="footer">
                    Confirmed via Duffel API • Electronic Ticket
                </div>
            </div>
        </body>
        </html>
        """
        
        # Store in memory for retrieval via API
        TICKET_STORE[pnr] = html_content

        # Return API URL (will be served by /ticket/{pnr} endpoint)
        base_url = os.getenv("BASE_URL", "https://biajez-d08x.onrender.com")
        return f"{base_url}/ticket/{pnr}"
            
    @staticmethod
    def generate_hotel_ticket(pnr, guest_name, hotel_data, amount):
        """
        Generates a Hotel Voucher.
        """
        hotel_name = hotel_data.get('name', 'Unknown Hotel')
        address = hotel_data.get('address', {}).get('cityName', 'Unknown City')
        checkin = hotel_data.get('checkin', '2025-12-15')
        checkout = hotel_data.get('checkout', '2025-12-20')
        
        html_content = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Hotel Voucher {pnr}</title>
            <style>
                body {{ font-family: 'Helvetica', Arial, sans-serif; background: #f4f4f4; padding: 40px; }}
                .voucher {{ max-width: 600px; margin: 0 auto; background: white; padding: 40px; border-top: 5px solid #000; box-shadow: 0 4px 20px rgba(0,0,0,0.05); }}
                .header {{ display: flex; justify-content: space-between; margin-bottom: 40px; }}
                .title {{ font-size: 24px; font-weight: bold; text-transform: uppercase; }}
                .pnr {{ font-size: 14px; color: #666; }}
                .hotel-name {{ font-size: 32px; font-weight: bold; margin-bottom: 10px; }}
                .address {{ font-size: 16px; color: #666; margin-bottom: 30px; }}
                .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; border-top: 1px solid #eee; border-bottom: 1px solid #eee; padding: 20px 0; }}
                .label {{ font-size: 12px; text-transform: uppercase; color: #999; margin-bottom: 5px; }}
                .value {{ font-size: 18px; font-weight: bold; }}
                .footer {{ margin-top: 40px; font-size: 12px; color: #999; text-align: center; }}
            </style>
        </head>
        <body>
            <div class="voucher">
                <div class="header">
                    <div class="title">Hotel Voucher</div>
                    <div class="pnr">CONF: {pnr}</div>
                </div>
                
                <div class="hotel-name">{hotel_name}</div>
                <div class="address">{address}</div>
                
                <div class="grid">
                    <div>
                        <div class="label">Guest</div>
                        <div class="value">{guest_name}</div>
                    </div>
                    <div>
                        <div class="label">Room Type</div>
                        <div class="value">Standard Double</div>
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
                    Confirmed via Amadeus Hotel API • Present this voucher at check-in
                </div>
            </div>
        </body>
        </html>
        """
        
        # Store in memory for retrieval via API
        TICKET_STORE[pnr] = html_content

        # Return API URL
        base_url = os.getenv("BASE_URL", "https://biajez-d08x.onrender.com")
        return f"{base_url}/ticket/{pnr}"
