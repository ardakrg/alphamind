from sentence_transformers import SentenceTransformer
import numpy as np

MODEL_NAME = "all-MiniLM-L6-v2"

_model = None

def get_model() -> SentenceTransformer:
    """Load the sentence embedding model once and reuse it."""
    global _model
    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)
    return _model

def embed_texts(texts: list[str]) -> np.ndarray:
    """Convert a list of texts into embedding vectors
    
    Args:
        texts: List of strings to embed

    Returns:
        A numpy array of shape (len(texts), 384), one row per input text
    """

    transformer = get_model()
    return transformer.encode(texts)

if __name__ == "__main__":
    texts = [
        # Real news headline (from your RSS output)
        "Trump scraps threat of 20% fee on Hormuz cargo as US prepares to resume blockade of Iran ports",
        # Real-ish market questions
        "Will the U.S. invade Iran before 2027?",
        "Will oil hit $100 by November?",
        "Will Trump win the 2028 election?",
        "Will Bitcoin hit $1m before GTA VI?",
    ]
    
    vectors = embed_texts(texts)
    print(f"Shape: {vectors.shape}")
    
    # Cosine similarity between first text and the other two
    from numpy.linalg import norm
    
    def cosine_sim(a, b):
        return np.dot(a, b) / (norm(a) * norm(b))
    
    print(f"\n'{texts[0][:40]}...'")
    for i in range(1, len(texts)):
        sim = cosine_sim(vectors[0], vectors[i])
        print(f"  vs '{texts[i][:45]}...' -> {sim:.3f}")