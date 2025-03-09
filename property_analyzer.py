#!/usr/bin/env python3
"""
Puerto Rico Property Analysis Tool
----------------------------------
A tool for analyzing and visualizing property data from the PR Property Search Tool.

This script processes CSV output from the Property Search Tool and generates
visualization and analysis reports to help understand property trends.

Features:
- Price trend analysis by year
- Property type distribution
- Geographic clustering
- Comparative market analysis
- Export visualizations to PNG/PDF
"""

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import os
import sys
import argparse
from datetime import datetime
from pathlib import Path

def load_property_data(file_path):
    """Load property data from CSV file into a pandas DataFrame."""
    try:
        df = pd.read_csv(file_path)
        print(f"Loaded {len(df)} properties from {file_path}")
        return df
    except Exception as e:
        print(f"Error loading file: {e}")
        return None

def clean_property_data(df):
    """Clean and prepare property data for analysis."""
    # Make a copy to avoid altering the original
    clean_df = df.copy()
    
    # Handle missing values for numeric columns
    numeric_cols = ['SALESAMT', 'CABIDA', 'LAND', 'STRUCTURE', 'MACHINERY', 
                    'TOTALVAL', 'EXEMP', 'EXON', 'TAXABLE']
    for col in numeric_cols:
        if col in clean_df.columns:
            # Replace missing/invalid with NaN, then with 0
            clean_df[col] = pd.to_numeric(clean_df[col], errors='coerce').fillna(0)
    
    # Ensure date columns are properly formatted
    if 'SALESDTTM_FORMATTED' in clean_df.columns:
        # Convert to datetime
        clean_df['SALESDTTM_FORMATTED'] = pd.to_datetime(
            clean_df['SALESDTTM_FORMATTED'], errors='coerce'
        )
        
        # Create year and month columns
        clean_df['SALE_YEAR'] = clean_df['SALESDTTM_FORMATTED'].dt.year
        clean_df['SALE_MONTH'] = clean_df['SALESDTTM_FORMATTED'].dt.month
    
    # Filter out unrealistic sale amounts (e.g., $1 symbolic sales)
    if 'SALESAMT' in clean_df.columns:
        # For some analyses, we'll want to exclude symbolic sales
        clean_df['VALID_SALE'] = clean_df['SALESAMT'] > 5000
    
    return clean_df

def analyze_price_trends(df, output_dir=None):
    """Analyze and visualize price trends over time."""
    if 'SALESDTTM_FORMATTED' not in df.columns or 'SALESAMT' not in df.columns:
        print("Required columns missing for price trend analysis")
        return
    
    # Ensure we have the year column
    if 'SALE_YEAR' not in df.columns:
        df['SALE_YEAR'] = pd.to_datetime(df['SALESDTTM_FORMATTED'], errors='coerce').dt.year
    
    # Group by year and calculate statistics
    yearly_stats = df.groupby('SALE_YEAR').agg({
        'SALESAMT': ['count', 'mean', 'median', 'min', 'max'],
        'CATASTRO': 'count'  # Total properties per year
    }).reset_index()
    
    # Flatten the column names
    yearly_stats.columns = [
        'Year', 'Sales_Count', 'Avg_Price', 'Median_Price', 'Min_Price', 'Max_Price', 'Total_Properties'
    ]
    
    # Filter to recent years with enough data
    recent_years = yearly_stats[yearly_stats['Sales_Count'] >= 1].copy()
    recent_years = recent_years[recent_years['Year'] >= 2000].copy()
    
    # Create visualization
    plt.figure(figsize=(12, 7))
    
    # Set style
    sns.set(style="whitegrid")
    
    # Plot average and median prices
    ax1 = plt.subplot(111)
    avg_line = ax1.plot(recent_years['Year'], recent_years['Avg_Price'], 
                        'b-', marker='o', linewidth=2, label='Average Price')
    med_line = ax1.plot(recent_years['Year'], recent_years['Median_Price'], 
                        'g-', marker='s', linewidth=2, label='Median Price')
    
    # Format y-axis as currency
    ax1.yaxis.set_major_formatter('${x:,.0f}')
    
    # Set labels
    ax1.set_xlabel('Year', fontsize=12)
    ax1.set_ylabel('Price ($)', fontsize=12)
    ax1.set_title('Property Prices Over Time', fontsize=14, fontweight='bold')
    
    # Add second y-axis for transaction count
    ax2 = ax1.twinx()
    count_bars = ax2.bar(recent_years['Year'], recent_years['Sales_Count'], 
                         alpha=0.2, color='gray', label='Number of Sales')
    ax2.set_ylabel('Number of Transactions', fontsize=12)
    
    # Add gridlines
    ax1.grid(True, linestyle='--', alpha=0.7)
    
    # Combine legends from both axes
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left')
    
    # Rotate x-axis labels for better readability
    plt.setp(ax1.get_xticklabels(), rotation=45)
    
    # Adjust layout for better fit
    plt.tight_layout()
    
    # Show plot
    if output_dir:
        plt.savefig(os.path.join(output_dir, 'price_trends.png'), dpi=300, bbox_inches='tight')
    else:
        plt.show()
    
    plt.close()
    
    return yearly_stats

def analyze_property_types(df, output_dir=None):
    """Analyze distribution of property types and their values."""
    if 'TIPO' not in df.columns or len(df['TIPO'].unique()) <= 1:
        print("Not enough property type variation for analysis")
        return

    # Count properties by type
    type_counts = df['TIPO'].value_counts().reset_index()
    type_counts.columns = ['Type', 'Count']
    
    # Calculate average values by type
    type_values = df.groupby('TIPO').agg({
        'TOTALVAL': 'mean',
        'SALESAMT': ['mean', 'median', 'count']
    }).reset_index()
    
    # Flatten columns
    type_values.columns = ['Type', 'Avg_Total_Value', 'Avg_Sale_Price', 'Median_Sale_Price', 'Sales_Count']
    
    # Create visualization
    plt.figure(figsize=(12, 8))
    
    # Create a pie chart for type distribution
    plt.subplot(121)
    plt.pie(type_counts['Count'], labels=type_counts['Type'], autopct='%1.1f%%',
            shadow=True, startangle=90)
    plt.axis('equal')
    plt.title('Property Type Distribution', fontsize=14, fontweight='bold')
    
    # Create a bar chart for average values
    plt.subplot(122)
    sns.barplot(x='Type', y='Avg_Total_Value', data=type_values)
    plt.title('Average Property Value by Type', fontsize=14, fontweight='bold')
    plt.ylabel('Average Value ($)')
    plt.xticks(rotation=45)
    
    # Format y-axis as currency
    ax = plt.gca()
    ax.yaxis.set_major_formatter('${x:,.0f}')
    
    plt.tight_layout()
    
    if output_dir:
        plt.savefig(os.path.join(output_dir, 'property_types.png'), dpi=300, bbox_inches='tight')
    else:
        plt.show()
    
    plt.close()
    
    return type_values

def analyze_spatial_distribution(df, output_dir=None):
    """Analyze and visualize the spatial distribution of properties."""
    # Check if we have coordinate data
    if 'INSIDE_X' not in df.columns or 'INSIDE_Y' not in df.columns:
        print("Coordinate data missing for spatial analysis")
        return
    
    # Filter out any rows with missing coordinates
    geo_df = df.dropna(subset=['INSIDE_X', 'INSIDE_Y']).copy()
    
    # Create a scatter plot of property locations
    plt.figure(figsize=(10, 10))
    
    # Use different colors for different price points
    if 'SALESAMT' in geo_df.columns:
        # Create price brackets
        geo_df['price_bracket'] = pd.cut(
            geo_df['SALESAMT'], 
            bins=[0, 50000, 100000, 200000, 500000, float('inf')],
            labels=['<$50K', '$50K-$100K', '$100K-$200K', '$200K-$500K', '>$500K']
        )
        
        # Plot with price coloring
        scatter = plt.scatter(
            geo_df['INSIDE_X'], 
            geo_df['INSIDE_Y'],
            c=pd.Categorical(geo_df['price_bracket']).codes,
            alpha=0.7,
            s=80,
            cmap='viridis'
        )
        
        # Add a legend
        legend1 = plt.legend(scatter.legend_elements()[0], 
                            geo_df['price_bracket'].cat.categories,
                            title="Price Range")
        plt.gca().add_artist(legend1)
    else:
        # Simple scatter plot without color coding
        plt.scatter(geo_df['INSIDE_X'], geo_df['INSIDE_Y'], alpha=0.7, s=80)
    
    plt.title('Spatial Distribution of Properties', fontsize=14, fontweight='bold')
    plt.xlabel('Longitude', fontsize=12)
    plt.ylabel('Latitude', fontsize=12)
    plt.grid(True, linestyle='--', alpha=0.7)
    
    if output_dir:
        plt.savefig(os.path.join(output_dir, 'spatial_distribution.png'), dpi=300, bbox_inches='tight')
    else:
        plt.show()
    
    plt.close()
    
    return geo_df

def analyze_distance_vs_price(df, output_dir=None):
    """Analyze how property prices change with distance from search center."""
    if 'DISTANCE_MILES' not in df.columns or 'SALESAMT' not in df.columns:
        print("Distance or price data missing for analysis")
        return
    
    # Filter to valid sales with distance data
    dist_df = df[(df['SALESAMT'] > 5000) & (~df['DISTANCE_MILES'].isna())].copy()
    
    # Create a scatter plot
    plt.figure(figsize=(10, 6))
    
    # Plot distance vs price
    plt.scatter(dist_df['DISTANCE_MILES'], dist_df['SALESAMT'], alpha=0.7, s=80)
    
    # Add trendline
    if len(dist_df) > 1:
        z = np.polyfit(dist_df['DISTANCE_MILES'], dist_df['SALESAMT'], 1)
        p = np.poly1d(z)
        plt.plot(dist_df['DISTANCE_MILES'], p(dist_df['DISTANCE_MILES']), "r--", linewidth=2)
    
    plt.title('Property Price vs. Distance from Center', fontsize=14, fontweight='bold')
    plt.xlabel('Distance (miles)', fontsize=12)
    plt.ylabel('Sale Price ($)', fontsize=12)
    plt.grid(True, linestyle='--', alpha=0.7)
    
    # Format y-axis as currency
    ax = plt.gca()
    ax.yaxis.set_major_formatter('${x:,.0f}')
    
    if output_dir:
        plt.savefig(os.path.join(output_dir, 'price_vs_distance.png'), dpi=300, bbox_inches='tight')
    else:
        plt.show()
    
    plt.close()
    
    return dist_df

def generate_property_report(df, output_dir=None):
    """Generate a comprehensive property analysis report."""
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    
    # Create a summary of the data
    summary = {
        'total_properties': len(df),
        'properties_with_sales': len(df[df['SALESAMT'] > 0]),
        'avg_sale_price': df[df['SALESAMT'] > 5000]['SALESAMT'].mean(),
        'median_sale_price': df[df['SALESAMT'] > 5000]['SALESAMT'].median(),
        'min_sale_price': df[df['SALESAMT'] > 5000]['SALESAMT'].min(),
        'max_sale_price': df[df['SALESAMT'] > 5000]['SALESAMT'].max(),
        'avg_property_value': df['TOTALVAL'].mean(),
        'most_recent_sale': df['SALESDTTM_FORMATTED'].max(),
        'oldest_sale': df['SALESDTTM_FORMATTED'].min(),
    }
    
    # Print summary
    print("\n=== Property Analysis Summary ===")
    print(f"Total properties: {summary['total_properties']}")
    print(f"Properties with sales data: {summary['properties_with_sales']}")
    print(f"Average sale price: ${summary['avg_sale_price']:,.2f}")
    print(f"Median sale price: ${summary['median_sale_price']:,.2f}")
    print(f"Sale price range: ${summary['min_sale_price']:,.2f} to ${summary['max_sale_price']:,.2f}")
    print(f"Average property value: ${summary['avg_property_value']:,.2f}")
    print(f"Date range: {summary['oldest_sale']} to {summary['most_recent_sale']}")
    
    # Run all analyses
    price_trends = analyze_price_trends(df, output_dir)
    property_types = analyze_property_types(df, output_dir)
    spatial_data = analyze_spatial_distribution(df, output_dir)
    distance_data = analyze_distance_vs_price(df, output_dir)
    
    # If output directory is provided, save the summary
    if output_dir:
        summary_file = os.path.join(output_dir, 'analysis_summary.txt')
        with open(summary_file, 'w') as f:
            f.write("=== Property Analysis Summary ===\n")
            f.write(f"Analysis date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Total properties: {summary['total_properties']}\n")
            f.write(f"Properties with sales data: {summary['properties_with_sales']}\n")
            f.write(f"Average sale price: ${summary['avg_sale_price']:,.2f}\n")
            f.write(f"Median sale price: ${summary['median_sale_price']:,.2f}\n")
            f.write(f"Sale price range: ${summary['min_sale_price']:,.2f} to ${summary['max_sale_price']:,.2f}\n")
            f.write(f"Average property value: ${summary['avg_property_value']:,.2f}\n")
            f.write(f"Date range: {summary['oldest_sale']} to {summary['most_recent_sale']}\n")
        
        print(f"\nAnalysis report saved to {output_dir}")
    
    return summary

def setup_cli_parser():
    """Set up command-line interface parser."""
    parser = argparse.ArgumentParser(description="Property Analysis Tool")
    
    parser.add_argument("input_file", help="Input CSV file from property search")
    parser.add_argument("--output-dir", "-o", help="Output directory for reports and visualizations")
    parser.add_argument("--analysis", "-a", choices=['all', 'price', 'types', 'spatial', 'distance'],
                        default='all', help="Type of analysis to perform")
    
    return parser

def main():
    """Main function for command-line interface."""
    parser = setup_cli_parser()
    args = parser.parse_args()
    
    # Load and clean data
    df = load_property_data(args.input_file)
    if df is None:
        return 1
    
    clean_df = clean_property_data(df)
    
    # Create output directory if specified
    if args.output_dir:
        os.makedirs(args.output_dir, exist_ok=True)
    
    # Run analyses based on user selection
    if args.analysis == 'all':
        generate_property_report(clean_df, args.output_dir)
    elif args.analysis == 'price':
        analyze_price_trends(clean_df, args.output_dir)
    elif args.analysis == 'types':
        analyze_property_types(clean_df, args.output_dir)
    elif args.analysis == 'spatial':
        analyze_spatial_distribution(clean_df, args.output_dir)
    elif args.analysis == 'distance':
        analyze_distance_vs_price(clean_df, args.output_dir)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())