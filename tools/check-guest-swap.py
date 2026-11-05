#!/usr/bin/env python3
"""Host check of the guest memory's swap (src/guest_memory_service.inc, "Swap").

src/memory_pages.cpp is built as on the console (PS5_NATIVE) over a stand-in for the console's
direct memory: a memory file is the pool, a mapping of a part of it is a mapping of direct memory,
and a reserved range is an inaccessible one. The guest's memory is taken backed where used, slots
are written with a pattern, the pool is made to look short so that the swapper puts them on
probation and sends them to the swap file, and then eight threads read and write them back while
the pool looks plentiful again: every byte must be as it was written, every slot Own again, and
the memory the slots held must go back while they are in the file. A slot cleared while it is in
the file reads zeroes, and the session ends with the file's places given back.
"""
import pathlib
import subprocess
import sys
import tempfile

root = pathlib.Path(__file__).resolve().parents[1]

MOCK = r'''
#ifndef _GNU_SOURCE
#define _GNU_SOURCE
#endif
#include <atomic>
#include <cerrno>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fcntl.h>
#include <mutex>
#include <sys/mman.h>
#include <unistd.h>
#include <vector>

// The console's pool: a memory file, handed out in 16 KiB pages.
namespace mock {
constexpr std::size_t Pool = std::size_t{3} << 30, Page = 16384, Pages = Pool / Page;
int fd = -1;
std::mutex lock;
std::vector<bool> used(Pages, false);
std::atomic<std::size_t> taken{0};
std::atomic<long long> largest_override{-1};
void Open() {
    if (fd >= 0) return;
    fd = memfd_create("eden-pool", 0);
    if (fd < 0 || ftruncate(fd, Pool) != 0) { std::perror("pool"); std::abort(); }
}
int Take(std::size_t size, std::size_t alignment, std::int64_t* start) {
    Open();
    if (size == 0 || size % Page != 0) return -1;
    if (alignment < Page) alignment = Page;
    const std::size_t pages = size / Page, step = alignment / Page;
    std::lock_guard guard{lock};
    for (std::size_t first = 0; first + pages <= Pages; first += step) {
        bool free = true;
        for (std::size_t p = first; p < first + pages && free; ++p) free = !used[p];
        if (!free) continue;
        for (std::size_t p = first; p < first + pages; ++p) used[p] = true;
        *start = static_cast<std::int64_t>(first * Page);
        taken += size;
        return 0;
    }
    return -1;
}
int Release(std::int64_t start, std::size_t size) {
    std::lock_guard guard{lock};
    for (std::size_t p = start / Page; p < (start + size) / Page; ++p) {
        if (!used[p]) { std::fprintf(stderr, "released a free page of the pool at %lld\n", (long long)start); std::abort(); }
        used[p] = false;
    }
    taken -= size;
    (void)fallocate(fd, FALLOC_FL_PUNCH_HOLE | FALLOC_FL_KEEP_SIZE, start, size);
    return 0;
}
std::size_t Largest() {
    std::lock_guard guard{lock};
    std::size_t best = 0, run = 0;
    for (std::size_t p = 0; p < Pages; ++p) {
        run = used[p] ? 0 : run + 1;
        if (run > best) best = run;
    }
    return best * Page;
}
void* Aligned(void* hint, std::size_t size, std::size_t alignment) {
    if (alignment < 4096) alignment = 4096;
    void* raw = mmap(hint, size + alignment, PROT_NONE, MAP_PRIVATE | MAP_ANONYMOUS | MAP_NORESERVE, -1, 0);
    if (raw == MAP_FAILED) return nullptr;
    const auto base = (reinterpret_cast<std::uintptr_t>(raw) + alignment - 1) / alignment * alignment;
    const auto lead = base - reinterpret_cast<std::uintptr_t>(raw);
    if (lead) munmap(raw, lead);
    if (alignment - lead) munmap(reinterpret_cast<void*>(base + size), alignment - lead);
    return reinterpret_cast<void*>(base);
}
} // namespace mock

extern "C" {
std::int64_t sceKernelGetDirectMemorySize() { return mock::Pool; }
std::int32_t sceKernelAllocateDirectMemory(std::int64_t, std::int64_t, std::size_t size, std::size_t alignment, int,
                                           std::int64_t* start) {
    return mock::Take(size, alignment, start);
}
std::int32_t sceKernelMapDirectMemory(void** address, std::size_t size, int protection, int flags, std::int64_t physical,
                                      std::size_t alignment) {
    mock::Open();
    void* at = *address;
    if (!(flags & MAP_FIXED)) {
        at = mock::Aligned(at, size, alignment);
        if (at == nullptr) return -1;
    }
    void* mapped = mmap(at, size, protection, MAP_SHARED | MAP_FIXED, mock::fd, physical);
    if (mapped == MAP_FAILED) return -1;
    *address = mapped;
    return 0;
}
std::int32_t sceKernelReleaseDirectMemory(std::int64_t start, std::size_t size) { return mock::Release(start, size); }
std::int32_t sceKernelReserveVirtualRange(void** address, std::size_t size, int flags, std::size_t alignment) {
    void* at = *address;
    if (flags & MAP_FIXED) {
        void* mapped = mmap(at, size, PROT_NONE, MAP_PRIVATE | MAP_ANONYMOUS | MAP_FIXED | MAP_NORESERVE, -1, 0);
        if (mapped == MAP_FAILED) return -1;
        *address = mapped;
        return 0;
    }
    at = mock::Aligned(at, size, alignment);
    if (at == nullptr) return -1;
    *address = at;
    return 0;
}
std::int32_t sceKernelEnableDmemAliasing() { return 0; }
std::int32_t sceKernelAvailableDirectMemorySize(std::int64_t, std::int64_t, std::size_t, std::int64_t* start,
                                                std::size_t* size) {
    *start = 0;
    const long long forced = mock::largest_override.load();
    *size = forced >= 0 ? static_cast<std::size_t>(forced) : mock::Largest();
    return 0;
}
int sceKernelDebugOutText(int, const char* text) { return (int)write(2, text, std::strlen(text)); }
int eden_direct_high(std::size_t size, std::size_t alignment, int, std::int64_t* start) {
    return mock::Take(size, alignment, start);
}
int eden_direct_low(std::size_t size, std::size_t alignment, int, std::int64_t* start) {
    return mock::Take(size, alignment, start);
}
}
'''

TEST = r'''
#include <chrono>
#include <thread>

namespace Common {
void SetGuestMemorySwap(bool on, const char* path, unsigned cold_seconds) noexcept;
int GuestMemorySlotState(std::uint64_t offset) noexcept;
void GuestMemoryUsage(std::size_t* span, std::size_t* held) noexcept;
void ClearGuestMemory(std::uint8_t* at, std::uint64_t offset, std::size_t bytes, int fill) noexcept;
}

static std::uint64_t Word(std::size_t slot, std::size_t index, unsigned round) {
    return (std::uint64_t{slot} << 40) ^ (std::uint64_t{index} * 0x9e3779b97f4a7c15ull) ^ round;
}
static void Fill(std::uint8_t* base, std::size_t slot, unsigned round) {
    auto* words = reinterpret_cast<std::uint64_t*>(base + slot * Common::SparseSlot);
    for (std::size_t i = 0; i < Common::SparseSlot / 8; ++i) words[i] = Word(slot, i, round);
}
static bool Verify(const std::uint8_t* base, std::size_t slot, unsigned round) {
    const auto* words = reinterpret_cast<const volatile std::uint64_t*>(base + slot * Common::SparseSlot);
    for (std::size_t i = 0; i < Common::SparseSlot / 8; ++i)
        if (words[i] != Word(slot, i, round)) {
            std::fprintf(stderr, "slot %zu word %zu: %llx, not %llx\n", slot, i, (unsigned long long)words[i],
                         (unsigned long long)Word(slot, i, round));
            return false;
        }
    return true;
}
static std::size_t Count(std::size_t slots, int state) {
    std::size_t count = 0;
    for (std::size_t slot = 0; slot < slots; ++slot)
        count += Common::GuestMemorySlotState(slot * Common::SparseSlot) == state;
    return count;
}
static std::size_t Held() {
    std::size_t span = 0, held = 0;
    Common::GuestMemoryUsage(&span, &held);
    return held;
}
static void WaitFor(const char* what, const std::function<bool()>& done, int seconds) {
    for (int tenth = 0; tenth < seconds * 10; ++tenth) {
        if (done()) return;
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
    }
    std::fprintf(stderr, "timed out waiting for %s\n", what);
    std::abort();
}

int main(int argc, char** argv) {
    if (argc < 2) return 2;
    setenv("EDEN_SWAP_COLD_SECONDS", "2", 1);
    Common::SetGuestMemorySwap(true, argv[1], 0);
    constexpr std::size_t Size = std::size_t{256} << 20, Slots = Size / Common::SparseSlot, Written = 64;
    auto* base = static_cast<std::uint8_t*>(Common::AllocateGuestMemoryWhereUsed(Size));
    if (base == nullptr) { std::fprintf(stderr, "no guest memory\n"); return 1; }
    for (std::size_t slot = 0; slot < Written; ++slot) Fill(base, slot, 1);
    if (Count(Slots, 1) != Written) { std::fprintf(stderr, "%zu slots Own after the writes\n", Count(Slots, 1)); return 1; }
    const std::size_t held_written = Held();

    // The pool looks short: every written slot goes on probation, then to the file.
    mock::largest_override = std::int64_t{100} << 20;
    WaitFor("the written slots to be swapped", [&] { return Count(Slots, 5) == Written; }, 30);
    const std::size_t held_swapped = Held();
    if (held_written - held_swapped < Written * Common::SparseSlot) {
        std::fprintf(stderr, "held %zu MiB written, %zu MiB swapped\n", held_written >> 20, held_swapped >> 20);
        return 1;
    }
    std::printf("swapped: %zu slots in the file, the guest's memory from %zu to %zu MiB\n", Count(Slots, 5),
                held_written >> 20, held_swapped >> 20);

    // Plenty again: eight threads read every slot back and write half of them anew.
    mock::largest_override = std::int64_t{2} << 30;
    std::atomic<bool> failed{false};
    std::atomic<unsigned> arrived{0};
    std::vector<std::thread> threads;
    for (unsigned t = 0; t < 8; ++t)
        threads.emplace_back([&, t] {
            for (std::size_t slot = t; slot < Written; slot += 8) {
                if (!Verify(base, slot, 1)) failed = true;
                if (slot % 2 == 0) Fill(base, slot, 2);
            }
            // Every thread has written its slots before any reads them all.
            arrived.fetch_add(1);
            while (arrived.load() < 8) std::this_thread::yield();
            for (std::size_t slot = 0; slot < Written; ++slot)
                if (!Verify(base, slot, slot % 2 == 0 ? 2 : 1)) failed = true;
        });
    for (auto& thread : threads) thread.join();
    if (failed) return 1;
    if (Count(Slots, 1) != Written) { std::fprintf(stderr, "%zu slots Own after reading back\n", Count(Slots, 1)); return 1; }
    std::printf("read back: 8 threads, every byte as written, %zu slots Own again\n", Count(Slots, 1));

    // Short again: out once more; a slot cleared while in the file reads zeroes; the rest come back.
    mock::largest_override = std::int64_t{100} << 20;
    WaitFor("the slots to be swapped again", [&] { return Count(Slots, 5) == Written; }, 30);
    mock::largest_override = std::int64_t{2} << 30;
    Common::ClearGuestMemory(base + 3 * Common::SparseSlot, 3 * Common::SparseSlot, Common::SparseSlot, 0);
    if (Common::GuestMemorySlotState(3 * Common::SparseSlot) != 0) { std::fprintf(stderr, "cleared slot not Zero\n"); return 1; }
    for (std::size_t i = 0; i < Common::SparseSlot; i += 4096)
        if (base[3 * Common::SparseSlot + i] != 0) { std::fprintf(stderr, "cleared slot reads %d\n", base[3 * Common::SparseSlot + i]); return 1; }
    for (std::size_t slot = 0; slot < Written; ++slot)
        if (slot != 3 && !Verify(base, slot, slot % 2 == 0 ? 2 : 1)) return 1;
    std::printf("again: swapped out and back, a cleared slot reads zeroes\n");

    // The hard case: the pool stays short while eight threads use their slots. Each thread owns
    // eight slots, writes one now and then and reads all of its own, with pauses, so that slots
    // go cold, out and back again under the swapper's feet.
    mock::largest_override = std::int64_t{100} << 20;
    std::atomic<std::uint64_t> touches{0};
    std::vector<std::thread> users;
    for (unsigned t = 0; t < 8; ++t)
        users.emplace_back([&, t] {
            unsigned round[8];
            for (std::size_t k = 0; k < 8; ++k) {
                const std::size_t slot = t * 8 + k;
                round[k] = slot == 3 ? 0 : slot % 2 == 0 ? 2 : 1;
                if (slot == 3) { Fill(base, slot, 10); round[k] = 10; }
            }
            std::uint64_t seed = 0x1234567ull * (t + 1);
            const auto until = std::chrono::steady_clock::now() + std::chrono::seconds(8);
            while (std::chrono::steady_clock::now() < until && !failed) {
                seed = seed * 6364136223846793005ull + 1442695040888963407ull;
                const std::size_t k = (seed >> 33) % 8, slot = t * 8 + k;
                if ((seed >> 20) % 3 == 0) {
                    Fill(base, slot, ++round[k] + 10);
                    round[k] += 10;
                } else if (!Verify(base, slot, round[k])) {
                    failed = true;
                }
                touches.fetch_add(1);
                std::this_thread::sleep_for(std::chrono::milliseconds(20 + (seed >> 40) % 400));
            }
            for (std::size_t k = 0; k < 8 && !failed; ++k)
                if (!Verify(base, t * 8 + k, round[k])) failed = true;
        });
    for (auto& user : users) user.join();
    if (failed) return 1;
    std::printf("under the swapper: %llu touches in 8 s from 8 threads, every byte as last written\n",
                (unsigned long long)touches.load());
    mock::largest_override = std::int64_t{2} << 30;

    Common::FreeGuestMemory(base, Size);
    if (mock::taken.load() > (std::size_t{64} << 20)) {
        std::fprintf(stderr, "%zu MiB of the pool still taken after the session\n", mock::taken.load() >> 20);
        return 1;
    }
    std::printf("Guest memory swap: probation, out to the file under a short pool, back on any access from 8 threads, "
                "cleared while out, given back with the session PASS\n");
    return 0;
}
'''

with tempfile.TemporaryDirectory(prefix='eden-swap-') as work:
    work = pathlib.Path(work)
    source = work / 'swap.cpp'
    source.write_text(MOCK + '#include <functional>\n#include "' + str(root / 'src/memory_pages.cpp') + '"\n' + TEST)
    binary = work / 'swap'
    subprocess.run(['clang++-18', '-std=c++20', '-O1', '-g', '-pthread', '-DPS5_NATIVE=1', '-Wall', '-Wno-unused-function',
                    f'-I{root / "src"}', f'-I{root / "Eglantine/src"}', f'-I{root / "headless"}', str(source),
                    '-Wl,--defsym=__eden_text_start=__executable_start', '-Wl,--defsym=__eden_text_end=etext',
                    '-o', str(binary)], check=True)
    result = subprocess.run([str(binary), str(work / 'swap.bin')], capture_output=True, text=True, timeout=300)
    sys.stdout.write(result.stdout)
    for line in result.stderr.splitlines():
        if line.startswith('EDEN_SWAP end'):
            print(line)
    if result.returncode != 0:
        sys.stderr.write(result.stderr[-4000:])
        sys.exit(f'guest memory swap check failed: exit {result.returncode}')
