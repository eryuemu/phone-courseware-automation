"""Attach to the phone's Unipus WebView over Chrome DevTools Protocol.

Root + the app's enabled devtools socket mean we can read the real DOM instead
of OCR'ing a screenshot. This file only ever reads; nothing here writes to a page.

  python cdp_probe.py            attach to every live target and describe it
"""
import json
import subprocess
import sys

import websocket

import ua


def targets(port):
    out = subprocess.run(
        ["curl", "-s", "--max-time", "5", f"http://127.0.0.1:{port}/json/list"],
        capture_output=True, text=True,
    ).stdout
    try:
        return json.loads(out)
    except Exception:
        return []


def evaluate(ws_url, expression, timeout=8):
    ws = websocket.create_connection(ws_url, timeout=timeout, suppress_origin=True)
    try:
        ws.send(json.dumps({
            "id": 1,
            "method": "Runtime.evaluate",
            "params": {"expression": expression, "returnByValue": True},
        }))
        deadline = timeout
        while True:
            msg = json.loads(ws.recv())
            if msg.get("id") == 1:
                return msg.get("result", {}).get("result", {}).get("value")
            if "error" in msg:
                return {"_error": msg["error"]}
            if timeout <= 0:
                break
            timeout -= 1
    finally:
        ws.close()


PROBE = """JSON.stringify({
  href: location.href,
  title: document.title,
  chars: (document.body && document.body.innerText || '').length,
  inputs: document.querySelectorAll('input,textarea,[contenteditable]').length,
  clickable: document.querySelectorAll('button,a,[onclick],[class*=btn]').length,
  preview: (document.body && document.body.innerText || '').replace(/\\s+/g,' ').slice(0,220)
})"""


def main():
    port = sys.argv[1] if len(sys.argv) > 1 else "9223"
    pid = subprocess.run(
        [ua.ADB, "shell", "pidof", "cn.unipus.cloud"],
        capture_output=True, text=True,
    ).stdout.split()[0]
    subprocess.run([ua.ADB, "forward", f"tcp:{port}",
                    f"localabstract:webview_devtools_remote_{pid}"])
    print(f"unipus pid {pid} -> tcp:{port}\n")

    for t in targets(port):
        ws = t.get("webSocketDebuggerUrl")
        print(f"--- target {t['id'][:8]} ({t['type']}) ---")
        if not ws:
            print("    no websocket url")
            continue
        try:
            data = json.loads(evaluate(ws, PROBE))
            for k, v in data.items():
                print(f"    {k:<10} {v}")
        except Exception as e:
            print(f"    attach failed: {type(e).__name__}: {str(e)[:140]}")
        print()


if __name__ == "__main__":
    main()
