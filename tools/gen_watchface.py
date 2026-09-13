#!/usr/bin/env python3
"""
Binary Watch Face generator.

One layout spec -> two outputs:
  * app/src/main/res/raw/watchface.xml   Wear OS Watch Face Format (WFF), v2
  * preview.html                          live browser preview, no build needed

Two display modes, switchable on the watch via a Boolean setting ("BCD mode"),
modelled on Paul's physical LED binary desk clock:

  BINARY   three rows (hours / minutes / seconds), each the raw value in
           binary, most-significant bit on the LEFT.
               H  . . o . o .      (o = lit)
               M  . o . . o o
               S  o . o . . o

  BCD      six columns  H10 H1 : M10 M1 : S10 S1, each column one decimal
           digit in binary with the 1s bit at the BOTTOM -- the classic
           desk "binary clock" toy layout.
               8  . .   . .   . .
               4  . o   o .   . o
               2  . .   . o   o .
               1  o .   . o   o o

The per-LED bit test is pure arithmetic so it works on every WFF version:
      lit = round( floor(value / 2**k) % 2 )
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW  = ROOT / "app" / "src" / "main" / "res" / "raw" / "watchface.xml"
PREVIEW = ROOT / "preview.html"

# ---- geometry -----------------------------------------------------------
CANVAS = 450
C      = CANVAS / 2
LED_R  = 15            # LED radius, px
GX     = 46            # horizontal pitch between LEDs
GY     = 52            # vertical pitch between LEDs

# ---- colours (defaults; all overridable on-watch via configuration) ----
BG     = "#FF000000"
OFF    = "#FF1C1C1C"
LABEL  = "#FF8A8A8A"

# LED colour picker shown on the watch (and in preview.html).
# (name, ARGB) -- edit freely, add/remove rows, reorder. Index 0 is the default.
ON_OPTS = [
    ("Green",   "#FF33FF66"),
    ("Emerald", "#FF00C853"),
    ("Teal",    "#FF1DE9B6"),
    ("Cyan",    "#FF33E1FF"),
    ("Blue",    "#FF33B5FF"),
    ("Indigo",  "#FF5C6BC0"),
    ("Violet",  "#FF9B7BFF"),
    ("Purple",  "#FFC061FF"),
    ("Magenta", "#FFFF5CD2"),
    ("Pink",    "#FFFF6EA6"),
    ("Red",     "#FFFF5A5A"),
    ("Orange",  "#FFFF9E42"),
    ("Amber",   "#FFFFC24B"),
    ("Yellow",  "#FFFFE14D"),
    ("White",   "#FFF5F5F5"),
]
DEFAULT_COLOR = 0    # index into ON_OPTS

# ---- clock model  (label, WFF value expression, number of bits) --------
BINARY_ROWS = [
    ("H", "[HOUR_0_23]", 6),   # 0-23 needs 5 bits; 6 keeps the grid square
    ("M", "[MINUTE]",     6),
    ("S", "[SECOND]",     6),
]
BCD_COLS = [
    ("H", "floor([HOUR_0_23] / 10)", 2),
    ("h", "([HOUR_0_23] % 10)",      4),
    ("M", "floor([MINUTE] / 10)",    3),
    ("m", "([MINUTE] % 10)",         4),
    ("S", "floor([SECOND] / 10)",    3),
    ("s", "([SECOND] % 10)",         4),
]


def bit_expr(value_expr: str, k: int) -> str:
    """WFF arithmetic yielding 1 when bit k of value_expr is set, else 0."""
    return f"round(floor(({value_expr}) / {1 << k}) % 2)"


# ---- layout: yields dicts {x, y, k, expr, label} ----------------------
def binary_layout():
    n = len(BINARY_ROWS)
    for r, (label, expr, nbits) in enumerate(BINARY_ROWS):
        cy = C + (r - (n - 1) / 2) * GY
        for col in range(nbits):
            k = nbits - 1 - col
            cx = C + (col - (nbits - 1) / 2) * GX
            yield dict(x=cx, y=cy, k=k, expr=expr,
                       label=label if col == 0 else None,
                       label_x=cx - GX, label_y=cy)


def bcd_layout():
    n = len(BCD_COLS)
    max_bits = max(nb for _, _, nb in BCD_COLS)
    baseline = C + (max_bits - 1) / 2 * GY          # y of the 1s-bit row
    for ci, (label, expr, nbits) in enumerate(BCD_COLS):
        cx = C + (ci - (n - 1) / 2) * GX
        for j in range(nbits):                       # j = 0 is top of column
            k = nbits - 1 - j
            cy = baseline - k * GY
            yield dict(x=cx, y=cy, k=k, expr=expr,
                       label=label if j == nbits - 1 else None,
                       label_x=cx, label_y=baseline + GY * 0.75)


# ======================================================================
# WFF  (res/raw/watchface.xml)
# ======================================================================
def wff_cells(layout):
    d, lit = [], []
    for c in layout:
        x, y = round(c["x"] - LED_R), round(c["y"] - LED_R)
        w = LED_R * 2
        # always-on dim LED
        d.append(
            f'      <PartDraw x="{x}" y="{y}" width="{w}" height="{w}">\n'
            f'        <Ellipse x="0" y="0" width="{w}" height="{w}">'
            f'<Fill color="{OFF}"/></Ellipse>\n'
            f'      </PartDraw>')
        # lit LED, gated by the bit expression via Group alpha
        lit.append(
            f'      <Group x="{x}" y="{y}" width="{w}" height="{w}" '
            f'name="b{c["k"]}_{round(c["x"])}_{round(c["y"])}" '
            f'alpha="{bit_expr(c["expr"], c["k"])}">\n'
            f'        <PartDraw x="0" y="0" width="{w}" height="{w}">\n'
            f'          <Ellipse x="0" y="0" width="{w}" height="{w}">'
            f'<Fill color="[CONFIGURATION.litColor]"/></Ellipse>\n'
            f'        </PartDraw>\n'
            f'      </Group>')
    return "\n".join(d + lit)


def wff_labels(layout):
    out = []
    for c in layout:
        if not c["label"]:
            continue
        x, y = round(c["label_x"] - GX / 2), round(c["label_y"] - GY / 2)
        out.append(
            f'        <PartText x="{x}" y="{y}" width="{GX}" height="{GY}">\n'
            f'          <Text align="CENTER">\n'
            f'            <SimpleText>\n'
            f'              <Font family="SYNC_TO_DEVICE" size="22" '
            f'weight="NORMAL" color="{LABEL}">\n'
            f'                <Template>{c["label"].upper()}</Template>\n'
            f'              </Font>\n'
            f'            </SimpleText>\n'
            f'          </Text>\n'
            f'        </PartText>')
    return "\n".join(out)


def build_wff() -> str:
    b_cells = wff_cells(list(binary_layout()))
    d_cells = wff_cells(list(bcd_layout()))
    b_labels = wff_labels(list(binary_layout()))
    d_labels = wff_labels(list(bcd_layout()))
    colour_opts = "\n".join(
        f'      <ColorOption id="{i}" colors="{argb}"/>  <!-- {name} -->'
        for i, (name, argb) in enumerate(ON_OPTS))
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!-- GENERATED by tools/gen_watchface.py - do not hand-edit. -->
<WatchFace width="{CANVAS}" height="{CANVAS}" clipShape="CIRCLE">
  <Metadata key="CLOCK_TYPE" value="DIGITAL"/>
  <Metadata key="PREVIEW_TIME" value="10:08:32"/>

  <UserConfigurations>
    <BooleanConfiguration id="bcd" displayName="@string/cfg_bcd" defaultValue="FALSE"/>
    <BooleanConfiguration id="labels" displayName="@string/cfg_labels" defaultValue="TRUE"/>
    <ColorConfiguration id="litColor" displayName="@string/cfg_color" defaultValue="{DEFAULT_COLOR}">
{colour_opts}
    </ColorConfiguration>
  </UserConfigurations>

  <Scene>
    <!-- background -->
    <PartDraw x="0" y="0" width="{CANVAS}" height="{CANVAS}">
      <Rectangle x="0" y="0" width="{CANVAS}" height="{CANVAS}"><Fill color="{BG}"/></Rectangle>
    </PartDraw>

    <!-- ============ BINARY mode ============ -->
    <Group name="mode_binary" x="0" y="0" width="{CANVAS}" height="{CANVAS}"
           alpha="[CONFIGURATION.bcd] ? 0 : 1">
{b_cells}
      <Group name="binary_labels" x="0" y="0" width="{CANVAS}" height="{CANVAS}"
             alpha="[CONFIGURATION.labels] ? 1 : 0">
{b_labels}
      </Group>
    </Group>

    <!-- ============ BCD mode ============ -->
    <Group name="mode_bcd" x="0" y="0" width="{CANVAS}" height="{CANVAS}"
           alpha="[CONFIGURATION.bcd] ? 1 : 0">
{d_cells}
      <Group name="bcd_labels" x="0" y="0" width="{CANVAS}" height="{CANVAS}"
             alpha="[CONFIGURATION.labels] ? 1 : 0">
{d_labels}
      </Group>
    </Group>
  </Scene>
</WatchFace>
"""


# ======================================================================
# preview.html  (browser, live clock, no build)
# ======================================================================
_HTML_TMPL = r"""<!doctype html>
<meta charset="utf-8">
<title>Binary Watch Face - preview</title>
<style>
  body { background:#111; color:#ccc; font:14px system-ui; text-align:center; margin:0; padding:24px; }
  svg  { background:#000; border-radius:50%; box-shadow:0 0 40px #0008; }
  label { margin:0 10px; }
  .wrap { display:inline-block; }
</style>
<div class="wrap">
  <h2>Binary Watch Face</h2>
  <svg id="face" width="360" height="360" viewBox="0 0 __CANVAS__ __CANVAS__"></svg>
  <div style="margin-top:14px">
    <label><input type="checkbox" id="bcd"> BCD mode</label>
    <label><input type="checkbox" id="labels" checked> labels</label>
    <label>color <select id="color"></select></label>
  </div>
  <p id="readout" style="color:#666"></p>
</div>
<script>
const R = __LED_R__, GX = __GX__, MID = __C__, OFF = "__OFF__", LABEL = "__LABEL__";
const ON = __ON_JS__;
const BINARY = __BINARY_JS__;
const BCD = __BCD_JS__;
const svg = document.getElementById("face");
const sel = document.getElementById("color");
ON.forEach((opt, i) => { const el = document.createElement("option"); el.value = i; el.textContent = opt.n; sel.appendChild(el); });

function value(src, now) {           // mirror the WFF value expressions
  const H = now.getHours(), M = now.getMinutes(), S = now.getSeconds();
  src = src.replaceAll("[HOUR_0_23]", H).replaceAll("[MINUTE]", M).replaceAll("[SECOND]", S);
  src = src.replace(/floor\(([^()]+)\)/g, (_, e) => "Math.floor(" + e + ")");
  return Function('"use strict";return (' + src + ')')();
}
function bit(src, k, now) { return Math.round(Math.floor(value(src, now) / (2 ** k)) % 2); }

function draw() {
  const now = new Date();
  const bcd = document.getElementById("bcd").checked;
  const showLabels = document.getElementById("labels").checked;
  const on = ON[sel.value].c;
  let s = "";
  for (const c of (bcd ? BCD : BINARY)) {
    const lit = bit(c.src, c.k, now);
    s += `<circle cx="${c.x}" cy="${c.y}" r="${R}" fill="${lit ? on : OFF}"/>`;
    if (showLabels && c.label) {
      const lx = bcd ? c.x : c.x - GX;
      const ly = (bcd ? MID + 150 : c.y) + 7;
      s += `<text x="${lx}" y="${ly}" fill="${LABEL}" font-size="22" text-anchor="middle" font-family="system-ui">${c.label.toUpperCase()}</text>`;
    }
  }
  svg.innerHTML = s;
  document.getElementById("readout").textContent =
    now.toTimeString().slice(0, 8) + (bcd ? "   (BCD)" : "   (binary)");
}
setInterval(draw, 250); draw();
</script>
"""


def _css_hex(argb: str) -> str:
    """#FFRRGGBB -> #RRGGBB"""
    return "#" + argb[-6:]


def build_html() -> str:
    def js_layout(gen):
        rows = []
        for c in gen:
            lab = f'"{c["label"]}"' if c["label"] else "null"
            rows.append('{x:%.1f,y:%.1f,k:%d,src:%s,label:%s}' % (
                c["x"], c["y"], c["k"],
                repr(c["expr"]).replace("'", '"'), lab))
        return "[" + ",".join(rows) + "]"

    repl = {
        "__CANVAS__": str(CANVAS),
        "__LED_R__": str(LED_R),
        "__GX__": str(GX),
        "__C__": str(C),
        "__OFF__": _css_hex(OFF),
        "__LABEL__": _css_hex(LABEL),
        "__ON_JS__": "[" + ",".join(
            '{n:"%s",c:"%s"}' % (name, _css_hex(argb))
            for name, argb in ON_OPTS) + "]",
        "__BINARY_JS__": js_layout(binary_layout()),
        "__BCD_JS__": js_layout(bcd_layout()),
    }
    out = _HTML_TMPL
    for k, v in repl.items():
        out = out.replace(k, v)
    return out


def main():
    RAW.parent.mkdir(parents=True, exist_ok=True)
    RAW.write_text(build_wff(), encoding="utf-8")
    PREVIEW.write_text(build_html(), encoding="utf-8")
    n_bin = sum(nb for _, _, nb in BINARY_ROWS)
    n_bcd = sum(nb for _, _, nb in BCD_COLS)
    print(f"wrote {RAW.relative_to(ROOT)}   ({n_bin} binary + {n_bcd} BCD LEDs)")
    print(f"wrote {PREVIEW.relative_to(ROOT)}   (open in a browser)")


if __name__ == "__main__":
    main()
