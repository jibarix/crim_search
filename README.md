# Puerto Rico Property Search Tool

A sophisticated tool for efficiently searching and analyzing property data from the Puerto Rico Catastro database. This tool is designed to overcome the limitations of the official Catastro API while providing comprehensive property data analysis capabilities.

## Key Features

### Search Capabilities
- **Grid-based Radius Search**: Search for properties within a circular radius around coordinates or a catastro number
- **Municipality Search**: Find all properties within a specific municipality
- **Catastro Number Lookup**: Get details for a specific property by its catastro number
- **Address-based Search**: (Coming soon) Search for properties near an address

### Data Management
- **Export Options**: Save results to CSV or JSON formats
- **Advanced Filtering**: Filter by sale date range, price range, land area (cabida), and more
- **Completeness Detection**: Automatically identifies when search results might be incomplete due to API limitations and suggests solutions
- **Spatial Indexing**: Uses R-tree spatial indexing for efficient property filtering

### Performance Optimizations
- **Grid-based Search Algorithm**: Divides search area into a configurable grid to overcome API's 1,000 record limit
- **Rate Limiting**: Configurable rate limiting to avoid overwhelming the API and getting blocked
- **Session Handling**: Automated authentication with headless browser
- **Intelligent Deduplication**: Removes duplicate properties found in overlapping grid cells
- **Progressive Loading**: Uses pagination to efficiently retrieve and process large data sets

## Installation

### Prerequisites
- Python 3.8 or higher
- pip (Python package installer)

### Setup
1. Clone this repository:
   ```
   git clone https://github.com/yourusername/pr-property-search.git
   cd pr-property-search
   ```

2. Create a virtual environment:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

## Usage

### Radius Search
Search for properties within a radius around coordinates:

```
python property_search_tool.py radius --lat 18.445550 --lon -66.064836 --radius 1.5 --output results.csv
```

Or using a catastro number as the center:

```
python property_search_tool.py radius --catastro 042-000-006-29 --radius 1.5 --output results.csv
```

#### Parameters:
- `--lat`, `--lon`: Center coordinates (decimal degrees)
- `--catastro`: Alternative to coordinates; specify a catastro number as center
- `--radius`: Search radius in miles (required)
- `--grid`: Grid size for search (default: 3×3). Increase for more complete results in dense areas
- `--output`: Output file path (CSV or JSON)
- `--municipio`: Filter by municipality name
- `--min-price`, `--max-price`: Filter by sale price range
- `--min-date`, `--max-date`: Filter by sale date range (format: YYYY-MM-DD)
- `--min-cabida`, `--max-cabida`: Filter by land area range (in square meters)
- `--rate-limit`: Maximum API calls per minute (default: 30)

### Municipality Search
Search for all properties in a specific municipality:

```
python property_search_tool.py municipio "SAN JUAN" --output sanjuan.csv
```

#### Parameters:
- `municipio`: Municipality name (required)
- `--output`: Output file path (CSV or JSON)
- `--min-price`, `--max-price`: Filter by sale price range
- `--min-date`, `--max-date`: Filter by sale date range (format: YYYY-MM-DD)
- `--min-cabida`, `--max-cabida`: Filter by land area range (in square meters)
- `--rate-limit`: Maximum API calls per minute (default: 30)

### Catastro Search
Look up a specific property by its catastro number:

```
python property_search_tool.py catastro 042-000-006-29 --output property.csv
```

#### Parameters:
- `catastro`: Catastro number (required)
- `--output`: Output file path (CSV or JSON)
- `--rate-limit`: Maximum API calls per minute (default: 30)

## Grid-Based Search Algorithm: Technical Deep Dive

The grid-based search is a key innovation of this tool that overcomes fundamental limitations in the Catastro API. Here's how it works:

### Problem: API Limitations
1. The Catastro API has a hard limit of 1,000 records per query
2. Properties are returned based on OBJECTID order, not by distance
3. No built-in spatial proximity sort
4. No way to specify "get me all properties within X miles" directly

### Solution: Grid-Based Approach
1. **Area Division**: The search area (circle with radius R) is divided into a configurable N×N grid
2. **Independent Queries**: Each grid cell is queried independently
3. **Results Combination**: Results from all cells are combined
4. **Exact Distance Filtering**: Combined results are filtered to include only properties within the exact radius
5. **Deduplication**: Properties found in multiple grid cells (due to overlap) are deduplicated by OBJECTID

### Implementation Details:
1. **Grid Creation**: 
   - Given a center point (lat, lon) and radius in miles, the tool calculates a bounding box
   - The bounding box is divided into an N×N grid (configurable via `--grid`)
   - For each cell, a polygon geometry is created for querying the API

2. **Spatial Indexing**:
   - Uses R-tree spatial indexing for efficient filtering by actual distance
   - Two-phase filtering: first by bounding box, then by exact distance calculation using Haversine formula
   - Results are sorted by distance from center point

3. **Completeness Detection**:
   - The tool automatically detects when any grid cell hits the 1,000 record limit
   - Warns user that results may be incomplete
   - Suggests increasing the grid size parameter for more complete results

### Example Grid Visualization:
```
┌─────┬─────┬─────┐
│  1  │  2  │  3  │
├─────┼─────┼─────┤
│  4  │  5  │  6  │
├─────┼─────┼─────┤
│  7  │  8  │  9  │
└─────┴─────┴─────┘
```

In this 3×3 grid example, the tool would:
1. Query each numbered cell independently (9 total queries)
2. Combine all results while keeping track of their coordinates
3. Filter out properties beyond the radius using the Haversine formula
4. Remove duplicate properties

### Performance Considerations:
- Larger grid sizes (5×5, 7×7) provide more complete results in densely populated areas
- Each additional grid cell adds an API query, which affects performance
- The tool includes rate limiting to prevent overwhelming the API
- Random delays between requests help avoid triggering server-side blocks

## Understanding API and Tool Limitations

### API Limitations
1. **Record Limit**: The Catastro API has a hard limit of 1,000 records per query
2. **Return Order**: Results are returned based on database ID (OBJECTID), not by distance
3. **No Spatial Proximity Sort**: No native way to sort by distance from a point
4. **Date Filtering Limitations**: Date filtering must be done post-query for precise results

### Tool Limitations
1. **Incomplete Results Possibility**: In very densely populated areas, even with a large grid, some properties might be missed if multiple cells hit the 1,000 record limit
2. **Performance vs. Completeness Tradeoff**: Larger grids provide more complete results but require more API queries and time
3. **Rate Limiting Requirements**: Too many rapid queries can trigger server-side blocks, requiring rate limiting
4. **Memory Usage**: Very large searches (e.g., large radius or entire municipality) can require significant memory

## Best Practices

1. **Start Small**: Begin with smaller searches to understand the data and tool behavior
2. **Use Filters**: Narrow down results with filters when searching in dense areas
3. **Increase Grid Size When Needed**: If you see the warning about cells hitting the record limit, rerun with a larger grid size
4. **Mind API Limits**: Keep the rate limit reasonable (default: 30 calls/min) to avoid server blocks
5. **Save As You Go**: Always use the `--output` parameter to save results
6. **Recent Sales**: When looking for recent sales, always use the `--min-date` filter to narrow results
7. **Monitor Console Output**: Watch for warnings about cells hitting limits

## Example Use Cases

### Find Recent High-Value Sales Near a Specific Location
```
python property_search_tool.py radius --lat 18.445550 --lon -66.064836 --radius 1 --grid 4 --min-date 2024-01-01 --min-price 100000 --output high_value_recent.csv
```

### Find Medium-Sized Lots in San Juan
```
python property_search_tool.py municipio "SAN JUAN" --min-cabida 500 --max-cabida 2000 --output sanjuan_medium_lots.csv
```

### Find Properties Near a Known Property
```
python property_search_tool.py radius --catastro 042-000-006-29 --radius 0.5 --grid 4 --output nearby_properties.csv
```

### Find Recent Properties in an Entire Municipality
```
python property_search_tool.py municipio "PONCE" --min-date 2023-01-01 --output ponce_recent.csv
```

## Output Format

The results include:
- Property attributes from the Catastro database
- Formatted dates (SALESDTTM_FORMATTED)
- Google Maps satellite links for each property
- Distance from search center (for radius searches)
- Calculated fields for analysis

## Troubleshooting

### Common Issues

1. **"Some properties might not be included in the results"**
   - This warning appears when a grid cell hits the 1,000 record limit
   - Solution: Rerun your search with a larger grid value (e.g., `--grid 5` or `--grid 7`)

2. **Connection errors**
   - The tool automatically manages authentication with the Catastro service
   - If you see connection errors, try running the search again
   - Consider reducing the rate limit (e.g., `--rate-limit 20`)

3. **No results found**
   - Check your search parameters
   - For radius searches, try increasing the radius
   - For catastro searches, verify the number format

4. **Slow performance**
   - The tool implements rate limiting to avoid overwhelming the API
   - You can adjust the rate with `--rate-limit`, but setting it too high might cause connection issues

5. **Out of memory errors**
   - For very large searches (e.g., large radius or entire municipality), ensure your system has sufficient memory
   - Consider using more filters to narrow your search

## Dependencies

- `selenium`: For automated web session handling
- `pandas`: For data manipulation and export
- `requests`: For API communication
- `tqdm`: For progress bars
- `ratelimit`: For API rate limiting
- `rtree`: For spatial indexing