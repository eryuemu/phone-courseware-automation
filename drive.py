"""Interactive driver: attach to whatever U校园 H5 page is live, click by text.

Usage from a REPL / other scripts:
    from drive import page
    p = page()            # -> (CDP handle, page text)
    p.click_text("书架")
"""
import json
import time

import websocket

from cdp import CDP, _adb, PORT


class Page(CDP):
    def __init__(self):
        self.port = PORT
        self.url_like = None
        pid = _adb("shell", "pidof", "cn.unipus.cloud").split()[0]
        _adb("forward", f"tcp:{PORT}", f"localabstract:webview_devtools_remote_{pid}")
        self.ws = self._open(f"ws://127.0.0.1:{PORT}/devtools/browser")
        self._id = 0
        self.session = None
        self.target = None

    def use_live(self):
        """Bind to the first target that actually has visible text."""
        for t in self._cmd("Target.getTargets")["targetInfos"]:
            if t["type"] != "page":
                continue
            try:
                r = self._cmd("Target.attachToTarget",
                              {"targetId": t["targetId"], "flatten": True})
                self.session = r.get("sessionId")
                if self.text(200).strip():
                    self.target = t
                    return t["url"]
            except Exception:
                pass
            self.session = None
        raise RuntimeError("no live page target")

    def click_text(self, needle, wait=5, nth=0):
        els = self.find_all(needle)
        if len(els) <= nth:
            raise RuntimeError(f"not found in DOM: {needle!r}")
        el = els[nth]
        self.click(el["x"], el["y"])
        time.sleep(wait)
        return el

    def click_row(self, needle, wait=6, nth=0):
        """Click the nearest *clickable* ancestor of the text, not the text node.

        The bookshelf list binds its handler on the <li>/card, so tapping the
        inner <span> does nothing.
        """
        hits = self.js(f"""
        const needle={json.dumps(needle)};
        const out=[];
        document.querySelectorAll('*').forEach(el=>{{
          const own=[...el.childNodes].filter(n=>n.nodeType===3)
                    .map(n=>n.textContent).join('').trim();
          if(!own.includes(needle)) return;
          let a=el, chosen=null;
          for(let i=0;i<6 && a;i++){{
            const tag=a.tagName, cls=(a.className||'')+'';
            if(/^(A|BUTTON|LI|TR)$/.test(tag) || /item|card|btn|button|list|click/i.test(cls))
              {{chosen=a;break;}}
            a=a.parentElement;
          }}
          const t=chosen||el;
          const r=t.getBoundingClientRect();
          if(r.width<8||r.height<8) return;
          out.push({{x:Math.round(r.x+r.width/2), y:Math.round(r.y+r.height/2),
                    w:Math.round(r.width), h:Math.round(r.height),
                    tag:t.tagName, cls:(t.className||'')+'', text:own.slice(0,50)}});
        }});
        out.sort((a,b)=>a.y-b.y);
        return out;""")
        if len(hits) <= nth:
            raise RuntimeError(f"no clickable row for {needle!r}")
        el = hits[nth]
        self.click(el["x"], el["y"])
        time.sleep(wait)
        return el


def page():
    p = Page()
    url = p.use_live()
    return p, url
