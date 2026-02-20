"""
Email Service for sending booking confirmations, cancellations, and change notifications.
Uses Resend (simple, 100 emails/day free tier).

Supports:
- Flight booking confirmation (rich template with segments, airline, eTicket)
- Hotel booking confirmation
- Flight cancellation confirmation
- Flight change confirmation
- Airline-initiated change notification
"""
import os
import resend
from typing import Dict, Optional, List
from datetime import datetime

# Configure Resend API key
resend.api_key = os.getenv("RESEND_API_KEY", "")


class EmailService:
    """Service for sending transactional emails"""

    FROM_EMAIL = os.getenv("RESEND_FROM_EMAIL", "Biajez <onboarding@resend.dev>")

    # ─── Public Send Methods ────────────────────────────────────────────

    @staticmethod
    def send_booking_confirmation(
        to_email: str,
        booking_data: Dict,
        booking_type: str = "flight"
    ) -> bool:
        """
        Send booking confirmation email.

        Args:
            to_email: Recipient email
            booking_data: Dictionary with booking details
                For flights: pnr, departure_city, arrival_city, departure_date,
                             passenger_name, total_amount, currency,
                             segments (list), airline_name, eticket_number
                For hotels: booking_reference, hotel_name, check_in_date,
                            check_out_date, guest_name, total_amount, currency
            booking_type: "flight" or "hotel"

        Returns:
            bool: True if sent successfully
        """
        try:
            if booking_type == "flight":
                pnr = booking_data.get('pnr', 'N/A')
                subject = f"Confirmacion de vuelo - {pnr}"
                html_content = EmailService._generate_flight_email(booking_data)
            else:
                ref = booking_data.get('booking_reference', 'N/A')
                subject = f"Confirmacion de hotel - {ref}"
                html_content = EmailService._generate_hotel_email(booking_data)

            params = {
                "from": EmailService.FROM_EMAIL,
                "to": [to_email],
                "subject": subject,
                "html": html_content,
            }

            response = resend.Emails.send(params)
            print(f"📧 Email sent to {to_email}: {response}")
            return True

        except Exception as e:
            print(f"❌ Error sending email: {e}")
            return False

    @staticmethod
    def send_cancellation_email(
        to_email: str,
        cancellation_data: Dict
    ) -> bool:
        """
        Send flight cancellation confirmation email.

        Args:
            to_email: Recipient email
            cancellation_data: Dict with pnr, passenger_name, route,
                               refund_amount, currency, credit_amount
        """
        try:
            pnr = cancellation_data.get('pnr', 'N/A')
            subject = f"Cancelacion confirmada - {pnr}"
            html_content = EmailService._generate_cancellation_email(cancellation_data)

            params = {
                "from": EmailService.FROM_EMAIL,
                "to": [to_email],
                "subject": subject,
                "html": html_content,
            }

            response = resend.Emails.send(params)
            print(f"📧 Cancellation email sent to {to_email}: {response}")
            return True

        except Exception as e:
            print(f"❌ Error sending cancellation email: {e}")
            return False

    @staticmethod
    def send_change_confirmation_email(
        to_email: str,
        change_data: Dict
    ) -> bool:
        """
        Send flight change confirmation email.

        Args:
            to_email: Recipient email
            change_data: Dict with pnr, passenger_name, old_route, new_route,
                         new_departure_date, change_fee, new_total, currency
        """
        try:
            pnr = change_data.get('pnr', 'N/A')
            subject = f"Cambio de vuelo confirmado - {pnr}"
            html_content = EmailService._generate_change_email(change_data)

            params = {
                "from": EmailService.FROM_EMAIL,
                "to": [to_email],
                "subject": subject,
                "html": html_content,
            }

            response = resend.Emails.send(params)
            print(f"📧 Change confirmation email sent to {to_email}: {response}")
            return True

        except Exception as e:
            print(f"❌ Error sending change email: {e}")
            return False

    @staticmethod
    def send_airline_change_alert_email(
        to_email: str,
        alert_data: Dict
    ) -> bool:
        """
        Send airline-initiated change alert email.

        Args:
            to_email: Recipient email
            alert_data: Dict with pnr, passenger_name, old_details, new_segments
        """
        try:
            pnr = alert_data.get('pnr', 'N/A')
            subject = f"Cambio de aerolinea en tu vuelo - {pnr}"
            html_content = EmailService._generate_airline_change_alert_email(alert_data)

            params = {
                "from": EmailService.FROM_EMAIL,
                "to": [to_email],
                "subject": subject,
                "html": html_content,
            }

            response = resend.Emails.send(params)
            print(f"📧 Airline change alert email sent to {to_email}: {response}")
            return True

        except Exception as e:
            print(f"❌ Error sending airline change alert email: {e}")
            return False

    # ─── Shared CSS ─────────────────────────────────────────────────────

    @staticmethod
    def _base_styles() -> str:
        return """
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', sans-serif;
                line-height: 1.6;
                color: #1a1a2e;
                max-width: 600px;
                margin: 0 auto;
                padding: 0;
                background-color: #f0f2f5;
            }
            .container {
                background-color: #ffffff;
                border-radius: 16px;
                overflow: hidden;
                margin: 20px auto;
                box-shadow: 0 4px 24px rgba(0,0,0,0.08);
            }
            .content {
                padding: 32px 28px;
            }
            .detail-card {
                background: #f8f9fb;
                border-radius: 12px;
                padding: 20px;
                margin: 16px 0;
                border: 1px solid #e8ebf0;
            }
            .detail-row {
                display: flex;
                justify-content: space-between;
                padding: 8px 0;
                border-bottom: 1px solid #f0f2f5;
            }
            .detail-row:last-child {
                border-bottom: none;
            }
            .detail-label {
                font-size: 13px;
                color: #6b7280;
                font-weight: 500;
            }
            .detail-value {
                font-size: 14px;
                color: #1a1a2e;
                font-weight: 600;
            }
            .pnr-box {
                text-align: center;
                padding: 16px;
                background: linear-gradient(135deg, #f0f4ff, #e8ecff);
                border-radius: 12px;
                margin: 16px 0;
            }
            .pnr-label {
                font-size: 11px;
                color: #6b7280;
                text-transform: uppercase;
                letter-spacing: 1px;
                font-weight: 600;
            }
            .pnr-value {
                font-size: 28px;
                font-weight: 800;
                color: #3b5bdb;
                letter-spacing: 3px;
                font-family: 'SF Mono', 'Courier New', monospace;
            }
            .segment-card {
                background: #ffffff;
                border: 1px solid #e8ebf0;
                border-radius: 12px;
                padding: 16px;
                margin: 12px 0;
            }
            .segment-route {
                display: flex;
                align-items: center;
                justify-content: space-between;
                margin-bottom: 8px;
            }
            .segment-city {
                font-size: 24px;
                font-weight: 700;
                color: #1a1a2e;
            }
            .segment-arrow {
                color: #9ca3af;
                font-size: 20px;
                margin: 0 12px;
            }
            .segment-time {
                font-size: 13px;
                color: #6b7280;
            }
            .segment-airline {
                font-size: 12px;
                color: #3b5bdb;
                font-weight: 600;
                margin-top: 4px;
            }
            .total-box {
                text-align: center;
                padding: 16px;
                background: linear-gradient(135deg, #ecfdf5, #d1fae5);
                border-radius: 12px;
                margin: 16px 0;
            }
            .total-label {
                font-size: 12px;
                color: #059669;
                font-weight: 600;
            }
            .total-value {
                font-size: 24px;
                font-weight: 800;
                color: #047857;
            }
            .notice {
                padding: 14px 16px;
                background: #fffbeb;
                border-left: 4px solid #f59e0b;
                border-radius: 0 8px 8px 0;
                margin: 16px 0;
                font-size: 13px;
                color: #92400e;
            }
            .footer {
                text-align: center;
                padding: 24px 28px;
                color: #9ca3af;
                font-size: 12px;
                border-top: 1px solid #f0f2f5;
            }
            .footer a {
                color: #3b5bdb;
                text-decoration: none;
            }
        """

    # ─── Flight Booking Confirmation Email ──────────────────────────────

    @staticmethod
    def _generate_flight_email(booking_data: Dict) -> str:
        """Generate rich HTML email for flight booking confirmation"""

        pnr = booking_data.get('pnr', 'N/A')
        departure = booking_data.get('departure_city', 'N/A')
        arrival = booking_data.get('arrival_city', 'N/A')
        departure_date = booking_data.get('departure_date', 'N/A')
        passenger_name = booking_data.get('passenger_name', 'Pasajero')
        total_amount = booking_data.get('total_amount', '0')
        currency = booking_data.get('currency', 'USD')
        airline_name = booking_data.get('airline_name', '')
        eticket = booking_data.get('eticket_number', '')
        segments = booking_data.get('segments', [])

        # Build segments HTML
        segments_html = ""
        if segments:
            for seg in segments:
                origin = seg.get('origin', '???')
                destination = seg.get('destination', '???')
                dep_time = seg.get('departure_time', '')
                arr_time = seg.get('arrival_time', '')
                carrier = seg.get('carrier_code', '')
                flight_num = seg.get('number', '')

                # Format times
                dep_formatted = EmailService._format_datetime(dep_time)
                arr_formatted = EmailService._format_datetime(arr_time)

                segments_html += f"""
                <div class="segment-card">
                    <div class="segment-route">
                        <div>
                            <div class="segment-city">{origin}</div>
                            <div class="segment-time">{dep_formatted}</div>
                        </div>
                        <div class="segment-arrow">&#9992;</div>
                        <div style="text-align: right;">
                            <div class="segment-city">{destination}</div>
                            <div class="segment-time">{arr_formatted}</div>
                        </div>
                    </div>
                    <div class="segment-airline">{carrier} {flight_num}{' - ' + airline_name if airline_name else ''}</div>
                </div>
                """
        else:
            # Fallback: simple route display
            segments_html = f"""
            <div class="segment-card">
                <div class="segment-route">
                    <div class="segment-city">{departure}</div>
                    <div class="segment-arrow">&#9992;</div>
                    <div class="segment-city" style="text-align: right;">{arrival}</div>
                </div>
                <div class="segment-time" style="text-align: center;">{departure_date}</div>
            </div>
            """

        # eTicket row
        eticket_html = ""
        if eticket:
            eticket_html = f"""
            <div class="detail-row">
                <span class="detail-label">E-Ticket</span>
                <span class="detail-value" style="font-family: monospace;">{eticket}</span>
            </div>
            """

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Confirmacion de Vuelo</title>
            <style>{EmailService._base_styles()}</style>
        </head>
        <body>
            <div class="container">
                <!-- Header -->
                <div style="background: linear-gradient(135deg, #3b5bdb 0%, #5b4bdb 100%); color: white; padding: 32px 28px; text-align: center;">
                    <div style="font-size: 40px; margin-bottom: 8px;">&#9992;</div>
                    <h1 style="margin: 0; font-size: 22px; font-weight: 700;">Vuelo Confirmado</h1>
                    <p style="margin: 4px 0 0; opacity: 0.8; font-size: 14px;">Tu reserva fue procesada exitosamente</p>
                </div>

                <div class="content">
                    <p style="margin-top: 0;">Hola <strong>{passenger_name}</strong>,</p>
                    <p>Tu vuelo ha sido reservado con exito. Aqui tienes los detalles:</p>

                    <!-- PNR -->
                    <div class="pnr-box">
                        <div class="pnr-label">Codigo de Reserva (PNR)</div>
                        <div class="pnr-value">{pnr}</div>
                    </div>

                    <!-- Segments -->
                    <h3 style="font-size: 15px; color: #374151; margin-bottom: 8px;">Itinerario</h3>
                    {segments_html}

                    <!-- Booking Details -->
                    <div class="detail-card">
                        <div class="detail-row">
                            <span class="detail-label">Pasajero</span>
                            <span class="detail-value">{passenger_name}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Fecha</span>
                            <span class="detail-value">{departure_date}</span>
                        </div>
                        {eticket_html}
                    </div>

                    <!-- Total -->
                    <div class="total-box">
                        <div class="total-label">Total Pagado</div>
                        <div class="total-value">${total_amount} {currency}</div>
                    </div>

                    <!-- Notice -->
                    <div class="notice">
                        <strong>Importante:</strong> Llega al aeropuerto al menos 2 horas antes de la salida para vuelos nacionales y 3 horas para internacionales. Lleva tu identificacion oficial.
                    </div>

                    <p style="font-size: 13px; color: #6b7280;">Puedes ver tu itinerario completo en la app de Biajez o escribiendo <strong>'itinerario'</strong> por WhatsApp.</p>
                </div>

                <div class="footer">
                    <p>Este es un correo automatico de <strong>Biajez</strong>.</p>
                    <p>Si tienes preguntas, contacta soporte.</p>
                </div>
            </div>
        </body>
        </html>
        """

        return html

    # ─── Hotel Booking Confirmation Email ───────────────────────────────

    @staticmethod
    def _generate_hotel_email(booking_data: Dict) -> str:
        """Generate HTML email for hotel booking confirmation"""

        booking_ref = booking_data.get('booking_reference', 'N/A')
        hotel_name = booking_data.get('hotel_name', 'N/A')
        check_in = booking_data.get('check_in_date', 'N/A')
        check_out = booking_data.get('check_out_date', 'N/A')
        guest_name = booking_data.get('guest_name', 'Huesped')
        total_amount = booking_data.get('total_amount', '0')
        currency = booking_data.get('currency', 'USD')

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Confirmacion de Hotel</title>
            <style>{EmailService._base_styles()}</style>
        </head>
        <body>
            <div class="container">
                <div style="background: linear-gradient(135deg, #e040a0 0%, #f56565 100%); color: white; padding: 32px 28px; text-align: center;">
                    <div style="font-size: 40px; margin-bottom: 8px;">&#127976;</div>
                    <h1 style="margin: 0; font-size: 22px; font-weight: 700;">Hotel Confirmado</h1>
                    <p style="margin: 4px 0 0; opacity: 0.8; font-size: 14px;">Tu reservacion esta lista</p>
                </div>

                <div class="content">
                    <p style="margin-top: 0;">Hola <strong>{guest_name}</strong>,</p>
                    <p>Tu reservacion en <strong>{hotel_name}</strong> ha sido confirmada:</p>

                    <div class="pnr-box" style="background: linear-gradient(135deg, #fff0f6, #ffe0ec);">
                        <div class="pnr-label">Confirmacion</div>
                        <div class="pnr-value" style="color: #e040a0;">{booking_ref}</div>
                    </div>

                    <div class="detail-card">
                        <div class="detail-row">
                            <span class="detail-label">Hotel</span>
                            <span class="detail-value">{hotel_name}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Check-in</span>
                            <span class="detail-value">{check_in}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Check-out</span>
                            <span class="detail-value">{check_out}</span>
                        </div>
                    </div>

                    <div class="total-box">
                        <div class="total-label">Total Pagado</div>
                        <div class="total-value">${total_amount} {currency}</div>
                    </div>
                </div>

                <div class="footer">
                    <p>Este es un correo automatico de <strong>Biajez</strong>.</p>
                </div>
            </div>
        </body>
        </html>
        """

        return html

    # ─── Cancellation Confirmation Email ────────────────────────────────

    @staticmethod
    def _generate_cancellation_email(data: Dict) -> str:
        """Generate HTML email for flight cancellation confirmation"""

        pnr = data.get('pnr', 'N/A')
        passenger_name = data.get('passenger_name', 'Pasajero')
        route = data.get('route', 'N/A')
        refund_amount = data.get('refund_amount', 0)
        currency = data.get('currency', 'USD')
        credit_amount = data.get('credit_amount', 0)

        refund_html = ""
        if refund_amount and float(refund_amount) > 0:
            refund_html = f"""
            <div class="total-box" style="background: linear-gradient(135deg, #fff7ed, #ffedd5);">
                <div class="total-label" style="color: #c2410c;">Reembolso</div>
                <div class="total-value" style="color: #ea580c;">${refund_amount} {currency}</div>
            </div>
            """

        credit_html = ""
        if credit_amount and float(credit_amount) > 0:
            credit_html = f"""
            <div class="detail-card">
                <div class="detail-row">
                    <span class="detail-label">Credito de Aerolinea</span>
                    <span class="detail-value" style="color: #059669;">${credit_amount} {currency}</span>
                </div>
                <p style="font-size: 12px; color: #6b7280; margin: 8px 0 0;">
                    Este credito estara disponible para futuras reservaciones.
                </p>
            </div>
            """

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Cancelacion Confirmada</title>
            <style>{EmailService._base_styles()}</style>
        </head>
        <body>
            <div class="container">
                <div style="background: linear-gradient(135deg, #dc2626 0%, #991b1b 100%); color: white; padding: 32px 28px; text-align: center;">
                    <div style="font-size: 40px; margin-bottom: 8px;">&#10060;</div>
                    <h1 style="margin: 0; font-size: 22px; font-weight: 700;">Vuelo Cancelado</h1>
                    <p style="margin: 4px 0 0; opacity: 0.8; font-size: 14px;">Tu reserva ha sido cancelada</p>
                </div>

                <div class="content">
                    <p style="margin-top: 0;">Hola <strong>{passenger_name}</strong>,</p>
                    <p>Tu vuelo ha sido cancelado exitosamente. Aqui tienes el resumen:</p>

                    <div class="detail-card">
                        <div class="detail-row">
                            <span class="detail-label">PNR</span>
                            <span class="detail-value" style="font-family: monospace; letter-spacing: 2px;">{pnr}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Ruta</span>
                            <span class="detail-value">{route}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Estado</span>
                            <span class="detail-value" style="color: #dc2626;">Cancelado</span>
                        </div>
                    </div>

                    {refund_html}
                    {credit_html}

                    <p style="font-size: 13px; color: #6b7280;">
                        Si tienes preguntas sobre tu reembolso o credito, escribe <strong>'creditos'</strong> por WhatsApp o contacta soporte.
                    </p>
                </div>

                <div class="footer">
                    <p>Este es un correo automatico de <strong>Biajez</strong>.</p>
                </div>
            </div>
        </body>
        </html>
        """

        return html

    # ─── Flight Change Confirmation Email ───────────────────────────────

    @staticmethod
    def _generate_change_email(data: Dict) -> str:
        """Generate HTML email for flight change confirmation"""

        pnr = data.get('pnr', 'N/A')
        passenger_name = data.get('passenger_name', 'Pasajero')
        old_route = data.get('old_route', 'N/A')
        new_route = data.get('new_route', 'N/A')
        new_departure_date = data.get('new_departure_date', 'N/A')
        change_fee = data.get('change_fee', '0')
        new_total = data.get('new_total', '0')
        currency = data.get('currency', 'USD')
        new_segments = data.get('new_segments', [])

        segments_html = ""
        for seg in new_segments:
            origin = seg.get('origin', '???')
            dest = seg.get('destination', '???')
            dep = EmailService._format_datetime(seg.get('departing_at', ''))
            arr = EmailService._format_datetime(seg.get('arriving_at', ''))
            carrier = seg.get('carrier', '')

            segments_html += f"""
            <div class="segment-card">
                <div class="segment-route">
                    <div>
                        <div class="segment-city">{origin}</div>
                        <div class="segment-time">{dep}</div>
                    </div>
                    <div class="segment-arrow">&#9992;</div>
                    <div style="text-align: right;">
                        <div class="segment-city">{dest}</div>
                        <div class="segment-time">{arr}</div>
                    </div>
                </div>
                {f'<div class="segment-airline">{carrier}</div>' if carrier else ''}
            </div>
            """

        change_fee_html = ""
        if change_fee and float(change_fee) > 0:
            change_fee_html = f"""
            <div class="detail-row">
                <span class="detail-label">Cargo por cambio</span>
                <span class="detail-value" style="color: #dc2626;">${change_fee} {currency}</span>
            </div>
            """

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Cambio de Vuelo Confirmado</title>
            <style>{EmailService._base_styles()}</style>
        </head>
        <body>
            <div class="container">
                <div style="background: linear-gradient(135deg, #059669 0%, #047857 100%); color: white; padding: 32px 28px; text-align: center;">
                    <div style="font-size: 40px; margin-bottom: 8px;">&#128260;</div>
                    <h1 style="margin: 0; font-size: 22px; font-weight: 700;">Cambio de Vuelo Confirmado</h1>
                    <p style="margin: 4px 0 0; opacity: 0.8; font-size: 14px;">Tu itinerario ha sido actualizado</p>
                </div>

                <div class="content">
                    <p style="margin-top: 0;">Hola <strong>{passenger_name}</strong>,</p>
                    <p>Tu cambio de vuelo ha sido procesado exitosamente.</p>

                    <div class="pnr-box">
                        <div class="pnr-label">PNR</div>
                        <div class="pnr-value">{pnr}</div>
                    </div>

                    <!-- Old route strikethrough -->
                    <div class="detail-card" style="opacity: 0.6;">
                        <h4 style="margin: 0 0 8px; color: #6b7280; font-size: 12px;">VUELO ANTERIOR</h4>
                        <div style="text-decoration: line-through; color: #9ca3af; font-size: 18px; text-align: center;">
                            {old_route}
                        </div>
                    </div>

                    <!-- New segments -->
                    <h3 style="font-size: 15px; color: #059669; margin-bottom: 8px;">Nuevo Itinerario</h3>
                    {segments_html if segments_html else f'<div class="segment-card"><div style="text-align: center; font-size: 18px; font-weight: 600;">{new_route}</div><div class="segment-time" style="text-align: center;">{new_departure_date}</div></div>'}

                    <!-- Costs -->
                    <div class="detail-card">
                        {change_fee_html}
                        <div class="detail-row">
                            <span class="detail-label">Nuevo Total</span>
                            <span class="detail-value" style="color: #059669; font-size: 16px;">${new_total} {currency}</span>
                        </div>
                    </div>

                    <p style="font-size: 13px; color: #6b7280;">
                        Escribe <strong>'itinerario'</strong> por WhatsApp para ver tu nuevo vuelo.
                    </p>
                </div>

                <div class="footer">
                    <p>Este es un correo automatico de <strong>Biajez</strong>.</p>
                </div>
            </div>
        </body>
        </html>
        """

        return html

    # ─── Airline-Initiated Change Alert Email ───────────────────────────

    @staticmethod
    def _generate_airline_change_alert_email(data: Dict) -> str:
        """Generate HTML email for airline-initiated schedule changes"""

        pnr = data.get('pnr', 'N/A')
        passenger_name = data.get('passenger_name', 'Pasajero')
        old_details = data.get('old_details', {})
        new_segments = data.get('new_segments', [])

        old_route = f"{old_details.get('departure_city', '?')} → {old_details.get('arrival_city', '?')}"
        old_date = old_details.get('departure_date', 'N/A')

        new_segments_html = ""
        for seg in new_segments:
            origin = seg.get('origin', '?')
            dest = seg.get('destination', '?')
            dep = seg.get('departing_at', '')
            dep_formatted = EmailService._format_datetime(dep) if dep else 'N/A'
            carrier = seg.get('carrier', '')

            new_segments_html += f"""
            <div class="segment-card" style="border-color: #fbbf24;">
                <div class="segment-route">
                    <div class="segment-city">{origin}</div>
                    <div class="segment-arrow">&#9992;</div>
                    <div class="segment-city" style="text-align: right;">{dest}</div>
                </div>
                <div class="segment-time" style="text-align: center;">{dep_formatted}</div>
                {f'<div class="segment-airline">{carrier}</div>' if carrier else ''}
            </div>
            """

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Cambio de Aerolinea</title>
            <style>{EmailService._base_styles()}</style>
        </head>
        <body>
            <div class="container">
                <div style="background: linear-gradient(135deg, #d97706 0%, #b45309 100%); color: white; padding: 32px 28px; text-align: center;">
                    <div style="font-size: 40px; margin-bottom: 8px;">&#9888;</div>
                    <h1 style="margin: 0; font-size: 22px; font-weight: 700;">Cambio en tu Vuelo</h1>
                    <p style="margin: 4px 0 0; opacity: 0.8; font-size: 14px;">La aerolinea modifico tu itinerario</p>
                </div>

                <div class="content">
                    <p style="margin-top: 0;">Hola <strong>{passenger_name}</strong>,</p>
                    <p>La aerolinea ha realizado cambios en tu vuelo <strong>{pnr}</strong>. Revisa los nuevos detalles:</p>

                    <!-- Previous schedule -->
                    <div class="detail-card" style="opacity: 0.6; border-color: #fca5a5;">
                        <h4 style="margin: 0 0 8px; color: #dc2626; font-size: 12px;">HORARIO ANTERIOR</h4>
                        <div style="text-decoration: line-through; color: #9ca3af;">
                            {old_route} &middot; {old_date}
                        </div>
                    </div>

                    <!-- New schedule -->
                    <h3 style="font-size: 15px; color: #d97706; margin-bottom: 8px;">Nuevo Horario</h3>
                    {new_segments_html if new_segments_html else '<p style="color: #6b7280;">Los detalles del nuevo horario estan disponibles en la app.</p>'}

                    <div class="notice">
                        <strong>Accion requerida:</strong> Revisa los cambios en tu app de Biajez. Si el nuevo horario no te funciona, puedes rechazar el cambio y recibir un reembolso o credito.
                    </div>

                    <p style="font-size: 13px; color: #6b7280;">
                        Escribe <strong>'itinerario'</strong> por WhatsApp para mas detalles.
                    </p>
                </div>

                <div class="footer">
                    <p>Este es un correo automatico de <strong>Biajez</strong>.</p>
                </div>
            </div>
        </body>
        </html>
        """

        return html

    # ─── Helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _format_datetime(iso_str: str) -> str:
        """Format ISO datetime string to readable Spanish format"""
        if not iso_str:
            return "N/A"
        try:
            dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
            months = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun',
                      'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
            return f"{dt.day} {months[dt.month-1]} {dt.strftime('%H:%M')}"
        except Exception:
            # Fallback: return first 16 chars
            return iso_str[:16] if len(iso_str) > 16 else iso_str
