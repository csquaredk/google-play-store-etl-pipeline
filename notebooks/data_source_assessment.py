import pandas as pd
import re

def run_data_source_assessment(file_path):
    """
    Performs a comprehensive data quality assessment on a raw extraction sample.
    """
    print(f"=========================================================")
    print(f"DATA SOURCE ASSESSMENT: {file_path}")
    print(f"=========================================================\n")
    
    try:
        df = pd.read_csv(file_path)
    except FileNotFoundError:
        print(f"[Error] File not found. Please verify the relative path: {file_path}")
        return

    # 1. Structural & Completeness Profiling
    print("1. COMPLETENESS & SCHEMA")
    print("-" * 40)
    missing_data = df.isnull().sum()
    missing_percent = (missing_data / len(df)) * 100
    completeness_df = pd.DataFrame({'Missing Values': missing_data, 'Missing %': missing_percent})
    
    print(f"Total Rows Scanned: {len(df)}")
    print("\nColumns with Missing Data:")
    print(completeness_df[completeness_df['Missing Values'] > 0].to_string())
    print("\n")

    # 2. Uniqueness & Redundancy Profiling
    print("2. UNIQUENESS PROFILING")
    print("-" * 40)
    unique_ids = df['reviewId'].nunique() if 'reviewId' in df.columns else 'N/A'
    print(f"Unique 'reviewId' count: {unique_ids} / {len(df)}")
    
    if 'content' in df.columns:
        duplicate_texts = df.duplicated(subset=['content'], keep=False).sum()
        dupe_pct = (duplicate_texts / len(df)) * 100
        print(f"Duplicate Text Entries:  {duplicate_texts} ({dupe_pct:.2f}%)")
    print("\n")

    # 3. Statistical Profiling & Outliers (Word Count)
    print("3. STATISTICAL PROFILING: WORD COUNT DENSITY")
    print("-" * 40)
    if 'content' in df.columns:
        df['content'] = df['content'].fillna('').astype(str)
        df['word_count'] = df['content'].str.split().str.len()
        print(df['word_count'].describe(percentiles=[.25, .5, .75, .90]).to_string())
    print("\n")
    
    # 4. Domain Logic: International Marker Diagnostic
    print("4. DOMAIN LOGIC: INTERNATIONAL MARKERS")
    print("-" * 40)
    if 'content' in df.columns:
        text_data = df['content'].str.lower()
        pounds = text_data.str.contains('£').sum()
        euros = text_data.str.contains('€').sum()
        rupees = text_data.str.contains('₹').sum()
        
        # Regex to match exact words, preventing false positives
        uk_spelling = text_data.str.contains(r'\b(colour|favour|behaviour|programme|centre)\b', regex=True).sum()
        
        print(f"British Pounds (£):   {pounds}")
        print(f"Euros (€):            {euros}")
        print(f"Indian Rupees (₹):    {rupees}")
        print(f"UK Spelling Variants: {uk_spelling}")
        print(f"Total Markers Detected: {pounds + euros + rupees + uk_spelling}")
    
    print("\n=========================================================")
    print("ASSESSMENT COMPLETE")
    print("=========================================================")

if __name__ == "__main__":
    # Ensure the relative path matches the standard repository structure
    sample_file = './data/whatsapp_smoke_test.csv'
    run_data_source_assessment(sample_file)