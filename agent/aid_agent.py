#!/usr/bin/env python3
"""
SolarPunk Mutual Aid Agent
==========================
Maintains needs board, skills board, resource pool, emergency fund.
Matches needs to skills. Posts matched needs as GitHub Issues.
No bureaucracy. Just people helping people.

AGPL-3.0 -- SolarPunk Collective
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from matcher import match_needs_to_skills, score_matches

# -- Paths --
ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
NEEDS_FILE = DATA / "needs.json"
SKILLS_FILE = DATA / "skills.json"
FUND_FILE = DATA / "fund.json"
REPORT_DIR = DATA / "reports"

REPO = os.environ.get("MUTUAL_AID_REPO", "meekotharaccoon-cell/solarpunk-mutual-aid")


# -- Data bootstrap --

def _ensure_data():
    """Create data files if missing."""
    DATA.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    if not NEEDS_FILE.exists():
        NEEDS_FILE.write_text(json.dumps(_seed_needs(), indent=2))
    if not SKILLS_FILE.exists():
        SKILLS_FILE.write_text(json.dumps(_seed_skills(), indent=2))
    if not FUND_FILE.exists():
        FUND_FILE.write_text(json.dumps(_seed_fund(), indent=2))


def _seed_needs():
    return {
        "needs": [
            {
                "id": "n001",
                "posted": "2026-04-08T12:00:00Z",
                "person": "anonymous",
                "title": "Grocery delivery for immunocompromised neighbor",
                "category": "food",
                "urgency": 4,
                "location": "Portland, OR",
                "description": "Weekly grocery run needed -- person cannot leave home safely.",
                "status": "open"
            },
            {
                "id": "n002",
                "posted": "2026-04-07T09:30:00Z",
                "person": "anonymous",
                "title": "Resume help -- recently laid off",
                "category": "employment",
                "urgency": 3,
                "location": "remote",
                "description": "Need someone to review and improve my resume. Tech background.",
                "status": "open"
            },
            {
                "id": "n003",
                "posted": "2026-04-06T18:00:00Z",
                "person": "anonymous",
                "title": "Emergency rent assistance -- $400 short",
                "category": "housing",
                "urgency": 5,
                "location": "Detroit, MI",
                "description": "Eviction notice in 5 days. Need $400 to cover gap after losing hours.",
                "status": "open"
            },
            {
                "id": "n004",
                "posted": "2026-04-08T06:00:00Z",
                "person": "anonymous",
                "title": "Car repair -- brake pads replacement",
                "category": "transportation",
                "urgency": 4,
                "location": "Austin, TX",
                "description": "Brakes grinding, unsafe to drive. Can buy parts but need a mechanic.",
                "status": "open"
            },
            {
                "id": "n005",
                "posted": "2026-04-05T14:00:00Z",
                "person": "anonymous",
                "title": "Childcare for job interview",
                "category": "childcare",
                "urgency": 3,
                "location": "Chicago, IL",
                "description": "Need 3 hours of childcare on Thursday for a job interview. Two kids, ages 4 and 6.",
                "status": "open"
            }
        ]
    }


def _seed_skills():
    return {
        "skills": [
            {
                "id": "s001",
                "person": "volunteer_a",
                "title": "Grocery shopping & delivery",
                "category": "food",
                "location": "Portland, OR",
                "availability": "weekends",
                "description": "Happy to do grocery runs. Have a car and Costco membership."
            },
            {
                "id": "s002",
                "person": "volunteer_b",
                "title": "Resume writing & career coaching",
                "category": "employment",
                "location": "remote",
                "availability": "evenings",
                "description": "15 years in tech hiring. Can review resumes and do mock interviews."
            },
            {
                "id": "s003",
                "person": "volunteer_c",
                "title": "Auto mechanic -- brakes, oil, basic repair",
                "category": "transportation",
                "location": "Austin, TX",
                "availability": "weekends",
                "description": "Shade tree mechanic, 10 years experience. Have tools and a lift."
            },
            {
                "id": "s004",
                "person": "volunteer_d",
                "title": "Babysitting & childcare",
                "category": "childcare",
                "location": "Chicago, IL",
                "availability": "flexible",
                "description": "Retired teacher, love kids. Background check available."
            },
            {
                "id": "s005",
                "person": "volunteer_e",
                "title": "Legal aid -- tenant rights",
                "category": "housing",
                "location": "remote",
                "availability": "weekdays",
                "description": "Paralegal specializing in tenant rights. Can help with eviction defense."
            }
        ]
    }


def _seed_fund():
    return {
        "balance": 1250.00,
        "currency": "USD",
        "contributions": [
            {"date": "2026-04-01", "amount": 500.00, "source": "community_fundraiser"},
            {"date": "2026-04-05", "amount": 750.00, "source": "anonymous_donor"}
        ],
        "disbursements": [
            {"date": "2026-04-03", "amount": 0.00, "recipient": "--", "purpose": "--"}
        ],
        "pending_requests": [
            {
                "id": "n003",
                "amount": 400.00,
                "purpose": "Emergency rent assistance",
                "status": "pending_review"
            }
        ]
    }


# -- Load / save --

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# -- Needs board --

def get_open_needs():
    data = load_json(NEEDS_FILE)
    return [n for n in data["needs"] if n["status"] == "open"]


def add_need(title, category, urgency, location, description, person="anonymous"):
    data = load_json(NEEDS_FILE)
    new_id = f"n{len(data['needs']) + 1:03d}"
    need = {
        "id": new_id,
        "posted": datetime.now(timezone.utc).isoformat(),
        "person": person,
        "title": title,
        "category": category,
        "urgency": urgency,
        "location": location,
        "description": description,
        "status": "open"
    }
    data["needs"].append(need)
    save_json(NEEDS_FILE, data)
    return need


def close_need(need_id, resolution="fulfilled"):
    data = load_json(NEEDS_FILE)
    for n in data["needs"]:
        if n["id"] == need_id:
            n["status"] = resolution
            break
    save_json(NEEDS_FILE, data)


# -- Skills board --

def get_skills():
    data = load_json(SKILLS_FILE)
    return data["skills"]


def add_skill(title, category, location, availability, description, person="volunteer"):
    data = load_json(SKILLS_FILE)
    new_id = f"s{len(data['skills']) + 1:03d}"
    skill = {
        "id": new_id,
        "person": person,
        "title": title,
        "category": category,
        "location": location,
        "availability": availability,
        "description": description
    }
    data["skills"].append(skill)
    save_json(SKILLS_FILE, data)
    return skill


# -- Emergency fund --

def get_fund_status():
    return load_json(FUND_FILE)


def contribute(amount, source="anonymous"):
    fund = load_json(FUND_FILE)
    fund["balance"] += amount
    fund["contributions"].append({
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "amount": amount,
        "source": source
    })
    save_json(FUND_FILE, fund)
    return fund["balance"]


def disburse(amount, recipient, purpose):
    fund = load_json(FUND_FILE)
    if amount > fund["balance"]:
        return None  # insufficient funds
    fund["balance"] -= amount
    fund["disbursements"].append({
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "amount": amount,
        "recipient": recipient,
        "purpose": purpose
    })
    # remove from pending if present
    fund["pending_requests"] = [
        r for r in fund["pending_requests"]
        if r.get("purpose") != purpose
    ]
    save_json(FUND_FILE, fund)
    return fund["balance"]


# -- GitHub Issues integration --

def post_match_as_issue(match):
    """Post a match suggestion as a GitHub Issue using gh CLI."""
    title = "[Match] {} <-> {}".format(match["need_title"], match["skill_title"])
    body_lines = [
        "## Mutual Aid Match Found",
        "",
        "**Need:** {}".format(match["need_title"]),
        "- Category: {}".format(match["category"]),
        "- Urgency: {}/5".format(match["urgency"]),
        "- Location: {}".format(match["need_location"]),
        "- Description: {}".format(match["need_description"]),
        "",
        "**Matched Skill:** {}".format(match["skill_title"]),
        "- Volunteer: {}".format(match["skill_person"]),
        "- Location: {}".format(match["skill_location"]),
        "- Availability: {}".format(match["skill_availability"]),
        "- Description: {}".format(match["skill_description"]),
        "",
        "**Match Score:** {:.0f}/100".format(match["score"]),
        "**Match Reasons:** {}".format(", ".join(match["reasons"])),
        "",
        "---",
        "*Auto-generated by SolarPunk Mutual Aid Agent*"
    ]
    body = "\n".join(body_lines)
    labels = "mutual-aid,auto-match"
    try:
        result = subprocess.run(
            ["gh", "issue", "create",
             "--repo", REPO,
             "--title", title,
             "--body", body,
             "--label", labels],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            print("  -> Issue created: {}".format(result.stdout.strip()))
            return result.stdout.strip()
        else:
            # Labels might not exist yet -- retry without labels
            result2 = subprocess.run(
                ["gh", "issue", "create",
                 "--repo", REPO,
                 "--title", title,
                 "--body", body],
                capture_output=True, text=True, timeout=30
            )
            if result2.returncode == 0:
                print("  -> Issue created (no labels): {}".format(result2.stdout.strip()))
                return result2.stdout.strip()
            print("  -> Issue creation failed: {}".format(result2.stderr), file=sys.stderr)
            return None
    except Exception as e:
        print("  -> Issue creation error: {}".format(e), file=sys.stderr)
        return None


# -- Weekly report --

def generate_report():
    """Generate a weekly mutual aid status report."""
    needs = load_json(NEEDS_FILE)
    skills = load_json(SKILLS_FILE)
    fund = load_json(FUND_FILE)

    open_needs = [n for n in needs["needs"] if n["status"] == "open"]
    fulfilled = [n for n in needs["needs"] if n["status"] == "fulfilled"]

    now = datetime.now(timezone.utc)
    report = {
        "generated": now.isoformat(),
        "period": "Week of {}".format(now.strftime("%Y-%m-%d")),
        "summary": {
            "total_needs": len(needs["needs"]),
            "open_needs": len(open_needs),
            "fulfilled_needs": len(fulfilled),
            "total_volunteers": len(skills["skills"]),
            "fund_balance": fund["balance"],
            "pending_fund_requests": len(fund["pending_requests"])
        },
        "open_needs_by_urgency": sorted(
            [{"id": n["id"], "title": n["title"], "urgency": n["urgency"]}
             for n in open_needs],
            key=lambda x: x["urgency"],
            reverse=True
        ),
        "categories": {}
    }

    # count by category
    for n in open_needs:
        cat = n["category"]
        report["categories"][cat] = report["categories"].get(cat, 0) + 1

    report_path = REPORT_DIR / "report_{}.json".format(now.strftime("%Y%m%d"))
    save_json(report_path, report)
    print("Report saved: {}".format(report_path))
    return report


# -- Main run --

def run():
    """Main agent loop: load data, match, post issues, report."""
    print("=" * 60)
    print("  SolarPunk Mutual Aid Agent")
    print("  No bureaucracy. Just people helping people.")
    print("=" * 60)

    # Bootstrap data
    _ensure_data()

    # Load
    open_needs = get_open_needs()
    skills = get_skills()
    fund = get_fund_status()

    print("")
    print("Open needs:       {}".format(len(open_needs)))
    print("Volunteers:       {}".format(len(skills)))
    print("Fund balance:     ${:.2f}".format(fund["balance"]))
    print("Pending requests: {}".format(len(fund["pending_requests"])))

    # Match
    print("")
    print("--- Running matcher ---")
    matches = match_needs_to_skills(open_needs, skills)
    scored = score_matches(matches)

    if not scored:
        print("No matches found this cycle.")
    else:
        print("Found {} matches:".format(len(scored)))
        print("")
        for m in scored:
            print("  [{:.0f}] {}  <->  {}".format(m["score"], m["need_title"], m["skill_title"]))

    # Post top matches as issues
    print("")
    print("--- Posting matches as GitHub Issues ---")
    post_to_github = os.environ.get("POST_ISSUES", "true").lower() == "true"
    if post_to_github:
        for m in scored:
            if m["score"] >= 40:
                post_match_as_issue(m)
    else:
        print("  (Skipped -- POST_ISSUES != true)")

    # Generate report
    print("")
    print("--- Generating report ---")
    report = generate_report()
    print("  Open needs by urgency:")
    for item in report["open_needs_by_urgency"]:
        print("    [{}/5] {}".format(item["urgency"], item["title"]))

    print("")
    print("=" * 60)
    print("  Cycle complete.")
    print("=" * 60)


if __name__ == "__main__":
    run()
