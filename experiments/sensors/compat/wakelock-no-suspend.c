// SPDX-License-Identifier: GPL-2.0
/* The vendor lhd calls Android's legacy wakelock API, whose modern provider
 * waits forever for Android's system-suspend service. Ubuntu deliberately
 * masks all system-sleep targets on this port. Only in that configuration,
 * satisfy these two calls inside lhd's private runtime. No libc dependency.
 */
int acquire_wake_lock(int lock, const char *id)
{
 return 0;
}

int release_wake_lock(const char *id)
{
 return 0;
}
