from src.session_logs.database import LoggingDatabase

if __name__ == "__main__":
    db = LoggingDatabase()
    print("🧹 Starting GDPR 12-month log cleanup...")
    # This calls the function you wrote in database.py
    db.cleanup_old_records(months=12)
    print("✅ Cleanup complete.")
