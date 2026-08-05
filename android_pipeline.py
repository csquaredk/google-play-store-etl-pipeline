import os
import time
import sqlite3
import pandas as pd
import re
import datetime 
from langdetect import detect, DetectorFactory
from google_play_scraper import Sort, reviews

# ==========================================
# PRE-REQUISITES & HELPER FUNCTIONS
# ==========================================
DetectorFactory.seed = 0 

def is_english(text):
    """Safely checks if text is English by temporarily hiding emojis from the detector."""
    try:
        text_for_detection = re.sub(r'[^\x00-\x7F]+', '', str(text))
        if len(text_for_detection.strip()) < 2:
            return False
        return detect(text_for_detection) == 'en'
    except:
        return False

# ==========================================
# STEP 0: DATABASE SETUP 
# ==========================================
def init_db(db_name='play_store.db'):
    """Ensures the schema exists before we try to insert data."""
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    
    cursor.executescript('''
        CREATE TABLE IF NOT EXISTS apps (
            app_id INTEGER PRIMARY KEY AUTOINCREMENT,
            app_name TEXT NOT NULL UNIQUE,
            platform TEXT DEFAULT 'Android',
            category TEXT,
            store_url TEXT
        );

        CREATE TABLE IF NOT EXISTS ingestion_batches (
            run_id INTEGER PRIMARY KEY AUTOINCREMENT, 
            batch_id TEXT,                            
            run_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            app_name TEXT, 
            total_scraped INTEGER,
            rows_inserted INTEGER,
            duplicates_skipped INTEGER,
            runtime_seconds REAL,
            status TEXT
        );

        CREATE TABLE IF NOT EXISTS reviews (
            internal_id INTEGER PRIMARY KEY AUTOINCREMENT,
            app_id INTEGER,
            run_id INTEGER, 
            store_review_id TEXT UNIQUE, 
            rating INTEGER,
            review_date TEXT,
            app_version TEXT,
            language_code TEXT,
            raw_text TEXT,
            clean_text TEXT,
            word_count INTEGER,
            thumbs_up_count INTEGER,
            is_low_signal BOOLEAN,
            is_duplicate BOOLEAN,
            is_english_flag BOOLEAN, 
            is_clean_baseline BOOLEAN,
            FOREIGN KEY(app_id) REFERENCES apps(app_id),
            FOREIGN KEY(run_id) REFERENCES ingestion_batches(run_id)
        );
    ''')
    conn.commit()
    conn.close()

# ==========================================
# STEP 1: EXTRACT
# ==========================================
def extract_android_reviews(app_name, app_id, target_reviews=1000):
    print(f"-> EXTRACT: Scraping {app_name} (Target: {target_reviews} reviews)...")
    app_reviews = []
    seen_ids = set()
    continuation_token = None
    
    while len(app_reviews) < target_reviews:
        try:
            result, continuation_token = reviews(
                app_id, lang='en', country='us', sort=Sort.NEWEST,
                count=1000, continuation_token=continuation_token
            )
            
            if not result: break
                
            for review in result:
                r_id = review['reviewId']
                if r_id not in seen_ids:
                    seen_ids.add(r_id)
                    app_reviews.append({
                        'store_review_id': r_id,
                        'rating': review['score'],
                        'review_date': review['at'],
                        'app_version': review.get('reviewCreatedVersion', 'Unknown'),
                        'language_code': 'en',
                        'raw_text': review['content'],
                        'thumbs_up_count': review['thumbsUpCount']
                    })
            
            if len(app_reviews) >= target_reviews:
                app_reviews = app_reviews[:target_reviews]
                break
                
            time.sleep(0.3) 
            
        except Exception as e:
            print(f"[Error] on {app_name}: {e}")
            break
            
    print(f"   Successfully extracted {len(app_reviews)} rows.")
    return pd.DataFrame(app_reviews)

# ==========================================
# STEP 2: TRANSFORM
# ==========================================
def transform_data(df):
    print("-> TRANSFORM: Applying data quality flags...")
    if df.empty: return df
        
    df['review_date'] = df['review_date'].astype(str)
    df['clean_text'] = df['raw_text'].fillna("").astype(str).str.lower()
    df['word_count'] = df['clean_text'].str.split().str.len()
    
    df['is_duplicate'] = df.duplicated(subset=['store_review_id'], keep=False)
    df['is_low_signal'] = df['word_count'] < 3 
    df['is_english_flag'] = df['clean_text'].apply(is_english)
    
    df['is_clean_baseline'] = ~(df['is_duplicate'] | df['is_low_signal'] | ~df['is_english_flag'])
    print(f"   Identified {df['is_clean_baseline'].sum()} high-quality, English baseline reviews.")
    return df

# ==========================================
# STEP 3: LOAD 
# ==========================================
def load_to_sqlite(df, app_name, category, store_url, runtime_seconds, batch_id, db_name='play_store.db'):
    print("-> LOAD: Connecting to database...")
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    
    cursor.execute(
        "INSERT INTO ingestion_batches (batch_id, app_name, status) VALUES (?, ?, 'RUNNING')", 
        (batch_id, app_name)
    )
    current_run_id = cursor.lastrowid 
    
    cursor.execute('''
        INSERT OR IGNORE INTO apps (app_name, platform, category, store_url) 
        VALUES (?, 'Android', ?, ?)
    ''', (app_name, category, store_url))
    cursor.execute("SELECT app_id FROM apps WHERE app_name = ?", (app_name,))
    app_id = cursor.fetchone()[0]
    
    total_scraped = len(df)
    rows_inserted = 0
    
    if not df.empty:
        for index, row in df.iterrows():
            cursor.execute('''
                INSERT OR IGNORE INTO reviews (
                    app_id, run_id, store_review_id, rating, review_date, 
                    app_version, language_code, raw_text, clean_text, word_count, 
                    thumbs_up_count, is_low_signal, is_duplicate, is_english_flag, is_clean_baseline
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                app_id, current_run_id, row['store_review_id'], row['rating'],
                row['review_date'], row['app_version'], row['language_code'], 
                row['raw_text'], row['clean_text'], row['word_count'], 
                row['thumbs_up_count'], row['is_low_signal'], 
                row['is_duplicate'], row['is_english_flag'], row['is_clean_baseline']
            ))
            rows_inserted += cursor.rowcount
            
    duplicates_skipped = total_scraped - rows_inserted
        
    cursor.execute('''
        UPDATE ingestion_batches 
        SET total_scraped = ?, rows_inserted = ?, duplicates_skipped = ?, runtime_seconds = ?, status = 'SUCCESS' 
        WHERE run_id = ?
    ''', (total_scraped, rows_inserted, duplicates_skipped, runtime_seconds, current_run_id))
    
    conn.commit()
    conn.close()
    print(f"   Success! {rows_inserted} inserted. {duplicates_skipped} duplicates skipped.")

# ==========================================
# ORCHESTRATION (THE MASTER LOOP)
# ==========================================
if __name__ == "__main__":
    print("=== STARTING FULL PORTFOLIO PIPELINE RUN ===\n")
    init_db()
    
    APP_PORTFOLIO = {
        'WhatsApp':    {'id': 'com.whatsapp', 'category': 'Social & Communication'},
        'YouTube':     {'id': 'com.google.android.youtube', 'category': 'Social & Communication'},
        'Instagram':   {'id': 'com.instagram.android', 'category': 'Social & Communication'},
        'Discord':     {'id': 'com.discord', 'category': 'Social & Communication'},
        'X_Twitter':   {'id': 'com.twitter.android', 'category': 'Social & Communication'},
        'Gmail':       {'id': 'com.google.android.gm', 'category': 'Workspace & Productivity'},
        'Zoom':        {'id': 'us.zoom.videomeetings', 'category': 'Workspace & Productivity'},
        'Outlook':     {'id': 'com.microsoft.office.outlook', 'category': 'Workspace & Productivity'},
        'Teams':       {'id': 'com.microsoft.teams', 'category': 'Workspace & Productivity'},
        'Amazon':      {'id': 'com.amazon.mShop.android.shopping', 'category': 'E-Commerce & Marketplaces'},
        'eBay':        {'id': 'com.ebay.mobile', 'category': 'E-Commerce & Marketplaces'},
        'PayPal':      {'id': 'com.paypal.android.p2pmobile', 'category': 'FinTech & Payments'},
        'Venmo':       {'id': 'com.venmo', 'category': 'FinTech & Payments'},
        'Uber':        {'id': 'com.ubercab', 'category': 'Mobility, Travel & Maps'},
        'Lyft':        {'id': 'me.lyft.android', 'category': 'Mobility, Travel & Maps'},
        'Airbnb':      {'id': 'com.airbnb.android', 'category': 'Mobility, Travel & Maps'},
        'Google Maps': {'id': 'com.google.android.apps.maps', 'category': 'Mobility, Travel & Maps'},
        'Netflix':     {'id': 'com.netflix.mediaclient', 'category': 'Entertainment & Streaming'},
        'Spotify':     {'id': 'com.spotify.music', 'category': 'Entertainment & Streaming'},
        'Twitch':      {'id': 'tv.twitch.android.app', 'category': 'Entertainment & Streaming'}
    }
    
    master_batch_id = datetime.datetime.now().strftime("BATCH_%Y%m%d_%H%M%S")
    
    for app_name, app_info in APP_PORTFOLIO.items():
        print(f"--- Processing {app_name} ---")
        start_time = time.time() 
        target_url = f"https://play.google.com/store/apps/details?id={app_info['id']}"
        
        try:
            raw_data = extract_android_reviews(app_name, app_info['id'], target_reviews=1000)
            clean_data = transform_data(raw_data)
            
            end_time = time.time()
            runtime_seconds = round(end_time - start_time, 2)
            
            load_to_sqlite(
                df=clean_data, 
                app_name=app_name, 
                category=app_info['category'], 
                store_url=target_url,
                runtime_seconds=runtime_seconds,
                batch_id=master_batch_id 
            )
            print("\n") 
            
        except Exception as e:
            print(f"FAILED to process {app_name}. Error: {e}\n")
            
    print("=== FULL PORTFOLIO RUN COMPLETE ===")
