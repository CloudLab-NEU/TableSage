import sys
import os
import numpy as np
import time
from typing import List, Dict, Any

# Add app to path
app_path = r"d:\TableSage\app"
if app_path not in sys.path:
    sys.path.append(app_path)

from db.db_manager import DatabaseManager
from core_progress.bm25_searcher import BM25Searcher

def cosine_similarity(a, b):
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

from core_progress.search_similar_question import string_similarity

class Evaluator:
    def __init__(self):
        self.db = DatabaseManager()
        self.bm25_searcher = BM25Searcher()
        self.all_data = list(self.db.knowledge_db.find({}, {
            "table_id": 1, 
            "question": 1, 
            "question_skeleton": 1, 
            "sk_embedding": 1,
            "sql_skeleton": 1,
            "table_structure": 1
        }))
        print(f"Loaded {len(self.all_data)} records for evaluation.")

    def run_eval(self, num_samples=100):
        # Pick random samples to test as queries
        np.random.seed(42)
        indices = np.random.choice(len(self.all_data), num_samples, replace=False)
        test_samples = [self.all_data[i] for i in indices]

        strategies = [
            "Strategy 1 (Skeleton Only)", 
            "Strategy 2 (BM25 -> Skeleton)", 
            "Strategy 4 (Full: BM25 -> Skeleton + Table 0.7/0.3)",
            "Strategy 6 (Best: BM25 -> Skeleton + Table 0.9/0.1)"
        ]
        stats = {s: {"hit_at_1": 0, "recall_at_5": 0, "precision_at_5": 0, "mrr": 0, "time": 0} for s in strategies}

        for i, sample in enumerate(test_samples):
            query_q = sample['question']
            query_emb = np.array(sample['sk_embedding'])
            query_ts = sample.get('table_structure')
            query_logic = sample.get('sql_skeleton')
            query_id = sample['table_id']

            for s_name in strategies:
                t0 = time.time()
                if s_name == "Strategy 1 (Skeleton Only)":
                    results = self.search_v1(query_emb, query_id)
                elif s_name == "Strategy 2 (BM25 -> Skeleton)":
                    results = self.search_v2(query_q, query_emb, query_id)
                elif s_name == "Strategy 4 (Full: BM25 -> Skeleton + Table 0.7/0.3)":
                    results = self.search_v4(query_q, query_emb, query_ts, query_id)
                elif s_name == "Strategy 6 (Best: BM25 -> Skeleton + Table 0.9/0.1)":
                    results = self.search_v6(query_q, query_emb, query_ts, query_id)
                
                dt = time.time() - t0
                stats[s_name]["time"] += dt

                # Calculate metrics
                hits = [doc.get('sql_skeleton') == query_logic for doc in results[:5]]
                
                if hits and hits[0]:
                    stats[s_name]["hit_at_1"] += 1
                if any(hits):
                    stats[s_name]["recall_at_5"] += 1
                stats[s_name]["precision_at_5"] += sum(hits) / 5.0
                for rank, hit in enumerate(hits, 1):
                    if hit:
                        stats[s_name]["mrr"] += 1.0 / rank
                        break

            if (i+1) % 20 == 0:
                print(f"Processed {i+1}/{num_samples} samples...")

        # Final Report
        print("\n" + "="*90)
        print("FINAL RETRIEVAL EVALUATION REPORT (Weight Optimization)")
        print("="*90)
        print(f"{'Strategy':<45} | P@1     | R@5     | P@5     | MRR     | Latency")
        print("-" * 90)
        for name in strategies:
            data = stats[name]
            p1 = (data['hit_at_1'] / num_samples) * 100
            r5 = (data['recall_at_5'] / num_samples) * 100
            p5 = (data['precision_at_5'] / num_samples) * 100
            mrr = (data['mrr'] / num_samples)
            latency = (data['time'] / num_samples) * 1000
            print(f"{name: <45} | {p1:>5.1f}% | {r5:>5.1f}% | {p5:>5.1f}% | {mrr:>6.3f} | {latency:>5.1f}ms")
        print("="*90)

    def search_v1(self, query_emb, exclude_id):
        scored = []
        for doc in self.all_data:
            if doc['table_id'] == exclude_id: continue
            sim = cosine_similarity(query_emb, np.array(doc['sk_embedding']))
            scored.append({"doc": doc, "score": sim})
        scored.sort(key=lambda x: x['score'], reverse=True)
        return [s['doc'] for s in scored[:5]]

    def search_v2(self, query_q, query_emb, exclude_id):
        bm25_res = self.bm25_searcher.search(query_q, top_n=200)
        bm25_ids = {r['table_id'] for r in bm25_res}
        scored = []
        for doc in self.all_data:
            if doc['table_id'] == exclude_id: continue
            if doc['table_id'] not in bm25_ids: continue
            sim = cosine_similarity(query_emb, np.array(doc['sk_embedding']))
            scored.append({"doc": doc, "score": sim})
        scored.sort(key=lambda x: x['score'], reverse=True)
        return [s['doc'] for s in scored[:5]]

    def search_v4(self, query_q, query_emb, query_ts, exclude_id):
        bm25_res = self.bm25_searcher.search(query_q, top_n=200)
        bm25_ids = {r['table_id'] for r in bm25_res}
        scored = []
        for doc in self.all_data:
            if doc['table_id'] == exclude_id: continue
            if doc['table_id'] not in bm25_ids: continue
            sim_sk = cosine_similarity(query_emb, np.array(doc['sk_embedding']))
            sim_ts = string_similarity(str(doc.get('table_structure')), str(query_ts))
            final_score = 0.7 * sim_sk + 0.3 * sim_ts
            scored.append({"doc": doc, "score": final_score})
        scored.sort(key=lambda x: x['score'], reverse=True)
        return [s['doc'] for s in scored[:5]]

    def search_v6(self, query_q, query_emb, query_ts, exclude_id):
        # Weighted optimized: 0.9 Skeleton + 0.1 Table
        bm25_res = self.bm25_searcher.search(query_q, top_n=200)
        bm25_ids = {r['table_id'] for r in bm25_res}
        scored = []
        for doc in self.all_data:
            if doc['table_id'] == exclude_id: continue
            if doc['table_id'] not in bm25_ids: continue
            
            sim_sk = cosine_similarity(query_emb, np.array(doc['sk_embedding']))
            sim_ts = string_similarity(str(doc.get('table_structure')), str(query_ts))
            
            final_score = 0.9 * sim_sk + 0.1 * sim_ts
            scored.append({"doc": doc, "score": final_score})
            
        scored.sort(key=lambda x: x['score'], reverse=True)
        return [s['doc'] for s in scored[:5]]

if __name__ == "__main__":
    evaluator = Evaluator()
    evaluator.run_eval(num_samples=100)
