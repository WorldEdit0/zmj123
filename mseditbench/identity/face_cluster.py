"""Cluster face embeddings across all shots of one video → character_id table.

Approach: agglomerative clustering on cosine distance with a configurable
threshold. Default 0.45 (typical ArcFace identity boundary). Each cluster
becomes one character; clusters seen in only one shot are kept but flagged
`recurring=False`.

Reconciles with the source JSON's `characters` field by matching on appears-in-
shots overlap when possible, so downstream metrics can use the same C1/C2
labels as the prompt design.

CLI:
    python -m mseditbench.identity.face_cluster \
        --faces_json runs/faces/00000.faces.json \
        --embeddings_npy runs/faces/00000.faces.embeddings.npy \
        --source_item_idx 0 \
        --source_json seedance_api_example/source_prompts_multishot_v1.json \
        --output_json runs/faces/00000.character_db.json \
        --threshold 0.45
"""

from __future__ import annotations
import argparse
import json
import os
from pathlib import Path

import numpy as np


def _cosine_dist_matrix(emb: np.ndarray) -> np.ndarray:
    sims = emb @ emb.T
    return 1.0 - sims


def agglomerative_cluster(emb: np.ndarray, threshold: float = 0.45) -> np.ndarray:
    """Greedy agglomerative single-link clustering on cosine distance.

    Pure-numpy so we don't pull sklearn into the metrics layer. Returns
    a [N] array of integer cluster ids starting at 0.
    """
    if emb.shape[0] == 0:
        return np.zeros(0, dtype=int)
    n = emb.shape[0]
    labels = np.arange(n)
    dists = _cosine_dist_matrix(emb)
    np.fill_diagonal(dists, np.inf)

    while True:
        min_idx = np.unravel_index(np.argmin(dists), dists.shape)
        if dists[min_idx] > threshold:
            break
        i, j = sorted(min_idx)
        # merge cluster of j into cluster of i
        labels[labels == labels[j]] = labels[i]
        # update dists with single-link min
        new_row = np.minimum(dists[i], dists[j])
        dists[i, :] = new_row
        dists[:, i] = new_row
        dists[j, :] = np.inf
        dists[:, j] = np.inf
        dists[i, i] = np.inf

    # compact label space: 0..K-1
    uniq = sorted(set(labels.tolist()))
    relabel = {old: new for new, old in enumerate(uniq)}
    return np.array([relabel[l] for l in labels])


def cluster_to_character_db(
    faces_record: dict,
    embeddings: np.ndarray,
    src_characters: list[dict] | None = None,
    threshold: float = 0.45,
) -> dict:
    cluster_ids = agglomerative_cluster(embeddings, threshold=threshold)
    records = faces_record["records"]

    # group records by cluster
    by_cluster: dict[int, list[int]] = {}
    for i, c in enumerate(cluster_ids):
        by_cluster.setdefault(int(c), []).append(i)

    characters = []
    for cid, idxs in sorted(by_cluster.items()):
        shots_in = sorted({records[i]["shot_id"] for i in idxs})
        crops = [records[i]["crop_path"] for i in idxs if records[i].get("crop_path")][:5]
        centroid = embeddings[idxs].mean(axis=0)
        centroid = centroid / (np.linalg.norm(centroid) + 1e-8)

        characters.append({
            "character_id": f"K{cid}",            # K = clustered, before reconciliation
            "appears_in_shots": shots_in,
            "n_face_crops": len(idxs),
            "recurring": len(shots_in) >= 2,
            "centroid_embedding": centroid.tolist(),
            "sample_crop_paths": crops,
            "src_json_id": None,
        })

    # reconcile with source JSON characters by best appears-in-shots overlap
    if src_characters:
        for srcc in src_characters:
            # we don't know which shots they appear in from JSON alone; pair to the
            # cluster with most face appearances overall as a heuristic
            best = max(
                (c for c in characters if c["src_json_id"] is None),
                key=lambda c: c["n_face_crops"], default=None,
            )
            if best is not None:
                best["src_json_id"] = srcc["id"]
                best["canonical_label"] = srcc["desc"]

    return {
        "video_id": faces_record["video_id"],
        "fps": faces_record["fps"],
        "n_faces_total": embeddings.shape[0],
        "n_clusters": len(characters),
        "threshold": threshold,
        "characters": characters,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--faces_json", required=True)
    ap.add_argument("--embeddings_npy", required=True)
    ap.add_argument("--output_json", required=True)
    ap.add_argument("--source_json", default="")
    ap.add_argument("--threshold", type=float, default=0.45)
    args = ap.parse_args()

    faces = json.load(open(args.faces_json))
    emb = np.load(args.embeddings_npy)

    src_chars = None
    if args.source_json:
        src_items = json.load(open(args.source_json))
        vid = faces["video_id"]
        src_item = next((it for it in src_items
                         if f"{int(it['global_index']):05d}" == vid), None)
        if src_item:
            src_chars = src_item.get("characters", [])

    db = cluster_to_character_db(faces, emb, src_chars, threshold=args.threshold)

    os.makedirs(os.path.dirname(args.output_json) or ".", exist_ok=True)
    with open(args.output_json, "w") as f:
        json.dump(db, f, indent=2)
    print(f"{db['n_faces_total']} faces -> {db['n_clusters']} characters -> {args.output_json}")


if __name__ == "__main__":
    main()
