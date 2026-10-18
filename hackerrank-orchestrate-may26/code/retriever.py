from pathlib import Path
import re
from typing import NamedTuple
from rank_bm25 import BM25Okapi

class Chunk(NamedTuple):
    text: str
    source_file: str
    domain: str

class BM25Index:
    def __init__(self, chunks: list[Chunk], bm25: BM25Okapi):
        self.chunks = chunks
        self.bm25 = bm25

def tokenize(text: str) -> list[str]:
    text = text.lower()
    text = re.sub(r'[^\w\s]', '', text)
    return text.split()

def build_index(data_dir: Path) -> BM25Index:
    all_chunks = []
    
    for file_path in data_dir.rglob("*.md"):
        # Extract domain: first component after data_dir
        relative_path = file_path.relative_to(data_dir)
        domain = relative_path.parts[0]
        
        content = file_path.read_text(encoding='utf-8')
        
        # Strip YAML frontmatter
        if content.startswith('---'):
            parts = content.split('---', 2)
            if len(parts) >= 3:
                content = parts[2].strip()
        
        # Chunk by heading
        # Split on headings but keep them
        raw_chunks = re.split(r'^(#+ .*)$', content, flags=re.MULTILINE)
        
        processed_chunks = []
        current_heading = ""
        
        for part in raw_chunks:
            part = part.strip()
            if not part:
                continue
            if part.startswith('#'):
                current_heading = part
            else:
                text = f"{current_heading}\n{part}".strip() if current_heading else part
                
                # Further split if > 300 words
                if len(text.split()) > 300:
                    sub_parts = text.split('\n\n')
                    for sp in sub_parts:
                        if sp.strip():
                            processed_chunks.append(sp.strip())
                else:
                    processed_chunks.append(text)
        
        for text in processed_chunks:
            all_chunks.append(Chunk(
                text=text,
                source_file=file_path.name,
                domain=domain
            ))
            
    tokenized_corpus = [tokenize(c.text) for c in all_chunks]
    bm25 = BM25Okapi(tokenized_corpus)
    
    return BM25Index(chunks=all_chunks, bm25=bm25)

def get_context(index: BM25Index, query: str, 
                company: str | None, top_k: int = 3) -> tuple[str, float]:
    tokenized_query = tokenize(query)
    scores = index.bm25.get_scores(tokenized_query)
    
    # Apply boosting
    boosted_scores = []
    for i, score in enumerate(scores):
        if company and index.chunks[i].domain == company:
            boosted_scores.append(score * 1.5)
        else:
            boosted_scores.append(score)
            
    # Take top_k
    top_indices = sorted(range(len(boosted_scores)), key=lambda i: boosted_scores[i], reverse=True)[:top_k]
    
    results = []
    highest_score = boosted_scores[top_indices[0]] if top_indices else 0.0
    
    for idx in top_indices:
        chunk = index.chunks[idx]
        results.append(f"[Source: {chunk.domain} > {chunk.source_file}]\n{chunk.text}")
        
    context_string = "\n---\n".join(results)
    return context_string, float(highest_score)
