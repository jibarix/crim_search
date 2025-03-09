"""
Module for handling connections and authentication with the Catastro API.
Provides functions for session creation, cookie management, and link generation.
"""

import time
import urllib.parse
import math
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

def automate_splash_and_get_cookies_headless():
    """
    1) Launches a headless Chrome browser.
    2) Opens the CRIM Catastro site (cdprpc).
    3) Waits for the splash screen, clicks "OK" behind the scenes.
    4) Returns Selenium cookies.
    """
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # run without UI
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--enable-unsafe-swiftshader")  # Added to address WebGL warning
    chrome_options.add_argument("--disable-webgl")  # Added to suppress WebGL-related warnings
    
    # User agent to mimic a real browser
    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    
    driver = webdriver.Chrome(options=chrome_options)

    driver.get("https://catastro.crimpr.net/cdprpc/")
    time.sleep(5)  # Wait for splash to fully load

    try:
        ok_button = driver.find_element(By.XPATH, "//button[contains(text(), 'OK')]")
        ok_button.click()
        print("Splash screen dismissed (headless)!")
    except Exception as e:
        print("No splash screen detected or error clicking OK:", e)

    # Extract cookies from the Selenium browser session
    selenium_cookies = driver.get_cookies()
    driver.quit()
    return selenium_cookies

def transfer_cookies_to_requests_session(selenium_cookies, domain="catastro.crimpr.net"):
    """
    Transfers Selenium cookies into a requests.Session object
    so subsequent requests carry the same authentication.
    """
    session = requests.Session()
    for cookie in selenium_cookies:
        cookie_domain = cookie.get("domain", domain)
        session.cookies.set(
            name=cookie["name"],
            value=cookie["value"],
            domain=cookie_domain,
            path=cookie.get("path", "/")
        )
    return session

def decimal_to_dms(decimal_degrees, is_latitude=True):
    """
    Convert decimal degrees to degrees, minutes, seconds string.
    
    Parameters:
    - decimal_degrees: coordinate in decimal format
    - is_latitude: True if latitude, False if longitude
    
    Returns:
    - String in DMS format like "18°21'05.8"N"
    """
    # Determine sign and hemisphere
    if is_latitude:
        hemisphere = "N" if decimal_degrees >= 0 else "S"
    else:
        hemisphere = "E" if decimal_degrees >= 0 else "W"
    
    # Work with absolute value
    decimal_degrees = abs(decimal_degrees)
    
    # Calculate degrees, minutes, seconds
    degrees = int(decimal_degrees)
    minutes_full = (decimal_degrees - degrees) * 60
    minutes = int(minutes_full)
    seconds = (minutes_full - minutes) * 60
    
    # Format with proper padding
    seconds_str = f"{seconds:.1f}"
    if seconds < 10:
        seconds_str = f"0{seconds_str}"
    
    return f"{degrees}°{minutes:02d}'{seconds_str}\"{hemisphere}"

def generate_satellite_pin_link(lat, lon, zoom_meters=1146):
    """
    Generate a Google Maps link with satellite view and pin.
    
    Parameters:
    - lat: Latitude as decimal degrees
    - lon: Longitude as decimal degrees
    - zoom_meters: Zoom level in meters (default: 1146m)
    
    Returns:
    - Properly formatted Google Maps URL
    """
    # Convert to DMS format
    lat_dms = decimal_to_dms(lat, is_latitude=True)
    lon_dms = decimal_to_dms(lon, is_latitude=False)
    
    # Combine DMS coordinates
    dms_coordinates = f"{lat_dms} {lon_dms}"
    
    # URL encode the DMS coordinates
    encoded_coords = urllib.parse.quote(dms_coordinates)
    
    # Calculate the bounds parameters (approximate)
    # For most Google Maps links, the first lon is adjusted slightly for view centering
    view_lon = lon - 0.0025803  # Approximately matches example URLs
    
    # Build the URL with satellite view (!3m2!1e3!4b1) and pin (!4m4!3m3!8m2!...)
    url = (
        f"https://www.google.com/maps/place/{encoded_coords}/"
        f"@{lat},{view_lon},{zoom_meters}m/data=!3m2!1e3!4b1"
        f"!4m4!3m3!8m2!3d{lat}!4d{lon}?entry=ttu"
    )
    
    return url

def query_parcel_full_details(session, catastro_number):
    """
    Uses the authenticated requests.Session to query the CRIM Parcelario API
    for a given Número de Catastro. Returns all fields and geometry.
    """
    base_url = "https://catastro.crimpr.net"
    arcgis_service = "/server/rest/services/Parcelario/Parcelas/MapServer/654/query"

    # IMPORTANT: trailing '?' ensures two question marks in final URL
    query_url = f"{base_url}/proxy/proxy.ashx?{base_url}{arcgis_service}?"

    params = {
        "f": "json",
        "where": f"LOWER(CATASTRO) = '{catastro_number.lower()}'",
        "returnGeometry": "true",   # Include geometry
        "outFields": "*",          # Return ALL available fields
        "spatialRel": "esriSpatialRelIntersects",
        "outSR": "102100"          # Web Mercator
    }

    # Headers needed to avoid 403 or 404
    headers = {
        "Referer": "https://catastro.crimpr.net/cdprpc/",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/133.0.0.0 Safari/537.36"
        )
    }

    response = session.get(query_url, params=params, headers=headers)
    
    try:
        return response.json()
    except Exception as e:
        print("Error parsing JSON response:", e)
        return None