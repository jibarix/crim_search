# Puerto Rico Property Search Tool: User Guide

This guide will help you effectively use the Puerto Rico Property Search Tool to find and analyze property data from the Puerto Rico Catastro database.

## Installation

### Prerequisites
- Python 3.8 or higher
- pip (Python package installer)

### Setup Steps
1. Clone the repository:
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

## Search Types

The tool offers several search methods to find properties in Puerto Rico.

### 1. Radius Search

Search for properties within a specific radius around a point.

#### Command Syntax
```
python property_search_tool.py radius [OPTIONS]
```

#### Required Parameters (choose one):
- `--lat VALUE --lon VALUE`: Center coordinates in decimal degrees
- `--catastro NUMBER`: Center point defined by a catastro number
- `--radius VALUE`: Search radius in miles

#### Example Search Around Coordinates
```
python property_search_tool.py radius --lat 18.445550 --lon -66.064836 --radius 1.5 --output results.csv
```

#### Example Search Around Catastro Number
```
python property_search_tool.py radius --catastro 042-000-006-29 --radius 1.5 --output results.csv
```

#### Advanced Example with Multiple Filters
```
python property_search_tool.py radius --lat 18.445550 --lon -66.064836 --radius 1 --grid 4 --min-date 2024-01-01 --min-price 100000 --output downtown_properties.csv --min-cabida 20 --max-cabida 100
```

### 2. Municipality Search

Search for all properties within a specific municipality.

#### Command Syntax
```
python property_search_tool.py municipio "MUNICIPALITY_NAME" [OPTIONS]
```

#### Example
```
python property_search_tool.py municipio "SAN JUAN" --output sanjuan_properties.csv
```

#### Filtered Example
```
python property_search_tool.py municipio "PONCE" --min-price 200000 --min-date 2023-01-01 --output ponce_luxury.csv
```

### 3. Catastro Number Search

Look up details for a specific property by its catastro number.

#### Command Syntax
```
python property_search_tool.py catastro NUMBER [OPTIONS]
```

#### Example
```
python property_search_tool.py catastro 042-000-006-29 --output property_details.csv
```

## Common Options

These options can be used with any search type:

### Output Options
- `--output FILENAME`: Save results to a file (CSV or JSON)

### Filter Options
- `--min-price VALUE`: Minimum sale price
- `--max-price VALUE`: Maximum sale price
- `--min-date YYYY-MM-DD`: Minimum sale date
- `--max-date YYYY-MM-DD`: Maximum sale date
- `--min-cabida VALUE`: Minimum land area in square meters
- `--max-cabida VALUE`: Maximum land area in square meters

### Performance Options
- `--rate-limit VALUE`: Maximum API calls per minute (default: 30)
- `--grid VALUE`: Grid size for radius searches (default: 3, higher for more complete results)

## Understanding Grid-Based Search

The radius search divides the area into a grid to overcome API limitations:

1. The search area is divided into a grid (default 3×3, configurable with `--grid`)
2. Each grid cell is queried independently
3. Results are combined and filtered by exact distance
4. Duplicate properties are removed

This approach helps overcome the 1,000 record per query limit of the API and ensures more comprehensive coverage.

## Handling Incomplete Results

When a grid cell reaches the 1,000 record limit, you'll see a warning:

```
WARNING: 2 cell(s) reached the 1000 record limit!
Some properties might not be included in the results.
Consider using a finer grid (increase --grid parameter) for more complete results.
Current grid size: 3x3, consider trying 5x5
```

Solution: Rerun your search with a larger grid value (e.g., `--grid 5` or `--grid 7`)

## Output Fields

The results include:
- Property attributes from the Catastro database
- Formatted dates (SALESDTTM_FORMATTED)
- Google Maps satellite links for each property
- Distance from search center (for radius searches)

## Troubleshooting

### Common Issues

1. **Connection errors**: The tool automatically manages authentication with the Catastro service. If you see connection errors, try running the search again.

2. **No results found**: Check your search parameters. For radius searches, try increasing the radius. For catastro searches, verify the number format.

3. **Slow performance**: The tool implements rate limiting to avoid overwhelming the API. You can adjust the rate with `--rate-limit`, but setting it too high might cause connection issues.

4. **Out of memory errors**: For very large searches (e.g., large radius or entire municipality), ensure your system has sufficient memory.

## Best Practices

1. Start with smaller searches to understand the data
2. Use filters to narrow down results when searching in dense areas
3. For comprehensive radius searches, use larger grid sizes (5×5 or 7×7)
4. Save your results to CSV for easy analysis in spreadsheet programs
5. When searching recently sold properties, use the `--min-date` filter

## Examples for Common Use Cases

### Find Recent High-Value Sales in San Juan
```
python property_search_tool.py municipio "SAN JUAN" --min-date 2023-01-01 --min-price 500000 --output sanjuan_luxury_recent.csv
```

### Find Properties Within Walking Distance of a Location
```
python property_search_tool.py radius --lat 18.445550 --lon -66.064836 --radius 0.25 --grid 5 --output walking_distance.csv
```

### Find Medium-Sized Lots in Ponce
```
python property_search_tool.py municipio "PONCE" --min-cabida 500 --max-cabida 2000 --output ponce_medium_lots.csv
```

### Find Properties Near a Known Property
```
python property_search_tool.py radius --catastro 042-000-006-29 --radius 0.5 --grid 4 --output nearby_properties.csv
```