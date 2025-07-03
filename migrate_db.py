
import sqlite3
import os
from app import app

def migrate_database():
    """Add missing content_language column to video_jobs table"""
    db_path = os.path.join('instance', 'youtube_shorts_generator.db')
    
    if not os.path.exists(db_path):
        print("Database file not found")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if content_language column exists
        cursor.execute("PRAGMA table_info(video_jobs)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'content_language' not in columns:
            print("Adding content_language column to video_jobs table...")
            cursor.execute("ALTER TABLE video_jobs ADD COLUMN content_language VARCHAR(20) DEFAULT 'hinglish'")
            conn.commit()
            print("Successfully added content_language column")
        else:
            print("content_language column already exists")
        
        conn.close()
        
    except Exception as e:
        print(f"Error during migration: {e}")

if __name__ == '__main__':
    with app.app_context():
        migrate_database()
