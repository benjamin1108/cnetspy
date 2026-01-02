
import sqlite3
import json
import os

DB_PATH = 'data/sqlite/updates.db'

def get_latest_monthly_report():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        cursor.execute('''
            SELECT id, report_type, date_from, date_to, ai_summary
            FROM reports
            WHERE report_type = 'weekly'
            ORDER BY created_at DESC
            LIMIT 1
        ''')
        row = cursor.fetchone()

        if row:
            print(f"Report ID: {row['id']}")
            print(f"Date Range: {row['date_from']} to {row['date_to']}")
            
            ai_summary = row['ai_summary']
            if isinstance(ai_summary, str):
                try:
                    ai_summary = json.loads(ai_summary)
                except json.JSONDecodeError:
                    print("Error decoding ai_summary JSON")
                    return

            print("\n--- AI Summary Keys ---")
            print(json.dumps(list(ai_summary.keys()), indent=2))
            
            print("\n--- AI Summary Sample (Top Updates) ---")
            if 'top_updates' in ai_summary:
                print(json.dumps(ai_summary['top_updates'][:1], indent=2, ensure_ascii=False))
            elif 'landmark_updates' in ai_summary:
                print(json.dumps(ai_summary['landmark_updates'][:1], indent=2, ensure_ascii=False))
            else:
                print("No top_updates or landmark_updates found.")

            print("\n--- AI Summary Sample (Featured Blogs) ---")
            if 'featured_blogs' in ai_summary:
                print(json.dumps(ai_summary['featured_blogs'][:1], indent=2, ensure_ascii=False))
            
            print("\n--- AI Summary Sample (Quick Scan) ---")
            if 'quick_scan' in ai_summary:
                print(json.dumps(ai_summary['quick_scan'][:1], indent=2, ensure_ascii=False))

        else:
            print("No monthly reports found.")

    except Exception as e:
        print(f"Error querying database: {e}")
    finally:
        conn.close()

if __name__ == '__main__':
    get_latest_monthly_report()
