import json
import time


def handle(req):
    start_time = time.time()
    keywords = req.split(",")
    summary = {
        "keyword_count": len(keywords),
        "keywords": keywords,
        "note": "Keywords extracted successfully"
    }
    # return json.dumps(summary)
    return json.dumps(summary)