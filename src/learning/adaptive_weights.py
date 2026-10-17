import os
import json
from config import PROFILES_DIR

DEFAULT_WEIGHT = 1.0   # starting weight for a category the profile hasn't seen yet
MIN_WEIGHT = 0.1
MAX_WEIGHT = 2.0


class AdaptiveWeightEngine:
    def __init__(self, user_id: str = "default_user"):
        self.user_id = user_id
        self.profile_path = os.path.join(PROFILES_DIR, f"{user_id}.json")

    def _load_profile(self) -> dict:
        """Loads the saved profile, or returns an empty one if it doesn't exist or is unreadable."""
        if not os.path.exists(self.profile_path):
            return {}
        try:
            with open(self.profile_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}

    def get_weights(self) -> dict:
        """Returns the current topic weights (empty dict if nothing saved yet)."""
        return self._load_profile().get("topic_weights", {})

    def update_weights_from_telemetry(self, interactions: list) -> dict:
        """
        Adjusts interest topic weights based on implicit user interaction signals.
        - Positive signal (e.g., expanded, spent time reading): +0.1 weight
        - Negative signal (e.g., skipped, dismissed): -0.05 weight

        Categories not yet in the profile start at DEFAULT_WEIGHT, and the profile
        file is created automatically if it doesn't exist.
        """
        profile = self._load_profile()
        weights = profile.get("topic_weights", {})

        for event in interactions:
            category = event.get("category")
            action = event.get("action")  # 'read', 'bookmark', 'skip'

            if not category:
                continue

            current = weights.get(category, DEFAULT_WEIGHT)

            if action in ("read", "bookmark"):
                weights[category] = round(min(MAX_WEIGHT, current + 0.1), 2)
            elif action == "skip":
                weights[category] = round(max(MIN_WEIGHT, current - 0.05), 2)

        profile["topic_weights"] = weights

        os.makedirs(os.path.dirname(self.profile_path), exist_ok=True)
        with open(self.profile_path, "w", encoding="utf-8") as f:
            json.dump(profile, f, indent=4)

        return weights