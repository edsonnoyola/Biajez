#!/bin/bash
# Automated Vercel Deployment Script

echo "🚀 Starting Vercel Deployment..."
echo ""

cd frontend

# Set environment variables for non-interactive deployment
export VERCEL_ORG_ID="" # Will be set during first run
export VERCEL_PROJECT_ID="" # Will be set during first run

# Deploy to Vercel with environment variables
echo "📦 Deploying frontend to Vercel..."
vercel deploy --prod \
  --yes \
  --env VITE_API_URL=https://biajez-ah0g.onrender.com \
  --env VITE_STRIPE_PUBLISHABLE_KEY=pk_test_51SLzdO0ikaK8tETEV1QaPWaoXQeps3u4L8jW8q2mElOEBGr35hBrHbWNRfzyMy7sYLR2AlmjAOoC4It272gJZM8100ppJLap4v \
  --build-env VITE_API_URL=https://biajez-ah0g.onrender.com \
  --build-env VITE_STRIPE_PUBLISHABLE_KEY=pk_test_51SLzdO0ikaK8tETEV1QaPWaoXQeps3u4L8jW8q2mElOEBGr35hBrHbWNRfzyMy7sYLR2AlmjAOoC4It272gJZM8100ppJLap4v

echo ""
echo "✅ Deployment complete!"
echo "🌐 Your app should be live at the URL shown above"
