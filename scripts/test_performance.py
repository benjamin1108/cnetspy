
import os
import sys
import time
import random
import sqlite3
import logging
from datetime import datetime, timedelta

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.storage.database.sqlite_layer import UpdateDataLayer

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DB_PATH = "data/sqlite/updates.db"

def measure_time(func):
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        duration = (end_time - start_time) * 1000
        return result, duration
    return wrapper

@measure_time
def test_query_updates_paginated(db_layer, limit=20, offset=0):
    filters = {}
    return db_layer.query_updates_paginated(filters, limit, offset)

@measure_time
def test_query_updates_with_vendor(db_layer, vendor, limit=20):
    filters = {'vendor': vendor}
    return db_layer.query_updates_paginated(filters, limit, 0)

@measure_time
def test_query_updates_date_range(db_layer, date_from, date_to, limit=20):
    filters = {'date_from': date_from, 'date_to': date_to}
    return db_layer.query_updates_paginated(filters, limit, 0)

@measure_time
def test_count_updates(db_layer):
    return db_layer.count_updates()

@measure_time
def test_full_text_search(db_layer, keyword):
    # Simulating simple LIKE search if that's what's implemented, 
    # or FTS if available (assuming LIKE based on current codebase context)
    filters = {'keyword': keyword}
    return db_layer.query_updates_paginated(filters, 20, 0)

def check_pragma_settings(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Apply optimizations manually for the test script as it might bypass the app's init logic or use a fresh connection
    cursor.execute('PRAGMA mmap_size=2147483648') # 2GB
    
    pragmas = {
        'journal_mode': 'PRAGMA journal_mode;',
        'synchronous': 'PRAGMA synchronous;',
        'cache_size': 'PRAGMA cache_size;',
        'mmap_size': 'PRAGMA mmap_size;',
        'temp_store': 'PRAGMA temp_store;'
    }
    
    settings = {}
    for name, query in pragmas.items():
        cursor.execute(query)
        result = cursor.fetchone()
        settings[name] = result[0] if result else 'Unknown'
        
    conn.close()
    return settings

def main():
    if not os.path.exists(DB_PATH):
        logger.error(f"Database not found at {DB_PATH}")
        return

    logger.info(f"Checking database performance for: {DB_PATH}")
    
    # Check Pragma Settings
    settings = check_pragma_settings(DB_PATH)
    logger.info(f"Current PRAGMA settings: {settings}")

    db_layer = UpdateDataLayer(DB_PATH)
    
    # Warm up
    logger.info("Warming up database connection...")
    db_layer.count_updates()
    
    # Test 1: Count total updates
    count, duration = test_count_updates(db_layer)
    logger.info(f"Total Updates: {count} | Time: {duration:.2f}ms")
    
    # Test 2: Basic Pagination
    _, duration = test_query_updates_paginated(db_layer, limit=20)
    logger.info(f"Basic Pagination (Limit 20): {duration:.2f}ms")
    
    _, duration = test_query_updates_paginated(db_layer, limit=100)
    logger.info(f"Basic Pagination (Limit 100): {duration:.2f}ms")
    
    # Test 3: Vendor Filter
    vendors = ['AWS', 'Azure', 'Google Cloud', 'Cisco'] # Example vendors
    for vendor in vendors:
        _, duration = test_query_updates_with_vendor(db_layer, vendor)
        logger.info(f"Filter by Vendor '{vendor}': {duration:.2f}ms")

    # Test 4: Date Range
    today = datetime.now()
    last_month = today - timedelta(days=30)
    date_from = last_month.strftime('%Y-%m-%d')
    date_to = today.strftime('%Y-%m-%d')
    _, duration = test_query_updates_date_range(db_layer, date_from, date_to)
    logger.info(f"Date Range Query (Last 30 Days): {duration:.2f}ms")
    
    # Test 5: Keyword Search
    keywords = ['cloud', 'network', 'security']
    for keyword in keywords:
        _, duration = test_full_text_search(db_layer, keyword)
        logger.info(f"Keyword Search '{keyword}': {duration:.2f}ms")

if __name__ == "__main__":
    main()
