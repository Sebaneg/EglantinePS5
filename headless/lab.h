// SPDX-License-Identifier: GPL-3.0-or-later
// Lab file: switches a player tries on the console without a new build. /data/eglantineps5/
// laboratorio.txt, one switch per line ('#' starts a comment), read before each game; the guide
// is docs/LABORATORIO.md. A switch left out of the file has its normal value again in the next
// game (log filters excepted: those last until the app restarts). Each line read is reported,
// so the log says what a session ran with.
#pragma once
#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <string>
#include <vector>
#include "common/logging.h"
#include "common/settings.h"
#include "dev_vulkan.h"
#include "diagnostics.h"
#include "jit_list.h"
#include "performance.h"
#include "storage_paths.h"
#include "../src/fastmem.h"

extern "C" bool eden_jit_shared;  // headless/dynarmic/jit_group_support.inc

namespace Eden::Lab {

inline std::string Path() { return std::string{Eden::kDataDir} + "/laboratorio.txt"; }

// Environment variables a lab line set (radv_debug=, env=): unset again before the next game.
inline std::vector<std::string>& SetVariables() {
    static std::vector<std::string> names;
    return names;
}

inline void SetVariable(const std::string& name, const char* value) {
    setenv(name.c_str(), value, 1);
    SetVariables().push_back(name);
}

// The values the switches change, as the app has them before any lab file.
struct Defaults {
    bool null_descriptor, descriptor_buffer, robustness2, trace_pipelines, sparse, multi_range,
        custom_border, sync_submissions, gpu_time, conditional_rendering, compute_barriers,
        sparse_tiles, skip_tessellation, jit_shared, gc_keep_dirty, graphics_usage_from_pool;
    int hcr_mode;
    unsigned cache_lock_spins, idle_spin_iterations, dispatch_mask;
    ::Settings::AstcDecodeMode astc;
    bool vertex_input_dynamic;
    ::Settings::GpuClock gpu_clock;
    ::Settings::ExtendedDynamicState dyna_state;
    ::Settings::VSyncMode vsync;
    bool async_presentation;
};

inline const Defaults& Initial() {
    static const Defaults d{
        DevVulkan::disable_null_descriptor, DevVulkan::disable_descriptor_buffer,
        DevVulkan::robustness2, DevVulkan::trace_pipelines, DevVulkan::disable_sparse,
        DevVulkan::disable_multi_range, DevVulkan::disable_custom_border,
        DevVulkan::sync_submissions, DevVulkan::gpu_time,
        DevVulkan::disable_conditional_rendering, DevVulkan::compute_barriers,
        DevVulkan::sparse_tiles, DevVulkan::skip_tessellation, eden_jit_shared,
        Performance::gc_keep_dirty.load(), Performance::graphics_usage_from_pool.load(),
        DevVulkan::hcr_mode, Performance::cache_lock_spins.load(),
        Performance::idle_spin_iterations.load(), Performance::dispatch_mask.load(),
        ::Settings::values.accelerate_astc.GetValue(),
        ::Settings::values.vertex_input_dynamic_state.GetValue(),
        ::Settings::values.gpu_clock.GetValue(), ::Settings::values.dyna_state.GetValue(),
        ::Settings::values.vsync_mode.GetValue(), ::Settings::values.async_presentation.GetValue()};
    return d;
}

inline void Restore() {
    for (const auto& name : SetVariables()) unsetenv(name.c_str());
    SetVariables().clear();
    const Defaults& d = Initial();
    DevVulkan::disable_null_descriptor = d.null_descriptor;
    DevVulkan::disable_descriptor_buffer = d.descriptor_buffer;
    DevVulkan::robustness2 = d.robustness2;
    DevVulkan::trace_pipelines = d.trace_pipelines;
    DevVulkan::disable_sparse = d.sparse;
    DevVulkan::disable_multi_range = d.multi_range;
    DevVulkan::disable_custom_border = d.custom_border;
    DevVulkan::sync_submissions = d.sync_submissions;
    DevVulkan::gpu_time = d.gpu_time;
    DevVulkan::disable_conditional_rendering = d.conditional_rendering;
    DevVulkan::compute_barriers = d.compute_barriers;
    DevVulkan::sparse_tiles = d.sparse_tiles;
    DevVulkan::skip_tessellation = d.skip_tessellation;
    DevVulkan::skip_programs.clear();
    DevVulkan::hcr_mode = d.hcr_mode;
    eden_jit_shared = d.jit_shared;
    Performance::gc_keep_dirty = d.gc_keep_dirty;
    Performance::graphics_usage_from_pool = d.graphics_usage_from_pool;
    Performance::cache_lock_spins = d.cache_lock_spins;
    Performance::idle_spin_iterations = d.idle_spin_iterations;
    Performance::dispatch_mask = d.dispatch_mask;
    ::Settings::values.accelerate_astc.SetValue(d.astc);
    ::Settings::values.vertex_input_dynamic_state.SetValue(d.vertex_input_dynamic);
    ::Settings::values.gpu_clock.SetValue(d.gpu_clock);
    ::Settings::values.dyna_state.SetValue(d.dyna_state);
    ::Settings::values.vsync_mode.SetValue(d.vsync);
    ::Settings::values.async_presentation.SetValue(d.async_presentation);
    DevVulkan::present_frames = 0;
}

// The lines of the lab file, without comments, blanks and trailing spaces.
inline std::vector<std::string> Read() {
    std::vector<std::string> entries;
    std::ifstream file(Path());
    for (std::string line; std::getline(file, line);) {
        if (const auto hash = line.find('#'); hash != std::string::npos) line.erase(hash);
        while (!line.empty() && (line.back() == '\r' || line.back() == ' ' || line.back() == '\t'))
            line.pop_back();
        const auto start = line.find_first_not_of(" \t");
        if (start == std::string::npos) continue;
        entries.push_back(line.substr(start));
    }
    return entries;
}

inline bool Number(const std::string& entry, std::size_t at, unsigned long& value) {
    if (at >= entry.size()) return false;
    char* end = nullptr;
    value = std::strtoul(entry.c_str() + at, &end, 10);
    return end != entry.c_str() + at && *end == '\0';
}

// Before the session's own settings. block_list_set: a jit_list line decided the block list.
// Returns whether the entry is one of these switches.
inline bool ApplyEarly(const std::string& entry, bool& block_list_set) {
    unsigned long n = 0;
    // Graphics (Vulkan).
    if (entry == "teselacion=off") DevVulkan::skip_tessellation = true;
    else if (entry == "teselacion=on") DevVulkan::skip_tessellation = false;
    else if (entry.starts_with("saltar_programa=")) {
        // A stage hash as pipeline_trace=on lists it, with or without 0x.
        std::string hex = entry.substr(16);
        if (hex.starts_with("0x") || hex.starts_with("0X")) hex.erase(0, 2);
        char* end = nullptr;
        const unsigned long long hash = std::strtoull(hex.c_str(), &end, 16);
        if (hex.empty() || hash == 0 || *end != '\0') return false;
        DevVulkan::skip_programs.push_back(hash);
    } else if (entry == "dispersas=on") DevVulkan::sparse_tiles = true;
    else if (entry == "dispersas=off") DevVulkan::sparse_tiles = false;
    else if (entry == "sparse=off") DevVulkan::disable_sparse = true;
    else if (entry == "multirange=off") DevVulkan::disable_multi_range = true;
    else if (entry == "null_descriptor=off") DevVulkan::disable_null_descriptor = true;
    else if (entry == "descriptor_buffer=off") DevVulkan::disable_descriptor_buffer = true;
    else if (entry == "robustness2=on") DevVulkan::robustness2 = true;
    else if (entry == "custom_border=on") DevVulkan::disable_custom_border = false;
    else if (entry == "custom_border=off") DevVulkan::disable_custom_border = true;
    else if (entry == "conditional_rendering=off") DevVulkan::disable_conditional_rendering = true;
    else if (entry == "conditional_rendering=on") DevVulkan::disable_conditional_rendering = false;
    else if (entry == "compute_barriers=off") DevVulkan::compute_barriers = false;
    else if (entry == "hcr=eden" || entry == "hcr=exact" || entry == "hcr=cpu")
        DevVulkan::hcr_mode = entry == "hcr=eden" ? 0 : entry == "hcr=exact" ? 1 : 2;
    else if (entry == "submit_sync=on") DevVulkan::sync_submissions = true;
    else if (entry == "gpu_time=on") DevVulkan::gpu_time = true;
    else if (entry == "pipeline_trace=on") DevVulkan::trace_pipelines = true;
    else if (entry == "vertex_input_dynamic=off") ::Settings::values.vertex_input_dynamic_state.SetValue(false);
    else if (entry.starts_with("dyna_state=") && entry.size() == 12 && entry[11] >= '0' && entry[11] <= '3')
        ::Settings::values.dyna_state.SetValue(static_cast<::Settings::ExtendedDynamicState>(entry[11] - '0'));
    else if (entry == "astc=cpu") ::Settings::values.accelerate_astc.SetValue(::Settings::AstcDecodeMode::Cpu);
    else if (entry == "astc=gpu") ::Settings::values.accelerate_astc.SetValue(::Settings::AstcDecodeMode::Gpu);
    else if (entry == "vram=aggressive") ::Settings::values.vram_usage_mode.SetValue(::Settings::VramUsageMode::Aggressive);
    else if (entry == "vram=conservative") ::Settings::values.vram_usage_mode.SetValue(::Settings::VramUsageMode::Conservative);
    else if (entry == "gpu_clock=normal" || entry == "gpu_clock=boost" || entry == "gpu_clock=overclock")
        ::Settings::values.gpu_clock.SetValue(entry.ends_with("normal") ? ::Settings::GpuClock::Normal
                                            : entry.ends_with("boost") ? ::Settings::GpuClock::Boost
                                                                       : ::Settings::GpuClock::Overclock);
    // Presentation: how finished frames reach the TV, read when the game's renderer starts.
    else if (entry == "vsync=fifo") ::Settings::values.vsync_mode.SetValue(::Settings::VSyncMode::Fifo);
    else if (entry == "vsync=mailbox") ::Settings::values.vsync_mode.SetValue(::Settings::VSyncMode::Mailbox);
    else if (entry == "vsync=immediate") ::Settings::values.vsync_mode.SetValue(::Settings::VSyncMode::Immediate);
    else if (entry == "vsync=relaxed") ::Settings::values.vsync_mode.SetValue(::Settings::VSyncMode::FifoRelaxed);
    else if (entry == "presentacion_hilo=on" || entry == "presentacion_hilo=off")
        ::Settings::values.async_presentation.SetValue(entry.ends_with("on"));
    else if (entry.starts_with("imagenes=") && Number(entry, 9, n) && n >= 1 && n <= 7)
        DevVulkan::present_frames = static_cast<unsigned>(n);
    else if (entry == "graphics_usage=driver") Performance::graphics_usage_from_pool = false;
    else if (entry == "gc_dirty=upstream") Performance::gc_keep_dirty = false;
    else if (entry.starts_with("dispatch_draws=") && Number(entry, 15, n) && n >= 8 && n <= 512 && (n & (n - 1)) == 0)
        Performance::dispatch_mask = static_cast<unsigned>(n - 1);
    // The driver (RADV), read when the device is made: radv_debug=syncshaders,hang and the like.
    else if (entry.starts_with("radv_debug=")) SetVariable("RADV_DEBUG", entry.c_str() + 11);
    else if (entry.starts_with("env=") && entry.find('=', 4) != std::string::npos) {
        const auto split = entry.find('=', 4);
        SetVariable(entry.substr(4, split - 4), entry.c_str() + split + 1);
    }
    // CPU and memory.
    else if (entry == "fastmem=on" || entry == "fastmem=off") Fastmem::Request(entry.ends_with("on"));
    else if (entry == "jit_list=on" || entry == "jit_list=off") {
        JitList::enabled = entry.ends_with("on");
        block_list_set = true;
    } else if (entry == "jit_shared=off") eden_jit_shared = false;
    else if (entry.starts_with("cache_spin=") && Number(entry, 11, n)) Performance::cache_lock_spins = static_cast<unsigned>(n);
    else if (entry.starts_with("idle_spin_us=") && Number(entry, 13, n)) Performance::idle_spin_iterations = static_cast<unsigned>(n * 50);
    // Logs: every Eden filter, '+' for spaces (log_filter=*:Info+Render.Vulkan:Debug).
    else if (entry == "log=render" || entry.starts_with("log_filter=")) {
        std::string text = entry == "log=render"
                               ? "*:Info Render:Debug Render.Vulkan:Debug HW.GPU:Debug Shader:Debug"
                               : entry.substr(11);
        std::replace(text.begin(), text.end(), '+', ' ');
        Common::Log::Filter filter;
        filter.ParseFilterString(text);
        Common::Log::SetGlobalFilter(filter);
    } else return false;
    return true;
}

// After the session's own speed settings (Settings > Performance), which it would otherwise undo.
inline bool ApplyLate(const std::string& entry) {
    const auto on = entry.ends_with("=on");
    if (entry == "async_shaders=on" || entry == "async_shaders=off")
        ::Settings::values.use_asynchronous_shaders.SetValue(on);
    else if (entry == "reactive_flushing=on" || entry == "reactive_flushing=off")
        ::Settings::values.use_reactive_flushing.SetValue(on);
    else if (entry == "skip_invalidation=on" || entry == "skip_invalidation=off")
        ::Settings::values.skip_cpu_inner_invalidation.SetValue(on);
    else if (entry == "gpu_accuracy=low") {
        // Nothing calls UpdateGPUAccuracy() here; set the live value too.
        ::Settings::values.gpu_accuracy.SetValue(::Settings::GpuAccuracy::Low);
        ::Settings::values.current_gpu_accuracy = ::Settings::GpuAccuracy::Low;
    } else if (entry == "gpu_accuracy=high") {
        ::Settings::values.gpu_accuracy.SetValue(::Settings::GpuAccuracy::High);
        ::Settings::values.current_gpu_accuracy = ::Settings::GpuAccuracy::High;
    } else if (entry == "cpu_accuracy=unsafe") ::Settings::values.cpu_accuracy = ::Settings::CpuAccuracy::Unsafe;
    else if (entry == "cpu_accuracy=auto") ::Settings::values.cpu_accuracy = ::Settings::CpuAccuracy::Auto;
    else if (entry == "dma_accuracy=unsafe") ::Settings::values.dma_accuracy.SetValue(::Settings::DmaAccuracy::Unsafe);
    else if (entry == "dma_accuracy=default") ::Settings::values.dma_accuracy.SetValue(::Settings::DmaAccuracy::Default);
    else return false;
    return true;
}

} // namespace Eden::Lab
