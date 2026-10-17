import json
import os
from config import PROFILES_DIR, DEFAULT_CATEGORIES

class ProfileBuilder:
    def __init__(self, user_id: str = "default_user"):
        self.user_id = user_id
        self.profile_path = os.path.join(PROFILES_DIR, f"{user_id}.json")

    def load_or_create_profile(self) -> dict:
        """Loads an existing user profile or initializes a default profile."""
        if os.path.exists(self.profile_path):
            with open(self.profile_path, "r") as f:
                return json.load(f)
        
        default_profile = {
            "user_id": self.user_id,
            "categories": DEFAULT_CATEGORIES[:3],
            "topic_weights": {cat: 1.0 for cat in DEFAULT_CATEGORIES},
            "reading_depth": "High-Density Brief",
            "serendipity_preference": 0.15,
            "created_at": str(os.path.getmtime(self.profile_path)) if os.path.exists(self.profile_path) else ""
        }
        self.save_profile(default_profile)
        return default_profile

    def save_profile(self, profile_data: dict) -> None:
        """Saves updated user profile data to disk."""
        with open(self.profile_path, "w") as f:
            json.dump(profile_data, f, indent=4)