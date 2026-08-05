# Android Google Play Store ETL Pipeline 📱📊

> **An automated data engineering pipeline that extracts, transforms, and loads (ETL) mobile app reviews into a relational database to provide a clean, deduplicated foundation for downstream analytics.**

## 📖 Project Overview
This project was developed during my Data Engineering internship at **Sciencia AI**. It is a resilient Python-based ETL pipeline designed to scrape chronological user reviews from the Google Play Store. It processes the raw JSON data, applies data quality and language-detection flags to filter for high-signal English text, and utilizes an idempotent SQLite database architecture to prevent historical data duplication. 

### 🔍 Data Source Strategy: Why Google Play?
Before building the pipeline, the Google Play Store was evaluated and selected as the ideal data source for sustainable review ingestion. Compared to other platforms, Google Play provides:
* **High-Volume Velocity:** A consistent, daily stream of user feedback.
* **Granular Metadata:** Native access to exact timestamps, application versions, and user ratings.
* **Platform Stability:** A reliable extraction endpoint that supports scalable, long-term chronological scraping without heavy throttling.

---

## 🎯 The 20-App Portfolio
The pipeline actively monitors 20 leading applications across six major industry sectors to provide a diverse baseline for text analysis:

* **Social & Communication:** WhatsApp, YouTube, Instagram, Discord, X (Twitter)
* **Workspace & Productivity:** Gmail, Zoom, Outlook, Teams
* **E-Commerce & Marketplaces:** Amazon, eBay
* **FinTech & Payments:** PayPal, Venmo
* **Mobility, Travel & Maps:** Uber, Lyft, Airbnb, Google Maps
* **Entertainment & Streaming:** Netflix, Spotify, Twitch

---

## 🏗️ Database Architecture & Schema
The data is stored in a permanent SQLite relational database (`android_pipeline.db`). The architecture utilizes a **Task-Level Batching** system to guarantee pipeline durability.

### Terminology Hierarchy
* **`batch_id` (The Master Group):** A timestamped string (e.g., `BATCH_20260715_110500`) generated once per script execution. This ensures all 20 apps processed during a single run are mathematically grouped together.
* **`run_id` (The Task):** An auto-incrementing Primary Key generated for every individual app scraped. If the scraper fails on App #15, the first 14 `run_ids` remain safely locked and committed to the database.

### Core Tables
1. **`apps`**: Stores application metadata (Name, Platform, Category, Store URL).
2. **`ingestion_batches`**: The historical telemetry ledger. Tracks performance metrics including runtime, total scraped, rows inserted, and duplicates skipped per `run_id`.
3. **`reviews`**: The granular data table containing the raw text, star ratings, and data quality flags. Linked to both the app and the ingestion batch via Foreign Keys.

---

## 🧹 Data Quality & Transformation Pipeline
Before being loaded into the database, every raw review passes through a Python transformation layer to generate boolean flags for downstream data scientists:

* **`is_low_signal`**: Flags reviews with fewer than 3 words.
* **`is_english_flag`**: Utilizes the `langdetect` library (with temporary emoji-stripping) to verify the text is written in English.
* **`is_duplicate`**: Flags reviews that share an exact `store_review_id` to prevent data pollution.
* **`is_clean_baseline`**: A master boolean. Returns `TRUE` only if the review is English, contains 3+ words, and is not a duplicate. 

---

## 🚀 How to Run the Pipeline

### 1. Install Dependencies
Ensure you have Python 3 installed, then install the required libraries via your terminal:
```bash
pip install -r requirements.txt
