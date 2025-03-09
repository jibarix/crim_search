"""
Module for query processing functions.
Handles pagination, filtering, and data transformation.
"""

import time
import json
from datetime import datetime, timedelta
import pandas as pd

def get_recent_years_timestamp(years_back=5):
    """
    Calculate a timestamp from N years ago to use as a default date filter.
    This helps limit the data volume.
    
    Parameters:
    - years_back: Number of years to look back
    
    Returns:
    - Timestamp in milliseconds
    """
    now = datetime.now()
    years_ago = now.replace(year=now.year - years_back)
    timestamp = int(years_ago.timestamp() * 1000)
    return timestamp

def query_properties_paginated(session, base_params, page_size=100, max_pages=10):
    """
    Query properties with pagination to avoid overwhelming the API.
    
    Parameters:
    - session: Authenticated requests session
    - base_params: Basic query parameters (without pagination)
    - page_size: Number of records per page
    - max_pages: Maximum number of pages to retrieve
    
    Returns:
    - List of property records
    """
    base_url = "https://catastro.crimpr.net"
    arcgis_service = "/server/rest/services/Parcelario/Parcelas/MapServer/654/query"
    query_url = f"{base_url}/proxy/proxy.ashx?{base_url}{arcgis_service}?"
    
    # Headers needed to avoid 403 or 404
    headers = {
        "Referer": "https://catastro.crimpr.net/cdprpc/",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/133.0.0.0 Safari/537.36"
        )
    }
    
    all_results = []
    
    # Check if the API supports pagination properly
    # First, try with resultOffset parameter
    for page in range(max_pages):
        offset = page * page_size
        
        # Update pagination parameters
        params = base_params.copy()
        params.update({
            "resultOffset": offset,
            "resultRecordCount": page_size
        })
        
        print(f"Retrieving page {page + 1} (records {offset} to {offset + page_size})...")
        
        try:
            response = session.get(query_url, params=params, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                
                if 'features' in data:
                    page_results = [feature['attributes'] for feature in data['features']]
                    total_count = len(page_results)
                    
                    print(f"  Retrieved {total_count} records")
                    all_results.extend(page_results)
                    
                    # If we got fewer records than requested, we've reached the end
                    if total_count < page_size:
                        print("  Reached end of results")
                        break
                        
                else:
                    print("  No features found in response")
                    if 'error' in data:
                        print(f"  Error: {data['error'].get('message', 'Unknown error')}")
                    break
            else:
                print(f"  Query failed with status code: {response.status_code}")
                break
                
        except Exception as e:
            print(f"  Error querying page {page + 1}: {str(e)}")
            break
            
        # Short delay to avoid overwhelming the server
        time.sleep(1)
    
    return all_results

def post_filter_results_by_formatted_date(df, min_date=None, max_date=None):
    """
    Filter DataFrame results by SALESDTTM_FORMATTED date after processing.
    
    Parameters:
    - df: DataFrame containing property data with SALESDTTM_FORMATTED column
    - min_date: Minimum date as string 'YYYY-MM-DD'
    - max_date: Maximum date as string 'YYYY-MM-DD'
    
    Returns:
    - Filtered DataFrame
    """
    if not min_date and not max_date:
        return df
        
    # Create a copy to avoid modifying the original
    filtered_df = df.copy()
    
    # Apply filters
    if min_date and 'SALESDTTM_FORMATTED' in filtered_df.columns:
        print(f"Post-filtering dates on or after: {min_date}")
        filtered_df = filtered_df[filtered_df['SALESDTTM_FORMATTED'] >= min_date]
        
    if max_date and 'SALESDTTM_FORMATTED' in filtered_df.columns:
        print(f"Post-filtering dates on or before: {max_date}")
        filtered_df = filtered_df[filtered_df['SALESDTTM_FORMATTED'] <= max_date]
    
    print(f"Post-date filtering: {len(df)} → {len(filtered_df)} properties")
    return filtered_df

def process_property_data(properties, center_lat=None, center_lon=None):
    """
    Process property data to add useful derived fields.
    
    Parameters:
    - properties: List of dictionaries containing property data
    - center_lat: Optional center latitude for distance calculations
    - center_lon: Optional center longitude for distance calculations
    
    Returns:
    - List of processed property dictionaries
    """
    from connection_utils import generate_satellite_pin_link
    import math
    
    processed_data = []
    
    for prop in properties:
        # Create a new entry with all attributes
        entry = prop.copy()
        
        # Convert SALESDTTM from milliseconds to readable date
        if 'SALESDTTM' in entry and entry['SALESDTTM']:
            try:
                # Check if timestamp is within valid range
                timestamp_seconds = entry['SALESDTTM'] / 1000
                # Typical valid range for Unix timestamps (1970-01-01 to 2038-01-19)
                if 0 <= timestamp_seconds <= 2147483647:
                    date_obj = datetime.fromtimestamp(timestamp_seconds)
                    entry['SALESDTTM_FORMATTED'] = date_obj.strftime('%Y-%m-%d')
                else:
                    print(f"Invalid timestamp value: {entry['SALESDTTM']} (out of range)")
                    entry['SALESDTTM_FORMATTED'] = None
            except (ValueError, TypeError, OSError) as e:
                print(f"Error converting date: {e}, value: {entry['SALESDTTM']}")
                entry['SALESDTTM_FORMATTED'] = None
        
        # Extract latitude and longitude
        lat = prop.get('INSIDE_Y')
        lon = prop.get('INSIDE_X')
        
        if lat and lon:
            # Add coordinates and map links
            entry['google_maps_satellite_link'] = generate_satellite_pin_link(lat, lon)
            
            # Calculate distance if center coordinates are provided
            if center_lat is not None and center_lon is not None:
                # Convert decimal degrees to radians
                lat1, lon1, lat2, lon2 = map(math.radians, [center_lat, center_lon, lat, lon])
                
                # Haversine formula
                dlon = lon2 - lon1
                dlat = lat2 - lat1
                a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
                c = 2 * math.asin(math.sqrt(a))
                
                # Radius of earth in kilometers is 6371
                distance_km = 6371 * c
                distance_miles = distance_km / 1.60934
                
                entry['DISTANCE_KM'] = round(distance_km, 3)
                entry['DISTANCE_MILES'] = round(distance_miles, 3)
        
        processed_data.append(entry)
    
    return processed_data

def save_results_to_file(df, output_file):
    """
    Save DataFrame results to a file.
    
    Parameters:
    - df: DataFrame with results
    - output_file: Output file path (CSV or JSON)
    
    Returns:
    - None
    """
    if not output_file:
        print("No output file specified. Results not saved.")
        return
        
    file_ext = output_file.split('.')[-1].lower()
    if file_ext == 'csv':
        df.to_csv(output_file, index=False)
        print(f"Results saved to CSV: {output_file}")
    elif file_ext == 'json':
        # Convert to JSON with proper handling of dates and NaN values
        json_str = df.to_json(orient='records', date_format='iso')
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(json_str)
        print(f"Results saved to JSON: {output_file}")
    else:
        print(f"Unsupported file extension: {file_ext}. Supported: csv, json")