# Android dev environment setup (Toussaint)

Current state (2026-08-29): SDK at `/data/burney/Android/Sdk` is stale —
platforms top out at `android-30`, build-tools `30.0.2` / `31.0.0-rc2`, only
the legacy `tools/` (no `cmdline-tools/`), `adb` 1.0.41. JDK is OpenJDK 21
(fine — AGP 8.5 wants 17–21). No `gradle` on PATH.

Watch Face Format needs **compileSdk 33+**. Target here: platform 34,
build-tools 34.0.0, current platform-tools, Gradle 8.9.

> Disk: Toussaint was ~88% full — the runaway `/var/log/syslog` cleanup
> (Sèvo inbox) is worth doing first; the SDK packages below add ~1–2 GB.

## Path A — command-line only (recommended for this box)

### 1. Command-line tools
Download the current **"Command line tools only"** zip for Linux from
<https://developer.android.com/studio> (build number changes; grab whatever is
current).

```bash
SDK=/data/burney/Android/Sdk
mkdir -p "$SDK/cmdline-tools"
cd "$SDK/cmdline-tools"
unzip ~/Downloads/commandlinetools-linux-*_latest.zip   # -> ./cmdline-tools/
mv cmdline-tools latest                                  # must be named 'latest'
# result: $SDK/cmdline-tools/latest/bin/sdkmanager
```

### 2. Environment (add to ~/.bashrc)
```bash
export ANDROID_HOME=/data/burney/Android/Sdk
export ANDROID_SDK_ROOT=$ANDROID_HOME
export PATH="$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/platform-tools:$PATH"
```
Then `source ~/.bashrc`.

### 3. SDK packages
```bash
yes | sdkmanager --licenses
sdkmanager --update
sdkmanager "platform-tools" "platforms;android-34" "build-tools;34.0.0"
adb version        # should now report ~35.x
```

### 4. Gradle 8.9
Via SDKMAN:
```bash
curl -s "https://get.sdkman.io" | bash && source ~/.sdkman/bin/sdkman-init.sh
sdk install gradle 8.9
```
…or unzip `gradle-8.9-bin.zip` under `/opt/gradle/` and add its `bin/` to PATH.

### 5. Wire up the project + generate the wrapper
```bash
cd /data/BUSINESS/Burnilab/BinaryWatchFace
echo "sdk.dir=/data/burney/Android/Sdk" > local.properties
gradle wrapper --gradle-version 8.9      # one time; afterwards use ./gradlew
```

### 6. Build
```bash
./gradlew :app:assembleRelease
# -> app/build/outputs/apk/release/app-release-unsigned.apk
```

## Path B — Android Studio (heavier, foolproof)

Download from <https://developer.android.com/studio>, extract, run
`bin/studio.sh`. It bundles its own JDK + Gradle. Let it install SDK 34 /
build-tools 34 (point it at the existing `/data/burney/Android/Sdk` or a new
location). Open the `BinaryWatchFace` folder → it syncs and offers to create
the Gradle wrapper → **Build ▸ Build Bundle(s)/APK(s) ▸ Build APK(s)**.

## Install on the Pixel Watch 5 (wireless — no USB port)

```bash
# Watch: Settings ▸ System ▸ Developer options ▸ enable "ADB debugging"
#        and "Wireless debugging" ▸ note the IP and both ports
adb pair    <watch-ip>:<pair-port>     # enter the 6-digit code shown on watch
adb connect <watch-ip>:<debug-port>
adb devices                            # confirm it's listed
adb -s <watch-ip>:<debug-port> install -r \
    app/build/outputs/apk/release/app-release-unsigned.apk
```
On the watch: long-press the current face ▸ **+ Add** ▸ **Binary** ▸ tap the
gear to toggle BCD / labels / colour.

## Optional — WFF validator

Catches schema errors the build won't. Module `wff` in
<https://github.com/google/watchface> — build it or grab a release jar, then
run it against `app/src/main/res/raw/watchface.xml`.
