import feedparser
from bs4 import BeautifulSoup
import requests
from typing import List, Dict, Optional

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
FAILED_MARKER = "Content extraction failed or restricted."


class NewsIngestionPipeline:
    def __init__(self):
        # Curated RSS feed endpoints mapped to broad interest areas.
        # IMPORTANT: these keys must match the names in DEFAULT_CATEGORIES (config.py) exactly.
        self.default_feeds = {
            "Artificial Intelligence & Autonomous Systems": [
                "https://www.technologyreview.com/feed/",
                "https://www.artificialintelligence-news.com/feed/"
            ],
            "Global Economics & Geopolitics": [
                "https://www.economist.com/sections/economics/rss.xml",
                "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
                "https://feeds.bbci.co.uk/news/business/rss.xml"
            ],
            "Deep Tech & Engineering": [
                "https://feeds.feedburner.com/oreilly/radar/atom",
                "https://spectrum.ieee.org/rss/fulltext"
            ],
            "Ethics, Philosophy & Society": [
                "https://aeon.co/feed.rss"
            ],
            "Serendipity / Wildcard": [
                "https://www.quantamagazine.org/feed/",
                "https://www.atlasobscura.com/feeds/latest"
            ],
            "Science & Health": [
                "https://www.sciencedaily.com/rss/top/science.xml",
                "https://feeds.bbci.co.uk/news/health/rss.xml"
            ],
            "Business & Startups": [
                "https://techcrunch.com/feed/",
                "https://www.inc.com/rss"
            ],
            "Climate & Environment": [
                "https://www.theguardian.com/environment/climate-crisis/rss",
                "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml"
            ],
            "Politics & Policy": [
                "https://www.theguardian.com/politics/rss",
                "https://feeds.bbci.co.uk/news/politics/rss.xml"
            ],
            "Culture & Arts": [
                "https://www.theguardian.com/culture/rss",
                "https://feeds.bbci.co.uk/news/entertainment_and_arts/rss.xml"
            ],
            "Space & Physics": [
                "https://www.nasa.gov/feed/",
                "https://www.space.com/feeds/all"
            ]
        }

    def fetch_articles_from_rss(self, category: str, limit: int = 3) -> List[Dict[str, str]]:
        """
        Fetches and parses articles from predefined RSS feeds for a given category.
        Articles whose content could not be extracted are skipped.
        """
        articles = []
        feeds = self.default_feeds.get(category, [])

        for feed_url in feeds:
            try:
                parsed_feed = feedparser.parse(feed_url, agent=USER_AGENT)

                if not parsed_feed.entries:
                    print(f"[scraper] No entries from feed: {feed_url}")
                    continue

                for entry in parsed_feed.entries[:limit]:
                    title = entry.get("title", "No Title")
                    link = entry.get("link", "")
                    summary = entry.get("summary", entry.get("description", ""))

                    # Clean HTML tags from summary if present
                    clean_summary = BeautifulSoup(summary, "html.parser").get_text().strip()

                    if len(clean_summary) > 100:
                        content = clean_summary
                    else:
                        content = self._scrape_full_page(link) if link else FAILED_MARKER

                    # Skip stories we couldn't get real text for
                    if content.startswith(FAILED_MARKER) or len(content) < 100:
                        continue

                    articles.append({
                        "category": category,
                        "title": title,
                        "url": link,
                        "raw_content": content
                    })
            except Exception as e:
                print(f"[scraper] Error fetching feed {feed_url}: {e}")

        return articles

    def _scrape_full_page(self, url: str) -> str:
        """
        Fallback scraper to pull main text content from a direct article URL.
        """
        try:
            headers = {"User-Agent": USER_AGENT}
            response = requests.get(url, headers=headers, timeout=5)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")

                # Extract paragraphs from standard article wrappers
                paragraphs = soup.find_all("p")
                text = " ".join([p.get_text() for p in paragraphs]).strip()
                if text:
                    return text[:2000]  # Limit length for token efficiency
        except Exception:
            pass
        return FAILED_MARKER

    def gather_all_news(self, categories: Optional[List[str]] = None, per_feed: int = 2) -> List[Dict[str, str]]:
        """
        Gathers articles across categories.
        - categories: optional list of category names to fetch (defaults to all).
        - per_feed: max articles taken from each feed.
        """
        all_articles = []
        seen_urls = set()

        target_categories = categories if categories else list(self.default_feeds.keys())

        for category in target_categories:
            if category not in self.default_feeds:
                print(f"[scraper] No feeds configured for category: {category}")
                continue

            for article in self.fetch_articles_from_rss(category, limit=per_feed):
                # Avoid duplicates across feeds
                if article["url"] and article["url"] in seen_urls:
                    continue
                seen_urls.add(article["url"])
                all_articles.append(article)

        return all_articles