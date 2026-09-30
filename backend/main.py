import os
import json
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler, HTTPServer
from rag import RAGSystem
from security import score_injection, redact_pii

# Initialize RAG System
rag = RAGSystem()

def generate_answer(query: str, context: str) -> str:
    prompt = f"""
    You are a strict, zero-trust assistant. Answer the user's question using ONLY the provided context.
    If the context does not contain the answer, say "I cannot answer this question based on the provided context."
    Do not guess. Do not use outside knowledge. 
    
    Context:
    {context}
    
    Question:
    {query}
    """
    
    from config import GEMINI_API_KEY
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    req_data = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode('utf-8')
    req = urllib.request.Request(url, data=req_data, headers={'Content-Type': 'application/json'})
    
    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode())
            return result['candidates'][0]['content']['parts'][0]['text']
    except Exception as e:
        return f"Error generating answer: {e}"

class RequestHandler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_POST(self):
        if self.path == '/chat':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            
            try:
                data = json.loads(post_data.decode('utf-8'))
                query = data.get('query', '')
                
                # 1. Score the spoken query for prompt injection
                query_score = score_injection(query)
                if query_score['label'] == 'INJECTION' and query_score['score'] > 0.6:
                    self._send_json(200, {
                        "answer": "Refused: Prompt injection detected in query.",
                        "query_injection_score": query_score,
                        "retrieved_chunks": [],
                        "is_refused": True
                    })
                    return
                
                # 2. Retrieve chunks from RAG
                raw_chunks = rag.retrieve(query)
                if not raw_chunks:
                    self._send_json(200, {
                        "answer": "Refused: No relevant information found in the archive.",
                        "query_injection_score": query_score,
                        "retrieved_chunks": [],
                        "is_refused": True
                    })
                    return
                    
                # 3. Process retrieved chunks
                processed_chunks = []
                safe_context_parts = []
                for i, chunk in enumerate(raw_chunks):
                    redacted_chunk = redact_pii(chunk)
                    chunk_score = score_injection(redacted_chunk)
                    is_safe = chunk_score['label'] == 'SAFE' or chunk_score['score'] < 0.6
                    
                    processed_chunks.append({
                        "id": i,
                        "text": redacted_chunk,
                        "injection_score": chunk_score,
                        "included": is_safe
                    })
                    
                    if is_safe:
                        safe_context_parts.append(redacted_chunk)
                        
                if not safe_context_parts:
                    self._send_json(200, {
                        "answer": "Refused: All retrieved context was flagged as malicious.",
                        "query_injection_score": query_score,
                        "retrieved_chunks": processed_chunks,
                        "is_refused": True
                    })
                    return
                    
                context = "\n---\n".join(safe_context_parts)
                
                # 4. Generate final answer and Redact PII one last time from output
                raw_answer = generate_answer(query, context)
                final_answer = redact_pii(raw_answer)
                
                self._send_json(200, {
                    "answer": final_answer,
                    "query_injection_score": query_score,
                    "retrieved_chunks": processed_chunks,
                    "is_refused": False
                })
                
            except Exception as e:
                print(f"Error processing request: {e}")
                self._send_json(500, {"detail": "Internal server error"})
        else:
            self.send_response(404)
            self.end_headers()
            
    def _send_json(self, status, data):
        self.send_response(status)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))

if __name__ == '__main__':
    server_address = ('127.0.0.1', 8000)
    httpd = HTTPServer(server_address, RequestHandler)
    print("Starting pure Python HTTP server on http://127.0.0.1:8000...")
    httpd.serve_forever()
