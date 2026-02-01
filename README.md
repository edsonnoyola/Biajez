# Biajez - Executive Travel OS 🌍✈️

AI-powered travel booking platform with WhatsApp integration, real-time flight/hotel search, and intelligent booking management.

## Features

- ✈️ **Flight Search & Booking** - Amadeus + Duffel integration
- 🏨 **Hotel Booking** - LiteAPI integration  
- 📱 **WhatsApp Bot** - Full conversational AI with GPT-4o
- 💳 **Payment Processing** - Stripe integration
- 🔐 **User Profiles** - Preferences, loyalty programs, travel documents
- 🌐 **Multi-language** - Spanish & English support

## Tech Stack

**Frontend:**
- React 18 + TypeScript
- Vite
- TailwindCSS
- Axios

**Backend:**
- FastAPI (Python)
- PostgreSQL + SQLAlchemy
- Redis (sessions & rate limiting)
- OpenAI GPT-4o

**APIs:**
- Amadeus (flights, hotels)
- Duffel (flights)
- LiteAPI (hotel bookings)
- Stripe (payments)
- WhatsApp Business API
- Resend (email)

## Quick Start

### Backend
```bash
cd /path/to/Biajez
pip install -r requirements.txt
python3 -m uvicorn app.main:app --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

## Environment Variables

See `.env.example` for required variables.

Key APIs needed:
- `OPENAI_API_KEY`
- `AMADEUS_API_KEY` + `AMADEUS_API_SECRET`
- `DUFFEL_ACCESS_TOKEN`
- `STRIPE_SECRET_KEY`
- `WHATSAPP_ACCESS_TOKEN`
- `LITEAPI_API_KEY`

## Production Deployment

Configured for Railway (backend) + Vercel (frontend).

See `DEPLOYMENT_GUIDE.md` for full instructions.

## Documentation

- `PRODUCTION_SETUP_GUIDE.md` - API configuration
- `DEPLOYMENT_GUIDE.md` - Deploy instructions
- `WHATSAPP_PRODUCTION_VERIFICATION.md` - WhatsApp setup
- `ENHANCEMENTS_ROADMAP.md` - Future features

## License

Proprietary - All rights reserved

## Support

Contact: admin@biajez.com
