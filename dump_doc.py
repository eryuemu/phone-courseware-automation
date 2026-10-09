"""Dump the whole open WeChat document into a local text file.

Scrolls page by page, OCRs each stop, and stops when the screen stops changing
(bottom reached). After this, answers are a local grep away instead of a
phone-scrolling session.

  python dump_doc.py out.txt
"""
import difflib
import subprocess
import sys

import ua

out = sys.argv[1] if len(sys.argv) > 1 else "doc_dump.txt"
STEP = 1500
MAX = 60


def scroll_down():
    subprocess.run(
        [ua.ADB, "shell", "input", "swipe", "720", "2700", "720",
         str(2700 - STEP), "250"]
    )


def scroll_to_top():
    for _ in range(40):
        before = "\n".join(b["text"] for b in ua.blocks())
        subprocess.run(
            [ua.ADB, "shell", "input", "swipe", "720", "600", "720", "2700", "200"]
        )
        import time
        time.sleep(0.7)
        after = "\n".join(b["text"] for b in ua.blocks())
        if difflib.SequenceMatcher(None, before, after).ratio() > 0.95:
            return


def page_text():
    return "\n".join(b["text"] for b in ua.blocks())


scroll_to_top()
previous = ""
chunks = []
import time

for i in range(MAX):
    text = page_text()
    ratio = difflib.SequenceMatcher(None, previous, text).ratio()
    if ratio > 0.97:
        print(f"bottom reached at stop {i}", flush=True)
        break
    chunks.append(text)
    print(f"stop {i:>2} captured ({len(text)} chars)", flush=True)
    previous = text
    scroll_down()
    time.sleep(1.6)

with open(out, "w") as f:
    for n, c in enumerate(chunks):
        f.write(f"\n========== STOP {n} ==========\n{c}\n")
print(f"\nwrote {out}  ({sum(len(c) for c in chunks)} chars, {len(chunks)} stops)")
