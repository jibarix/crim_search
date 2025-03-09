#!/usr/bin/env python3
"""
Puerto Rico Property Search Tool
--------------------------------
A comprehensive tool for searching and analyzing property data
from the Puerto Rico Catastro database.

Features:
- Grid-based radius searches for comprehensive coverage
- Municipality-wide property searches
- Single property lookup by catastro number
- Address-based searches (future)
- Filtering by price, date, and other criteria
- Export to CSV or JSON formats
"""

import sys
from search_interface import main

if __name__ == "__main__":
    sys.exit(main())