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

import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW  = ROOT / "app" / "src" / "main" / "res" / "raw" / "watchface.xml"
PREVIEW = ROOT / "preview.html"
HEART_ICON = ROOT / "app" / "src" / "main" / "res" / "drawable" / "heart_icon.png"

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
    ("Olive",   "#FF8C8F5A"),
    ("White",   "#FFF5F5F5"),
]
DEFAULT_COLOR = 0    # index into ON_OPTS

# ---- widgets: date readout + two complication slots (heart rate, weather) --
# Sizes/positions chosen so both slots and the date line clear the LED grid
# (worst case: BCD mode with labels, which uses the most vertical space) AND
# stay inside the circular clip -- checked against the actual chord width at
# each corner, not just the square canvas.
DATE_X, DATE_Y, DATE_W, DATE_H = 125, 382, 200, 36
WIDGET_W, WIDGET_H = 120, 68          # complication slot size, px -- wide rather than square,
WIDGET_Y = 48                         # so icon+text has room without clipping
WIDGET_MARGIN_X = 98                  # inset from each edge to the slot's near edge

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
        # lit LED, shown only when the bit expression is truthy.  `alpha`
        # can't take an expression here (its declared type is a static
        # 0-255 component, confirmed against the WFF XSD validator), so
        # gate visibility with Condition/Compare instead.
        name = f'b{c["k"]}_{round(c["x"])}_{round(c["y"])}'
        lit.append(
            f'      <Condition>\n'
            f'        <Expressions>\n'
            f'          <Expression name="{name}">{bit_expr(c["expr"], c["k"])}</Expression>\n'
            f'        </Expressions>\n'
            f'        <Compare expression="{name}">\n'
            f'          <Group x="{x}" y="{y}" width="{w}" height="{w}" name="{name}">\n'
            f'            <PartDraw x="0" y="0" width="{w}" height="{w}">\n'
            f'              <Ellipse x="0" y="0" width="{w}" height="{w}">'
            f'<Fill color="[CONFIGURATION.litColor]"/></Ellipse>\n'
            f'            </PartDraw>\n'
            f'          </Group>\n'
            f'        </Compare>\n'
            f'      </Condition>')
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
            f'            <Font family="SYNC_TO_DEVICE" size="26" '
            f'weight="NORMAL" color="{LABEL}">{c["label"].upper()}</Font>\n'
            f'          </Text>\n'
            f'        </PartText>')
    return "\n".join(out)


def build_heart_icon():
    """Rasterize a heart to app/src/main/res/drawable/heart_icon.png. WFF's
    Image loader appears to only handle raster drawables -- a VectorDrawable
    XML compiled fine but never rendered on-device -- so this uses the
    standard parametric heart curve (x=16sin^3t, y=13cos t - 5cos 2t -
    2cos 3t - cos 4t) rather than a vector asset. Solid white on transparent;
    the watch face tints it to the LED color at render time via tintColor."""
    from PIL import Image, ImageDraw
    SS, SIZE = 4, 128                     # supersample then downscale for smooth edges
    S = SIZE * SS
    pts = []
    for i in range(240):
        t = 2 * math.pi * i / 240
        x = 16 * math.sin(t) ** 3
        y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        pts.append((x, y))
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
    w, h = maxx - minx, maxy - miny
    pad = 0.06
    scale = (1 - 2 * pad) * S / max(w, h)
    ox, oy = (S - w * scale) / 2, (S - h * scale) / 2

    def to_px(x, y):
        return (x - minx) * scale + ox, S - ((y - miny) * scale + oy)  # flip y: formula is y-up

    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(img).polygon([to_px(x, y) for x, y in pts], fill=(255, 255, 255, 255))
    img.resize((SIZE, SIZE), Image.LANCZOS).save(HEART_ICON)


def wff_complication_date() -> str:
    """Bottom-center: [COMPLICATION.TEXT], defaults to the on-device DATE
    system provider (locale-formatted, no setup needed) -- reassignable to
    anything else SHORT_TEXT via the standard complication editor, same as
    the other two slots. A rectangular BoundingRoundBox fits its wide/short
    shape better than the ovals used for the two square widget slots."""
    return (
        f'    <ComplicationSlot x="{DATE_X}" y="{DATE_Y}" width="{DATE_W}" height="{DATE_H}" '
        f'slotId="3" displayName="slot_date" supportedTypes="SHORT_TEXT EMPTY">\n'
        f'      <DefaultProviderPolicy defaultSystemProvider="DAY_AND_DATE" defaultSystemProviderType="SHORT_TEXT"/>\n'
        f'      <BoundingRoundBox x="0" y="0" width="{DATE_W}" height="{DATE_H}" cornerRadius="8"/>\n'
        f'      <Complication type="SHORT_TEXT">\n'
        f'        <Condition>\n'
        f'          <Expressions>\n'
        f'            <Expression name="date_on"><![CDATA[[COMPLICATION.TEXT] != null]]></Expression>\n'
        f'          </Expressions>\n'
        f'          <Compare expression="date_on">\n'
        f'            <PartText x="0" y="0" width="{DATE_W}" height="{DATE_H}">\n'
        f'              <Text align="CENTER">\n'
        f'                <Font family="SYNC_TO_DEVICE" size="30" weight="NORMAL" color="[CONFIGURATION.litColor]">\n'
        f'                  <Template>%s<Parameter expression="[COMPLICATION.TEXT]"/></Template>\n'
        f'                </Font>\n'
        f'              </Text>\n'
        f'            </PartText>\n'
        f'          </Compare>\n'
        f'        </Condition>\n'
        f'      </Complication>\n'
        f'    </ComplicationSlot>')


def wff_complication_heart(x: int) -> str:
    """Top-left: our own heart_icon drawable (tinted to litColor -- Android
    renders a bare Unicode heart glyph as a fixed-color emoji regardless of
    the Font color, so a real icon resource is the only reliable way to
    match the LED color) + [COMPLICATION.TEXT], defaulting to the on-device
    HEART_RATE system provider (no app/setup needed), still reassignable by
    the user like any complication. Invisible until a provider is assigned --
    an unassigned slot already renders nothing, so no separate toggle needed."""
    icon = 36                     # left region for the heart icon; text fills the rest
    text_w = WIDGET_W - icon
    return (
        f'    <ComplicationSlot x="{x}" y="{WIDGET_Y}" width="{WIDGET_W}" height="{WIDGET_H}" '
        f'slotId="1" displayName="slot_heart" supportedTypes="SHORT_TEXT EMPTY">\n'
        f'      <DefaultProviderPolicy defaultSystemProvider="HEART_RATE" defaultSystemProviderType="SHORT_TEXT"/>\n'
        f'      <BoundingRoundBox x="0" y="0" width="{WIDGET_W}" height="{WIDGET_H}" cornerRadius="12"/>\n'
        f'      <Complication type="SHORT_TEXT">\n'
        f'        <Condition>\n'
        f'          <Expressions>\n'
        f'            <Expression name="heart_on">'
        f'<![CDATA[[COMPLICATION.TEXT] != null]]></Expression>\n'
        f'          </Expressions>\n'
        f'          <Compare expression="heart_on">\n'
        f'            <PartImage x="0" y="{(WIDGET_H - icon) // 2}" width="{icon}" height="{icon}" '
        f'tintColor="[CONFIGURATION.litColor]">\n'
        f'              <Image resource="heart_icon"/>\n'
        f'            </PartImage>\n'
        f'            <PartText x="{icon}" y="0" width="{text_w}" height="{WIDGET_H}">\n'
        f'              <Text align="CENTER" ellipsis="TRUE">\n'
        f'                <Font family="SYNC_TO_DEVICE" size="30" weight="NORMAL" color="[CONFIGURATION.litColor]">\n'
        f'                  <Template>%s<Parameter expression="[COMPLICATION.TEXT]"/></Template>\n'
        f'                </Font>\n'
        f'              </Text>\n'
        f'            </PartText>\n'
        f'          </Compare>\n'
        f'        </Condition>\n'
        f'      </Complication>\n'
        f'    </ComplicationSlot>')


def wff_complication_weather(x: int) -> str:
    """Top-right: [COMPLICATION.TEXT] (temperature) + the provider's own icon
    when it supplies one -- no built-in system weather provider exists, so
    this stays unassigned (invisible) until the user picks a weather app in
    the on-watch complication editor."""
    icon = 36                     # right region for the icon; text fills the rest on the left
    text_w = WIDGET_W - icon
    icon_y = (WIDGET_H - icon) // 2
    return (
        f'    <ComplicationSlot x="{x}" y="{WIDGET_Y}" width="{WIDGET_W}" height="{WIDGET_H}" '
        f'slotId="2" displayName="slot_weather" supportedTypes="SHORT_TEXT EMPTY">\n'
        f'      <BoundingRoundBox x="0" y="0" width="{WIDGET_W}" height="{WIDGET_H}" cornerRadius="12"/>\n'
        f'      <Complication type="SHORT_TEXT">\n'
        f'        <Condition>\n'
        f'          <Expressions>\n'
        f'            <Expression name="weather_icon_text"><![CDATA['
        f'[COMPLICATION.TEXT] != null && [COMPLICATION.MONOCHROMATIC_IMAGE] != null]]></Expression>\n'
        f'            <Expression name="weather_text">'
        f'<![CDATA[[COMPLICATION.TEXT] != null]]></Expression>\n'
        f'          </Expressions>\n'
        f'          <Compare expression="weather_icon_text">\n'
        f'            <PartText x="0" y="0" width="{text_w}" height="{WIDGET_H}">\n'
        f'              <Text align="CENTER" ellipsis="TRUE">\n'
        f'                <Font family="SYNC_TO_DEVICE" size="30" weight="NORMAL" color="[CONFIGURATION.litColor]">\n'
        f'                  <Template>%s<Parameter expression="[COMPLICATION.TEXT]"/></Template>\n'
        f'                </Font>\n'
        f'              </Text>\n'
        f'            </PartText>\n'
        f'            <PartImage x="{text_w}" y="{icon_y}" width="{icon}" height="{icon}" tintColor="[CONFIGURATION.litColor]">\n'
        f'              <Image resource="[COMPLICATION.MONOCHROMATIC_IMAGE]"/>\n'
        f'            </PartImage>\n'
        f'          </Compare>\n'
        f'          <Compare expression="weather_text">\n'
        f'            <PartText x="0" y="0" width="{WIDGET_W}" height="{WIDGET_H}">\n'
        f'              <Text align="CENTER" ellipsis="TRUE">\n'
        f'                <Font family="SYNC_TO_DEVICE" size="30" weight="NORMAL" color="[CONFIGURATION.litColor]">\n'
        f'                  <Template>%s<Parameter expression="[COMPLICATION.TEXT]"/></Template>\n'
        f'                </Font>\n'
        f'              </Text>\n'
        f'            </PartText>\n'
        f'          </Compare>\n'
        f'        </Condition>\n'
        f'      </Complication>\n'
        f'    </ComplicationSlot>')


def build_wff() -> str:
    b_cells = wff_cells(list(binary_layout()))
    d_cells = wff_cells(list(bcd_layout()))
    b_labels = wff_labels(list(binary_layout()))
    d_labels = wff_labels(list(bcd_layout()))
    colour_opts = "\n".join(
        f'      <ColorOption id="{i}" displayName="color_{name.lower()}" '
        f'colors="{argb}"/>'
        for i, (name, argb) in enumerate(ON_OPTS))
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!-- GENERATED by tools/gen_watchface.py - do not hand-edit. -->
<WatchFace width="{CANVAS}" height="{CANVAS}" clipShape="CIRCLE">
  <Metadata key="CLOCK_TYPE" value="DIGITAL"/>
  <Metadata key="PREVIEW_TIME" value="10:08:32"/>

  <UserConfigurations>
    <BooleanConfiguration id="bcd" displayName="cfg_bcd" defaultValue="FALSE"/>
    <BooleanConfiguration id="labels" displayName="cfg_labels" defaultValue="TRUE"/>
    <ColorConfiguration id="litColor" displayName="cfg_color" defaultValue="{DEFAULT_COLOR}">
{colour_opts}
    </ColorConfiguration>
  </UserConfigurations>

  <Scene>
    <!-- background -->
    <PartDraw x="0" y="0" width="{CANVAS}" height="{CANVAS}">
      <Rectangle x="0" y="0" width="{CANVAS}" height="{CANVAS}"><Fill color="{BG}"/></Rectangle>
    </PartDraw>

    <!-- complications: independent of BCD/binary mode, so they sit outside
         that switch rather than being duplicated into both branches. -->
{wff_complication_date()}
{wff_complication_heart(WIDGET_MARGIN_X)}
{wff_complication_weather(CANVAS - WIDGET_MARGIN_X - WIDGET_W)}

    <!-- BCD vs BINARY is a UserConfiguration selection, not a per-frame value,
         so it's modelled as a BooleanConfiguration/BooleanOption switch rather
         than a computed alpha (alpha's declared type doesn't accept a
         CONFIGURATION-driven ternary expression per the WFF XSD validator). -->
    <BooleanConfiguration id="bcd">
      <BooleanOption id="FALSE">
        <Group name="mode_binary" x="0" y="0" width="{CANVAS}" height="{CANVAS}">
{b_cells}
          <BooleanConfiguration id="labels">
            <BooleanOption id="TRUE">
              <Group name="binary_labels" x="0" y="0" width="{CANVAS}" height="{CANVAS}">
{b_labels}
              </Group>
            </BooleanOption>
          </BooleanConfiguration>
        </Group>
      </BooleanOption>
      <BooleanOption id="TRUE">
        <Group name="mode_bcd" x="0" y="0" width="{CANVAS}" height="{CANVAS}">
{d_cells}
          <BooleanConfiguration id="labels">
            <BooleanOption id="TRUE">
              <Group name="bcd_labels" x="0" y="0" width="{CANVAS}" height="{CANVAS}">
{d_labels}
              </Group>
            </BooleanOption>
          </BooleanConfiguration>
        </Group>
      </BooleanOption>
    </BooleanConfiguration>
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
      s += `<text x="${lx}" y="${ly}" fill="${LABEL}" font-size="26" text-anchor="middle" font-family="system-ui">${c.label.toUpperCase()}</text>`;
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
    HEART_ICON.parent.mkdir(parents=True, exist_ok=True)
    build_heart_icon()
    RAW.write_text(build_wff(), encoding="utf-8")
    PREVIEW.write_text(build_html(), encoding="utf-8")
    n_bin = sum(nb for _, _, nb in BINARY_ROWS)
    n_bcd = sum(nb for _, _, nb in BCD_COLS)
    print(f"wrote {HEART_ICON.relative_to(ROOT)}")
    print(f"wrote {RAW.relative_to(ROOT)}   ({n_bin} binary + {n_bcd} BCD LEDs)")
    print(f"wrote {PREVIEW.relative_to(ROOT)}   (open in a browser)")


if __name__ == "__main__":
    main()
