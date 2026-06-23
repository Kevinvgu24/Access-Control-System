import numpy as np

def calculate_cosine_similarity(emb1, emb2):
    dot_product = np.dot(emb1, emb2.T)
    norm1 = np.linalg.norm(emb1)
    norm2 = np.linalg.norm(emb2)
    if norm1 == 0 or norm2 == 0: return 0.0
    return dot_product / (norm1 * norm2)

def cosine_to_percentage(cosine_score, threshold):
    if cosine_score <= 0: return 0.0
    if cosine_score >= 1.0: return 100.0
    if cosine_score >= threshold:
        return 75.0 + ((cosine_score - threshold) / (1.0 - threshold)) * 25.0
    return (cosine_score / threshold) * 74.0