"""Fill numbered blanks in a WebView exercise by locating each blank's underline.

Why not tap the text: the "(N)" label and its underline sit at the END of a
wrapped line, so aiming off the text block's centre lands on an ordinary word
and silently types nothing. Instead we scan the rows under each label for a long
horizontal grey run (the input's underline) and tap its middle.

Answers are supplied by you, not baked in:

  python fill_blanks.py answers.json          # all blanks in the file
  python fill_blanks.py answers.json 4 7 8    # only these numbers

answers.json is {"<blank number>": "<text>", ...} — see answers.example.json.
"""
import json
import re
import sys
import time

import numpy as np

import ua

LABEL = re.compile(r"\((\d{1,2})\)")


def underline_for(img, block):
    """Centre of the underline that follows this text block, or None."""
    y0 = max(0, block["top"] - 10)
    y1 = min(img.shape[0], block["bottom"] + 90)
    x0 = max(0, int(min(p[0] for p in block["box"])) - 20)
    best = None
    for y in range(y0, y1):
        row = img[y, x0:]
        grey = (
            (np.abs(row[:, 0].astype(int) - row[:, 1].astype(int)) < 30)
            & (np.abs(row[:, 1].astype(int) - row[:, 2].astype(int)) < 30)
            & (row[:, 0] > 70)
            & (row[:, 0] < 180)
        )
        run = end = None
        for x, ok in enumerate(grey):
            if ok:
                run = x if run is None else run
                end = x
            else:
                if run is not None and end - run > 140:
                    best = (x0 + (run + end) // 2, y)
                run = None
        if run is not None and end - run > 140:
            best = (x0 + (run + end) // 2, y)
    return best


def label_block(bs, n):
    for b in sorted(bs, key=lambda b: b["cy"]):
        m = LABEL.search(b["text"])
        if m and int(m.group(1)) == n:
            return b
    return None


def to_top(times=12):
    for _ in range(times):
        ua.sh("shell", "input", "swipe", "720", "500", "720", "1300", "200")
        time.sleep(0.6)
    time.sleep(1)


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    answers = {int(k): v for k, v in json.load(open(sys.argv[1])).items()}
    targets = [int(a) for a in sys.argv[2:]] or sorted(answers)

    for n in targets:
        text = answers[n]
        found = False
        to_top()
        for _ in range(14):
            img = ua.screenshot()
            blk = label_block(ua.blocks(img), n)
            spot = underline_for(img, blk) if blk else None
            if spot:
                x, y = spot
                print(f"({n}) underline ({x},{y}) <- {text!r}", flush=True)
                ua.tap(x, y - 25)
                time.sleep(1.2)
                ua.type_text(text)
                time.sleep(1)
                # Do NOT send ESCAPE to hide the keyboard: some courseware maps
                # ESC to "abandon this attempt", which discards everything typed.
                found = True
                break
            ua.sh("shell", "input", "swipe", "720", "1300", "720", "500", "300")
            time.sleep(1.8)
        if not found:
            print(f"({n}) FAILED - blank never located", flush=True)


if __name__ == "__main__":
    main()
