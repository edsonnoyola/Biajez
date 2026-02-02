"""
Currency Exchange Service - Get exchange rates
Uses exchangerate-api.com (free tier)
"""

import httpx
from typing import Dict, Optional
import os

class CurrencyService:
    """Get currency exchange rates"""

    # Common currency codes by country/city
    CURRENCY_MAP = {
        # North America
        "US": "USD", "USA": "USD", "MX": "MXN", "MEX": "MXN", "CA": "CAD", "CAN": "CAD",
        # Europe
        "ES": "EUR", "FR": "EUR", "DE": "EUR", "IT": "EUR", "PT": "EUR", "NL": "EUR",
        "GB": "GBP", "UK": "GBP", "CH": "CHF",
        # Latin America
        "BR": "BRL", "AR": "ARS", "CO": "COP", "CL": "CLP", "PE": "PEN",
        # Asia
        "JP": "JPY", "CN": "CNY", "KR": "KRW", "TH": "THB", "IN": "INR",
        # Cities to currency
        "MIAMI": "USD", "NEW YORK": "USD", "LOS ANGELES": "USD", "CANCUN": "MXN",
        "MADRID": "EUR", "BARCELONA": "EUR", "PARIS": "EUR", "ROME": "EUR",
        "LONDON": "GBP", "TOKYO": "JPY", "DUBAI": "AED",
    }

    def __init__(self):
        self.base_url = "https://api.exchangerate-api.com/v4/latest"

    async def get_exchange_rate(self, from_currency: str = "USD", to_currency: str = "MXN") -> Dict:
        """
        Get exchange rate between two currencies

        Args:
            from_currency: Source currency code (default USD)
            to_currency: Target currency code (default MXN)

        Returns:
            Exchange rate data
        """
        try:
            url = f"{self.base_url}/{from_currency.upper()}"

            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(url)

                if response.status_code != 200:
                    return {"error": "Could not get exchange rate"}

                data = response.json()
                rates = data.get("rates", {})

                to_upper = to_currency.upper()
                if to_upper not in rates:
                    return {"error": f"Currency {to_currency} not found"}

                rate = rates[to_upper]

                return {
                    "from": from_currency.upper(),
                    "to": to_upper,
                    "rate": rate,
                    "inverse": round(1/rate, 4) if rate else 0,
                    "examples": {
                        "100": round(100 * rate, 2),
                        "500": round(500 * rate, 2),
                        "1000": round(1000 * rate, 2),
                    }
                }

        except Exception as e:
            print(f"Currency API error: {e}")
            return {"error": str(e)}

    def get_currency_for_destination(self, destination: str) -> str:
        """Get currency code for a destination city/country"""
        dest_upper = destination.upper().strip()

        # Check direct match
        if dest_upper in self.CURRENCY_MAP:
            return self.CURRENCY_MAP[dest_upper]

        # Check if destination contains a known city/country
        for key, currency in self.CURRENCY_MAP.items():
            if key in dest_upper or dest_upper in key:
                return currency

        # Default to USD
        return "USD"

    def format_for_whatsapp(self, exchange: Dict, destination: str = "") -> str:
        """Format exchange rate for WhatsApp"""
        if exchange.get("error"):
            return f"No pude obtener el tipo de cambio: {exchange['error']}"

        from_curr = exchange.get("from", "USD")
        to_curr = exchange.get("to", "MXN")
        rate = exchange.get("rate", 0)
        examples = exchange.get("examples", {})

        msg = f"*Tipo de cambio*"
        if destination:
            msg += f" para {destination}"
        msg += "\n\n"

        msg += f"1 {from_curr} = {rate:.2f} {to_curr}\n\n"

        msg += "*Referencias:*\n"
        for amount, converted in examples.items():
            msg += f"• ${amount} {from_curr} = ${converted:,.2f} {to_curr}\n"

        return msg
