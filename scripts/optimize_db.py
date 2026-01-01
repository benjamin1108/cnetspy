
import sqlite3
import logging
import os

DB_PATH = "data/sqlite/updates.db"
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def optimize_database(db_path):
    if not os.path.exists(db_path):
        logger.error(f"Database not found at {db_path}")
        return

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # 1. Enable Memory-Mapped I/O (mmap)
        # Set to 2GB (value is in bytes)
        # This maps the database file into memory, reducing system call overhead for I/O
        mmap_size = 2 * 1024 * 1024 * 1024  # 2GB
        cursor.execute(f"PRAGMA mmap_size = {mmap_size};")
        
        # Verify the setting
        cursor.execute("PRAGMA mmap_size;")
        current_mmap = cursor.fetchone()[0]
        logger.info(f"Set PRAGMA mmap_size to: {current_mmap} bytes")

        # 2. Optimize Journal Mode (WAL is already on, but ensuring persistence)
        cursor.execute("PRAGMA journal_mode=WAL;")
        mode = cursor.fetchone()[0]
        logger.info(f"Confirmed PRAGMA journal_mode is: {mode}")

        # 3. Synchronous Mode
        # NORMAL is safe for WAL mode and faster than FULL
        cursor.execute("PRAGMA synchronous=NORMAL;")
        cursor.execute("PRAGMA synchronous;")
        sync_mode = cursor.fetchone()[0]
        logger.info(f"Set PRAGMA synchronous to: {sync_mode}")
        
        # 4. Temp Store
        # Store temp tables and indices in memory
        cursor.execute("PRAGMA temp_store=MEMORY;")
        cursor.execute("PRAGMA temp_store;")
        temp_store = cursor.fetchone()[0]
        logger.info(f"Set PRAGMA temp_store to: {temp_store}")

        # 5. VACUUM to defragment the database (optional but good for maintenance)
        # logger.info("Running VACUUM to defragment database...")
        # cursor.execute("VACUUM;") 
        # logger.info("VACUUM completed.")

        conn.commit()
        conn.close()
        logger.info("Database optimization settings applied successfully.")

    except Exception as e:
        logger.error(f"Failed to optimize database: {e}")

if __name__ == "__main__":
    optimize_database(DB_PATH)
