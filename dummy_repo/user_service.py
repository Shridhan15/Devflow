# dummy_repo/user_service.py
import json
from datetime import datetime

def load_config():
    """Standalone utility function to load config."""
    return {"timeout": 30, "retries": 3}

class UserManager:
    def __init__(self):
        self.users = {}
        
    def add_user(self, user_id, name):
        """Adds a user to the system."""
        self.users[user_id] = {"name": name, "active": True}
        print(f"User {name} added.")
        
    def deactivate_user(self, user_id):
        """Deactivates an existing user."""
        if user_id in self.users:
            self.users[user_id]["active"] = False
            self.users[user_id]["deactivated_at"] = datetime.utcnow().isoformat()
