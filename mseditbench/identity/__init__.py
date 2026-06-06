"""Cross-shot character identity DB.

    from mseditbench.identity.face_extract import extract_faces_for_video
    from mseditbench.identity.face_cluster import cluster_to_character_db

CLI:
    python -m mseditbench.identity.face_extract --help
    python -m mseditbench.identity.face_cluster --help
    python -m mseditbench.identity.run_batch    --help
"""

from .face_extract import extract_faces_for_video
from .face_cluster import cluster_to_character_db, agglomerative_cluster

__all__ = ["extract_faces_for_video", "cluster_to_character_db", "agglomerative_cluster"]
