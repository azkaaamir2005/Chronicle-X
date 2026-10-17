import json
from groq import Groq
from config import GROQ_API_KEY, DEFAULT_LLM_MODEL

from dotenv import load_dotenv
load_dotenv()

class NewsSynthesizer:
    def __init__(self):
        if not GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY is not set. Please ensure it is defined in your environment variables.")
        
        # Initialize the official Groq client
        self.client = Groq(api_key=GROQ_API_KEY)
        self.model = DEFAULT_LLM_MODEL

    def synthesize_article(self, article_text: str, user_profile: dict) -> dict:
        """
        Takes raw article text and a user profile, utilizing Groq to synthesize 
        a journalistic summary and a dialectic perspective.
        """
        system_prompt = (
            "You are the Chief Editor of ChronicleX, an advanced autonomous newsroom. "
            "Your goal is to transform raw articles into high-density, engaging journalistic briefs "
            "that include critical analysis and dialectic counter-perspectives."
        )

        user_prompt = f"""
        Analyze and synthesize the following article for a reader with this profile:
        Reader Profile: {json.dumps(user_profile)}

        Raw Article Text:
        {article_text}

        Return your output strictly as a JSON object with the following keys:
        - "headline": A compelling, publication-ready headline.
        - "summary": A concise, high-density editorial summary of the core story.
        - "dialectic_perspective": A contrasting viewpoint, historical context, or critical counter-analysis challenging or expanding the core narrative.
        - "category": The primary interest category this belongs to.
        """

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.4
            )
            
            return json.loads(response.choices[0].message.content)
            
        except Exception as e:
            print(f"SYNTHESIS ERROR: {type(e).__name__}: {e}")
            # Fallback structure if API call or JSON parsing fails
            return {
                "headline": "Synthesis Generation Notice",
                "summary": article_text[:300] + "...",
                "dialectic_perspective": "Automated dialectic parsing temporarily unavailable.",
                "category": "General"
            }