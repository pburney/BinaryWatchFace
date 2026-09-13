# Android dev environment setup (Toussaint)

Current state (2026-09-13): **Android Studio is installed**
(`/home/developer/bin/android-studio`) and its bundled SDK manager has already
provisioned a working SDK at `~/Android/Sdk` — platform `android-37.0`,
build-tools `36.0.0`, current `platform-tools` (`adb` 37.0.1). That's well
past the `compileSdk 34` / WFF-33+ requirement, so **no manual `sdkmanager`
bootstrap is needed** — the steps below that used to target the stale
`/data/burney/Android/Sdk` (capped at platform 30) are obsolete now that
Studio's own SDK exists.

`local.properties` (gitignored, not committed) points at it:
```
sdk.dir=/home/developer/Android/Sdk
```

## Gradle

No system `gradle` and no bundled Studio Gradle binary on `PATH`. The
project's Gradle **wrapper is committed** (`./gradlew`, `gradle/wrapper/`,
pinned to 8.9) — just run `./gradlew :app:assembleDebug` (or `assembleRelease`
for a signed-for-store build later). If the wrapper is ever regenerated:
```bash
# one-time, only if gradlew is missing/corrupted
curl -Lo /tmp/gradle-8.9-bin.zip https://services.gradle.org/distributions/gradle-8.9-bin.zip
unzip /tmp/gradle-8.9-bin.zip -d ~/opt/gradle
cd /data/BUSINESS/Burnilab/BinaryWatchFace
~/opt/gradle/gradle-8.9/bin/gradle wrapper --gradle-version 8.9
```

## Build

```bash
cd /data/BUSINESS/Burnilab/BinaryWatchFace
./gradlew :app:assembleDebug
# -> app/build/outputs/apk/debug/app-debug.apk
```

Use the **debug** build for sideloading — a fully unsigned `assembleRelease`
APK fails to install on-device (`INSTALL_PARSE_FAILED_NO_CERTIFICATES`).
AGP auto-signs debug builds with a default debug keystore, which real
devices accept fine. Release signing for Play Store submission is a
separate, later step (see README's Publishing section).

## Install on the Pixel Watch (wireless — no USB port)

```bash
# Watch: Settings -> System -> About -> tap "Build number" 7x to unlock
#        Developer options, then enable "ADB debugging" and
#        "Wireless debugging" -> "Pair new device" for a pairing IP:port + code
ADB=/home/developer/Android/Sdk/platform-tools/adb
$ADB pair <watch-ip>:<pair-port>      # 6-digit code shown on watch
$ADB devices -l                        # confirms it (often auto-connects via mDNS)
$ADB install -r app/build/outputs/apk/debug/app-debug.apk
```
On the watch: long-press the current face -> **+ Add** -> **Binary** -> tap
the gear to toggle BCD / labels / colour.

## Gotcha: watch face not appearing in the gallery after install

If `adb install` succeeds but the face never shows up when you long-press to
add a new one, check logcat for:
```
adb logcat -d | grep DeclarativeWatchFaceResolver
# W WearServices: [DeclarativeWatchFaceResolver] ... could not be parsed - Resource ID #0x0
```
The fix (found 2026-09-13): **`app/src/main/res/xml/watch_face_info.xml` is
required** — it's a separate file from `res/raw/watchface.xml`, auto-discovered
by name, and declares the gallery preview image:
```xml
<WatchFaceInfo>
    <Preview value="@drawable/preview" />
    <Category value="CATEGORY_EMPTY" />
    <AvailableInRetail value="true" />
    <MultipleInstancesAllowed value="false" />
    <Editable value="true" />
</WatchFaceInfo>
```
Without it, the on-device resolver fails at the gallery-listing step with the
generic `Resource ID #0x0` error above, even though the app installs cleanly,
`res/raw/watchface.xml` compiles fine, and the manifest's own
`com.google.android.wearable.watchface.preview` meta-data is present and
valid. This isn't documented as a hard requirement anywhere obvious — it was
found by installing Google's own `watchface` XSD validator
(`github.com/google/watchface`, `third_party/wff`) and confirming our XML
validated clean while the device still failed the same way, which pointed at
something outside `watchface.xml` entirely.

## Validating watchface.xml offline

Before any device round-trip, validate the generated XML against Google's
official schema — much faster than a rebuild+reinstall+logcat cycle:
```bash
git clone --depth 1 https://github.com/google/watchface.git /tmp/wff-validator-src
cd /tmp/wff-validator-src/third_party/wff/specification/validator
mkdir out
javac -cp "$(find libs -name '*.jar' | tr '\n' ':')" -d out $(find src/main -name '*.java')
(cd ../documents && zip -qr ../validator/out/docs.zip .)
java -cp "$(find libs -name '*.jar' | tr '\n' ':')out" \
  com.samsung.watchface.DWFValidationApplication 4 \
  /data/BUSINESS/Burnilab/BinaryWatchFace/app/src/main/res/raw/watchface.xml
```
(The `./gradlew :specification:validator:executable-jar` path from the repo's
own README works too, but building it via its own Gradle project can OOM this
box when other apps are already heavy on memory — the direct `javac` +
manual `docs.zip` above sidesteps that.)

Two schema issues this caught that are worth knowing about if you touch
`tools/gen_watchface.py`'s WFF-generation code:
- **`alpha` cannot take a `[CONFIGURATION.x] ? a : b` expression or any other
  arithmetic expression** — its declared type is a static 0-255 value only.
  Config-driven mode switching (BCD vs binary, labels on/off) uses a
  `BooleanConfiguration`/`BooleanOption` structural wrapper instead; per-bit
  LED lighting (which genuinely needs a live clock-driven expression) uses a
  `Condition`/`Expressions`/`Compare` block instead of a computed `alpha`.
- **`displayName` attributes inside `res/raw/watchface.xml` use bare string
  resource names** (`displayName="cfg_bcd"`), not the normal Android
  `@string/cfg_bcd` syntax — raw resources bypass AAPT's binary XML
  compilation, so the WFF runtime resolves these itself and expects the bare
  name, matching `res/values/strings.xml`.

## Optional — WFF validator via Android Studio

Android Studio, once it's opened on this project at least once, can also run
the same schema validation through its own tooling. The manual `javac` route
above is what was actually used and doesn't require opening the IDE.
