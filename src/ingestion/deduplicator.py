from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from typing import List, Dict

class ArticleDeduplicator:
    def __init__(self, similarity_threshold: float = 0.65):
        self.threshold = similarity_threshold

    def deduplicate(self, articles: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """
        Filters out semantically redundant articles based on title & raw content similarity.
        """
        if not articles or len(articles) <= 1:
            return articles

        texts = [f"{a.get('title', '')} {a.get('raw_content', '')}" for a in articles]
        
        vectorizer = TfidfVectorizer(stop_words='english')
        tfidf_matrix = vectorizer.fit_transform(texts)
        
        sim_matrix = cosine_similarity(tfidf_matrix, tfidf_matrix)
        
        unique_articles = []
        visited = set()

        for i in range(len(articles)):
            if i in visited:
                continue
            
            unique_articles.append(articles[i])
            visited.add(i)

            # Mark duplicates that exceed the similarity threshold
            for j in range(i + 1, len(articles)):
                if sim_matrix[i][j] >= self.threshold:
                    visited.add(j)

        return unique_articles