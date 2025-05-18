"""
Sample weather tool implementation.
"""

from typing import Any, Dict

import logging
import httpx

from mcp.server.fastmcp import Context
from mcp_host import app_setup

NWS_API_BASE = "https://api.weather.gov"
USER_AGENT = "weather-app/1.0"


async def request_nws(url: str) -> dict[str, Any] | None:
    """Request the NWS API."""
    headers = {"User-Agent": USER_AGENT, "Accept": "application/geo+json"}
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers, timeout=30.0)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logging.error(f"Error requesting NWS API: {e}")
            return None


@app_setup.mcp_app.tool()
async def get_forecast(ctx: Context, latitude: float, longitude: float) -> str:
    """Get weather forecast for a location.

    Args:
        ctx: The MCP context
        latitude: Latitude of the location
        longitude: Longitude of the location
    """
    logging.info(f"get_forecast called with latitude: {latitude}, longitude: {longitude}")

    # First get the forecast grid endpoint
    points_url = f"{NWS_API_BASE}/points/{latitude},{longitude}"
    logging.info(f"Attempting to fetch points data from: {points_url}")
    points_data = await request_nws(points_url)

    if not points_data:
        logging.error(f"Failed to fetch points_data for {latitude},{longitude}. request_nws returned None.")
        return "Unable to fetch forecast data for this location (points data failed)."

    forecast_url: str | None = None
    try:
        forecast_url = points_data["properties"]["forecast"]
        logging.info(f"Successfully extracted forecast_url: {forecast_url}")
    except KeyError:
        logging.exception(f"KeyError when trying to access ['properties']['forecast'] from points_data for {latitude},{longitude}. points_data: {points_data}")
        return "Unable to parse forecast data from initial API response (missing forecast URL)."
    except Exception:
        logging.exception(f"An unexpected error occurred extracting forecast_url from points_data for {latitude},{longitude}. points_data: {points_data}")
        return "Unexpected error processing initial forecast data."

    if not forecast_url: # Should be caught by KeyError, but as a safeguard
        logging.error(f"forecast_url is None or empty after attempting to extract it for {latitude},{longitude}.")
        return "Forecast URL was not found in the API response."

    logging.info(f"Attempting to fetch detailed forecast data from: {forecast_url}")
    forecast_data = await request_nws(forecast_url)

    if not forecast_data:
        logging.error(f"Failed to fetch detailed forecast_data from {forecast_url}. request_nws returned None.")
        return "Unable to fetch detailed forecast."

    try:
        periods = forecast_data["properties"]["periods"]
        logging.info(f"Successfully extracted {len(periods)} periods from forecast_data.")
        forecasts = []
        for i, period in enumerate(periods[:5]):  # Get up to the first 5 periods
            try:
                forecast = (
                    f"{period['name']}:\n"
                    f"  Temperature: {period['temperature']}°{period['temperatureUnit']}\n"
                    f"  Wind: {period['windSpeed']} {period['windDirection']}\n"
                    f"  Forecast: {period['detailedForecast']}"
                )
                forecasts.append(forecast)
            except KeyError as e:
                logging.exception(f"KeyError processing period #{i+1} from forecast_data. Period data: {period}. Missing key: {e}")
                # Optionally skip this period or return an error message
                forecasts.append(f"{period.get('name', 'Unknown Period')}: Error processing this period's details.")
            except Exception as e:
                logging.exception(f"Unexpected error processing period #{i+1}. Period data: {period}.")
                forecasts.append(f"{period.get('name', 'Unknown Period')}: Unexpected error processing this period.")


        if not forecasts:
            logging.warning(f"No forecast periods were successfully processed from forecast_data for {forecast_url}.")
            return "No forecast details could be processed."

        return "\n\n---\n\n".join(forecasts)

    except KeyError:
        logging.exception(f"KeyError when trying to access ['properties']['periods'] from forecast_data from {forecast_url}. forecast_data: {forecast_data}")
        return "Unable to parse detailed forecast periods from API response."
    except TypeError: # For example, if forecast_data is unexpectedly not a dict
        logging.exception(f"TypeError while processing forecast_data (was it a dict?) from {forecast_url}. forecast_data: {forecast_data}")
        return "Error processing detailed forecast data due to unexpected data type."
    except Exception:
        logging.exception(f"An unexpected error occurred formatting the forecast periods from {forecast_url}. forecast_data: {forecast_data}")
        return "Unexpected error formatting detailed forecast."
