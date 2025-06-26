import requests


# --- Execute via local faas unit ---
def invoke_local_faas(func_name, payload):
    try:
        url = f"http://127.0.0.1:31112/function/{func_name}"
        resp = requests.post(url, data=payload, timeout=60)
        return {"resp": resp.text}
    except Exception as e:
        return {"error": f"local faas call failed: {str(e)}"}
    

# --- Execute via remote faas unit, scheduler ---
def invoke_remote_faas(func_name, payload, target):
    try:
        url = f"http://{target['address']}:31112/function/{func_name}"
        resp = requests.post(url, data=payload, timeout=60)
        return {"resp": resp.text}
    except Exception as e:
        return {"error": f"remote faas call to {target} failed: {str(e)}"}