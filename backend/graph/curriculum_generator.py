"""Curriculum Generator — Louvain community detection + LLM chapter naming.

Uses the Louvain algorithm on the knowledge graph to auto-detect
chapter-like communities, orders them by prerequisite structure,
builds a topic/subtopic/concept hierarchy, and uses Ollama LLM
to generate human-readable chapter names and descriptions.
"""

import asyncio
import json
import logging
import os
import sqlite3
from typing import List, Optional

import community as community_louvain
import httpx
import networkx as nx

from graph.graph_service import KnowledgeGraphService

from fastapi import APIRouter

router = APIRouter()

log = logging.getLogger("curriculum_generator")


@router.post("/generate-curriculum")
async def generate_curriculum():
    """Auto-generate curriculum chapters from knowledge graph using Louvain + LLM."""
    gen = CurriculumGenerator()
    chapters = await gen.generate_curriculum()
    return {
        "status": "ok",
        "total_chapters": len(chapters),
        "chapters": chapters,
    }


BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DB_PATH = os.path.join(BASE_DIR, "graph_db", "ingestor.db")


class CurriculumGenerator:
    """Auto-generate a structured curriculum from a knowledge graph."""

    def __init__(self):
        """Load the knowledge graph and initialize curriculum table."""
        self.db_path = DB_PATH
        self.ollama_url = "http://localhost:11434/api/generate"
        self.model = "llama3.1:8b"
        self.graph_svc = KnowledgeGraphService()
        self.graph_svc.load_graph()
        self.G = self.graph_svc.graph
        self.init_curriculum_table()

    def init_curriculum_table(self):
        """Create the curriculum SQLite table if it doesn't exist."""
        with sqlite3.connect(self.db_path, timeout=30.0) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS curriculum (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chapter_num INTEGER,
                    chapter_name TEXT,
                    chapter_description TEXT,
                    topic_list TEXT,
                    concept_list TEXT,
                    estimated_hours REAL,
                    community_id INTEGER
                )
            """)
            conn.commit()

    def detect_chapters(self) -> dict:
        """Run Louvain community detection on the knowledge graph.

        Returns a partition dict mapping node_name → community_id.
        Updates each node's chapter_id attribute in the graph.
        """
        if self.G.number_of_nodes() == 0:
            raise ValueError("Graph is empty — cannot detect chapters")

        G_undirected = self.G.to_undirected()
        partition = community_louvain.best_partition(G_undirected, weight="weight")

        # Update chapter_id on each node
        for node, community_id in partition.items():
            self.G.nodes[node]["chapter_id"] = community_id

        unique_chapters = len(set(partition.values()))
        print(f"Detected {unique_chapters} chapters from {len(partition)} concepts")
        return partition

    def order_chapters(self, partition: dict) -> List[int]:
        """Order chapters by prerequisite structure using topological sort.

        Builds a chapter-level directed graph from cross-chapter prerequisite
        edges, then topologically sorts. Falls back to importance-based
        ordering if cycles are detected.
        """
        chapter_graph = nx.DiGraph()

        # All unique chapter IDs
        all_chapters = set(partition.values())
        for ch in all_chapters:
            chapter_graph.add_node(ch)

        # Add edges between chapters based on prerequisite relationships
        for u, v, d in self.G.edges(data=True):
            if d.get("relation_type") == "prerequisite":
                ch_u = partition.get(u)
                ch_v = partition.get(v)
                if ch_u is not None and ch_v is not None and ch_u != ch_v:
                    chapter_graph.add_edge(ch_u, ch_v)

        # Topological sort (or fallback)
        try:
            ordered = list(nx.topological_sort(chapter_graph))
        except nx.NetworkXUnfeasible:
            # Cycle detected — fallback: sort by average importance
            log.warning("Cycle detected in chapter graph, falling back to importance ordering")
            ch_importance = {}
            for node, ch in partition.items():
                imp = self.G.nodes[node].get("importance", 1.0)
                ch_importance.setdefault(ch, []).append(imp)
            avg_imp = {ch: sum(vals) / len(vals) for ch, vals in ch_importance.items()}
            ordered = sorted(avg_imp.keys(), key=lambda c: avg_imp[c], reverse=True)

        return ordered

    def build_hierarchy(self, partition: dict, order: List[int]) -> List[dict]:
        """Build a topic/subtopic/concept hierarchy for each chapter.

        Topics = top 30% by importance or importance >= 6.
        Subtopics = middle 40%.
        Concepts = remaining.
        """
        chapters = []

        for chapter_id in order:
            nodes_in_ch = [
                n for n, c in partition.items() if c == chapter_id
            ]

            # Sort by importance descending
            nodes_in_ch.sort(
                key=lambda n: self.G.nodes[n].get("importance", 1.0),
                reverse=True,
            )

            total = len(nodes_in_ch)
            if total == 0:
                continue

            # Split into tiers
            topics_cutoff = max(1, int(total * 0.3))
            subtopics_cutoff = max(topics_cutoff + 1, int(total * 0.7))

            # Also promote nodes with importance >= 6 to topics
            topics = []
            subtopics = []
            concepts = []

            for i, n in enumerate(nodes_in_ch):
                imp = self.G.nodes[n].get("importance", 1.0)
                entry = {"name": n, "importance": imp}

                if i < topics_cutoff or imp >= 6:
                    topics.append(entry)
                elif i < subtopics_cutoff:
                    subtopics.append(entry)
                else:
                    concepts.append(entry)

            chapter_dict = {
                "community_id": chapter_id,
                "topics": topics,
                "subtopics": subtopics,
                "concepts": concepts,
                "all_nodes": nodes_in_ch,
                "size": len(nodes_in_ch),
            }
            chapters.append(chapter_dict)

        return chapters

    async def name_chapter(self, chapter: dict) -> dict:
        """Use Ollama LLM to generate a human-readable chapter name and description.

        Falls back to 'Chapter N: {first_topic}' if LLM parsing fails.
        """
        # Collect top 8 topics/subtopics by importance
        combined = chapter.get("topics", []) + chapter.get("subtopics", [])
        combined.sort(key=lambda x: x.get("importance", 0), reverse=True)
        top_names = [c["name"] for c in combined[:8]]

        if not top_names:
            chapter["chapter_name"] = f"Chapter {chapter.get('chapter_num', '?')}"
            chapter["chapter_description"] = "Auto-generated chapter"
            return chapter

        concepts_str = ", ".join(top_names)
        prompt = (
            f"You are a curriculum designer. Given these key concepts from one chapter "
            f"of a textbook, suggest a concise chapter name and a 1-sentence description.\n"
            f"Concepts: {concepts_str}\n"
            f'Respond ONLY as JSON: {{"chapter_name": "...", "description": "one sentence"}}'
        )

        try:
            async with httpx.AsyncClient(timeout=180.0) as client:
                response = await client.post(
                    self.ollama_url,
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {"temperature": 0.1, "num_predict": 200},
                    },
                )
                response.raise_for_status()
                raw = response.json().get("response", "")

                # Parse JSON
                cleaned = raw.strip()
                cleaned = cleaned.removeprefix("```json").removesuffix("```").strip()
                first_brace = cleaned.find("{")
                last_brace = cleaned.rfind("}")
                if first_brace != -1 and last_brace > first_brace:
                    parsed = json.loads(cleaned[first_brace : last_brace + 1])
                    chapter["chapter_name"] = parsed.get("chapter_name", "")
                    chapter["chapter_description"] = parsed.get("description", "")
                    return chapter
        except Exception as e:
            log.warning("Ollama chapter naming failed: %s", e)

        # Fallback naming
        first_topic = top_names[0] if top_names else "Untitled"
        chapter["chapter_name"] = (
            f"Chapter {chapter.get('chapter_num', '?')}: {first_topic.title()}"
        )
        chapter["chapter_description"] = (
            f" Covers concepts related to {first_topic} and related topics."
        )
        return chapter

    def estimate_hours(self, chapter: dict) -> float:
        """Estimate study hours for a chapter based on content volume.

        Formula: topics*0.5 + subtopics*0.3 + concepts*0.1, minimum 0.5h.
        """
        hours = (
            len(chapter.get("topics", [])) * 0.5
            + len(chapter.get("subtopics", [])) * 0.3
            + len(chapter.get("concepts", [])) * 0.1
        )
        return round(max(hours, 0.5), 1)

    async def generate_curriculum(self) -> List[dict]:
        """Full pipeline: detect → order → hierarchy → name → save.

        Returns list of chapter dicts with names, descriptions,
        and estimated hours. Saves to SQLite and updates concept chapter_ids.
        """
        partition = self.detect_chapters()
        order = self.order_chapters(partition)
        chapters = self.build_hierarchy(partition, order)

        # Name each chapter via LLM and estimate hours
        for i, chapter in enumerate(chapters):
            chapter["chapter_num"] = i + 1
            await self.name_chapter(chapter)
            chapter["estimated_hours"] = self.estimate_hours(chapter)

        # Save to SQLite
        with sqlite3.connect(self.db_path, timeout=30.0) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("DELETE FROM curriculum")
            for ch in chapters:
                conn.execute(
                    """INSERT INTO curriculum
                       (chapter_num, chapter_name, chapter_description,
                        topic_list, concept_list, estimated_hours, community_id)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        ch["chapter_num"],
                        ch["chapter_name"],
                        ch["chapter_description"],
                        json.dumps([t["name"] for t in ch.get("topics", [])]),
                        json.dumps([c["name"] for c in ch.get("concepts", [])]),
                        ch["estimated_hours"],
                        ch["community_id"],
                    ),
                )

            # Update chapter_id on concepts
            for node, community_id in partition.items():
                conn.execute(
                    "UPDATE concepts SET chapter_id = ? WHERE normalized_name = ?",
                    (community_id, node),
                )

            conn.commit()

        print(f"\nCurriculum generated: {len(chapters)} chapters")
        for ch in chapters:
            print(
                f"  Ch {ch['chapter_num']}: {ch['chapter_name']} "
                f"({ch['estimated_hours']}h, {ch['size']} concepts)"
            )

        return chapters
