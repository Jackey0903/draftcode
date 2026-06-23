#!/usr/bin/env python3
# 把「得意黑」(Display) 与「FusionPixel12」(Pixel) 按 index.src.html 实际用字
# 子集化并 base64 内嵌为 @font-face,产出自包含的 index.html。
#
# 用法:  python3 build_fonts.py
# 重新生成: 改 index.src.html 后再跑一次即可(幂等,从 src 重建 index.html)。
import base64, os, subprocess, sys, tempfile, shutil

ROOT = os.path.dirname(os.path.abspath(__file__))
# 每个 (源, 产物) 各自按自身用字子集化并内嵌字体
FILES = [
    ("index.src.html", "index.html"),
    ("选秀作战室_架构图.src.html", "选秀作战室_架构图.html"),
]

# 得意黑 = Smiley Sans Oblique(name 表内含「得意黑」)
DISPLAY_FONT = "/Users/wuguangyu/Desktop/毕业设计/答辩演示/SmileySans-Oblique.otf"
PIXEL_FONT = os.path.join(ROOT, "assets/fonts/fusion-pixel-font/fusion-pixel-12px-monospaced-zh_hans.otf.woff2")

PYFTSUBSET = os.path.expanduser("~/Library/Python/3.9/bin/pyftsubset")
SITE = os.path.expanduser("~/Library/Python/3.9/lib/python/site-packages")

MARK_DISPLAY = "/*__DEYIHEI_FONTFACE__*/"
MARK_PIXEL = "/*__FUSIONPIXEL_FONTFACE__*/"

# 始终覆盖的安全字符集:常见数字/单位/占位用字,避免占位文案换字后缺字形
SAFE = set("0123456789%+-−.×/·:()<>=≠→ "
           "第顺位名届年场强队控卫中锋国际乐透区前后置信度概率赔率天赋专家资金背离"
           "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz")
UNICODES = "U+0020-007E,U+00A0-00FF,U+2010-201F,U+2026,U+2032-2033,U+2190-2193,U+2260,U+2212,U+3000-303F,U+FF00-FFEF"


def run_subset(font_in, text, out_path, want_woff2=True):
    fd, txt = tempfile.mkstemp(suffix=".txt")
    os.close(fd)
    open(txt, "w", encoding="utf-8").write(text)
    env = dict(os.environ, PYTHONPATH=SITE + os.pathsep + os.environ.get("PYTHONPATH", ""))
    flavors = [("woff2", "woff2"), ("woff", "woff")] if want_woff2 else [("woff", "woff")]
    for flavor, fmt in flavors:
        cmd = [PYFTSUBSET, font_in,
               "--text-file=" + txt,
               "--unicodes=" + UNICODES,
               "--layout-features=*", "--no-hinting", "--desubroutinize",
               "--flavor=" + flavor, "--output-file=" + out_path]
        r = subprocess.run(cmd, capture_output=True, text=True, env=env)
        if r.returncode == 0 and os.path.exists(out_path) and os.path.getsize(out_path) > 0:
            os.remove(txt)
            return fmt
        last = (r.stderr or r.stdout or "").strip()[:300]
    os.remove(txt)
    raise SystemExit("subset failed for %s: %s" % (font_in, last))


def face(family, mime, fmt, path):
    b64 = base64.b64encode(open(path, "rb").read()).decode("ascii")
    return ("@font-face{font-family:'%s';font-style:normal;font-weight:400;"
            "font-display:swap;src:url(data:%s;base64,%s) format('%s');}"
            % (family, mime, b64, fmt))


def build_one(src, out, fmt_map):
    html = open(src, encoding="utf-8").read()
    if MARK_DISPLAY not in html or MARK_PIXEL not in html:
        raise SystemExit("markers not found in " + src)
    chars = set(html) | SAFE
    text = "".join(sorted(c for c in chars if c.strip() and ord(c) > 31))

    tmp = tempfile.mkdtemp()
    try:
        d_out = os.path.join(tmp, "deyihei.font")
        d_fmt = run_subset(DISPLAY_FONT, text, d_out)
        d_face = face("DeyiHei", fmt_map[d_fmt][1], fmt_map[d_fmt][0], d_out)

        p_out = os.path.join(tmp, "fusionpixel.font")
        p_fmt = run_subset(PIXEL_FONT, text, p_out)
        p_face = face("FusionPixel12", fmt_map[p_fmt][1], fmt_map[p_fmt][0], p_out)

        html = html.replace(MARK_DISPLAY, d_face, 1).replace(MARK_PIXEL, p_face, 1)
        open(out, "w", encoding="utf-8").write(html)
        print("%-30s -> 得意黑 %dKB(%d字) · 像素 %dKB · 总 %dKB"
              % (out, os.path.getsize(d_out) // 1024, len(text),
                 os.path.getsize(p_out) // 1024, len(html.encode("utf-8")) // 1024))
    finally:
        shutil.rmtree(tmp)


def main():
    if not os.path.exists(DISPLAY_FONT):
        raise SystemExit("missing 得意黑 source: " + DISPLAY_FONT)
    if not os.path.exists(PIXEL_FONT):
        raise SystemExit("missing FusionPixel source: " + PIXEL_FONT)
    fmt_map = {"woff2": ("woff2", "font/woff2"), "woff": ("woff", "font/woff")}
    for src, out in FILES:
        srcp = os.path.join(ROOT, src)
        if not os.path.exists(srcp):
            print("skip (missing): " + src)
            continue
        build_one(srcp, os.path.join(ROOT, out), fmt_map)


if __name__ == "__main__":
    main()
