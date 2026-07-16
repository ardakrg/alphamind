import numpy as np

def find_candidates(
        query_vector: np.ndarray,
        corpus_vectors: np.ndarray,
        corpus_items: list[dict],
        top_k: int = 5,
        min_similarity: float = 0.1,
) -> list[tuple[dict, float]]:
    """Find the most semantically similar corpus items to a query vector.
    
    Args:
        query_vector: Embedding of the query, shape (384,).
        corpus_vectors: Embeddings of all corpus items, shape (N, 384).
        corpus_items: The items themselves, same order as corpus_vectors.
        top_k: Maximum number of candidates to return.
        min_similarity: Candidates below this score are dropped.
    
    Returns:
        List of (item, similarity) tuples, sorted by similarity descending.
    """

    # computes vectorized similarities
    dots = corpus_vectors @ query_vector
    query_norm = np.linalg.norm(query_vector)
    corpus_norm = np.linalg.norm(corpus_vectors, axis=1)
    similarities = dots / (query_norm * corpus_norm)

    top_indices = np.argsort(similarities)[::-1][:top_k]

    results = []
    for i in top_indices:
        score = similarities[i]
        if score < min_similarity:
            continue
        results.append((corpus_items[i], float(score)))

    return results


if __name__ == "__main__":
    from embedder import embed_texts   # or: from matcher.embedder import embed_texts

    news = "Trump scraps threat of 20% fee on Hormuz cargo as US prepares to resume blockade of Iran ports"
    
    markets = [
        {"question": "Will the U.S. invade Iran before 2027?"},
        {"question": "Will oil hit $100 by November?"},
        {"question": "Will Trump win the 2028 election?"},
        {"question": "Will Bitcoin hit $1m before GTA VI?"},
        {"question": "Will the Fed cut rates in September?"},
    ]
    
    news_vec = embed_texts([news])[0]          # (1, 384) -> (384,)
    market_vecs = embed_texts([m["question"] for m in markets])
    
    candidates = find_candidates(news_vec, market_vecs, markets, top_k=3)
    
    print(f"News: {news}\n")
    print("Top candidates:")
    for market, score in candidates:
        print(f"  {score:.3f}  {market['question']}")