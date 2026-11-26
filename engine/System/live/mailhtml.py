r"""An email's own HTML, made safe to show on the Mail page as it was sent (formatting and pictures).

The page shows it in a frame of its own that may run nothing (no script, no form, nothing fetched but its own pictures);
this module is the second lock: whatever could run, send or reach out is taken out here before the page ever gets it.

    sanitize(html, message_id, cids, pictures)   (the complete document the frame shows, whether it has pictures from the
                                                  internet). cids: {content id: "att:N"}, the email's own pictures put back
                                                  in place; pictures: show pictures from the internet (the default; else left out)
"""
import html as H
import re
from html.parser import HTMLParser

DROP_ALL = {"script", "iframe", "frame", "frameset", "object", "embed", "applet", "noscript", "template", "title", "select",
            "textarea", "button", "noembed", "noframes", "portal", "dialog"}          # left out with everything inside them
DROP_TAG = {"html", "head", "form", "label", "fieldset", "legend", "option", "optgroup", "datalist", "output"}
DROP_VOID = {"meta", "link", "base", "input", "keygen", "param", "source", "track", "isindex"}
VOID = {"area", "br", "col", "hr", "img", "wbr", "basefont", "spacer"} | DROP_VOID
URL_ATTRS = {"href", "src", "background", "xlink:href", "poster", "lowsrc", "dynsrc", "cite", "longdesc", "data", "codebase",
             "usemap", "action", "formaction", "srcset", "ping", "manifest", "profile", "classid", "archive"}
PICTURE_ATTRS = {"src", "background"}
LINK_SCHEMES = ("http:", "https:", "mailto:", "tel:")
PICTURE_DATA = re.compile(r"data:image/(png|gif|jpe?g|webp|bmp);", re.I)
NAME = re.compile(r"^[a-z][a-z0-9:_.-]*$")
CSS_URL = re.compile(r"""url\(\s*(['"]?)(.*?)\1\s*\)""", re.I | re.S)
CSS_BAD = re.compile(r"expression\s*\(|javascript\s*:|vbscript\s*:|behavior\s*:|-moz-binding|@import[^;]*;?", re.I)
CONTROL = re.compile(r"[\x00-\x20\x7f]+")
FILE_URL = "/api/mail/file?ref={ref}&view=1"

WRAP = """<!doctype html><html><head><meta charset="utf-8"><meta name="referrer" content="no-referrer">
<meta name="color-scheme" content="light"><style>
html,body{margin:0;padding:0;background:#fff;color:#1f2328;color-scheme:light}
body{padding:14px 16px;font:14px/1.5 -apple-system,"Segoe UI",system-ui,sans-serif;overflow-wrap:anywhere;overflow-y:hidden}
img{max-width:100%;height:auto}
table{max-width:100%}
pre{white-space:pre-wrap}
a{color:#0b57d0}
</style></head><body>"""


def _clean_url(v):
    return CONTROL.sub("", H.unescape(v or "")).strip()


class _Clean(HTMLParser):
    def __init__(self, message_id, cids, pictures):
        super().__init__(convert_charrefs=False)
        self.mid, self.cids, self.pictures = message_id, cids or {}, pictures
        self.out, self.skip, self.remote = [], [], False
        self.in_style = 0

    # --- what a picture's address becomes ----------------------------------------------------------------------------
    def _picture(self, url):
        """The address a picture may load from, or None (left out)."""
        u = _clean_url(url)
        low = u.lower()
        if low.startswith("cid:"):
            ref = self.cids.get(u[4:].strip("<>")) or self.cids.get(u[4:])
            return FILE_URL.format(ref=ref) if ref else None
        if PICTURE_DATA.match(low):
            return u
        if low.startswith(("http:", "https:", "//")):
            self.remote = True
            return (("https:" + u) if low.startswith("//") else u) if self.pictures else None
        return None

    def _css(self, text):
        text = CSS_BAD.sub("", text)

        def url(m):
            got = self._picture(m.group(2))
            return f"url('{got}')" if got else "none"
        return CSS_URL.sub(url, text)

    # --- tags -----------------------------------------------------------------------------------------------------------
    def _attrs(self, tag, attrs):
        out = []
        for k, v in attrs:
            k = (k or "").lower()
            if not NAME.match(k) or k.startswith("on") or k in ("srcdoc", "formaction", "action", "srcset", "ping", "is",
                                                               "http-equiv", "autofocus", "contenteditable"):
                continue
            v = "" if v is None else v
            if k in PICTURE_ATTRS and tag != "a":
                v = self._picture(v)
                if v is None:
                    continue
            elif k in ("href", "xlink:href"):
                u = _clean_url(v)
                if u.startswith("#") and tag == "a":
                    v = u
                elif u.lower().startswith(LINK_SCHEMES):
                    v = u
                else:
                    continue
            elif k in URL_ATTRS:
                continue
            elif k == "style":
                v = self._css(H.unescape(v))
            out.append((k, v))
        if tag in ("a", "area") and any(k == "href" and not v.startswith("#") for k, v in out):
            out = [(k, v) for k, v in out if k not in ("target", "rel")] + [("target", "_blank"), ("rel", "noopener noreferrer")]
        return "".join(f' {k}="{H.escape(v, quote=True)}"' for k, v in out)

    def handle_starttag(self, tag, attrs, closed=False):
        tag = tag.lower()
        if self.skip:
            if tag == self.skip[-1] and tag not in VOID and not closed:
                self.skip.append(tag)
            return
        if tag in DROP_ALL:
            if tag not in VOID and not closed:
                self.skip.append(tag)
            return
        if tag in DROP_TAG or tag in DROP_VOID:
            return
        if tag == "body":
            self.out.append(f'<div class="mail-root"{self._attrs("div", attrs)}>')
            return
        if tag == "style":
            self.in_style += 1
        self.out.append(f"<{tag}{self._attrs(tag, attrs)}{' /' if closed else ''}>")

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs, closed=True)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if self.skip:
            if tag == self.skip[-1]:
                self.skip.pop()
            return
        if tag in DROP_ALL or tag in DROP_TAG or tag in VOID:
            return
        if tag == "body":
            self.out.append("</div>")
            return
        if tag == "style":
            self.in_style = max(0, self.in_style - 1)
        self.out.append(f"</{tag}>")

    # --- text -----------------------------------------------------------------------------------------------------------
    def handle_data(self, data):
        if self.skip:
            return
        if self.in_style:
            self.out.append(self._css(data).replace("<", ""))
        else:
            self.out.append(data.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))

    def handle_entityref(self, name):
        if not self.skip:
            self.out.append(f"&{name};" if name.isalnum() else "&amp;" + name)

    def handle_charref(self, name):
        if not self.skip:
            self.out.append(f"&#{name};" if re.fullmatch(r"x?[0-9a-fA-F]+", name) else "")

    def handle_comment(self, data):
        pass

    def handle_decl(self, decl):
        pass

    def handle_pi(self, data):
        pass

    def unknown_decl(self, data):
        pass


def sanitize(markup, message_id, cids=None, pictures=True):
    """(the whole document to show, whether the email has pictures from the internet)."""
    p = _Clean(message_id, cids, pictures)
    p.feed(markup or "")
    p.close()
    return WRAP + "".join(p.out) + "</body></html>", p.remote
