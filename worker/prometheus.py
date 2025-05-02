import os

from prometheus_client import Counter, Histogram

__all__ = [
    'closest_tag_hist',
    'farthest_tag_hist',
    'average_tag_hist',
    'metric_namespace',
]

os.makedirs(os.environ.get('PROMETHEUS_MULTIPROC_DIR', '/tmp/prometheus_multiproc'), exist_ok=True)

metric_namespace = "worker"

# MongoDB metrics
new_conversation_counter = Counter(
    "new_conversation_total",
    "Number of new conversations processed",
    namespace=metric_namespace,
)

no_answer_counter = Counter(
    "no_answer_total",
    "Number of times no answer was found",
    namespace=metric_namespace,
)

answer_not_exact_counter = Counter(
    "answer_not_exact_total",
    "Number of times answer was not exact",
    namespace=metric_namespace,
)

# Qdrant metrics
average_tag_hist = Histogram(
    "average_tag_similarity",
    "Average similarity score for tags",
    namespace=metric_namespace,
    buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
)

closest_tag_hist = Histogram(
    "closest_tag_similarity",
    "Similarity score for closest tag",
    namespace=metric_namespace,
    buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
)

farthest_tag_hist = Histogram(
    "farthest_tag_similarity",
    "Similarity score for farthest tag",
    namespace=metric_namespace,
    buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
)
