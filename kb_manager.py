import os
import json
import datetime
from pathlib import Path

KB_FILE = os.environ.get("KB_FILE", "knowledge_base.json")
LOG_FILE = os.environ.get("LOG_FILE", "query_logs.json")

def _make_sure_file_exists(filename, default_content):
    path = Path(filename)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(filename, 'w') as f:
            json.dump(default_content, f)

def _load_knowledge_base():
    _make_sure_file_exists(KB_FILE, {"last_updated": None, "topics": {}})
    
    try:
        with open(KB_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading knowledge base: {e}")
        return {"last_updated": None, "topics": {}}

def save_knowledge_base(kb_data):
    with open(KB_FILE, 'w') as f:
        json.dump(kb_data, f, indent=2)

def get_knowledge(query, category=None):
    kb = _load_knowledge_base()
    query = query.lower()
    results = []
    
    for title, content in kb.get("topics", {}).items():
        if category and category not in content.get("categories", []):
            continue
        
        title_match = query in title.lower()
        content_match = any(query in p.lower() for p in content.get("paragraphs", []))
        
        if title_match or content_match:
            results.append({
                "title": title,
                "content": content["paragraphs"][0] if content.get("paragraphs") else "",
                "url": content.get("url", "")
            })
    
    return results[:5]  # Limit to 5 results

def _load_query_logs():
    _make_sure_file_exists(LOG_FILE, [])
    
    try:
        with open(LOG_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading query logs: {e}")
        return []

def save_query_log(user_id, username, command, query):
    logs = _load_query_logs()
    
    log_entry = {
        "timestamp": datetime.datetime.now().isoformat(),
        "user_id": user_id,
        "username": username,
        "command": command,
        "query": query
    }
    
    logs.append(log_entry)
    
    with open(LOG_FILE, 'w') as f:
        json.dump(logs, f, indent=2)

def get_stats():
    kb = _load_knowledge_base()
    logs = _load_query_logs()
    
    if not logs:
        return "No usage data available yet."
    
    total_queries = len(logs)
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    queries_today = sum(1 for log in logs if log["timestamp"].startswith(today))
    
    # Count command usage
    cmd_counts = {}
    for log in logs:
        cmd = log["command"]
        cmd_counts[cmd] = cmd_counts.get(cmd, 0) + 1
    
    # Get popular queries
    query_counts = {}
    for log in logs:
        query = log["query"].lower()
        query_counts[query] = query_counts.get(query, 0) + 1
    
    top_queries = sorted(query_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    
    # Format the stats message
    stats = f"Bot Stats:\n\n"
    stats += f"Knowledge base topics: {len(kb.get('topics', {}))}\n"
    stats += f"Last updated: {kb.get('last_updated', 'Never')}\n\n"
    stats += f"Total queries: {total_queries}\n"
    stats += f"Queries today: {queries_today}\n\n"
    
    stats += "Command usage:\n"
    for cmd, count in sorted(cmd_counts.items(), key=lambda x: x[1], reverse=True):
        stats += f"/{cmd}: {count}\n"
    
    stats += "\nPopular queries:\n"
    for query, count in top_queries:
        stats += f"'{query}': {count} times\n"
    
    return stats