import os
import json
from config import PROFILES_DIR

class AdaptiveWeightEngine:
    def __init__(self, user_id: str = "default_user"):
        self.user_id = user_id
        self.profile_path = os.path.join(PROFILES_DIR, f"{user_id}.json")

    def update_weights_from_telemetry(self, interactions: list) -> dict:
        """
        Adjusts interest topic weights based on implicit user interaction signals.
        - Positive signal (e.g., expanded, spent time reading): +0.1 weight
        - Negative signal (e.g., skipped, dismissed): -0.05 weight
        """
        if not os.path.exists(self.profile_path):
            return {}

        with open(self.profile_path, "r") as f:
            profile = json.load(f)

        weights = profile.get("topic_weights", {})

        for event in interactions:
            category = event.get("category")
            action = event.get("action")  # 'read', 'bookmark', 'skip'

            if category in weights:
                if action in ['read', 'bookmark']:
                    weights[category] = round(min(2.0, weights[category] + 0.1), 2)
                elif action == 'skip':
                    weights[category] = round(max(0.1, weights[category] - 0.05), 2)

        profile["topic_weights"] = weights

        with open(self.profile_path, "w") as f:
            json.dump(profile, f, indent=4)

        return weights