import sqlite3
import os

db_path = 'hotclaw.db'
if not os.path.exists(db_path):
    print('Database not found')
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Check current columns
cursor.execute("PRAGMA table_info(account_analysis_snapshots)")
columns = [col[1] for col in cursor.fetchall()]
print('Current columns:', columns)

# Add missing columns
if 'recommendation_diagnostics_json' not in columns:
    cursor.execute('ALTER TABLE account_analysis_snapshots ADD COLUMN recommendation_diagnostics_json TEXT')
    print('Added: recommendation_diagnostics_json')

if 'recommendation_refreshed_at' not in columns:
    cursor.execute('ALTER TABLE account_analysis_snapshots ADD COLUMN recommendation_refreshed_at TIMESTAMP')
    print('Added: recommendation_refreshed_at')

conn.commit()

# Verify
cursor.execute("PRAGMA table_info(account_analysis_snapshots)")
columns = [col[1] for col in cursor.fetchall()]
print('Updated columns:', columns)
conn.close()
print('Done!')
