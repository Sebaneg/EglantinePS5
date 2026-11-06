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
// The size from which a heap block gets memory of its own (headless/heap_arenas.inc); 0: default.
extern "C" void eden_heap_set_large_request(std::size_t bytes) __attribute__((weak));
// How many 32 MiB pieces a growth of the heap takes at least (headless/heap_arenas.inc); 0: default.
extern "C" void eden_heap_set_grow_pieces(unsigned pieces) __attribute__((weak));
// The most arenas the heap makes for threads' small blocks (headless/heap_arenas.inc); 0: default.
extern "C" void eden_heap_set_arena_limit(unsigned limit) __attribute__((weak));

// The guest's memory service (src/guest_memory_service.inc), read by its scanner as it runs.
namespace Common {
void SetGuestMemoryService(bool on, bool scan, bool dedup) noexcept;
void SetGuestMemoryFine(bool on) noexcept;
void SetGuestMemoryReserve(std::size_t mib) noexcept;
void SetGuestMemorySwap(bool on, const char* path, unsigned cold_seconds) noexcept;
void SetGuestBlocksHigh(bool on) noexcept;
} // namespace Common

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
    ::Settings::AstcRecompression astc_recompression;
    bool vertex_input_dynamic;
    ::Settings::GpuClock gpu_clock;
    ::Settings::ExtendedDynamicState dyna_state;
    ::Settings::VSyncMode vsync;
    bool async_presentation;
    bool log_flush_line;
    ::Settings::AnisotropyMode anisotropy;
    ::Settings::AntiAliasing anti_aliasing;
    int fsr_sharpening;
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
        ::Settings::values.accelerate_astc.GetValue(), ::Settings::values.astc_recompression.GetValue(),
        ::Settings::values.vertex_input_dynamic_state.GetValue(),
        ::Settings::values.gpu_clock.GetValue(), ::Settings::values.dyna_state.GetValue(),
        ::Settings::values.vsync_mode.GetValue(), ::Settings::values.async_presentation.GetValue(),
        ::Settings::values.log_flush_line.GetValue(), ::Settings::values.max_anisotropy.GetValue(),
        ::Settings::values.anti_aliasing.GetValue(), ::Settings::values.fsr_sharpening_slider.GetValue()};
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
    ::Settings::values.astc_recompression.SetValue(d.astc_recompression);
    Common::SetGuestMemoryReserve(1024);
    Common::SetGuestMemorySwap(false, nullptr, 8);
    Common::SetGuestBlocksHigh(false);
    Performance::pool_usable_metric = false;
    Performance::short_memory_bytes = Performance::kShortMemory;
    ::Settings::values.vertex_input_dynamic_state.SetValue(d.vertex_input_dynamic);
    ::Settings::values.gpu_clock.SetValue(d.gpu_clock);
    ::Settings::values.dyna_state.SetValue(d.dyna_state);
    ::Settings::values.vsync_mode.SetValue(d.vsync);
    ::Settings::values.async_presentation.SetValue(d.async_presentation);
    ::Settings::values.log_flush_line.SetValue(d.log_flush_line);
    ::Settings::values.max_anisotropy.SetValue(d.anisotropy);
    ::Settings::values.anti_aliasing.SetValue(d.anti_aliasing);
    ::Settings::values.fsr_sharpening_slider.SetValue(d.fsr_sharpening);
    Performance::vulkan_cost_enabled = false;
    DevVulkan::present_frames = 0;
    DevVulkan::no_semaphore_latch = false;
    Common::SetGuestMemoryService(true, true, false);
    Common::SetGuestMemoryFine(false);
    if (eden_heap_set_large_request) eden_heap_set_large_request(0);
    if (eden_heap_set_grow_pieces) eden_heap_set_grow_pieces(0);
    if (eden_heap_set_arena_limit) eden_heap_set_arena_limit(0);
    // Task/mesh draws hang the GPU under RADV (Mario Kart World on the console, and on desktop
    // AMD GPUs: Djihads80/Eglantine#404), so they are skipped unless the lab file says mesh=on.
    // Eglantine reads this once, at the first draw of the app's run.
    SetVariable("EDEN_NX2_NO_MESH", "1");
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
    // The game's texture pools in GPU-only regions take its tiles as sparse regions do
    // (Eglantine patch 0005), instead of blocks of their own; read once per app start.
    else if (entry == "zonas_gpu_trozos=on") SetVariable("EDEN_NX2_GPU_ONLY_TILES", "1");
    // The smallest zone zonas_gpu_trozos takes (MiB, 286 to 1024; 1024 without this line).
    // The most device memory one layered terrain texture binds (MiB, 128 to 768; read once per app
    // start, Eglantine patch 0009).
    // The most memory ASTC conversion keeps in decode images (MiB, 0 to 2048; 192 without this
    // line, 0: no limit), read once per app start (Eglantine patch 0010).
    // The descriptor queues' payload, divided by N (1 to 8; 1 without this line): 96 MiB at 1, 24 at 4
    // (Eglantine patch 0011). Read when the renderer starts.
    else if (entry.starts_with("cola_descriptores=") && Number(entry, 18, n) && n >= 1 && n <= 8)
        SetVariable("EDEN_DESCRIPTOR_QUEUE_DIV", entry.c_str() + 18);
    else if (entry.starts_with("astc_temporal=") && Number(entry, 14, n) && n <= 2048)
        SetVariable("EDEN_NX2_TRANSCODE_INFLIGHT_MIB", entry.c_str() + 14);
    else if (entry.starts_with("capas_max=") && Number(entry, 10, n) && n >= 128 && n <= 768)
        SetVariable("EDEN_NX2_LAYERS_CAP_MIB", entry.c_str() + 10);
    else if (entry.starts_with("zonas_gpu_minimo=") && Number(entry, 17, n) && n >= 286 && n <= 1024)
        SetVariable("EDEN_NX2_GPU_ONLY_TILES_MIB", entry.c_str() + 17);
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
    // ASTC textures re-compressed to BC1 (8 bytes a block, alpha on or off) instead of BC3 (16).
    else if (entry == "astc_bc1=on") ::Settings::values.astc_recompression.SetValue(::Settings::AstcRecompression::Bc1);
    else if (entry == "vram=aggressive") ::Settings::values.vram_usage_mode.SetValue(::Settings::VramUsageMode::Aggressive);
    else if (entry == "vram=conservative") ::Settings::values.vram_usage_mode.SetValue(::Settings::VramUsageMode::Conservative);
    else if (entry == "gpu_clock=normal" || entry == "gpu_clock=boost" || entry == "gpu_clock=overclock")
        ::Settings::values.gpu_clock.SetValue(entry.ends_with("normal") ? ::Settings::GpuClock::Normal
                                            : entry.ends_with("boost") ? ::Settings::GpuClock::Boost
                                                                       : ::Settings::GpuClock::Overclock);
    else if (entry == "mesh=on") unsetenv("EDEN_NX2_NO_MESH");
    else if (entry == "mesh=off") SetVariable("EDEN_NX2_NO_MESH", "1");
    else if (entry == "atajo=off") DevVulkan::no_semaphore_latch = true;
    else if (entry == "atajo=on") DevVulkan::no_semaphore_latch = false;
    // The thread a freeze report shows (crash_report.cpp FreezeWatch): GPU unless named here.
    else if (entry.starts_with("congelamiento_hilo=") && entry.size() > 19)
        SetVariable("EDEN_FREEZE_THREAD", entry.c_str() + 19);
    // medir=on: what is needed to tell where a slow game's time goes, at a small cost. The Vulkan
    // calls that can block, timed into EDEN_TIMELINE2 (performance.cpp); the GPU thread's time by
    // zone every 10 s in eden_log.txt (Eglantine's Nx2Profile, read late by patch 0013); the texture
    // cache's numbers every 60 frames; and hitch samples after 700 ms (tirones=N still sets its own).
    // Not eden_log.txt line by line: each line was then a write to the SSD on the GPU thread, which
    // waited on it for seconds while the swap file was being written.
    else if (entry == "medir=on") {
        Performance::vulkan_cost_enabled = true;
        SetVariable("EDEN_NX2_GPU_PROFILE", "1");
        if (!std::getenv("EDEN_NX2_TC_LOG")) SetVariable("EDEN_NX2_TC_LOG", "60");
        if (!std::getenv("EDEN_HITCH_MS")) SetVariable("EDEN_HITCH_MS", "700");
    }
    // Hitch samples (crash_report.cpp HitchWatch): after N ms (300 to 10000) without a game frame,
    // where the GPU, Vulkan and guest core threads are, in EDEN_HITCH lines. Read as the game starts.
    else if (entry.starts_with("tirones=") && Number(entry, 8, n) && n >= 300 && n <= 10000)
        SetVariable("EDEN_HITCH_MS", entry.c_str() + 8);
    // Picture quality, read when the game's renderer starts. anisotropico=N (2, 4, 8 or 16; 0: what the
    // game asks): textures seen at an angle (the track ahead) stay sharp. aa=off|fxaa|smaa: the
    // anti-aliasing pass on the output (fxaa without the line). nitidez_fsr=N (0 to 200, 25 without the
    // line): how much the AMD FSR filter (Settings > Video) sharpens what it scales up.
    else if (entry.starts_with("anisotropico=") && Number(entry, 13, n) && (n == 0 || n == 2 || n == 4 || n == 8 || n == 16))
        ::Settings::values.max_anisotropy.SetValue(n == 0 ? ::Settings::AnisotropyMode::Default
                                                 : n == 2 ? ::Settings::AnisotropyMode::X2
                                                 : n == 4 ? ::Settings::AnisotropyMode::X4
                                                 : n == 8 ? ::Settings::AnisotropyMode::X8
                                                          : ::Settings::AnisotropyMode::X16);
    else if (entry == "aa=off") ::Settings::values.anti_aliasing.SetValue(::Settings::AntiAliasing::None);
    else if (entry == "aa=fxaa") ::Settings::values.anti_aliasing.SetValue(::Settings::AntiAliasing::Fxaa);
    else if (entry == "aa=smaa") ::Settings::values.anti_aliasing.SetValue(::Settings::AntiAliasing::Smaa);
    else if (entry.starts_with("nitidez_fsr=") && Number(entry, 12, n) && n <= 200)
        ::Settings::values.fsr_sharpening_slider.SetValue(static_cast<int>(n));
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
    // The game's memory: memoria_compacta keeps only the written 16 KiB pages of a 2 MiB block that
    // holds many pages of zeroes; bloques_repetidos shares 2 MiB blocks with the same contents.
    else if (entry == "memoria_compacta=on" || entry == "memoria_compacta=off")
        Common::SetGuestMemoryFine(entry.ends_with("on"));
    // The game's headroom (MiB, 32 to 1024; 1024 without this line): blocks held for its writes.
    // The game's memory nothing touched goes to a file on the SSD while memory is short, and comes
    // back when it is touched (src/guest_memory_service.inc, "Swap"). swap_frio=N: seconds a block
    // must go untouched first (2 to 120; 8 without the line). Both read as the game starts.
    // Graphics memory: memoria_util=on measures what graphics can use as the pool's free stretches of
    // 16 MiB or more together; memoria_corta=N (MiB, 128 to 1024; 1024 without it) is the mark under
    // which the caches see memory short; margen_texturas=N (MiB, 0 to 3072; 3072 without it) is the
    // most room the texture cache keeps free after images did not fit (Eglantine patch 0012).
    else if (entry == "memoria_util=on" || entry == "memoria_util=off")
        Performance::pool_usable_metric = entry.ends_with("on");
    else if (entry.starts_with("memoria_corta=") && Number(entry, 14, n) && n >= 128 && n <= 1024)
        Performance::short_memory_bytes = static_cast<std::size_t>(n) << 20;
    else if (entry.starts_with("margen_texturas=") && Number(entry, 16, n) && n <= 3072)
        SetVariable("EDEN_NX2_TC_PRESSURE_MAX_MIB", entry.c_str() + 16);
    // The game's 2 MiB blocks from the top of the pool, apart from the graphics' memory
    // (src/memory_pages.cpp, GuestDirect).
    else if (entry == "juego_arriba=on" || entry == "juego_arriba=off")
        Common::SetGuestBlocksHigh(entry.ends_with("on"));
    else if (entry == "swap=on" || entry == "swap=off") {
        static const std::string path = std::string{Eden::kDataDir} + "/swap_juego.bin";
        Common::SetGuestMemorySwap(entry.ends_with("on"), path.c_str(), 0);
    } else if (entry.starts_with("swap_frio=") && Number(entry, 10, n) && n >= 2 && n <= 120)
        SetVariable("EDEN_SWAP_COLD_SECONDS", entry.c_str() + 10);
    // swap_caliente=N: seconds a block read back from the swap file stays in memory (a quarter of it
    // for one touched on probation); 0 to 3600, 120 without the line, 0 as before. Read as the game starts.
    // swap_bloque=on: the swapper also writes to make the pool's largest block larger (juego_arriba=on), as
    // before; off without the line. Read as the game starts.
    else if (entry == "swap_bloque=on") SetVariable("EDEN_SWAP_FOR_BLOCK", "1");
    // swap_intermedio=off: the swap file is written and read straight from the guest's slots, without the
    // bounce buffers (src/guest_memory_service.inc). Read as the game starts.
    else if (entry == "swap_intermedio=off") SetVariable("EDEN_SWAP_BOUNCE", "0");
    // swap_comprimido=off: slots sent out go to the swap file only, not compressed into memory first
    // (src/guest_memory_service.inc, "The swap in memory"). Read as the game starts.
    else if (entry == "swap_comprimido=off") SetVariable("EDEN_SWAP_COMPRESS", "0");
    // atajos_bufer=off: no effect since Lichii (Eglantine patch 0016 left: Lichii skips clean buffers
    // itself); kept so older lab files still read.
    else if (entry == "atajos_bufer=off") {}
    // gpu_dos_hilos=off: the GPU thread stays one thread even with gpu_accuracy=low (EDEN_NX2_SPLIT=0).
    else if (entry == "gpu_dos_hilos=off") SetVariable("EDEN_NX2_SPLIT", "0");
    // terrenos_bc=off|bc1: the huge ASTC arrays (title 1's 8192x8192x68 terrain) stay RGBA8 on the host as
    // before, or all go to BC1; BC3 without the line (BC1 for opaque ones). Eglantine patch 0021. Read once.
    else if (entry == "terrenos_bc=off") SetVariable("EDEN_NX2_HUGE_ASTC_BC", "0");
    else if (entry == "terrenos_bc=bc1") SetVariable("EDEN_NX2_HUGE_ASTC_BC", "bc1");
    // texturas_recientes=N: the texture cache keeps images used in the last N ms (0 to 10000; 2000 without
    // the line, 0: by frames only, as before) unless device memory is 512 MiB past its critical
    // threshold. Eglantine patch 0022. Read once.
    else if (entry.starts_with("texturas_recientes=") && Number(entry, 19, n) && n <= 10000)
        SetVariable("EDEN_NX2_TC_KEEP_MS", entry.c_str() + 19);
    // bufer_max=N: the largest buffer the buffer cache makes by joining overlapping ones (MiB, 0 to
    // 4096; 256 without the line, 0: no limit, as before). Eglantine patch 0015; read once per app start.
    else if (entry.starts_with("bufer_max=") && Number(entry, 10, n) && n <= 4096)
        SetVariable("EDEN_BUFFER_JOIN_MAX_MIB", entry.c_str() + 10);
    else if (entry.starts_with("swap_caliente=") && Number(entry, 14, n) && n <= 3600)
        SetVariable("EDEN_SWAP_HOT_SECONDS", entry.c_str() + 14);
    else if (entry.starts_with("reserva_juego=") && Number(entry, 14, n))
        Common::SetGuestMemoryReserve(static_cast<std::size_t>(n));
    else if (entry == "bloques_repetidos=on" || entry == "bloques_repetidos=off")
        Common::SetGuestMemoryService(true, true, entry.ends_with("on"));
    // The emulator's heap: blocks of this many MiB or more (2 to 32) get memory of their own,
    // which goes back to the console when they are freed instead of leaving a hole in the heap.
    else if (entry.starts_with("heap_bloque_propio=") && Number(entry, 19, n) && n >= 2 && n <= 32 &&
             eden_heap_set_large_request)
        eden_heap_set_large_request(static_cast<std::size_t>(n) << 20);
    // The heap grows by this many MiB (32, 64, 96 or 128; 128 without this line). Smaller growths
    // empty more often, and an empty one goes back to the console.
    else if (entry.starts_with("heap_trozo=") && Number(entry, 11, n) && n >= 32 && n <= 128 && n % 32 == 0 &&
             eden_heap_set_grow_pieces)
        eden_heap_set_grow_pieces(static_cast<unsigned>(n / 32));
    // Each guest thread's stack (KiB, 256 to 2048; 2048 without this line), read as the game makes
    // its threads (Eglantine patch 0008).
    // The most arenas (8 MiB each, kept for good) the heap makes for threads' small blocks (8 to
    // 256; 256 without this line). Past it, threads share the arenas there are.
    else if (entry.starts_with("heap_arenas=") && Number(entry, 12, n) && n >= 8 && n <= 256 &&
             eden_heap_set_arena_limit)
        eden_heap_set_arena_limit(static_cast<unsigned>(n));
    else if (entry.starts_with("pila_hilos=") && Number(entry, 11, n) && n >= 256 && n <= 2048)
        SetVariable("EDEN_FIBER_STACK_KIB", entry.c_str() + 11);
    // The code cache of guest cores 3-5 (MiB, 16 to 128 in steps of 16; 16 without this line).
    else if (entry.starts_with("jit_nucleos=") && Number(entry, 12, n) && n >= 16 && n <= 128 && n % 16 == 0)
        SetVariable("EDEN_JIT_CORE_MIB", entry.c_str() + 12);
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
    // mkw_30fps=on: Mario Kart World runs its own 30 FPS frame mode (the one of its split screen), with the
    // game at full speed: half the frames to make for each second of play. mkw_fps_dinamico=on: the game
    // picks 60 or 30 from its whole frame time (experimental). Read when the game loads (loader/nso.cpp).
    else if (entry == "mkw_30fps=on") ::Settings::values.mkw_30fps.SetValue(true);
    else if (entry == "mkw_fps_dinamico=on") ::Settings::values.mkw_dynamic_fps.SetValue(true);
    else return false;
    return true;
}

} // namespace Eden::Lab
