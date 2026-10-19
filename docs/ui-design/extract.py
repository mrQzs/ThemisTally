"""From the 13 Claude Design exports, build a compact design package: per-variant page markup (bundle stripped),
the screen component sources (*.dc.html), the dc runtime, the logo; fonts and CDN libraries are listed, not copied."""
import base64, gzip, hashlib, json, re, sys
from pathlib import Path

def blocks(text):
    def one(kind):
        m = re.search(r'<script type="__bundler/%s">(.*?)</script>' % kind, text, re.S)
        return json.loads(m.group(1)) if m else None
    return one("manifest") or {}, one("ext_resources") or [], one("template")

def resources(text):
    manifest, ext, template = blocks(text)
    names = {e["uuid"]: e["id"] for e in ext if isinstance(e, dict) and "uuid" in e}
    out = []
    for uid, res in manifest.items():
        raw = base64.b64decode(res["data"])
        if res.get("compressed"):
            raw = gzip.decompress(raw)
        out.append((names.get(uid, uid), res["mime"], raw))
    return out, template

src, dst = Path(sys.argv[1]), Path(sys.argv[2])
(dst / "pages").mkdir(parents=True, exist_ok=True)
(dst / "screens").mkdir(exist_ok=True)
(dst / "assets").mkdir(exist_ok=True)
index, fonts, cdn = [], {}, set()
for export in sorted(src.glob("*.html"), key=lambda p: int(p.stem)):
    outer, outer_template = resources(export.read_text(encoding="utf-8", errors="replace"))
    order = re.findall(r'title="([^"]+)"', outer_template or "")
    for name, mime, raw in outer:
        if mime != "text/html":
            continue
        page_text = raw.decode("utf-8", "replace")
        inner, template = resources(page_text)
        title = re.search(r"<title>(.*?)</title>", template or page_text, re.S)
        title = (title.group(1).strip() if title else name)
        uses = []
        for iname, imime, iraw in inner:
            if iname.startswith("http"):
                cdn.add(iname)
            elif iname.endswith(".dc.html"):
                (dst / "screens" / Path(iname).name).write_bytes(iraw)
                uses.append("screens/" + Path(iname).name)
            elif iname.endswith("support.js") or iraw[:40].startswith(b"// GENERATED from dc-runtime"):
                (dst / "assets" / "support.js").write_bytes(iraw)
            elif imime.startswith("font/") or iraw[:4] == b"wOF2":
                fonts[hashlib.sha256(iraw).hexdigest()[:12]] = len(iraw)
            elif imime == "image/png" or iraw[:4] == b"\x89PNG":
                (dst / "assets" / "Logo.png").write_bytes(iraw)
                uses.append("assets/Logo.png")
            else:
                (dst / "assets" / Path(iname).name).write_bytes(iraw)
                uses.append("assets/" + Path(iname).name)
        slug = "%02d-%s" % (int(export.stem), re.sub(r'[\/:*?"<>|\s·]+', "-", title).strip("-"))
        body = template if template is not None else page_text
        (dst / "pages" / (slug + ".html")).write_text(body, encoding="utf-8", newline="\n")
        index.append({"export": export.name, "page": "pages/%s.html" % slug, "title": title, "uses": sorted(set(uses))})
(dst / "index.json").write_text(json.dumps({"pages": index, "cdn": sorted(cdn), "fonts_not_copied": fonts},
                                           ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
total = sum(p.stat().st_size for p in dst.rglob("*") if p.is_file())
print("pages", len(index), "screens", len(list((dst / "screens").iterdir())), "assets", [p.name for p in (dst / "assets").iterdir()],
      "total KB", total // 1024, "| cdn", sorted(cdn), "| fonts", fonts)
