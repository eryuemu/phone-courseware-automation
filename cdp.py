"""Drive the phone's Unipus WebView through Chrome DevTools Protocol.

Reading and targeting go through the DOM (exact text, no OCR, no pixel guessing).
Taps are still real touches at the element's own centre, so the app cannot tell
the difference from a finger.

  from cdp import CDP
  c = CDP()
  c.dump()                       # page text + counts
  c.tap_text("教程学习")          # find by text, tap its centre
  c.fields()                     # every input/textarea with a selector
"""
import json
import subprocess

import websocket

import ua

PORT = 9223


def _adb(*args):
    return subprocess.run([ua.ADB, *args], capture_output=True, text=True).stdout


class CDP:
    def __init__(self, package="cn.unipus.cloud", port=PORT, url_like=None):
        self.port = port
        self.url_like = url_like
        pid = _adb("shell", "pidof", package).split()[0]
        _adb("forward", f"tcp:{port}", f"localabstract:webview_devtools_remote_{pid}")
        self.ws = self._open(f"ws://127.0.0.1:{port}/devtools/browser")
        self._id = 0
        self.session = None
        self.target = None
        self.attach()

    def _open(self, url):
        return websocket.create_connection(url, timeout=15, suppress_origin=True)

    def _cmd(self, method, params=None, timeout=15):
        self._id += 1
        mid = self._id
        msg = {"id": mid, "method": method, "params": params or {}}
        if self.session:
            msg["sessionId"] = self.session
        self.ws.send(json.dumps(msg))
        self.ws.settimeout(timeout)
        while True:
            try:
                got = json.loads(self.ws.recv())
            except Exception:
                # An action that navigates destroys the context before Chrome
                # can answer; the missing reply is expected, not a failure.
                return {}
            if got.get("id") == mid:
                if "error" in got:
                    raise RuntimeError(got["error"])
                return got.get("result", {})

    def attach(self):
        """Bind to a loaded page. The app keeps stale targets alive, so pass
        url_like when you know which page you want."""
        infos = self._cmd("Target.getTargets")["targetInfos"]
        pages = [t for t in infos if t["type"] == "page"
                 and t.get("url", "").startswith("http")]
        if self.url_like:
            pages = [t for t in pages if self.url_like in t["url"]] or pages
        if not pages:
            raise RuntimeError("no loaded http page target")
        t = pages[0]
        res = self._cmd("Target.attachToTarget",
                        {"targetId": t["targetId"], "flatten": True})
        self.session = res["sessionId"]
        self.target = t
        return t["url"]

    def ev(self, expression, timeout=15):
        res = self._cmd("Runtime.evaluate",
                        {"expression": expression, "returnByValue": True},
                        timeout)
        obj = res.get("result", {})
        if obj.get("type") == "string":
            return obj["value"]
        return obj.get("value")

    def js(self, body):
        """Run a JS function body that returns a JSON-serialisable value."""
        return json.loads(self.ev(f"JSON.stringify((()=>{{{body}}})())"))

    # ---------- reading ----------

    def url(self):
        return self.ev("location.href")

    def text(self, limit=4000):
        return self.js(
            f"return (document.body.innerText||'').replace(/\\s+/g,' ').slice(0,{limit})"
        )

    def fields(self):
        return self.js("""
        const out=[];
        document.querySelectorAll('input,textarea,[contenteditable=true]').forEach((el,i)=>{
          const r=el.getBoundingClientRect();
          out.push({i, tag:el.tagName.toLowerCase(), type:el.type||'',
                    placeholder:el.placeholder||'', value:el.value||'',
                    x:Math.round(r.x+r.width/2), y:Math.round(r.y+r.height/2),
                    w:Math.round(r.width), h:Math.round(r.height),
                    visible:r.width>0&&r.height>0});
        });
        return out;""")

    def find_text(self, needle):
        """Centre of the smallest visible element whose own text matches needle."""
        return self.js(f"""
        const needle={json.dumps(needle)};
        let best=null;
        document.querySelectorAll('*').forEach(el=>{{
          const own=[...el.childNodes].filter(n=>n.nodeType===3)
                    .map(n=>n.textContent).join('').trim();
          if(!own || !own.includes(needle)) return;
          const r=el.getBoundingClientRect();
          if(r.width<4||r.height<4) return;
          const area=r.width*r.height;
          if(!best||area<best.area)
            best={{area, x:r.x+r.width/2, y:r.y+r.height/2,
                   w:r.width, h:r.height, tag:el.tagName, cls:el.className, text:own}};
        }});
        if(!best) return null;
        return {{x:Math.round(best.x), y:Math.round(best.y),
                 w:Math.round(best.w), h:Math.round(best.h),
                 tag:best.tag, text:best.text.slice(0,80)}};""")

    def find_all(self, needle):
        """Every visible element whose own text contains needle, top-to-bottom."""
        return self.js(f"""
        const needle={json.dumps(needle)};
        const out=[];
        document.querySelectorAll('*').forEach(el=>{{
          const own=[...el.childNodes].filter(n=>n.nodeType===3)
                    .map(n=>n.textContent).join('').trim();
          if(!own || !own.includes(needle)) return;
          const r=el.getBoundingClientRect();
          if(r.width<4||r.height<4) return;
          out.push({{x:Math.round(r.x+r.width/2), y:Math.round(r.y+r.height/2),
                    w:Math.round(r.width), h:Math.round(r.height),
                    tag:el.tagName, text:own.slice(0,60)}});
        }});
        out.sort((a,b)=>a.y-b.y);
        return out;""")

    # ---------- acting ----------

    def click(self, x, y):
        """Dispatch a real tap inside the page; no screen-coordinate math.

        Mobile H5 binds touch, not mouse, so touchStart/touchEnd first and a
        mouse click afterwards for anything that only listens for click.
        """
        pt = [{"x": x, "y": y, "radiusX": 8, "radiusY": 8, "force": 1}]
        self._cmd("Input.dispatchTouchEvent",
                  {"type": "touchStart", "touchPoints": pt})
        self._cmd("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
        for t in ("mousePressed", "mouseReleased"):
            self._cmd("Input.dispatchMouseEvent",
                      {"type": t, "x": x, "y": y, "button": "left",
                       "clickCount": 1})

    def tap_text(self, needle):
        el = self.find_text(needle)
        if not el:
            raise RuntimeError(f"text not found in DOM: {needle!r}")
        self.click(el["x"], el["y"])
        return el

    def set_value(self, index, text):
        """Write into input #index the way a framework expects: native setter +
        input/change events, so Vue/React actually see the new value."""
        return self.js(f"""
        const els=document.querySelectorAll('input,textarea,[contenteditable=true]');
        const el=els[{index}];
        if(!el) return 'no such field';
        const proto = el.tagName==='TEXTAREA' ? HTMLTextAreaElement.prototype
                    : (el.isContentEditable ? HTMLElement.prototype : HTMLInputElement.prototype);
        const setter = Object.getOwnPropertyDescriptor(proto,'value')?.set;
        if (el.isContentEditable) {{ el.textContent={json.dumps(text)}; }}
        else if (setter) {{ setter.call(el, {json.dumps(text)}); }}
        else {{ el.value={json.dumps(text)}; }}
        el.dispatchEvent(new Event('input',{{bubbles:true}}));
        el.dispatchEvent(new Event('change',{{bubbles:true}}));
        return el.value;""")
