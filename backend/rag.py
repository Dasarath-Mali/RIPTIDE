import os
import json
import math
import urllib.request
import urllib.error

def cosine_similarity(v1, v2):
    dot_product = sum(a*b for a, b in zip(v1, v2))
    mag1 = math.sqrt(sum(a*a for a in v1))
    mag2 = math.sqrt(sum(b*b for b in v2))
    if mag1 == 0 or mag2 == 0:
        return 0
    return dot_product / (mag1 * mag2)

class RAGSystem:
    def __init__(self):
        self.db = []
        if os.path.exists("local_db.json"):
            with open("local_db.json", "r") as f:
                self.db = json.load(f)
            
    def retrieve(self, query: str, top_k: int = 5):
        if not self.db:
            return []
            
        from config import GEMINI_API_KEY
        
        # Get query embedding
        url = f"https://generativelanguage.googleapis.com/v1beta/models/text-embedding-004:embedContent?key={GEMINI_API_KEY}"
        data = json.dumps({
            "model": "models/text-embedding-004",
            "content": {"parts": [{"text": query}]}
        }).encode('utf-8')
        
        req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
        
        try:
            with urllib.request.urlopen(req) as response:
                result = json.loads(response.read().decode())
                query_vector = result.get("embedding", {}).get("values", [])
        except urllib.error.URLError as e:
            print(f"API Error: {e}")
            return []
            
        if not query_vector:
            return []
        
        # Calculate similarities
        scored_docs = []
        for doc in self.db:
            score = cosine_similarity(query_vector, doc['vector'])
            scored_docs.append((score, doc['text']))
            
        scored_docs.sort(reverse=True, key=lambda x: x[0])
        return [text for score, text in scored_docs[:top_k]]

