"""
Email Service for sending booking confirmations
Uses Resend (simple and free tier available)
"""
import os
import resend
from typing import Dict, Optional

# Configure Resend API key
resend.api_key = os.getenv("RESEND_API_KEY", "")

class EmailService:
    """Service for sending booking confirmation emails"""
    
    @staticmethod
    def send_booking_confirmation(
        to_email: str,
        booking_data: Dict,
        booking_type: str = "flight"
    ) -> bool:
        """
        Send booking confirmation email
        
        Args:
            to_email: Recipient email
            booking_data: Dictionary with booking details
            booking_type: "flight" or "hotel"
            
        Returns:
            bool: True if sent successfully
        """
        try:
            if booking_type == "flight":
                subject = f"✈️ Flight Confirmation - {booking_data.get('pnr', 'N/A')}"
                html_content = EmailService._generate_flight_email(booking_data)
            else:
                subject = f"🏨 Hotel Confirmation - {booking_data.get('booking_reference', 'N/A')}"
                html_content = EmailService._generate_hotel_email(booking_data)
            
            # Send email using Resend
            # Use onboarding@resend.dev for testing until domain is verified
            from_email = os.getenv("RESEND_FROM_EMAIL", "Biajez <onboarding@resend.dev>")
            params = {
                "from": from_email,
                "to": [to_email],
                "subject": subject,
                "html": html_content,
            }
            
            response = resend.Emails.send(params)
            print(f"✅ Email sent to {to_email}: {response}")
            return True
            
        except Exception as e:
            print(f"❌ Error sending email: {e}")
            return False
    
    @staticmethod
    def _generate_flight_email(booking_data: Dict) -> str:
        """Generate HTML email for flight confirmation"""
        
        pnr = booking_data.get('pnr', 'N/A')
        departure = booking_data.get('departure_city', 'N/A')
        arrival = booking_data.get('arrival_city', 'N/A')
        departure_date = booking_data.get('departure_date', 'N/A')
        passenger_name = booking_data.get('passenger_name', 'Passenger')
        total_amount = booking_data.get('total_amount', '0')
        currency = booking_data.get('currency', 'USD')
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Flight Confirmation</title>
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 20px;
                }}
                .header {{
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    padding: 30px;
                    border-radius: 10px 10px 0 0;
                    text-align: center;
                }}
                .content {{
                    background: #f9fafb;
                    padding: 30px;
                    border-radius: 0 0 10px 10px;
                }}
                .booking-card {{
                    background: white;
                    padding: 20px;
                    border-radius: 8px;
                    margin: 20px 0;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                }}
                .detail-row {{
                    display: flex;
                    justify-content: space-between;
                    padding: 10px 0;
                    border-bottom: 1px solid #e5e7eb;
                }}
                .detail-label {{
                    font-weight: 600;
                    color: #6b7280;
                }}
                .detail-value {{
                    color: #111827;
                }}
                .pnr {{
                    font-size: 24px;
                    font-weight: bold;
                    color: #667eea;
                    text-align: center;
                    padding: 20px;
                    background: #f3f4f6;
                    border-radius: 8px;
                    margin: 20px 0;
                }}
                .footer {{
                    text-align: center;
                    padding: 20px;
                    color: #6b7280;
                    font-size: 14px;
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>✈️ Flight Confirmed!</h1>
                <p>Your booking has been confirmed</p>
            </div>
            
            <div class="content">
                <p>Dear {passenger_name},</p>
                <p>Your flight has been successfully booked. Here are your booking details:</p>
                
                <div class="pnr">
                    PNR: {pnr}
                </div>
                
                <div class="booking-card">
                    <h3>Flight Details</h3>
                    <div class="detail-row">
                        <span class="detail-label">From:</span>
                        <span class="detail-value">{departure}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">To:</span>
                        <span class="detail-value">{arrival}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Departure:</span>
                        <span class="detail-value">{departure_date}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Total:</span>
                        <span class="detail-value">{currency} {total_amount}</span>
                    </div>
                </div>
                
                <p><strong>Important:</strong> Please arrive at the airport at least 2 hours before departure.</p>
                <p>You can manage your booking in the Biajez app.</p>
            </div>
            
            <div class="footer">
                <p>This is an automated confirmation email from Biajez.</p>
                <p>If you have any questions, please contact support.</p>
            </div>
        </body>
        </html>
        """
        
        return html
    
    @staticmethod
    def _generate_hotel_email(booking_data: Dict) -> str:
        """Generate HTML email for hotel confirmation"""
        
        booking_ref = booking_data.get('booking_reference', 'N/A')
        hotel_name = booking_data.get('hotel_name', 'N/A')
        check_in = booking_data.get('check_in_date', 'N/A')
        check_out = booking_data.get('check_out_date', 'N/A')
        guest_name = booking_data.get('guest_name', 'Guest')
        total_amount = booking_data.get('total_amount', '0')
        currency = booking_data.get('currency', 'USD')
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 20px;
                }}
                .header {{
                    background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
                    color: white;
                    padding: 30px;
                    border-radius: 10px 10px 0 0;
                    text-align: center;
                }}
                .content {{
                    background: #f9fafb;
                    padding: 30px;
                    border-radius: 0 0 10px 10px;
                }}
                .booking-card {{
                    background: white;
                    padding: 20px;
                    border-radius: 8px;
                    margin: 20px 0;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>🏨 Hotel Confirmed!</h1>
                <p>Your reservation is confirmed</p>
            </div>
            
            <div class="content">
                <p>Dear {guest_name},</p>
                <p>Your hotel reservation has been confirmed:</p>
                
                <div class="booking-card">
                    <h3>{hotel_name}</h3>
                    <p><strong>Confirmation:</strong> {booking_ref}</p>
                    <p><strong>Check-in:</strong> {check_in}</p>
                    <p><strong>Check-out:</strong> {check_out}</p>
                    <p><strong>Total:</strong> {currency} {total_amount}</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return html

# Example usage
if __name__ == "__main__":
    # Test email
    test_booking = {
        "pnr": "ABC123",
        "departure_city": "Mexico City (MEX)",
        "arrival_city": "New York (JFK)",
        "departure_date": "2026-01-20 10:30",
        "passenger_name": "John Doe",
        "total_amount": "450.00",
        "currency": "USD"
    }
    
    EmailService.send_booking_confirmation(
        to_email="test@example.com",
        booking_data=test_booking,
        booking_type="flight"
    )
