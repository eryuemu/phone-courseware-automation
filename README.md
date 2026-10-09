# phone-courseware-automation

[中文说明](./README.zh-CN.md)

Drive Android courseware apps (超星学习通 / U校园 Unipus) from a Linux laptop over
ADB: read what is on the phone screen, decide the answer, and tap or type it back.

## Why this project exists

The tedious grind of courseware apps like U校园 (Unipus) prompted me to search for an open-source solution since last year. However, I couldn't find any stable, mature, and reliable project that worked out of the box. I tried using AI Agents to modify and adapt existing open-source scripts, but the maintenance was painful. Furthermore, most existing tools heavily rely on LLMs to answer questions on the fly—without verified answer keys, LLMs make plenty of mistakes.

This sparked a thought: why not let automation directly control the screen to complete the exercises?
Having previously experimented with AI Agents controlling Android phones over ADB—and having specifically bought a Xiaomi-ecosystem spare phone, unlocked its bootloader, rooted it, and flashed a stock/custom AOSP ROM—I wondered: why not let a program/AI directly drive the phone, reading the display and tapping answers just like a human? That is how this project came to be.

Built the hard way, by measuring what actually costs time instead of guessing.
Everything below was observed on two real devices on 2026-10-09.

## What it does

| script | purpose |
|---|---|
| `ua.py` | the toolkit: screenshot, OCR, tap, swipe, type, and "which option is currently selected" |
| `probe.py` | dump the accessibility/control tree of the current screen |
| `validate_ocr.py` | prove OCR reads a known screenshot correctly before trusting it |
| `dump_doc.py` | bulk-capture a long scrolling document into one local text file |
| `fill_blanks.py` | fill numbered blanks by locating each blank's underline pixel-wise |
| `cdp.py`, `drive.py`, `cdp_probe.py` | the alternative route: read the WebView DOM over Chrome DevTools Protocol (needs root) |

## Install

```bash
python3 -m venv .venv                      # isolated; do not touch system python
./.venv/bin/python -m pip install -r requirements.txt
```

`rapidocr-onnxruntime` ships its own ONNX models, so recognition never phoning
home. `opencv-python-headless` is deliberate — nothing here opens a window.

Point the tools at your ADB binary if it is not on `PATH`:

```bash
ADB=~/platform-tools/adb ./.venv/bin/python ua.py look
```

## Usage

```bash
./.venv/bin/python ua.py look              # every text block + device coordinates
./.venv/bin/python ua.py shot page         # save a screenshot AND print blocks, one pass
./.venv/bin/python ua.py state             # which option is filled blue right now
./.venv/bin/python ua.py tap "答题"         # find text, tap it
./.venv/bin/python ua.py tapxy 720 1500    # raw tap
./.venv/bin/python ua.py swipe up
./.venv/bin/python ua.py type "some text"  # quoted safely for the device shell
./.venv/bin/python ua.py back
```

## Measured costs (this is the useful part)

| operation | latency |
|---|---|
| `adb exec-out screencap -p` (1440x3136 PNG) | 918 ms |
| `uiautomator2 d.screenshot()` | **230 ms** |
| RapidOCR on a full 1440x3136 frame | **1921 ms** |
| RapidOCR on a cropped band / half-resolution | 1357 ms / 1390 ms |
| `adb shell input tap` | 32 ms |
| CDP `Runtime.evaluate` | ~50 ms |

**The bottleneck is OCR, not the screenshot.** Cropping the frame buys only ~30%,
so the win is not "OCR faster" — it is "OCR fewer times": capture once, plan every
action on that page from one block list, execute them all, then take a single
verification shot. A 10-blank page goes from ~10 observations (~28 s) to 2.

## Findings that cost real time to discover

**The WebView's contents are not in the accessibility tree — but it varies by
activity, not by app.** U校园's textbook 目录页 (`EmbeddedWebViewActivity`) exposes
all its text to `uiautomator`; the exercise pages (`CustomWebViewActivity`) expose
`android.webkit.WebView` as a single empty leaf. A conclusion drawn from one page
does not generalise; check per activity.

**Without root there is no DOM route.** Neither app exposes a
`webview_devtools_remote` socket on a stock device, so screenshot + OCR is the
only option. On a LineageOS device where `adb root` works, the same app *does*
expose the socket and its H5 is served from `http://127.0.0.1:8290/...`, which
makes `cdp.py` viable. Two traps there: the endpoint only answers while the app is
foregrounded with a loaded page, and empty `never_attached` targets refuse a
page-level WebSocket, so attach via the browser endpoint with
`Target.attachToTarget(flatten: true)` and pick the target that actually has text.

**OCR is for coordinates, never for judgement.** It reads `%o` as `%0`, drops
quotes and backslashes, and misses pure-digit options entirely. Anything that
decides an answer must be read off the screenshot by a human (or a vision model).
In particular: **never infer "the option OCR failed to read must be the right
one"** — that exact shortcut cost one point.

**Fill-in blanks are not where the label is.** The clickable input is the underline
to the lower-right of the `(N)` label, and that underline sits at the end of a
wrapped line, so aiming off the text block's centre hits an ordinary word and
types nothing silently. `fill_blanks.py` finds the underline as a long grey pixel
run instead.

**`adb shell input text` quoting.** Wrap the whole string in single quotes for the
device shell (spaces then work — `%s` is the *only* escape the tool understands,
`%2C`/`%20` get typed literally). Unquoted `(` or `)` dies with
`syntax error: unexpected '('`. An apostrophe needs `'\''`.

**Never send ESCAPE to dismiss the keyboard.** Some courseware maps ESC to "abandon
this attempt" and warns 退出后本次作答记录不保存 — every answer typed is lost.

**Wide tables overflow the viewport.** A three-column table on a narrow phone
clips its own inputs off-screen. Reset to the left edge, fill the visible half, do
one deterministic horizontal swipe, fill the rest. Do not guess horizontal offsets
live.

**Option order is reshuffled between attempts**, so locate by text content and
never reuse coordinates from a previous run.

## Platform behaviour

学习通 pre-fills your previous attempt when you 重做 (so only the wrong item needs
changing) and **the final grade is the highest attempt** — redoing carries no
downside. Submitting is blocked until every blank is filled
(请全部作答完成后再提交).

## Layout

```
ua.py        screenshot + OCR + tap/swipe/type toolkit
probe.py     control-tree dumper (diagnose whether a page is readable)
validate_ocr.py   known-answer check for OCR
dump_doc.py  scroll-capture a long document to text
fill_blanks.py    underline-aware blank filler
cdp.py / drive.py / cdp_probe.py   Chrome DevTools Protocol route (root only)
answers.example.json  shape of the answer file
```

Answer text is not included: it comes from third-party course material. Supply
your own `answers.json` (gitignored).

## License

MIT
