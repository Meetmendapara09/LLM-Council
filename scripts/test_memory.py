"""Quick test script to verify mem0 behavior locally.

Usage: run backend (uvicorn) and then:
    python scripts/test_memory.py

It will create a conversation, send a message that includes a "preference", wait for the council to respond,
then send a follow-up asking to recall the preference and print memory contents.
"""
import time
import requests

API_BASE = "http://localhost:8001"


def wait_for_conversation_ready(cid, timeout=60):
    start = time.time()
    while time.time() - start < timeout:
        r = requests.get(f"{API_BASE}/api/conversations/{cid}")
        r.raise_for_status()
        conv = r.json()
        if len(conv.get("messages", [])) >= 2:
            # Expect at least one user and one assistant message
            last = conv["messages"][-1]
            if last.get("role") == "assistant" and last.get("stage3"):
                return conv
        time.sleep(1)
    raise RuntimeError("Timeout waiting for conversation to finish")


if __name__ == "__main__":
    # 1) Create
    r = requests.post(f"{API_BASE}/api/conversations", json={})
    r.raise_for_status()
    conv = r.json()
    cid = conv["id"]
    print("Created conversation:", cid)

    # 2) Send message that contains a preference
    msg1 = "My name is Alice. I prefer the color blue and I like tea over coffee."
    r = requests.post(f"{API_BASE}/api/conversations/{cid}/message", json={"content": msg1})
    r.raise_for_status()
    print("Sent first message, waiting for council to respond...")

    conv = wait_for_conversation_ready(cid)
    print("First assistant reply stored.")

    # 3) Send a follow-up asking for the preference
    msg2 = "What color do I prefer?"
    r = requests.post(f"{API_BASE}/api/conversations/{cid}/message", json={"content": msg2})
    r.raise_for_status()
    print("Sent follow-up, waiting for council to respond...")

    conv = wait_for_conversation_ready(cid)
    print("Follow-up reply stored.")
    last = conv["messages"][-1]
    assistant_text = last.get("stage3", {}).get("response", "")
    print("Assistant response to follow-up:\n", assistant_text)

    # 4) Inspect memory
    r = requests.get(f"{API_BASE}/api/conversations/{cid}/memory")
    r.raise_for_status()
    mem = r.json()
    print("Memory summary:\n", mem.get("summary"))
    print("Short memory entries:")
    for e in mem.get("short", []):
        print(e)
