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
    subprocess.run(["pkill", "-HUP", "mosquitto"], check=True)

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

def main():
    parser = argparse.ArgumentParser(description="Register a new traffic light detector.")
    parser.add_argument("name", type=str, help="Name of the traffic light detector")
    
    args = parser.parse_args()
    password = generate_password()
    
    create_mqtt_user(args.name, password)
    save_to_db(args.name, password)
    
    print(f"Detector '{args.name}' registered successfully.")
    print(f"Generated password: {password}")

if __name__ == "__main__":
    main()
