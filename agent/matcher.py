#!/usr/bin/env python3
"""
Mutual Aid Matching Engine
==========================
Fuzzy text matching between needs and skills.
Priority scoring: urgency, recency, location proximity.
All stdlib -- no ML dependencies.

AGPL-3.0 -- SolarPunk Collective
"""

import re
from datetime import datetime, timezone
from difflib import SequenceMatcher

# -- Text utilities --

def _normalize(text):
    """Lowercase, strip punctuation, collapse whitespace."""
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _tokenize(text):
    """Split normalized text into word set."""
    return set(_normalize(text).split())


STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "shall",
    "should", "may", "might", "must", "can", "could", "i", "me", "my",
    "we", "our", "you", "your", "he", "she", "it", "they", "them",
    "need", "help", "want", "looking", "someone", "anyone", "please"
}


def _meaningful_tokens(text):
    """Tokens minus stopwords."""
    return _tokenize(text) - STOPWORDS


# -- Similarity functions --

def text_similarity(a, b):
    """Combined fuzzy similarity: token overlap + sequence ratio."""
    # Token overlap (Jaccard)
    tokens_a = _meaningful_tokens(a)
    tokens_b = _meaningful_tokens(b)
    if not tokens_a or not tokens_b:
        return 0.0
    jaccard = len(tokens_a & tokens_b) / len(tokens_a | tokens_b)

    # Sequence similarity on normalized strings
    seq_ratio = SequenceMatcher(None, _normalize(a), _normalize(b)).ratio()

    # Weighted blend
    return (jaccard * 0.6) + (seq_ratio * 0.4)


def category_match(need_cat, skill_cat):
    """Exact category match score."""
    if _normalize(need_cat) == _normalize(skill_cat):
        return 1.0
    # Partial matches for related categories
    related = {
        frozenset({"food", "grocery"}): 0.8,
        frozenset({"housing", "rent"}): 0.8,
        frozenset({"transportation", "car"}): 0.8,
        frozenset({"employment", "career"}): 0.8,
        frozenset({"childcare", "babysitting"}): 0.8,
    }
    pair = frozenset({_normalize(need_cat), _normalize(skill_cat)})
    return related.get(pair, 0.0)


def location_proximity(loc_a, loc_b):
    """Simple location matching -- exact string or both remote."""
    a = _normalize(loc_a)
    b = _normalize(loc_b)
    if a == b:
        return 1.0
    if "remote" in a or "remote" in b:
        return 0.7  # remote can serve anyone
    # Same state check
    states_a = re.findall(r"\b([A-Z]{2})\b", loc_a)
    states_b = re.findall(r"\b([A-Z]{2})\b", loc_b)
    if states_a and states_b and states_a[-1] == states_b[-1]:
        return 0.6
    return 0.1


def recency_score(posted_iso):
    """Score based on how recently a need was posted (0-1).
    Newer = higher priority."""
    try:
        posted = datetime.fromisoformat(posted_iso.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        hours_old = (now - posted).total_seconds() / 3600
        if hours_old <= 24:
            return 1.0
        elif hours_old <= 72:
            return 0.8
        elif hours_old <= 168:  # 1 week
            return 0.5
        else:
            return 0.2
    except (ValueError, TypeError):
        return 0.3


# -- Matching engine --

def match_needs_to_skills(needs, skills):
    """
    Match each open need against all available skills.
    Returns list of match dicts with similarity data.
    """
    matches = []

    for need in needs:
        need_text = "{} {}".format(need["title"], need["description"])
        need_cat = need.get("category", "")
        need_loc = need.get("location", "")

        for skill in skills:
            skill_text = "{} {}".format(skill["title"], skill["description"])
            skill_cat = skill.get("category", "")
            skill_loc = skill.get("location", "")

            # Compute similarities
            txt_sim = text_similarity(need_text, skill_text)
            cat_sim = category_match(need_cat, skill_cat)
            loc_sim = location_proximity(need_loc, skill_loc)

            # Only keep if there is SOME relevance
            combined = (txt_sim * 0.3) + (cat_sim * 0.5) + (loc_sim * 0.2)
            if combined >= 0.25:
                matches.append({
                    "need_id": need["id"],
                    "need_title": need["title"],
                    "need_description": need["description"],
                    "need_location": need_loc,
                    "category": need_cat,
                    "urgency": need.get("urgency", 1),
                    "posted": need.get("posted", ""),
                    "skill_id": skill["id"],
                    "skill_title": skill["title"],
                    "skill_description": skill["description"],
                    "skill_person": skill.get("person", "volunteer"),
                    "skill_location": skill_loc,
                    "skill_availability": skill.get("availability", "unknown"),
                    "text_similarity": txt_sim,
                    "category_similarity": cat_sim,
                    "location_similarity": loc_sim,
                    "combined_similarity": combined
                })

    return matches


def score_matches(matches):
    """
    Final scoring: combines similarity with urgency and recency.
    Returns sorted list (best match first) with score 0-100.
    """
    scored = []

    for m in matches:
        # Base similarity (0-1)
        sim = m["combined_similarity"]

        # Urgency boost (1-5 mapped to 0-1)
        urg = (m["urgency"] - 1) / 4.0

        # Recency boost
        rec = recency_score(m["posted"])

        # Final score: similarity 50%, urgency 30%, recency 20%
        raw_score = (sim * 0.50) + (urg * 0.30) + (rec * 0.20)
        final_score = min(raw_score * 100, 100)

        # Build reason list
        reasons = []
        if m["category_similarity"] >= 0.8:
            reasons.append("category match")
        if m["text_similarity"] >= 0.3:
            reasons.append("skill description aligns")
        if m["location_similarity"] >= 0.6:
            reasons.append("same area")
        elif m["location_similarity"] >= 0.5:
            reasons.append("remote-capable")
        if m["urgency"] >= 4:
            reasons.append("high urgency")
        if not reasons:
            reasons.append("partial overlap")

        scored.append({
            **m,
            "score": final_score,
            "reasons": reasons
        })

    # Sort by score descending, then by urgency
    scored.sort(key=lambda x: (x["score"], x["urgency"]), reverse=True)

    # Deduplicate: keep best match per need
    seen_needs = set()
    deduped = []
    for s in scored:
        if s["need_id"] not in seen_needs:
            seen_needs.add(s["need_id"])
            deduped.append(s)

    return deduped


# -- Standalone test --

if __name__ == "__main__":
    # Quick self-test
    test_needs = [
        {
            "id": "t1", "title": "Need groceries delivered",
            "description": "Cannot leave house, need weekly grocery delivery",
            "category": "food", "urgency": 4, "location": "Portland, OR",
            "posted": "2026-04-08T10:00:00Z"
        }
    ]
    test_skills = [
        {
            "id": "s1", "title": "Grocery delivery volunteer",
            "description": "Happy to shop and deliver groceries, have a car",
            "category": "food", "location": "Portland, OR",
            "person": "helper", "availability": "weekends"
        },
        {
            "id": "s2", "title": "Math tutoring",
            "description": "Can tutor algebra and calculus",
            "category": "education", "location": "remote",
            "person": "tutor", "availability": "evenings"
        }
    ]

    matches = match_needs_to_skills(test_needs, test_skills)
    scored = score_matches(matches)

    print("Test matches:")
    for m in scored:
        print("  [{:.0f}] {} <-> {}".format(m["score"], m["need_title"], m["skill_title"]))
        print("       Reasons: {}".format(", ".join(m["reasons"])))
    print("")
    print("Total matches: {}".format(len(scored)))
