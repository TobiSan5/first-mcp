# MCP Memory Server — Tag-Based Retrieval Architecture

> Design document for Claude Code. Written April 27, 2026.
> Context: improving the retrieval function in the user's custom Python MCP memory server.

---

## Background: The Problem

The current retrieval system uses text embedding + similarity score on `content` and `tags` to find relevant memories. This works well in many cases, but fails when the query uses different vocabulary than what was used at storage time.

**Documented failure case:**

```
Query: "scheduling calendar software"
Expected: Ergatax memory (academic timetabling SaaS)
Result:   No hits

Query: "timetabling higher education Norway"
Result:   Ergatax memory found correctly ✓
```

This is the **encoding specificity problem** (Tulving, 1973): retrieval succeeds when cues match encoding context, fails when vocabulary differs. Analogous to the "butcher on the bus" phenomenon in cognitive psychology — you recognize a face but can't place it without the original context.

A secondary issue: very long memory entries (6000+ words) produce noisy embeddings that dilute precise content matching.

---

## Core Design Decision

**Tags are the primary semantic carrier for retrieval** — not raw content embeddings, not cluster membership alone.

The key insight: tags are short, high-signal, precisely chosen representations of a memory's topic. They are far easier to embed and compare meaningfully than long content blobs. The retrieval system should be built around **soft tag-to-tag similarity matching**.

---

## The Scoring Model

For a search query with tags `Q = {q1, q2, ...}` against a stored memory with tags `M = {m1, m2, ...}`:

### Step 1 — Per query-tag: find best match among memory's tags

```
score(qi) = max_{mj ∈ M} cosine_similarity(embed(qi), embed(mj))
```

### Step 2 — Hit criterion (one tag is sufficient for a hit)

```
hit = True  if  max_i(score(qi)) > threshold
```

### Step 3 — Ranking (more matching tags = higher priority)

```
rank_score = Σ score(qi)   for all qi where score(qi) > threshold
```

This means:
- A memory that matches **one** query tag is a hit
- A memory that matches **three** query tags ranks higher than one that matches one
- The score accumulates over query tags, not memory tags — so a memory with 20 tags doesn't automatically beat one with 3

### Python implementation sketch

```python
def score_memory(query_tags, memory_tag_embeddings, tag_registry, threshold=0.75):
    tag_scores = []

    for qt in query_tags:
        # Use cached embedding if tag is known; embed on-the-fly otherwise
        qt_emb = tag_registry.get(qt) or model.encode(qt)

        # Best cosine match among this memory's tags
        best = max(
            cosine(qt_emb, mt_emb)
            for mt_emb in memory_tag_embeddings
        )
        if best > threshold:
            tag_scores.append(best)

    if not tag_scores:
        return 0.0          # no hit

    return sum(tag_scores)  # ranking score: more matching tags = higher
```

---

## Adaptive Threshold

A fixed threshold is fragile. Use an **adaptive threshold per query-tag** based on the score distribution across all memories:

```python
all_scores_for_qi = [cosine(qt_emb, mt_emb) for each memory, each tag]
threshold = mean(all_scores_for_qi) + 0.5 * std(all_scores_for_qi)
```

This scales automatically with how densely populated the tag landscape is. In a sparse tag space, the threshold is lower; in a dense space, higher.

---

## Two-Stage Architecture (Scalability)

Soft tag matching against every memory is expensive at scale. Use clusters as a **coarse pre-filter**:

```
STAGE 1 — Coarse filtering (fast):
  query-tags → cluster lookup → candidate memories (~10-20% of total)

STAGE 2 — Precise scoring (on small candidate set):
  soft tag matching → ranked results

FALLBACK:
  If candidate set is too small → expand to neighboring clusters
```

### Tag Registry

All known tags are stored with their embedding vectors:
- Known tags at query time: O(1) lookup, no re-embedding
- Unknown tags: embed on-the-fly, then compare against registry

### Cluster Construction (HDBSCAN on tags)

```python
from sentence_transformers import SentenceTransformer
import umap, hdbscan

model = SentenceTransformer('all-MiniLM-L6-v2')  # 384-dim

all_tags = list({tag for mem in memories for tag in mem['tags']})
tag_embeddings = model.encode(all_tags)

# Reduce dimensionality before clustering (avoids curse of dimensionality)
reducer = umap.UMAP(n_components=15, metric='cosine')
tag_emb_reduced = reducer.fit_transform(tag_embeddings)

clusterer = hdbscan.HDBSCAN(min_cluster_size=2, metric='euclidean')
tag_labels = clusterer.fit_predict(tag_emb_reduced)

# tag → cluster_id registry
tag_to_cluster = {tag: int(label) for tag, label in zip(all_tags, tag_labels)}

# Cluster centroids computed in ORIGINAL 384-dim space (not reduced)
# — better for cosine similarity at query time
cluster_centroids = {}
for cid in set(tag_labels):
    if cid == -1: continue  # outlier tags — handle separately
    idxs = [i for i, l in enumerate(tag_labels) if l == cid]
    cluster_centroids[cid] = tag_embeddings[idxs].mean(axis=0)
```

**Important:** Centroids are computed in full 384-dim space. UMAP reduction is used only to make HDBSCAN work well — the reduced vectors are discarded afterward. Query matching uses the full-dimensional centroids.

### Memories store cluster_ids, not embedding vectors

```json
{
  "content": "...",
  "tags": ["ergatax", "startup", "higher-education"],
  "cluster_ids": [1, 4],
  "tag_embeddings": { "ergatax": [...], "startup": [...], "higher-education": [...] }
}
```

Each memory stores the embedding of its own tags compactly. No full content embedding needed.

---

## Spreading Activation (Future Extension)

This is the solution to the "empty drawer" problem: if the primary cluster is sparse, expand search to neighboring clusters.

Clusters are connected by weighted edges based on **tag co-occurrence in memories**:

```
Memory with tags ["ergatax", "agentic-systems"]
  → creates edge: cluster(ergatax) ↔ cluster(agentic-systems)
  → weight increases each time two clusters co-occur
```

Search with spreading activation:
```
1. Match query → cluster 1 (score 0.8) → retrieve memories
2. Activate neighbor cluster 4 with dampened score (0.8 × edge_weight)
3. If still insufficient → activate next ring of neighbors (further dampened)
```

Analogous to human associative memory: partial cues gradually activate related nodes until recognition occurs.

---

## Why Not Cluster Content Directly?

An earlier design considered running HDBSCAN on memory content embeddings. This was rejected because:

1. Long memories (thousands of words) produce diluted embeddings — the mean of all words drifts to a semantically vague centroid
2. Tags are already the author's own compression of the content — they are cleaner and more precise than re-deriving clusters from raw text
3. Tag co-occurrence across memories provides structural information (which topics appear together) that raw content embeddings don't preserve

---

## Why Not 2D Spatial Grid?

An earlier idea was to project embeddings to 2D and store memories in grid cells ("drawers"), searching neighboring cells when the primary cell is empty.

This is the right spatial intuition but the wrong dimensionality. Reducing 384 dimensions to 2 loses too much information — two memories that are neighbors in 2D may be semantically distant in the original space, and vice versa. UMAP/t-SNE preserve local topology well enough for visualization but not for reliable nearest-neighbor retrieval.

The soft tag matching approach captures the same intuition ("expand search when primary match is empty") algebraically without the information loss of 2D projection.

---

## Analogy to Pauline Logits Project

This architecture is structurally identical to the logits-based analysis of Paul's epistles developed in earlier sessions:

| Paul project | Memory system |
|---|---|
| Verse embeddings | Memory content |
| Logit labels (theological concepts) | Tags |
| Cosine similarity: verse ↔ logit | Cosine similarity: query-tag ↔ memory-tag |
| Latent theological dimensions (autoencoder) | Cluster structure (HDBSCAN) |
| Score profile across logits | rank_score across query-tags |

Both systems discretize a continuous semantic space into meaningful units and use similarity scores as the bridge between a continuous query and a discrete index. Tags are the user's personalized "logit dimensions" — emergent from their own tagging patterns rather than predefined.

---

## Implementation Checklist for Claude Code

- [ ] Build tag registry: collect all unique tags, embed with `all-MiniLM-L6-v2`, store as dict
- [ ] Run UMAP (15-dim) + HDBSCAN (`min_cluster_size=2`) on tag embeddings
- [ ] Compute cluster centroids in original 384-dim space
- [ ] Update memory schema: add `cluster_ids` and `tag_embeddings` fields
- [ ] Implement `score_memory()` with adaptive threshold
- [ ] Implement two-stage search: cluster filter → soft tag matching
- [ ] Implement cluster fallback/expansion when candidate set < N
- [ ] Schedule periodic re-clustering (e.g., every 10 new memories)
- [ ] (Future) Build cluster co-occurrence graph for spreading activation
