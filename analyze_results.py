#!/usr/bin/env python3
"""
Puerto Rico Property Results Analyzer
------------------------------------
A command-line tool for analyzing results from the PR Property Search Tool.

Usage:
    python analyze_results.py results.csv --output-dir ./analysis_output
"""

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import os
import sys
import argparse
from datetime import datetime

def load_and_clean_data(csv_path):
    """Load and clean the property data from CSV."""
    # Load the CSV file
    df = pd.read_csv(csv_path)
    print(f"Loaded {len(df)} properties from {csv_path}")
    
    # Convert date column to datetime
    if 'SALESDTTM_FORMATTED' in df.columns:
        df['SALESDTTM_FORMATTED'] = pd.to_datetime(df['SALESDTTM_FORMATTED'], errors='coerce')
        
    # Clean numeric columns
    numeric_cols = ['SALESAMT', 'TOTALVAL', 'LAND', 'STRUCTURE', 'MACHINERY', 'DISTANCE_MILES']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    
    # Add year and month columns if date is available
    if 'SALESDTTM_FORMATTED' in df.columns:
        df['Sale_Year'] = df['SALESDTTM_FORMATTED'].dt.year
        df['Sale_Month'] = df['SALESDTTM_FORMATTED'].dt.month
        
    # Flag for valid sales (non-symbolic transactions)
    df['Valid_Sale'] = df['SALESAMT'] > 5000
    
    return df

def generate_summary_statistics(df, output_dir=None):
    """Generate and display summary statistics."""
    # Basic property counts
    total_properties = len(df)
    properties_with_sales = len(df[df['SALESAMT'] > 0])
    valid_sales = len(df[df['Valid_Sale']])
    
    # Price statistics for valid sales
    if valid_sales > 0:
        avg_price = df[df['Valid_Sale']]['SALESAMT'].mean()
        median_price = df[df['Valid_Sale']]['SALESAMT'].median()
        min_price = df[df['Valid_Sale']]['SALESAMT'].min()
        max_price = df[df['Valid_Sale']]['SALESAMT'].max()
    else:
        avg_price = median_price = min_price = max_price = 0
    
    # Property values
    avg_property_value = df['TOTALVAL'].mean() if 'TOTALVAL' in df.columns else 0
    
    # Date range
    if 'SALESDTTM_FORMATTED' in df.columns:
        min_date = df['SALESDTTM_FORMATTED'].min()
        max_date = df['SALESDTTM_FORMATTED'].max()
        date_range = f"{min_date:%Y-%m-%d} to {max_date:%Y-%m-%d}"
    else:
        date_range = "No date data available"
    
    # Municipality information
    if 'MUNICIPIO' in df.columns:
        municipalities = df['MUNICIPIO'].value_counts()
        main_municipality = municipalities.index[0] if not municipalities.empty else "Unknown"
        main_municipality_count = municipalities.iloc[0] if not municipalities.empty else 0
    else:
        main_municipality = "Unknown"
        main_municipality_count = 0
    
    # Create summary text
    summary_text = [
        "=== PROPERTY ANALYSIS SUMMARY ===",
        f"Total properties: {total_properties}",
        f"Properties with sales data: {properties_with_sales}",
        f"Valid sales (non-symbolic): {valid_sales}",
        f"Average sale price: ${avg_price:,.2f}",
        f"Median sale price: ${median_price:,.2f}",
        f"Sale price range: ${min_price:,.2f} to ${max_price:,.2f}",
        f"Average property value: ${avg_property_value:,.2f}",
        f"Date range: {date_range}",
        f"Main municipality: {main_municipality} ({main_municipality_count} properties)"
    ]
    
    # Print to console
    for line in summary_text:
        print(line)
    
    # Save to file if output directory provided
    if output_dir:
        with open(os.path.join(output_dir, 'summary_statistics.txt'), 'w') as f:
            f.write('\n'.join(summary_text))
    
    # Create a summary dataframe for potential further use
    summary_df = pd.DataFrame({
        'Metric': ['Total Properties', 'Properties with Sales', 'Valid Sales',
                  'Average Price', 'Median Price', 'Minimum Price', 'Maximum Price',
                  'Average Value', 'Date Range', 'Main Municipality'],
        'Value': [total_properties, properties_with_sales, valid_sales,
                 f"${avg_price:,.2f}", f"${median_price:,.2f}", 
                 f"${min_price:,.2f}", f"${max_price:,.2f}",
                 f"${avg_property_value:,.2f}", date_range, 
                 f"{main_municipality} ({main_municipality_count})"]
    })
    
    return summary_df

def analyze_sales_over_time(df, output_dir=None):
    """Analyze and visualize sales over time."""
    # Check if we have date and price data
    if 'SALESDTTM_FORMATTED' not in df.columns or 'SALESAMT' not in df.columns:
        print("WARNING: Missing date or sales data for time analysis")
        return None
    
    # Group by year and calculate statistics
    yearly_stats = df[df['Valid_Sale']].groupby('Sale_Year').agg({
        'SALESAMT': ['count', 'mean', 'median', 'min', 'max'],
        'CATASTRO': 'count'  # Total properties per year
    }).reset_index()
    
    # Flatten the multi-level columns
    yearly_stats.columns = [
        'Year', 'Sales_Count', 'Avg_Price', 'Median_Price', 'Min_Price', 'Max_Price', 'Total_Properties'
    ]
    
    # Filter to years with sufficient data and within reasonable range
    recent_years = yearly_stats[yearly_stats['Sales_Count'] >= 1].copy()
    
    # Create visualization
    plt.figure(figsize=(12, 7))
    
    # Set style
    sns.set(style="whitegrid")
    
    # Plot average and median prices
    ax1 = plt.subplot(111)
    ax1.plot(recent_years['Year'], recent_years['Avg_Price'], 
             'b-', marker='o', linewidth=2, label='Average Price')
    ax1.plot(recent_years['Year'], recent_years['Median_Price'], 
             'g-', marker='s', linewidth=2, label='Median Price')
    
    # Set labels
    ax1.set_xlabel('Year', fontsize=12)
    ax1.set_ylabel('Price ($)', fontsize=12)
    ax1.set_title('Property Prices Over Time', fontsize=14, fontweight='bold')
    
    # Format y-axis as currency
    from matplotlib.ticker import FuncFormatter
    ax1.yaxis.set_major_formatter(FuncFormatter(lambda x, p: f'${x:,.0f}'))
    
    # Add second y-axis for transaction count
    ax2 = ax1.twinx()
    ax2.bar(recent_years['Year'], recent_years['Sales_Count'], 
            alpha=0.2, color='gray', label='Number of Sales')
    ax2.set_ylabel('Number of Transactions', fontsize=12)
    
    # Add gridlines
    ax1.grid(True, linestyle='--', alpha=0.7)
    
    # Combine legends from both axes
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left')
    
    # Adjust layout for better fit
    plt.tight_layout()
    
    # Save or show the plot
    if output_dir:
        plt.savefig(os.path.join(output_dir, 'sales_over_time.png'), dpi=300, bbox_inches='tight')
    else:
        plt.show()
    
    plt.close()
    
    return yearly_stats

def analyze_property_values(df, output_dir=None):
    """Analyze and visualize property values and prices."""
    # Price distribution histogram
    if 'SALESAMT' in df.columns and df[df['Valid_Sale']].shape[0] > 0:
        plt.figure(figsize=(10, 6))
        
        # Create price bins
        max_price = min(df[df['Valid_Sale']]['SALESAMT'].max(), 2000000)  # Cap at $2M for better visualization
        price_bins = np.arange(0, max_price + 100000, 100000)
        
        # Plot histogram
        sns.histplot(df[df['Valid_Sale'] & (df['SALESAMT'] <= max_price)]['SALESAMT'], 
                     bins=price_bins, kde=True)
        
        plt.title('Distribution of Property Sale Prices', fontsize=14, fontweight='bold')
        plt.xlabel('Sale Price ($)', fontsize=12)
        plt.ylabel('Number of Properties', fontsize=12)
        
        # Format x-axis as currency
        from matplotlib.ticker import FuncFormatter
        plt.gca().xaxis.set_major_formatter(FuncFormatter(lambda x, p: f'${x/1000:.0f}k'))
        
        # Add grid
        plt.grid(True, linestyle='--', alpha=0.7)
        
        # Save or show the plot
        if output_dir:
            plt.savefig(os.path.join(output_dir, 'price_distribution.png'), dpi=300, bbox_inches='tight')
        else:
            plt.show()
        
        plt.close()
    
    # Total value vs sale price scatter plot
    if 'TOTALVAL' in df.columns and 'SALESAMT' in df.columns and df[df['Valid_Sale']].shape[0] > 0:
        plt.figure(figsize=(10, 6))
        
        # Filter data
        plot_df = df[df['Valid_Sale'] & (df['TOTALVAL'] > 0) & (df['SALESAMT'] <= 2000000)]
        
        # Create scatter plot
        sns.scatterplot(data=plot_df, x='TOTALVAL', y='SALESAMT', alpha=0.7)
        
        # Add diagonal line (x=y)
        max_val = max(plot_df['TOTALVAL'].max(), plot_df['SALESAMT'].max())
        plt.plot([0, max_val], [0, max_val], 'r--', linewidth=1)
        
        plt.title('Property Value vs Sale Price', fontsize=14, fontweight='bold')
        plt.xlabel('Total Assessed Value ($)', fontsize=12)
        plt.ylabel('Sale Price ($)', fontsize=12)
        
        # Format axes as currency
        from matplotlib.ticker import FuncFormatter
        plt.gca().xaxis.set_major_formatter(FuncFormatter(lambda x, p: f'${x/1000:.0f}k'))
        plt.gca().yaxis.set_major_formatter(FuncFormatter(lambda x, p: f'${x/1000:.0f}k'))
        
        # Add grid
        plt.grid(True, linestyle='--', alpha=0.7)
        
        # Save or show the plot
        if output_dir:
            plt.savefig(os.path.join(output_dir, 'value_vs_price.png'), dpi=300, bbox_inches='tight')
        else:
            plt.show()
        
        plt.close()
    
    return None

def analyze_spatial_distribution(df, output_dir=None):
    """Analyze and visualize the spatial distribution of properties."""
    # Check if we have coordinate data
    if 'INSIDE_X' not in df.columns or 'INSIDE_Y' not in df.columns:
        print("WARNING: Coordinate data missing for spatial analysis")
        return None
    
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
        sns.scatterplot(
            data=geo_df,
            x='INSIDE_X',
            y='INSIDE_Y',
            hue='price_bracket',
            palette='viridis',
            s=100,
            alpha=0.7
        )
        
        plt.legend(title='Price Range')
    else:
        # Simple scatter plot without color coding
        sns.scatterplot(data=geo_df, x='INSIDE_X', y='INSIDE_Y', s=100, alpha=0.7)
    
    plt.title('Spatial Distribution of Properties', fontsize=14, fontweight='bold')
    plt.xlabel('Longitude', fontsize=12)
    plt.ylabel('Latitude', fontsize=12)
    plt.grid(True, linestyle='--', alpha=0.7)
    
    # Save or show the plot
    if output_dir:
        plt.savefig(os.path.join(output_dir, 'spatial_distribution.png'), dpi=300, bbox_inches='tight')
    else:
        plt.show()
    
    plt.close()
    
    return geo_df

def analyze_distance_vs_price(df, output_dir=None):
    """Analyze the relationship between distance and property price."""
    # Check if we have distance and price data
    if 'DISTANCE_MILES' not in df.columns or 'SALESAMT' not in df.columns:
        print("WARNING: Distance or price data missing for analysis")
        return None
    
    # Filter to valid sales with distance data
    dist_df = df[(df['Valid_Sale']) & (~df['DISTANCE_MILES'].isna())].copy()
    
    if len(dist_df) > 0:
        # Create a scatter plot
        plt.figure(figsize=(10, 6))
        
        # Plot distance vs price
        sns.scatterplot(data=dist_df, x='DISTANCE_MILES', y='SALESAMT', alpha=0.7, s=80)
        
        # Add trendline
        sns.regplot(data=dist_df, x='DISTANCE_MILES', y='SALESAMT', 
                   scatter=False, color='red', line_kws={"linestyle": "--"})
        
        plt.title('Property Price vs. Distance from Center', fontsize=14, fontweight='bold')
        plt.xlabel('Distance (miles)', fontsize=12)
        plt.ylabel('Sale Price ($)', fontsize=12)
        plt.grid(True, linestyle='--', alpha=0.7)
        
        # Format y-axis as currency
        from matplotlib.ticker import FuncFormatter
        plt.gca().yaxis.set_major_formatter(FuncFormatter(lambda x, p: f'${x:,.0f}'))
        
        # Save or show the plot
        if output_dir:
            plt.savefig(os.path.join(output_dir, 'price_vs_distance.png'), dpi=300, bbox_inches='tight')
        else:
            plt.show()
        
        plt.close()
    
    return dist_df

def export_analysis_to_csv(df, output_dir):
    """Export additional analysis to CSV files."""
    if not output_dir:
        return
    
    # 1. Sales data by year
    if 'Sale_Year' in df.columns:
        yearly_data = df[df['Valid_Sale']].groupby('Sale_Year').agg({
            'SALESAMT': ['count', 'mean', 'median', 'min', 'max', 'sum'],
            'CATASTRO': 'count'
        }).reset_index()
        
        # Flatten columns
        yearly_data.columns = [
            'Year', 'Sales_Count', 'Avg_Price', 'Median_Price', 
            'Min_Price', 'Max_Price', 'Total_Value', 'Property_Count'
        ]
        
        yearly_data.to_csv(os.path.join(output_dir, 'yearly_sales_data.csv'), index=False)
    
    # 2. Price statistics by property type (if available)
    if 'TIPO' in df.columns:
        type_stats = df[df['Valid_Sale']].groupby('TIPO').agg({
            'SALESAMT': ['count', 'mean', 'median', 'min', 'max'],
            'TOTALVAL': ['mean', 'median']
        }).reset_index()
        
        # Flatten columns
        type_stats.columns = [
            'Property_Type', 'Sales_Count', 'Avg_Sale_Price', 'Median_Sale_Price', 
            'Min_Sale_Price', 'Max_Sale_Price', 'Avg_Value', 'Median_Value'
        ]
        
        type_stats.to_csv(os.path.join(output_dir, 'property_type_stats.csv'), index=False)
    
    # 3. Export price range data
    price_ranges = pd.cut(
        df[df['Valid_Sale']]['SALESAMT'],
        bins=[0, 50000, 100000, 200000, 300000, 500000, 1000000, float('inf')],
        labels=['<$50K', '$50K-$100K', '$100K-$200K', '$200K-$300K', 
                '$300K-$500K', '$500K-$1M', '>$1M']
    ).value_counts().reset_index()
    
    price_ranges.columns = ['Price_Range', 'Property_Count']
    price_ranges.to_csv(os.path.join(output_dir, 'price_range_distribution.csv'), index=False)

def main():
    """Main function."""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Analyze property search results')
    parser.add_argument('csv_file', help='Path to results CSV file')
    parser.add_argument('--output-dir', '-o', help='Directory to save analysis outputs')
    args = parser.parse_args()
    
    # Create output directory if specified
    if args.output_dir:
        os.makedirs(args.output_dir, exist_ok=True)
        print(f"Analysis outputs will be saved to: {args.output_dir}")
    
    # Load and clean data
    df = load_and_clean_data(args.csv_file)
    
    # Generate summary
    generate_summary_statistics(df, args.output_dir)
    
    # Run analyses
    analyze_sales_over_time(df, args.output_dir)
    analyze_property_values(df, args.output_dir)
    analyze_spatial_distribution(df, args.output_dir)
    analyze_distance_vs_price(df, args.output_dir)
    
    # Export additional data
    if args.output_dir:
        export_analysis_to_csv(df, args.output_dir)
        print(f"Analysis complete. Results saved to {args.output_dir}")
    else:
        print("Analysis complete.")

if __name__ == "__main__":
    main()