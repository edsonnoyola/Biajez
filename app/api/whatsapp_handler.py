from fastapi import APIRouter, Request, Depends, Response
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.ai.agent import AntigravityAgent
from app.services.flight_engine import FlightAggregator
from app.services.booking_execution import BookingOrchestrator
from app.models.models import Profile
from twilio.twiml.messaging_response import MessagingResponse
import json
from datetime import datetime

router = APIRouter()
agent = AntigravityAgent()
flight_aggregator = FlightAggregator()

# Store user state (simple in-memory for MVP, use Redis in production)
user_sessions = {}

@router.post("/v1/whatsapp/webhook")
async def whatsapp_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Webhook para recibir mensajes de WhatsApp vía Twilio
    Reusa todo el backend existente (AI agent, flight search, booking)
    """
    try:
        form_data = await request.form()
        incoming_msg = form_data.get('Body', '')
        from_number = form_data.get('From', '')  # whatsapp:+521234567890
        
        print(f"📱 WhatsApp message from {from_number}: {incoming_msg}")
        
        # Get or create user session
        if from_number not in user_sessions:
            user_sessions[from_number] = {
                "messages": [],
                "user_id": f"whatsapp_{from_number.replace('whatsapp:', '').replace('+', '')}",
                "pending_flights": [],
                "selected_flight": None
            }
        
        session = user_sessions[from_number]
        
        # Check if user is selecting a flight by number
        if incoming_msg.strip().isdigit() and session.get("pending_flights"):
            flight_num = int(incoming_msg.strip()) - 1
            if 0 <= flight_num < len(session["pending_flights"]):
                selected = session["pending_flights"][flight_num]
                session["selected_flight"] = selected
                
                # Format confirmation message
                price = selected.get("price", "N/A")
                segments = selected.get("segments", [])
                if segments:
                    seg = segments[0]
                    origin = seg.get("departure_iata", "")
                    dest = seg.get("arrival_iata", "")
                    time = seg.get("departure_time", "")[:5]
                
                response_text = f"📋 *Confirmar reserva*\n\n"
                response_text += f"✈️ {origin} → {dest}\n"
                response_text += f"💰 ${price} USD\n"
                response_text += f"🕐 {time}\n\n"
                response_text += "_Responde 'Sí' para confirmar o 'No' para cancelar_"
                
                resp = MessagingResponse()
                resp.message(response_text)
                return Response(content=str(resp), media_type="application/xml")
        
        # Check if user is confirming booking
        if incoming_msg.lower() in ['si', 'sí', 'yes', 'confirmar'] and session.get("selected_flight"):
            # Execute booking using existing orchestrator
            flight = session["selected_flight"]
            offer_id = flight.get("offer_id")
            provider = flight.get("provider")
            amount = float(flight.get("price", 0))
            
            # Get or create profile
            profile = db.query(Profile).filter(Profile.user_id == session["user_id"]).first()
            if not profile:
                profile = Profile(
                    user_id=session["user_id"],
                    legal_first_name="WhatsApp",
                    legal_last_name="User",
                    email=f"{session['user_id']}@whatsapp.temp",
                    phone_number=from_number.replace('whatsapp:', ''),
                    gender="M",
                    dob=datetime.strptime("1990-01-01", "%Y-%m-%d").date(),
                    passport_number="000000000",
                    passport_expiry=datetime.strptime("2030-01-01", "%Y-%m-%d").date(),
                    passport_country="US"
                )
                db.add(profile)
                db.commit()
            
            try:
                orchestrator = BookingOrchestrator(db)
                booking_result = orchestrator.execute_booking(
                    session["user_id"], offer_id, provider, amount
                )
                
                pnr = booking_result.get("pnr", "N/A")
                response_text = f"✅ *¡Reserva confirmada!*\n\n"
                response_text += f"📝 PNR: {pnr}\n"
                response_text += f"💰 Total: ${amount} USD\n\n"
                response_text += "_Te enviaremos el ticket por email_"
                
                # Clear session
                session["selected_flight"] = None
                session["pending_flights"] = []
                
            except Exception as e:
                print(f"❌ Booking error: {e}")
                response_text = f"❌ Error al procesar la reserva: {str(e)}\n\n_Intenta nuevamente_"
            
            resp = MessagingResponse()
            resp.message(response_text)
            return Response(content=str(resp), media_type="application/xml")
        
        # Regular message - use AI agent
        session["messages"].append({"role": "user", "content": incoming_msg})
        
        # Get user context
        profile = db.query(Profile).filter(Profile.user_id == session["user_id"]).first()
        user_context = ""
        if profile:
            user_context = f"User: {profile.legal_first_name} {profile.legal_last_name}"
        
        # Call existing AI agent
        response_message = await agent.chat(session["messages"], user_context)
        
        # Handle tool calls (flight search, booking)
        if response_message.tool_calls:
            session["messages"].append(response_message.model_dump())
            
            for tool_call in response_message.tool_calls:
                function_name = tool_call.function.name
                arguments = json.loads(tool_call.function.arguments)
                tool_result = None
                
                if function_name == "search_hybrid_flights":
                    # Reuse existing flight search
                    tool_result = await flight_aggregator.search_hybrid_flights(
                        arguments["origin"], 
                        arguments["destination"], 
                        arguments["date"],
                        arguments.get("return_date"),
                        arguments.get("cabin", "ECONOMY"),
                        arguments.get("airline"),
                        arguments.get("time_of_day", "ANY")
                    )
                    tool_result = [f.dict() for f in tool_result]
                    
                    # Store top 5 flights in session
                    if tool_result:
                        session["pending_flights"] = tool_result[:5]
                
                # Append tool result
                session["messages"].append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(tool_result, default=str)
                })
            
            # Get final response
            final_response = await agent.chat(session["messages"], user_context)
            response_text = final_response.content
        else:
            response_text = response_message.content
        
        # Format response for WhatsApp
        formatted_response = format_for_whatsapp(response_text, session)
        
        # Send response via Twilio
        resp = MessagingResponse()
        resp.message(formatted_response)
        
        return Response(content=str(resp), media_type="application/xml")
        
    except Exception as e:
        print(f"❌ WhatsApp webhook error: {e}")
        import traceback
        traceback.print_exc()
        
        resp = MessagingResponse()
        resp.message("❌ Error procesando tu mensaje. Intenta nuevamente.")
        return Response(content=str(resp), media_type="application/xml")

def format_for_whatsapp(text: str, session: dict) -> str:
    """
    Format AI response for WhatsApp (add emojis, structure, flight list)
    Shows price, time, route, airline, stops, and change/refund conditions.
    """
    # If there are pending flights, add numbered list
    if session.get("pending_flights"):
        flights = session["pending_flights"]
        flight_list = "\n\n✈️ *Vuelos encontrados:*\n"
        for i, flight in enumerate(flights, 1):
            price = flight.get("price", "N/A")
            currency = flight.get("currency", "USD")
            segments = flight.get("segments", [])
            if segments:
                seg = segments[0]
                time_raw = seg.get("departure_time", "")
                time = time_raw[11:16] if len(time_raw) > 16 else time_raw[:5]
                origin = seg.get("departure_iata", "")
                dest = seg.get("arrival_iata", "")
                carrier = seg.get("carrier_code", "")
                flight_num = seg.get("flight_number", "")

                # Stops indicator
                num_segments = len(segments)
                stops = "Directo" if num_segments == 1 else f"{num_segments - 1} escala{'s' if num_segments > 2 else ''}"

                # Change/refund conditions from Duffel docs
                metadata = flight.get("metadata") or {}
                refundable = flight.get("refundable", False)
                changeable = metadata.get("changeable", False)
                change_penalty = metadata.get("change_penalty")

                # Build conditions tag (compact for WhatsApp)
                conditions = []
                if changeable:
                    if change_penalty and float(change_penalty) > 0:
                        conditions.append(f"Cambio: ${change_penalty}")
                    else:
                        conditions.append("Cambio gratis")
                else:
                    conditions.append("Sin cambios")

                if refundable:
                    conditions.append("Reembolsable")

                cond_str = " | ".join(conditions)

                flight_list += f"\n*{i}.* ${price} {currency}"
                flight_list += f"\n   {carrier}{flight_num} {time} {origin}→{dest}"
                flight_list += f"\n   {stops} | {cond_str}\n"

        text += flight_list
        text += "\n_Responde con el numero para reservar_"

    # Add emoji to make it more friendly
    if "encontré" in text.lower() or "found" in text.lower():
        text = "🔍 " + text

    return text
