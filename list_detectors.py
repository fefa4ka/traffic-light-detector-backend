import sqlite3

DB_PATH = "/data/detectors.db"

def list_detectors():
    """Retrieve and print all registered detectors with their passwords."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT name, password FROM detectors")
    detectors = cursor.fetchall()

    conn.close()

    print("Registered Traffic Light Detectors:")
    for name, password in detectors:
        print(f"Name: {name}, Password: {password}")

if __name__ == "__main__":
    list_detectors()
