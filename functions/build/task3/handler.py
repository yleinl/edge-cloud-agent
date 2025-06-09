import json
import time
import sys

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


if __name__ == "__main__":
    req = sys.stdin.read()
    res = handle(req)
    print(res)