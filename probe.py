"""Dump the visible control tree of the current phone screen.

Usage: python probe.py [text-substring-to-filter]
"""
import sys
import time

import uiautomator2 as u2

d = u2.connect()
d.settings["operation_delay"] = (0, 0)

if len(sys.argv) > 1 and sys.argv[1] == "--tap":
    target = sys.argv[2]
    obj = d(text=target)
    print("found:", obj.exists, "bounds:", obj.info.get("bounds") if obj.exists else None)
    obj.click()
    time.sleep(2.5)

xml = d.dump_hierarchy()
open(".scratch/hierarchy.xml", "w").write(xml)

import re

nodes = re.findall(r"<node\b[^>]*>", xml)
print("total nodes:", len(nodes))
for n in nodes:
    text = re.search(r'\btext="([^"]*)"', n)
    desc = re.search(r'\bcontent-desc="([^"]*)"', n)
    cls = re.search(r'\bclass="([^"]*)"', n)
    bounds = re.search(r'\bbounds="([^"]*)"', n)
    clickable = re.search(r'\bclickable="([^"]*)"', n)
    label = (text.group(1) if text and text.group(1) else "") or (
        desc.group(1) if desc else ""
    )
    if not label:
        continue
    if len(sys.argv) > 1 and sys.argv[1] not in label:
        continue
    print(
        f"[{(cls.group(1).split('.')[-1] if cls else '?'):>10}] "
        f"click={clickable.group(1) if clickable else '?'} "
        f"{bounds.group(1) if bounds else '?':>22}  {label[:70]}"
    )
