import sqlite3
import pandas as pd

def peek_database():
    # Open the database connection safely
    with sqlite3.connect('android_pipeline.db') as conn:
        
        # 1. Pull the Manager's Telemetry Report
        telemetry_query = """
            SELECT run_id, batch_id, app_name, run_date, total_scraped, rows_inserted, duplicates_skipped, runtime_seconds, status
            FROM ingestion_batches
            ORDER BY run_id DESC
        """
        telemetry_df = pd.read_sql(telemetry_query, conn)
        
        # 2. Pull a sample of your clean, baseline data
        sample_reviews_query = """
            SELECT r.app_id, a.app_name, r.rating, r.clean_text, r.is_english_flag, r.run_id, b.batch_id
            FROM reviews r
            JOIN apps a ON r.app_id = a.app_id
            JOIN ingestion_batches b ON r.run_id = b.run_id
            WHERE r.is_clean_baseline = 1 AND r.run_id = 2
            LIMIT 5
        """
        reviews_df = pd.read_sql(sample_reviews_query, conn)

    # Display the results!
    print("=== TELEMETRY SUMMARY (LATEST RUN) ===")
    print(telemetry_df.head(20).to_string()) 

    print("\n=== SAMPLE OF CLEAN BASELINE REVIEWS ===")
    print(reviews_df.to_string())

if __name__ == "__main__":
    peek_database()