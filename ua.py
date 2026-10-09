"""Unipus quiz clicker: the question pages are rendered inside a WebView that
exposes no text to the accessibility tree, so everything here goes through
screenshot + local OCR + coordinate taps.

  python ua.py look                 print what the phone currently shows
  python ua.py look 答题             same, filtered by text
  python ua.py tap "A. More than"   find that text on screen and tap it
  python ua.py tapxy 720 1500       tap raw coordinates
  python ua.py swipe up             scroll the page
  python ua.py back                 press the phone back button
"""

import argparse
import os
import re
import subprocess
import sys
import time

import cv2
import numpy as np
from rapidocr_onnxruntime import RapidOCR

ADB = os.environ.get(
    "ADB", "/home/eryuemu/workspace/tool/platform-tools/adb"
)

_engine = None


def engine():
    global _engine
    if _engine is None:
        _engine = RapidOCR()
    return _engine


def sh(*args):
    return subprocess.run([ADB, *args], capture_output=True, text=True).stdout


def screenshot():
    raw = subprocess.run(
        [ADB, "exec-out", "screencap", "-p"], capture_output=True
    ).stdout
    img = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        sys.exit("screencap returned nothing - is the phone still connected?")
    return img


def blocks(img=None):
    """Return [(text, cx, cy, score, box)] for every piece of OCR'd text."""
    if img is None:
        img = screenshot()
    result, _ = engine()(img)
    out = []
    for box, text, score in result or []:
        xs = [p[0] for p in box]
        ys = [p[1] for p in box]
        out.append(
            {
                "text": text,
                "cx": int(sum(xs) / 4),
                "cy": int(sum(ys) / 4),
                "top": int(min(ys)),
                "bottom": int(max(ys)),
                "score": float(score),
                "box": box,
            }
        )
    return out


def norm(s):
    return re.sub(r"\s+", "", s).lower()


def find(bs, needle, nth=0, below=None, above=None):
    hits = [b for b in bs if norm(needle) in norm(b["text"])]
    if below is not None:
        hits = [b for b in hits if b["cy"] > below]
    if above is not None:
        hits = [b for b in hits if b["cy"] < above]
    hits.sort(key=lambda b: b["cy"])
    if not hits:
        return None
    return hits[nth] if nth < len(hits) else None


def selected_rows(img, x=145):
    """The chosen option's letter circle is filled solid blue; scan that column."""
    runs, start = [], None
    for y in range(img.shape[0]):
        b, g, r = (int(v) for v in img[y, x])
        blue = b > 170 and r < 130 and 110 < g < 220
        if blue and start is None:
            start = y
        elif not blue and start is not None:
            if y - start > 60:
                runs.append((start + y) // 2)
            start = None
    return runs


def show(bs, filt=None):
    for i, b in enumerate(bs):
        if filt and norm(filt) not in norm(b["text"]):
            continue
        print(
            f"{i:>3}  ({b['cx']:>4},{b['cy']:>4})  "
            f"y{b['top']}-{b['bottom']:<5} c={b['score']:.2f}  {b['text']}"
        )


def tap(x, y):
    sh("shell", "input", "tap", str(x), str(y))


def swipe(direction, distance=1200):
    cx = 720
    if direction == "up":  # content moves up == scroll down the page
        tap_range(cx, 2200, cx, 2200 - distance)
    else:
        tap_range(cx, 1000, cx, 1000 + distance)


def tap_range(x1, y1, x2, y2):
    sh("shell", "input", "swipe", str(x1), str(y1), str(x2), str(y2), "350")


def type_text(s):
    """Wrap in single quotes for the device shell; ' becomes '\\''."""
    esc = s.replace("'", "'\\''")
    sh("shell", f"input text '{esc}'")


def clear_field(n):
    subprocess.run(
        [ADB, "shell", "input keyevent " + " ".join(["KEYCODE_DEL"] * n)],
        capture_output=True,
    )


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("look")
    s.add_argument("filter", nargs="?")
    s.add_argument("--shot", help="OCR this png instead of the live screen")

    s = sub.add_parser("shot")
    s.add_argument("name", nargs="?", default="live")

    s = sub.add_parser("state")
    s.add_argument("filter", nargs="?")

    s = sub.add_parser("tap")
    s.add_argument("text")
    s.add_argument("--nth", type=int, default=0)
    s.add_argument("--below", type=int)
    s.add_argument("--wait", type=float, default=2.0)

    s = sub.add_parser("tapxy")
    s.add_argument("x", type=int)
    s.add_argument("y", type=int)

    s = sub.add_parser("swipe")
    s.add_argument("direction", choices=["up", "down"])

    s = sub.add_parser("type")
    s.add_argument("text")

    s = sub.add_parser("clear")
    s.add_argument("n", type=int)

    sub.add_parser("back")

    a = p.parse_args()

    if a.cmd == "look":
        img = cv2.imread(a.shot) if a.shot else None
        show(blocks(img), a.filter)
    elif a.cmd == "shot":
        img = screenshot()
        cv2.imwrite(f".scratch/{a.name}.png", img)
        bs = blocks(img)
        print(f"saved .scratch/{a.name}.png   ({img.shape[1]}x{img.shape[0]})")
        show(bs)
    elif a.cmd == "state":
        img = screenshot()
        bs = blocks(img)
        rows = selected_rows(img)
        print(f"selected circles at y = {rows}")
        for b in bs:
            if a.filter and norm(a.filter) not in norm(b["text"]):
                continue
            if b["cy"] < 800:
                continue
            on = any(abs(b["cy"] - y) < 130 for y in rows)
            print(f"{'[*]' if on else '[ ]'}  ({b['cx']:>4},{b['cy']:>4})  {b['text']}")
    elif a.cmd == "tap":
        b = find(blocks(), a.text, a.nth, a.below)
        if not b:
            sys.exit(f"not found on screen: {a.text!r}  (run `ua.py look` to see it)")
        print(f"tapping ({b['cx']},{b['cy']}) {b['text']!r}")
        tap(b["cx"], b["cy"])
        time.sleep(a.wait)
    elif a.cmd == "tapxy":
        tap(a.x, a.y)
        time.sleep(1)
    elif a.cmd == "type":
        type_text(a.text)
        time.sleep(1)
    elif a.cmd == "clear":
        clear_field(a.n)
        time.sleep(1)
    elif a.cmd == "swipe":
        swipe(a.direction)
        time.sleep(1.5)
    elif a.cmd == "back":
        sh("shell", "input", "keyevent", "4")
        time.sleep(1.5)


if __name__ == "__main__":
    main()
