# Binary Watch Face

A Pixel Watch (Wear OS) watch face that shows the time in binary, modelled on
Paul's physical LED binary desk clock. Two modes, switchable in the watch face
settings:

### BINARY mode
Three rows — hours, minutes, seconds — each the raw value in base 2,
most-significant bit on the **left**.

```
        32 16  8  4  2  1
   H     .  .  o  .  o  .     = 10
   M     .  o  .  .  o  o     = 19
   S     o  .  o  .  .  o     = 41      -> 10:19:41
```

### BCD mode  (the desk-clock toy layout)
Six columns — `H₁₀ H₁ : M₁₀ M₁ : S₁₀ S₁` — each column one decimal digit in
binary, **1s bit at the bottom**.

```
   8    .   .     .   .     .   .
   4    .   .     o   .     o   .
   2    .   .     .   o     .   .
   1    o   .     .   o     .   o
        1   0     4   3     0   9        -> 10:43:09
```

## How it works

Everything is generated from one spec in **`tools/gen_watchface.py`** —
LED positions, colours, and the per-LED bit test:

```
lit(value, k) = round( floor(value / 2^k) % 2 )
```

That's pure arithmetic, so it works on every Watch Face Format version. The
generator emits two things from the same layout:

| output | purpose |
|---|---|
| `app/src/main/res/raw/watchface.xml` | the actual Wear OS watch face (WFF v2) |
| `preview.html` | a live browser preview — **no build required** |

Tweak geometry/colours at the top of `gen_watchface.py`, re-run, refresh the
preview. When it looks right, build the APK.

```
python3 tools/gen_watchface.py
xdg-open preview.html          # see it now
```

## Building the APK

**Toolchain (the SDK at `/data/burney/Android/Sdk` is too old — max platform is
android-30; WFF needs 33+):**

```bash
# get modern command-line tools, then:
sdkmanager "platforms;android-34" "build-tools;34.0.0" "platform-tools"
sdkmanager --licenses
echo "sdk.dir=/data/burney/Android/Sdk" > local.properties
```

Then, with a recent Gradle (8.5+) or Android Studio:

```bash
gradle :app:assembleRelease
# -> app/build/outputs/apk/release/app-release-unsigned.apk
```

There is no Gradle wrapper checked in yet. Either open the project in Android
Studio (it will offer to add one) or run `gradle wrapper` once with a system
Gradle.

## Installing on the Pixel Watch

1. On the watch: Settings → Developer options → **ADB debugging** +
   **Debug over Wi-Fi** (note the IP:port).
2. From Toussaint:
   ```bash
   adb connect <watch-ip>:<port>
   adb install -r app/build/outputs/apk/release/app-release-unsigned.apk
   ```
   (An unsigned APK installs fine for personal debug use.)
3. Long-press the current face → **+ Add** → pick **Binary**.
4. Tap the gear on the face to toggle BCD mode / labels / colour.

## Publishing

**Google Play** — watch faces ship as normal apps (there's a "Watch face"
category). Needs a Play Console account ($25 one-time), a signed release
AAB/APK, a store listing + privacy policy (even though this collects nothing),
and it goes through review. Free or paid both fine. This is where essentially
all Wear OS watch-face distribution happens.

**F-Droid** — accepts FOSS Android apps, and a pure-WFF face is close to ideal
for it: no code, no dependencies, no network, no trackers. Requirements: public
source, an OSI license, reproducible build. Caveats: F-Droid's Wear OS install
path is clunky and watch-face discoverability there is near zero. A common
lighter first step is **IzzyOnDroid** (add-on repo, easier acceptance).

**Recommended:** license the repo (Apache-2.0 keeps it maximally reusable and
matches Google's own Wear samples; GPLv3 if you want copyleft), push to
GitHub/Codeberg, ship the *same signed APK* to Play and attach it to repo
releases + submit to IzzyOnDroid/F-Droid. A binary/BCD clock isn't novel IP —
several exist — but a clean generator-driven WFF one is a tidy open-source
contribution and portfolio piece.

Not applicable: Facer / WatchMaker are separate ecosystems with their own
creator tools, not WFF APKs.

## Validate before publishing

Google's WFF validator catches schema mistakes the build won't:
<https://github.com/google/watchface> → `wff` memory validator / format validator.

## Things to diff against the official sample

The **layout and bit-math are solid**; the WFF boilerplate is ~90% and worth
checking against
<https://github.com/android/wear-os-samples/tree/main/WatchFaceFormat>:

- `BooleanConfiguration` `defaultValue` casing (`TRUE`/`FALSE` vs `true`/`false`)
- `ColorConfiguration` reference syntax — is it `[CONFIGURATION.litColor]` or
  `[CONFIGURATION.litColor.0]`?
- whether a `preview` drawable is mandatory for the face to load
- `PartText` / `Font` element shape for the row labels
- target WFF version for Wear OS 5 (may want `format.version` = 3 or 4)

Spec: <https://developer.android.com/training/wearables/wff>

## Layout

```
BinaryWatchFace/
├── tools/gen_watchface.py      the spec + generator (edit this)
├── preview.html                generated — open in a browser
├── app/
│   ├── build.gradle.kts
│   └── src/main/
│       ├── AndroidManifest.xml
│       └── res/
│           ├── raw/watchface.xml    generated
│           └── values/strings.xml
├── settings.gradle.kts
├── build.gradle.kts
└── gradle.properties
```
