#!/bin/bash
# Build against an isolated copy of the exact running kernel's source/output.
set -euo pipefail
REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
: "${KERNEL_SRC:?Set KERNEL_SRC to the prepared kernel source directory}"
WORK=${SENSOR_IDLE_WORK:-$REPO/.build/sensors-idle}
export ARCH=arm64 CROSS_COMPILE=${CROSS_COMPILE:-aarch64-linux-gnu-}
mkdir -p "$WORK/sensors-driver" "$WORK/modules" "$WORK/compat"
"${CROSS_COMPILE}gcc" -shared -nostdlib -fPIC -Wl,-soname,libwakelock-no-suspend.so \
    -o "$WORK/compat/libwakelock-no-suspend.so" \
    "$REPO/experiments/sensors/compat/wakelock-no-suspend.c"
cp -a "$REPO/experiments/sensors/driver/." "$WORK/sensors-driver/"
cd "$KERNEL_SRC"
scripts/config --file out/.config -m IIO
make O=out olddefconfig modules_prepare
make O=out -j"${JOBS:-8}" drivers/iio/industrialio.ko
make O=out M="$WORK/sensors-driver" -j"${JOBS:-8}" modules
cp out/drivers/iio/industrialio.ko "$WORK/sensors-driver/"*.ko \
    "$WORK/modules/"
for module in "$WORK/modules/"{industrialio.ko,zrn-bbd.ko,s9plus-sensor-iio.ko}; do
    case "$(modinfo -F vermagic "$module")" in
        "$(cat out/include/config/kernel.release) "*) ;;
        *) echo "Wrong module ABI: $module" >&2; exit 1 ;;
    esac
done
(cd "$WORK/modules" && sha256sum ./industrialio.ko ./zrn-bbd.ko ./s9plus-sensor-iio.ko > SHA256SUMS)
