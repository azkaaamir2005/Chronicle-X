import json
from groq import Groq
from config import GROQ_API_KEY, DEFAULT_LLM_MODEL

class NewsEditor:
    def __init__(self):
        if not GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY is not set in environment variables.")
        self.client = Groq(api_key=GROQ_API_KEY)

    def Review_and_rank(self, synthesized_articles: list, user_profile: dict) -> list:
        """
        Reviews, refines formatting, and sorts synthesized articles based on priority relevance.
        """
        if not synthesized_articles:
            return []

        # Simple preference-based ranking using weights
        topic_weights = user_profile.get("topic_weights", {})
        
        for article in synthesized_articles:
            category = article.get("category", "")
            base_score = topic_weights.get(category, 1.0)
            article["relevance_score"] = base_score

        # Sort articles descending by relevance score
        ranked_articles = sorted(synthesized_articles, key=lambda x: x.get("relevance_score", 0), reverse=True)
        return ranked_articles