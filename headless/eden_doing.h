// SPDX-License-Identifier: GPL-3.0-or-later
// What a thread is doing in a call that can take long (a system call, a lock, a wait for the GPU).
// The hitch watch (crash_report.cpp, lab file tirones=N) prints it next to each thread it samples,
// and for a thread that does not take its signal it is the only trace: a thread stuck in the
// kernel (disk, memory mappings) answers no signal until it comes back.
//
// Named threads only (crash_report.h, NameThread); others do nothing. Safe in a signal handler:
// a table lookup, a clock read and atomic stores. The functions are weak so that code linked
// without the crash report (tests, tools) still builds.
#pragma once

// Also declared by Eglantine's common/fs/file.h (patch 0014), the same, under the same guard.
#ifndef EDEN_DOING_DEFINED
#define EDEN_DOING_DEFINED
extern "C" {
struct EdenDoing {
    const char* what;
    unsigned long long since_ms;
    void* entry;
};
void eden_doing_begin(EdenDoing* save, const char* what) __attribute__((weak));
void eden_doing_end(const EdenDoing* save) __attribute__((weak));
}
#endif
extern "C" {
// Names the calling thread for the crash report and the hitch watch (crash_report.h NameThread).
void eden_name_thread(const char* name) __attribute__((weak));
}

// Marks the thread as doing `what` until the end of the scope (nested scopes restore the outer one).
struct EdenDoingScope {
    EdenDoing save{};
    explicit EdenDoingScope(const char* what) noexcept {
        if (eden_doing_begin) eden_doing_begin(&save, what);
    }
    ~EdenDoingScope() {
        if (eden_doing_end) eden_doing_end(&save);
    }
    EdenDoingScope(const EdenDoingScope&) = delete;
    EdenDoingScope& operator=(const EdenDoingScope&) = delete;
};
