"""
One-time script to seed San Antonio upcoming events.
Run via: python seed_sa_events.py
Or events can be added manually via the Events page "+ Add Event" button.
"""

from email_parser.database import init_db, seed_events

SA_EVENTS = [
    {"item_name": "PRIME TIME KICKOFF | Northern Hills", "event_date": "2026-03-15", "course": "Northern Hills", "chapter": "San Antonio"},
    {"item_name": "s9.1 The Quarry", "event_date": "2026-03-17", "course": "The Quarry", "chapter": "San Antonio"},
    {"item_name": "s9.2 Canyon Springs", "event_date": "2026-03-24", "course": "Canyon Springs", "chapter": "San Antonio"},
    {"item_name": "s9.3 Silverhorn", "event_date": "2026-03-31", "course": "Silverhorn", "chapter": "San Antonio"},
    {"item_name": "s9.4 Willow Springs", "event_date": "2026-04-07", "course": "Willow Springs", "chapter": "San Antonio"},
    {"item_name": "s18.4 LANDA PARK", "event_date": "2026-04-11", "course": "Landa Park", "chapter": "San Antonio"},
    {"item_name": "s9.5 Cedar Creek", "event_date": "2026-04-14", "course": "Cedar Creek", "chapter": "San Antonio"},
    {"item_name": "s9.6 The Quarry", "event_date": "2026-04-21", "course": "The Quarry", "chapter": "San Antonio"},
    {"item_name": "s9.7 Canyon Springs", "event_date": "2026-04-28", "course": "Canyon Springs", "chapter": "San Antonio"},
    {"item_name": "s18.5 WILLOW SPRINGS", "event_date": "2026-05-02", "course": "Willow Springs", "chapter": "San Antonio"},
    {"item_name": "s9.8 Silverhorn", "event_date": "2026-05-05", "course": "Silverhorn", "chapter": "San Antonio"},
    {"item_name": "s9.9 TPC San Antonio | Canyons", "event_date": "2026-05-12", "course": "TPC San Antonio - Canyons", "chapter": "San Antonio"},
    {"item_name": "HILL COUNTRY MATCHES | Comanche Trace", "event_date": "2026-05-16", "course": "Comanche Trace", "chapter": "San Antonio"},
    {"item_name": "s9.10 Brackenridge", "event_date": "2026-05-19", "course": "Brackenridge", "chapter": "San Antonio"},
    {"item_name": "s9.11 The Quarry", "event_date": "2026-05-26", "course": "The Quarry", "chapter": "San Antonio"},
    {"item_name": "s18.6 KISSING TREE", "event_date": "2026-05-30", "course": "Kissing Tree", "chapter": "San Antonio"},
    {"item_name": "s9.12 Canyon Springs", "event_date": "2026-06-02", "course": "Canyon Springs", "chapter": "San Antonio"},
]

if __name__ == "__main__":
    init_db()
    result = seed_events(SA_EVENTS)
    print(f"Seeded SA events: {result['inserted']} inserted, {result['skipped']} already existed")
