"""
Module for grid-based spatial search functionality.
Core implementation of the grid-based approach for comprehensive radius searches.
"""

import math
import json
import time
from functools import lru_cache
from rtree import index  # For spatial indexing

# Constants
MILES_TO_KM = 1.60934
EARTH_RADIUS_KM = 6371.0

def create_grid_cells(center_lat, center_lon, radius_miles, grid_size=3):
    """
    Create a grid of cells covering the search radius.
    
    Parameters:
    - center_lat: Center latitude
    - center_lon: Center longitude
    - radius_miles: Radius in miles
    - grid_size: Number of cells along one dimension (total cells = grid_size^2)
    
    Returns:
    - List of cells as [min_lon, min_lat, max_lon, max_lat]
    """
    # Convert radius to kilometers
    radius_km = radius_miles * MILES_TO_KM
    
    # Convert radius to degrees (approximate)
    # 1 degree of latitude is approximately 111 kilometers
    radius_deg_lat = radius_km / 111.0
    
    # 1 degree of longitude varies with latitude
    radius_deg_lon = radius_km / (111.0 * math.cos(math.radians(center_lat)))
    
    # Create the bounding box
    min_lat = center_lat - radius_deg_lat
    max_lat = center_lat + radius_deg_lat
    min_lon = center_lon - radius_deg_lon
    max_lon = center_lon + radius_deg_lon
    
    # Calculate cell dimensions
    cell_width = (max_lon - min_lon) / grid_size
    cell_height = (max_lat - min_lat) / grid_size
    
    # Create grid cells
    cells = []
    for i in range(grid_size):
        for j in range(grid_size):
            cell_min_lon = min_lon + i * cell_width
            cell_max_lon = min_lon + (i + 1) * cell_width
            cell_min_lat = min_lat + j * cell_height
            cell_max_lat = min_lat + (j + 1) * cell_height
            
            cells.append([cell_min_lon, cell_min_lat, cell_max_lon, cell_max_lat])
    
    return cells

def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the great circle distance between two points 
    on the earth (specified in decimal degrees).
    
    Returns:
    - Distance in kilometers
    """
    # Convert decimal degrees to radians
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    
    # Haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    
    # Radius of earth in kilometers is 6371
    km = EARTH_RADIUS_KM * c
    return km

def create_cell_query_parameters(cell, additional_params=None):
    """
    Create query parameters for a specific grid cell.
    
    Parameters:
    - cell: [min_lon, min_lat, max_lon, max_lat]
    - additional_params: Dictionary of additional parameters to filter by
    
    Returns:
    - Dictionary of query parameters, min_date, max_date
    """
    min_lon, min_lat, max_lon, max_lat = cell
    
    # Store min_date and max_date
    min_date = None
    max_date = None
    
    # Create a polygon representing the cell
    cell_polygon = {
        "rings": [
            [
                [min_lon, min_lat],
                [min_lon, max_lat],
                [max_lon, max_lat],
                [max_lon, min_lat],
                [min_lon, min_lat]  # Close the polygon
            ]
        ],
        "spatialReference": {"wkid": 4326}  # WGS84 coordinate system
    }
    
    # Convert polygon to JSON string
    geometry_json = json.dumps(cell_polygon)
    
    # Base query parameters
    base_params = {
        "f": "json",
        "geometry": geometry_json,
        "geometryType": "esriGeometryPolygon",
        "spatialRel": "esriSpatialRelIntersects",
        "returnGeometry": "true",
        "outFields": "*",
        "outSR": "102100"  # Web Mercator
    }
    
    # Add any additional query parameters
    if additional_params:
        # Extract date range parameters for post-processing filtering
        min_date = additional_params.pop('SALESDTTM_MIN', None) if additional_params.get('SALESDTTM_MIN') else None
        max_date = additional_params.pop('SALESDTTM_MAX', None) if additional_params.get('SALESDTTM_MAX') else None
        
        # Build WHERE clause for remaining parameters
        where_conditions = []
        
        # Process MUNICIPIO if provided
        municipio = additional_params.get('MUNICIPIO')
        if municipio:
            where_conditions.append(f"MUNICIPIO = '{municipio}'")
        
        # Process sales amount parameters
        min_amount = additional_params.get('SALESAMT_MIN')
        if min_amount is not None:
            where_conditions.append(f"SALESAMT >= {min_amount}")
        
        max_amount = additional_params.get('SALESAMT_MAX')
        if max_amount is not None:
            where_conditions.append(f"SALESAMT <= {max_amount}")
        
        # Process cabida (land area) parameters
        min_cabida = additional_params.get('CABIDA_MIN')
        if min_cabida is not None:
            where_conditions.append(f"CABIDA >= {min_cabida}")
        
        max_cabida = additional_params.get('CABIDA_MAX')
        if max_cabida is not None:
            where_conditions.append(f"CABIDA <= {max_cabida}")
        
        # Add any remaining parameters as exact matches
        for key, value in additional_params.items():
            if key not in ['MUNICIPIO', 'SALESAMT_MIN', 'SALESAMT_MAX', 'CABIDA_MIN', 'CABIDA_MAX']:
                if isinstance(value, str):
                    where_conditions.append(f"{key} = '{value}'")
                else:
                    where_conditions.append(f"{key} = {value}")
        
        # Combine all conditions with AND
        if where_conditions:
            where_clause = " AND ".join(where_conditions)
            base_params["where"] = where_clause
    
    return base_params, min_date, max_date

@lru_cache(maxsize=128)
def get_coordinates_by_catastro(session, catastro_number):
    """
    Get coordinates for a catastro number.
    Uses LRU cache to avoid repeated lookups.
    
    Parameters:
    - session: Authenticated requests session
    - catastro_number: Catastro number to look up
    
    Returns:
    - Tuple of (latitude, longitude) or None if not found
    """
    from connection_utils import query_parcel_full_details
    
    print(f"Looking up coordinates for catastro number: {catastro_number}")
    
    try:
        # Query the catastro details
        catastro_data = query_parcel_full_details(session, catastro_number)
        
        # Check if we got valid data with features
        if catastro_data and 'features' in catastro_data and len(catastro_data['features']) > 0:
            feature = catastro_data['features'][0]
            if 'attributes' in feature:
                attributes = feature['attributes']
                
                # Extract lat/lon
                lat = attributes.get('INSIDE_Y')
                lon = attributes.get('INSIDE_X')
                
                if lat and lon:
                    print(f"Found coordinates: {lat}, {lon}")
                    return (lat, lon)
        
        print(f"No coordinates found for catastro {catastro_number}")
        return None
    
    except Exception as e:
        print(f"Error looking up catastro {catastro_number}: {str(e)}")
        return None

def filter_properties_by_radius(properties, center_lat, center_lon, radius_miles):
    """
    Filter properties by distance from center point using spatial indexing.
    
    Parameters:
    - properties: List of property dictionaries
    - center_lat: Center latitude
    - center_lon: Center longitude
    - radius_miles: Radius in miles
    
    Returns:
    - List of properties within radius, with distance fields added
    """
    radius_km = radius_miles * MILES_TO_KM
    filtered_properties = []
    
    # Create spatial index for fast radius filtering
    p = index.Property()
    p.dimension = 2
    idx = index.Index(properties=p)
    
    # Calculate bounding box for initial filtering
    # This creates a square that fully contains the circle
    lat_offset = radius_km / 111.0  # approx degrees per km for latitude
    lon_offset = radius_km / (111.0 * math.cos(math.radians(center_lat)))
    
    min_lat = center_lat - lat_offset
    max_lat = center_lat + lat_offset
    min_lon = center_lon - lon_offset
    max_lon = center_lon + lon_offset
    
    # First pass: Add properties to spatial index
    valid_properties = []
    for i, prop in enumerate(properties):
        prop_lat = prop.get('INSIDE_Y')
        prop_lon = prop.get('INSIDE_X')
        
        if prop_lat and prop_lon:
            # Add to index with ID equal to position in original list
            idx.insert(i, (prop_lon, prop_lat, prop_lon, prop_lat))
            valid_properties.append((i, prop))
    
    # Second pass: Use spatial index to find properties in bounding box
    # Then refine by calculating exact distances
    for id_object in idx.intersection((min_lon, min_lat, max_lon, max_lat)):
        i, prop = valid_properties[id_object]
        prop_lat = prop.get('INSIDE_Y')
        prop_lon = prop.get('INSIDE_X')
        
        # Calculate exact distance
        distance_km = haversine_distance(center_lat, center_lon, prop_lat, prop_lon)
        distance_miles = distance_km / MILES_TO_KM
        
        # If within exact radius, add to results
        if distance_miles <= radius_miles:
            prop['DISTANCE_KM'] = round(distance_km, 3)
            prop['DISTANCE_MILES'] = round(distance_miles, 3)
            filtered_properties.append(prop)
    
    # Sort results by distance from center point
    filtered_properties.sort(key=lambda x: x.get('DISTANCE_MILES', float('inf')))
    
    return filtered_properties