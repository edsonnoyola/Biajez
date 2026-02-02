"""
Weather Service - Get weather forecast for destinations
Uses wttr.in API (no API key required)
"""

import httpx
from typing import Dict, Optional
from datetime import datetime

class WeatherService:
    """Get weather forecasts for travel destinations"""

    def __init__(self):
        self.base_url = "https://wttr.in"

    async def get_weather(self, city: str, days: int = 3) -> Dict:
        """
        Get weather forecast for a city

        Args:
            city: City name or IATA code
            days: Number of days to forecast (1-3)

        Returns:
            Weather data dict
        """
        try:
            # wttr.in accepts city names and returns JSON
            url = f"{self.base_url}/{city}?format=j1"

            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(url)

                if response.status_code != 200:
                    return {"error": f"Could not get weather for {city}"}

                data = response.json()

                # Parse the response
                current = data.get("current_condition", [{}])[0]
                forecast = data.get("weather", [])[:days]

                result = {
                    "city": city,
                    "current": {
                        "temp_c": current.get("temp_C", "N/A"),
                        "temp_f": current.get("temp_F", "N/A"),
                        "condition": current.get("weatherDesc", [{}])[0].get("value", "N/A"),
                        "humidity": current.get("humidity", "N/A"),
                        "wind_kmh": current.get("windspeedKmph", "N/A"),
                    },
                    "forecast": []
                }

                for day in forecast:
                    result["forecast"].append({
                        "date": day.get("date", "N/A"),
                        "max_c": day.get("maxtempC", "N/A"),
                        "min_c": day.get("mintempC", "N/A"),
                        "max_f": day.get("maxtempF", "N/A"),
                        "min_f": day.get("mintempF", "N/A"),
                        "condition": day.get("hourly", [{}])[4].get("weatherDesc", [{}])[0].get("value", "N/A"),
                    })

                return result

        except Exception as e:
            print(f"Weather API error: {e}")
            return {"error": str(e)}

    def format_for_whatsapp(self, weather: Dict) -> str:
        """Format weather data for WhatsApp message"""
        if weather.get("error"):
            return f"No pude obtener el clima: {weather['error']}"

        city = weather.get("city", "")
        current = weather.get("current", {})
        forecast = weather.get("forecast", [])

        msg = f"*Clima en {city.title()}*\n\n"
        msg += f"Ahora: {current['temp_c']}°C ({current['temp_f']}°F)\n"
        msg += f"{current['condition']}\n"
        msg += f"Humedad: {current['humidity']}%\n\n"

        if forecast:
            msg += "*Próximos días:*\n"
            for day in forecast:
                date_str = day['date']
                try:
                    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                    date_str = date_obj.strftime("%a %d")
                except:
                    pass
                msg += f"• {date_str}: {day['min_c']}° - {day['max_c']}°C, {day['condition']}\n"

        return msg
