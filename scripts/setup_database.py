#!/usr/bin/env python3
"""Database setup script - run this before starting the application."""

import os
import sys
import psycopg
from pathlib import Path

def setup_database():
    """Run database migrations."""
    database_url = os.getenv("DATABASE_URL", "postgresql://rohit.jain@localhost:5432/langgraph_chats")
    
    print(f"Setting up database: {database_url}")
    
    try:
        with psycopg.connect(database_url) as conn:
            print("✅ Database connection successful")
            
            # Read and execute migration
            migration_file = Path(__file__).parent.parent / "db" / "init_db.sql"
            
            if migration_file.exists():
                with open(migration_file) as f:
                    migration_sql = f.read()
                
                with conn.cursor() as cur:
                    cur.execute(migration_sql)
                    conn.commit()
                    print("✅ Agent configurations table and default data created")
            else:
                print("❌ Migration file not found")
                return False
                
    except Exception as e:
        print(f"❌ Database setup failed: {e}")
        return False
    
    print("🎉 Database setup complete!")
    return True

if __name__ == "__main__":
    success = setup_database()
    sys.exit(0 if success else 1)