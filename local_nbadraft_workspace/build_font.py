#!/usr/bin/env python3
# Subset 得意黑.otf to the glyphs used in index.html, embed as base64 @font-face.
import base64, re, subprocess, sys, os, tempfile, shutil

ROOT = "/Users/wuguangyu/Desktop/NBADRAFT"
HTML = os.path.join(ROOT, "index.html")
FONT = os.path.join(ROOT, "设计元素/ClaudeDesign本机读取_ReDraft素材_only/05_字体_可选/得意黑.otf")
PYFTSUBSET = os.path.expanduser("~/Library/Python/3.9/bin/pyftsubset")
MARKER = "/*__DEYIHEI_FONTFACE__*/"

html = open(HTML, encoding="utf-8").read()

# 1) unique chars in the document (cover all current text) + safety set
chars = set(html)
# add likely fill chars for placeholders rendered in display font (numbers/units/symbols)
chars |= set("0123456789%+-−.×/ 第顺位名届年场强队控卫中锋国际乐透区前后")
text = "".join(sorted(c for c in chars if c.strip() and ord(c) > 31))

tmpdir = tempfile.mkdtemp()
txtfile = os.path.join(tmpdir, "chars.txt")
open(txtfile, "w", encoding="utf-8").write(text)

UNICODES = "U+0020-007E,U+00A0-00FF,U+2010-201F,U+2026,U+2032-2033,U+2212,U+3000-303F,U+FF00-FFEF"

def run_subset(flavor, out):
    cmd = [PYFTSUBSET, FONT,
           "--text-file=" + txtfile,
           "--unicodes=" + UNICODES,
           "--layout-features=*",
           "--no-hinting", "--desubroutinize",
           "--output-file=" + out]
    if flavor:
        cmd.append("--flavor=" + flavor)
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode == 0, r.stderr

# 2) try woff2 -> woff -> otf
out_path, fmt, mime = None, None, None
for flavor, ext, fmtname, m in [("woff2","woff2","woff2","font/woff2"),
                                ("woff","woff","woff","font/woff"),
                                (None,"otf","opentype","font/otf")]:
    cand = os.path.join(tmpdir, "deyihei." + ext)
    ok, err = run_subset(flavor, cand)
    if ok and os.path.exists(cand) and os.path.getsize(cand) > 0:
        out_path, fmt, mime = cand, fmtname, m
        print("subset OK via", flavor or "otf", "->", os.path.getsize(cand), "bytes")
        break
    else:
        print("subset failed for", flavor, ":", (err or "").strip()[:200])

if not out_path:
    print("ERROR: subsetting failed entirely"); shutil.rmtree(tmpdir); sys.exit(1)

# 3) base64 + build @font-face
b64 = base64.b64encode(open(out_path, "rb").read()).decode("ascii")
face = ("@font-face{font-family:'DeyiHei';font-style:normal;font-weight:400;"
        "font-display:swap;src:url(data:%s;base64,%s) format('%s');}" % (mime, b64, fmt))

if MARKER not in html:
    print("ERROR: marker not found in index.html"); shutil.rmtree(tmpdir); sys.exit(1)

html = html.replace(MARKER, face, 1)
open(HTML, "w", encoding="utf-8").write(html)
print("injected @font-face: %d glyphs text, html now %d KB" % (len(text), len(html)//1024))
shutil.rmtree(tmpdir)
