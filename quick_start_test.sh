#!/bin/bash

# Quick Start Script for Testing Airline Credits
# This script helps you start the servers and run tests

echo "🚀 AIRLINE CREDITS - QUICK START"
echo "================================"
echo ""

# Check if backend is running
echo "Checking if backend is running..."
if curl -s http://localhost:8000/docs > /dev/null 2>&1; then
    echo "✅ Backend is running on port 8000"
else
    echo "❌ Backend is NOT running"
    echo ""
    echo "To start backend:"
    echo "  cd /Users/end/Downloads/Biajez"
    echo "  uvicorn app.main:app --reload"
    echo ""
fi

# Check if frontend is running
echo "Checking if frontend is running..."
if curl -s http://localhost:5173 > /dev/null 2>&1; then
    echo "✅ Frontend is running on port 5173"
else
    echo "❌ Frontend is NOT running"
    echo ""
    echo "To start frontend:"
    echo "  cd /Users/end/Downloads/Biajez/frontend"
    echo "  npm run dev"
    echo ""
fi

echo ""
echo "📋 Next Steps:"
echo "1. Start servers if not running (see commands above)"
echo "2. Run backend tests: python3 test_credits_complete.py"
echo "3. Open browser: http://localhost:5173"
echo "4. Follow TESTING_GUIDE.md for manual UI tests"
echo ""
echo "📖 Documentation:"
echo "  - TESTING_GUIDE.md - Complete testing guide"
echo "  - walkthrough.md - Implementation details"
echo ""
