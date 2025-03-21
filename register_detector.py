import argparse
import hashlib
import os
import sqlite3
import subprocess

DB_PATH = "/data/detectors.db"
MOSQUITTO_PASSWD_FILE = "/data/passwords"

def generate_password():
    """Generate a random secure password."""
    return hashlib.sha256(os.urandom(16)).hexdigest()[:16]

def create_mqtt_user(name, password):
    """Create an MQTT user with the given credentials."""
    # Ensure the password file directory exists before using it
    password_dir = os.path.dirname(MOSQUITTO_PASSWD_FILE)
    os.makedirs(password_dir, exist_ok=True)
    # Ensure password file exists with correct permissions
    if not os.path.exists(MOSQUITTO_PASSWD_FILE):
        os.makedirs(os.path.dirname(MOSQUITTO_PASSWD_FILE), exist_ok=True)
        open(MOSQUITTO_PASSWD_FILE, 'a').close()
        os.chmod(MOSQUITTO_PASSWD_FILE, 0o600)  # Secure file permissions

    cmd = ["mosquitto_passwd", "-b", MOSQUITTO_PASSWD_FILE, name, password]
    subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # Restart Mosquitto to apply the new user credentials
    try:
        # Check if mosquitto is actually running first
        subprocess.run(["pgrep", "mosquitto"], check=True)
        subprocess.run(["pkill", "-SIGHUP", "mosquitto"], check=True)
    except subprocess.CalledProcessError:
        print("Mosquitto not running yet, will pick up new config on startup")

def save_to_db(name, password):
    """Save detector information to the SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS detectors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)
    
    cursor.execute("INSERT INTO detectors (name, password) VALUES (?, ?)", (name, password))
    conn.commit()
    conn.close()

def get_or_create_user(detector_id):
    """Retrieve stored credentials or create new ones if they don't exist."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT name, password FROM detectors WHERE name=?", (f"detector_{detector_id}",))
    result = cursor.fetchone()

    if result:
        conn.close()
        return result[0], result[1]

    # If not found, create a new user
    name = f"detector_{detector_id}"
    password = generate_password()
    create_mqtt_user(name, password)
    save_to_db(name, password)

    conn.close()
    return name, password   

def main():
    parser = argparse.ArgumentParser(description="Register a new traffic light detector.")
    parser.add_argument("name", type=str, help="Name of the traffic light detector")
    parser.add_argument("--password", "-p", type=str, help="Optional password (will be generated if not provided)")
    
    args = parser.parse_args()
    password = args.password if args.password else generate_password()
    
    create_mqtt_user(args.name, password)
    save_to_db(args.name, password)
    
    print(f"Detector '{args.name}' registered successfully.")
    print(f"{'Provided' if args.password else 'Generated'} password: {password}")

if __name__ == "__main__":
    main()
