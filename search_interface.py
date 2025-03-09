"""
Module for search interface and orchestration.
Provides functions for different types of property searches.
"""

import pandas as pd
import argparse
import time
from tqdm import tqdm
import random
from ratelimit import limits, sleep_and_retry

# Import modules from the package
from connection_utils import (
    automate_splash_and_get_cookies_headless,
    transfer_cookies_to_requests_session
)
from query_utils import (
    query_properties_paginated,
    post_filter_results_by_formatted_date,
    process_property_data,
    save_results_to_file
)
from grid_search import (
    create_grid_cells,
    create_cell_query_parameters,
    filter_properties_by_radius,
    get_coordinates_by_catastro
)

# Rate limiting configuration
CALLS_PER_MINUTE = 30  # Maximum 30 API calls per minute
RATE_LIMIT_PERIOD = 60  # 60 seconds (1 minute)

@sleep_and_retry
@limits(calls=CALLS_PER_MINUTE, period=RATE_LIMIT_PERIOD)
def rate_limited_query(session, base_params, page_size=100, max_pages=10):
    """
    Wrapper for query_properties_paginated with rate limiting.
    
    Parameters:
    - session: Authenticated requests session
    - base_params: Basic query parameters
    - page_size: Number of records per page
    - max_pages: Maximum number of pages to retrieve
    
    Returns:
    - List of property records
    """
    return query_properties_paginated(session, base_params, page_size, max_pages)

def grid_radius_search(center_point, radius_miles, additional_params=None, grid_size=3, output_file=None):
    """
    Search for properties within a radius using grid-based approach.
    
    Parameters:
    - center_point: Either tuple of (latitude, longitude) or catastro number string
    - radius_miles: Radius in miles
    - additional_params: Dictionary of additional parameters to filter by
    - grid_size: Size of the grid (number of cells along one dimension)
    - output_file: Output file path (CSV or JSON)
    
    Returns:
    - DataFrame with search results
    """
    # Initialize session
    print("Initializing session with catastro.crimpr.net...")
    selenium_cookies = automate_splash_and_get_cookies_headless()
    session = transfer_cookies_to_requests_session(selenium_cookies)
    
    # Determine center point coordinates
    if isinstance(center_point, str):
        # Assume it's a catastro number
        coords = get_coordinates_by_catastro(session, center_point)
        if not coords:
            print(f"Could not find coordinates for catastro {center_point}")
            return pd.DataFrame()  # Return empty DataFrame
        center_lat, center_lon = coords
    else:
        # Assume it's a (lat, lon) tuple
        center_lat, center_lon = center_point
    
    # Create grid cells
    print(f"Creating {grid_size}x{grid_size} grid for radius search...")
    cells = create_grid_cells(center_lat, center_lon, radius_miles, grid_size)
    
    # Query properties in each cell
    all_properties = []
    seen_objectids = set()  # For deduplication
    cell_properties_list = []  # Store properties for each cell for completeness check
    page_size = 100
    max_pages = 10
    limit_threshold = page_size * max_pages  # 1000 records
    
    # Store date filters for post-processing
    min_date = None
    max_date = None
    
    # Create progress bar for grid cells
    with tqdm(total=len(cells), desc="Querying grid cells", unit="cell") as pbar:
        for i, cell in enumerate(cells):
            # Create query parameters for this cell
            base_params, cell_min_date, cell_max_date = create_cell_query_parameters(cell, additional_params)
            
            # Store date parameters for post-processing
            if cell_min_date and (min_date is None or cell_min_date < min_date):
                min_date = cell_min_date
            if cell_max_date and (max_date is None or cell_max_date > max_date):
                max_date = cell_max_date
            
            # Query the API with rate limiting
            cell_properties = rate_limited_query(session, base_params, page_size=page_size, max_pages=max_pages)
            cell_properties_list.append(cell_properties)  # Store for completeness check
            
            # Deduplicate by OBJECTID
            new_properties = 0
            for prop in cell_properties:
                objectid = prop.get('OBJECTID')
                if objectid and objectid not in seen_objectids:
                    seen_objectids.add(objectid)
                    all_properties.append(prop)
                    new_properties += 1
            
            # Update progress bar description with cell results
            pbar.set_postfix({"Found": len(cell_properties), "New": new_properties, "Total": len(all_properties)})
            pbar.update(1)
            
            # Add a small random delay between 0.5 and 1.5 seconds
            # This helps spread out requests and avoid triggering rate limits
            time.sleep(0.5 + random.random())
    
    # Check if any cells hit the limit and might be incomplete
    cells_at_limit = sum(1 for cell_props in cell_properties_list if len(cell_props) >= limit_threshold)
    if cells_at_limit > 0:
        print(f"\nWARNING: {cells_at_limit} cell(s) reached the {limit_threshold} record limit!")
        print("Some properties might not be included in the results.")
        print("Consider using a finer grid (increase --grid parameter) for more complete results.")
        print(f"Current grid size: {grid_size}x{grid_size}, consider trying {grid_size+2}x{grid_size+2}\n")
    
    print(f"Total unique properties found across all cells: {len(all_properties)}")
    
    # Filter by actual radius with a progress bar
    print("Filtering properties by radius...")
    with tqdm(total=1, desc="Spatial filtering", unit="batch") as pbar:
        radius_filtered_properties = filter_properties_by_radius(
            all_properties, center_lat, center_lon, radius_miles
        )
        pbar.update(1)
    
    print(f"After radius filtering: {len(radius_filtered_properties)} properties within {radius_miles} miles")
    
    # Process properties with a progress bar
    print("Processing property data...")
    with tqdm(total=1, desc="Processing data", unit="batch") as pbar:
        processed_data = process_property_data(radius_filtered_properties, center_lat, center_lon)
        pbar.update(1)
    
    # Convert to DataFrame
    df = pd.DataFrame(processed_data)
    
    # Apply post-processing date filter
    if min_date or max_date:
        df = post_filter_results_by_formatted_date(df, min_date, max_date)
    
    # Save results if output file is specified
    if output_file:
        print(f"Saving results to {output_file}...")
        save_results_to_file(df, output_file)
    
    return df

def address_search(address_text, radius_miles=0.25, additional_params=None, grid_size=3, output_file=None):
    """
    Search for properties near an address using grid-based approach.
    Geocodes the address to get coordinates.
    
    Parameters:
    - address_text: Address text to geocode
    - radius_miles: Radius in miles
    - additional_params: Dictionary of additional parameters to filter by
    - grid_size: Size of the grid (number of cells along one dimension)
    - output_file: Output file path (CSV or JSON)
    
    Returns:
    - DataFrame with search results
    """
    # TODO: Implement geocoding for addresses
    # This would typically use a service like Google Maps Geocoding API
    # For now, return a message that this isn't implemented
    print("Address geocoding is not yet implemented.")
    print("Please use coordinates or a catastro number for the center point.")
    return pd.DataFrame()

@sleep_and_retry
@limits(calls=CALLS_PER_MINUTE, period=RATE_LIMIT_PERIOD)
def municipio_search(municipio, min_date=None, max_date=None, min_price=None, max_price=None, min_cabida=None, max_cabida=None, output_file=None):
    """
    Search for properties within a municipality.
    
    Parameters:
    - municipio: Municipality name (e.g., "SAN JUAN")
    - min_date: Minimum sale date (YYYY-MM-DD)
    - max_date: Maximum sale date (YYYY-MM-DD)
    - min_price: Minimum sale price
    - max_price: Maximum sale price
    - min_cabida: Minimum land area (cabida) in square meters
    - max_cabida: Maximum land area (cabida) in square meters
    - output_file: Output file path (CSV or JSON)
    
    Returns:
    - DataFrame with search results
    """
    # Initialize session
    print("Initializing session with catastro.crimpr.net...")
    selenium_cookies = automate_splash_and_get_cookies_headless()
    session = transfer_cookies_to_requests_session(selenium_cookies)
    
    # Build WHERE clause for parameters
    where_conditions = [f"MUNICIPIO = '{municipio}'"]
    
    if min_price is not None:
        where_conditions.append(f"SALESAMT >= {min_price}")
    if max_price is not None:
        where_conditions.append(f"SALESAMT <= {max_price}")
    if min_cabida is not None:
        where_conditions.append(f"CABIDA >= {min_cabida}")
    if max_cabida is not None:
        where_conditions.append(f"CABIDA <= {max_cabida}")
    
    # Combine all conditions with AND
    where_clause = " AND ".join(where_conditions)
    
    # Base query parameters
    base_params = {
        "f": "json",
        "where": where_clause,
        "returnGeometry": "true",
        "outFields": "*",
        "spatialRel": "esriSpatialRelIntersects",
        "outSR": "102100"
    }
    
    # Query the API with progress bar
    print(f"Querying properties in {municipio}...")
    with tqdm(total=1, desc=f"Searching {municipio}", unit="query") as pbar:
        all_properties = query_properties_paginated(session, base_params, page_size=100, max_pages=10)
        pbar.update(1)
    
    print(f"Found {len(all_properties)} properties in {municipio}")
    
    # Process properties with progress bar
    print("Processing property data...")
    with tqdm(total=1, desc="Processing data", unit="batch") as pbar:
        processed_data = process_property_data(all_properties)
        pbar.update(1)
    
    # Convert to DataFrame
    df = pd.DataFrame(processed_data)
    
    # Apply post-processing date filter
    if min_date or max_date:
        df = post_filter_results_by_formatted_date(df, min_date, max_date)
    
    # Save results if output file is specified
    if output_file:
        print(f"Saving results to {output_file}...")
        save_results_to_file(df, output_file)
    
    return df

@sleep_and_retry
@limits(calls=CALLS_PER_MINUTE, period=RATE_LIMIT_PERIOD)
def catastro_search(catastro_number, output_file=None):
    """
    Search for a single property by catastro number.
    
    Parameters:
    - catastro_number: Catastro number string
    - output_file: Output file path (CSV or JSON)
    
    Returns:
    - DataFrame with search results (single row)
    """
    # Initialize session
    print("Initializing session with catastro.crimpr.net...")
    selenium_cookies = automate_splash_and_get_cookies_headless()
    session = transfer_cookies_to_requests_session(selenium_cookies)
    
    from connection_utils import query_parcel_full_details
    
    # Query the catastro details with progress bar
    print(f"Looking up catastro number: {catastro_number}...")
    with tqdm(total=1, desc="Querying API", unit="request") as pbar:
        catastro_data = query_parcel_full_details(session, catastro_number)
        pbar.update(1)
    
    if not catastro_data or 'features' not in catastro_data or not catastro_data['features']:
        print(f"No property found for catastro number: {catastro_number}")
        return pd.DataFrame()
    
    # Extract property data
    feature = catastro_data['features'][0]
    if 'attributes' not in feature:
        print(f"No attributes found for catastro number: {catastro_number}")
        return pd.DataFrame()
    
    property_data = [feature['attributes']]
    
    # Process property data
    processed_data = process_property_data(property_data)
    
    # Convert to DataFrame
    df = pd.DataFrame(processed_data)
    
    # Save results if output file is specified
    if output_file:
        print(f"Saving results to {output_file}...")
        save_results_to_file(df, output_file)
    
    return df

def setup_cli_parser():
    """
    Set up command-line interface parser.
    
    Returns:
    - Configured ArgumentParser
    """
    parser = argparse.ArgumentParser(description="Property Search Tool")
    subparsers = parser.add_subparsers(dest="command", help="Search command")
    
    # Radius search command
    radius_parser = subparsers.add_parser("radius", help="Search properties within radius")
    radius_parser.add_argument("--lat", type=float, help="Center latitude")
    radius_parser.add_argument("--lon", type=float, help="Center longitude")
    radius_parser.add_argument("--catastro", help="Center catastro number")
    radius_parser.add_argument("--radius", type=float, required=True, help="Search radius in miles")
    radius_parser.add_argument("--grid", type=int, default=3, help="Grid size (default: 3x3)")
    radius_parser.add_argument("--output", help="Output file path (CSV or JSON)")
    radius_parser.add_argument("--municipio", help="Municipality name")
    radius_parser.add_argument("--min-price", type=float, help="Minimum sale price")
    radius_parser.add_argument("--max-price", type=float, help="Maximum sale price")
    radius_parser.add_argument("--min-date", help="Minimum sale date (YYYY-MM-DD)")
    radius_parser.add_argument("--max-date", help="Maximum sale date (YYYY-MM-DD)")
    radius_parser.add_argument("--min-cabida", type=float, help="Minimum land area (cabida) in square meters")
    radius_parser.add_argument("--max-cabida", type=float, help="Maximum land area (cabida) in square meters")
    radius_parser.add_argument("--rate-limit", type=int, default=30, 
                              help="Maximum API calls per minute (default: 30)")
    
    # Address search command
    address_parser = subparsers.add_parser("address", help="Search properties near an address")
    address_parser.add_argument("address", help="Address text")
    address_parser.add_argument("--radius", type=float, default=0.25, help="Search radius in miles (default: 0.25)")
    address_parser.add_argument("--grid", type=int, default=3, help="Grid size (default: 3x3)")
    address_parser.add_argument("--output", help="Output file path (CSV or JSON)")
    address_parser.add_argument("--municipio", help="Municipality name")
    address_parser.add_argument("--min-price", type=float, help="Minimum sale price")
    address_parser.add_argument("--max-price", type=float, help="Maximum sale price")
    address_parser.add_argument("--min-date", help="Minimum sale date (YYYY-MM-DD)")
    address_parser.add_argument("--max-date", help="Maximum sale date (YYYY-MM-DD)")
    address_parser.add_argument("--rate-limit", type=int, default=30, 
                               help="Maximum API calls per minute (default: 30)")
    
    # Municipio search command
    municipio_parser = subparsers.add_parser("municipio", help="Search properties in a municipality")
    municipio_parser.add_argument("municipio", help="Municipality name")
    municipio_parser.add_argument("--output", help="Output file path (CSV or JSON)")
    municipio_parser.add_argument("--min-price", type=float, help="Minimum sale price")
    municipio_parser.add_argument("--max-price", type=float, help="Maximum sale price")
    municipio_parser.add_argument("--min-date", help="Minimum sale date (YYYY-MM-DD)")
    municipio_parser.add_argument("--max-date", help="Maximum sale date (YYYY-MM-DD)")
    municipio_parser.add_argument("--min-cabida", type=float, help="Minimum land area (cabida) in square meters")
    municipio_parser.add_argument("--max-cabida", type=float, help="Maximum land area (cabida) in square meters")
    municipio_parser.add_argument("--rate-limit", type=int, default=30, 
                                 help="Maximum API calls per minute (default: 30)")
    
    # Catastro search command
    catastro_parser = subparsers.add_parser("catastro", help="Search property by catastro number")
    catastro_parser.add_argument("catastro", help="Catastro number")
    catastro_parser.add_argument("--output", help="Output file path (CSV or JSON)")
    catastro_parser.add_argument("--rate-limit", type=int, default=30, 
                                help="Maximum API calls per minute (default: 30)")
    
    return parser

def main():
    """
    Main function for command-line interface.
    """
    parser = setup_cli_parser()
    args = parser.parse_args()
    
    # Set global rate limit
    if hasattr(args, 'rate_limit') and args.rate_limit:
        global CALLS_PER_MINUTE
        CALLS_PER_MINUTE = args.rate_limit
        print(f"Rate limit set to {CALLS_PER_MINUTE} API calls per minute")
    
    if args.command == "radius":
        # Check if we have valid center point arguments
        has_coords = args.lat is not None and args.lon is not None
        has_catastro = args.catastro is not None
        
        if not (has_coords or has_catastro):
            print("Error: You must provide either coordinates (--lat, --lon) or a catastro number (--catastro)")
            return 1
        
        if has_coords and has_catastro:
            print("Warning: Both coordinates and catastro number provided. Using coordinates.")
        
        # Build additional parameters
        additional_params = {}
        if args.municipio:
            additional_params["MUNICIPIO"] = args.municipio
        if args.min_price is not None:
            additional_params["SALESAMT_MIN"] = args.min_price
        if args.max_price is not None:
            additional_params["SALESAMT_MAX"] = args.max_price
        if args.min_date:
            additional_params["SALESDTTM_MIN"] = args.min_date
        if args.max_date:
            additional_params["SALESDTTM_MAX"] = args.max_date
        if args.min_cabida is not None:
            additional_params["CABIDA_MIN"] = args.min_cabida
        if args.max_cabida is not None:
            additional_params["CABIDA_MAX"] = args.max_cabida
        
        # Determine center point
        if has_coords:
            center_point = (args.lat, args.lon)
        else:
            center_point = args.catastro
        
        # Execute the search
        start_time = time.time()
        results_df = grid_radius_search(
            center_point=center_point,
            radius_miles=args.radius,
            additional_params=additional_params,
            grid_size=args.grid,
            output_file=args.output
        )
        end_time = time.time()
        elapsed_time = end_time - start_time
        
        # Print summary
        print(f"Search completed in {elapsed_time:.2f} seconds. Found {len(results_df)} properties within {args.radius} miles.")