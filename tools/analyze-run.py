#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""One run's logs, summed up: where the time went and what stopped the game.

    analyze-run.py LOGS_FOLDER [SYMBOLS.elf]

LOGS_FOLDER is a copy of the console's /data/eglantineps5/logs (stderr.log, eden_log.txt, heap.log,
crash-*.txt). SYMBOLS.elf is the build's EglantinePS5-vX.Y.Z.elf (the EglantinePS5-symbols artifact
of the CI run that made it: gh run download RUN -n EglantinePS5-symbols); with it the hitch samples'
eboot+0x addresses become function names (llvm-symbolizer-18 or llvm-symbolizer).

What it reads (the lab file's medir=on turns all of it on):
  EDEN_TIMELINE / EDEN_TIMELINE2  every 2 s: frames, memory, swap, guest cores idle, Vulkan calls
  EDEN_HITCH                      where the main threads were while no frame came (tirones=N)
  EDEN_SWAP                       the swap file's totals, slow reads back
  eden_log.txt                    the GPU thread by zone (Nx2Profile), the texture cache, ASTC,
                                  pipelines built on the GPU thread, memory warnings
  crash-*.txt                     a crash report
"""
import collections
import json
import pathlib
import re
import shutil
import statistics
import subprocess
import sys


def read(path):
    try:
        return path.read_text(errors='replace').splitlines()
    except OSError:
        return []


def fields(line):
    return {k: v for k, v in re.findall(r'(\w+)=([^\s]+)', line)}


def num(text, default=0.0):
    try:
        return float(re.sub(r'[^0-9.\-]', '', text) or default)
    except ValueError:
        return default


def section(title):
    print(f'\n== {title} ' + '=' * max(0, 70 - len(title)))


class Symbols:
    def __init__(self, elf):
        self.names = {}
        self.tool = None
        if elf and pathlib.Path(elf).exists():
            self.tool = shutil.which('llvm-symbolizer-18') or shutil.which('llvm-symbolizer')
        self.elf = elf

    def load(self, addresses):
        if not self.tool or not addresses:
            return
        out = subprocess.run([self.tool, f'--obj={self.elf}', '--no-inlines', '-C', '--output-style=JSON'],
                             input='\n'.join(hex(a) for a in sorted(addresses)), capture_output=True, text=True)
        for line in out.stdout.splitlines():
            try:
                entry = json.loads(line)
                name = entry['Symbol'][0]['FunctionName']
            except (ValueError, KeyError, IndexError):
                continue
            name = re.sub(r'std::__1::', '', name)
            name = re.sub(r'\(.*', '', name)
            self.names[int(entry['Address'], 16)] = name[-70:]

    def name(self, token):
        if token.startswith('eboot+'):
            address = int(token[6:], 16)
            return self.names.get(address, token)
        return 'system/JIT'


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    folder = pathlib.Path(sys.argv[1])
    symbols = Symbols(sys.argv[2] if len(sys.argv) > 2 else None)
    stderr = read(folder / 'stderr.log')
    eden = read(folder / 'eden_log.txt')
    verdict = []

    section('Session')
    for line in stderr:
        if 'laboratorio: applied:' in line or line.startswith('[EglantinePS5] launch: Resolution'):
            print('  ' + line.split('] ', 1)[-1])
    crashes = [c for c in sorted(folder.glob('crash-2*.txt')) if not c.name.endswith('-eden_log.txt')]
    for crash in crashes:
        text = read(crash)
        reason = next((l for l in text if l.startswith('reason:')), '')
        when = next((l for l in text if l.startswith('time:')), '')
        print(f'  crash report {crash.name}: {when} {reason}')
    if not stderr:
        print('  no stderr.log')
        return 1

    # Timeline -------------------------------------------------------------------------------------
    timeline = [fields(l) for l in stderr if l.startswith('EDEN_TIMELINE ')]
    detail = {fields(l).get('t'): l for l in stderr if l.startswith('EDEN_TIMELINE2 ')}
    section('Frames (EDEN_TIMELINE, 2 s windows once the game draws)')
    playing = [t for t in timeline if num(t.get('fps', '0')) > 0 or num(t.get('worst_ms', '0')) > 0]
    if playing:
        fps = [num(t['fps']) for t in playing]
        bands = collections.Counter('0-5' if f < 5 else '5-15' if f < 15 else '15-30' if f < 30 else '30+' for f in fps)
        print(f'  windows {len(fps)}: median {statistics.median(fps):.1f} fps; '
              + ', '.join(f'{k} fps {bands[k]}' for k in ('0-5', '5-15', '15-30', '30+')))
        worst = sorted(playing, key=lambda t: -num(t.get('worst_ms', '0')))[:5]
        print('  longest gaps: ' + ', '.join(f"t={t['t']} {t['worst_ms']} ms" for t in worst))
        slow = [t for t in playing if num(t['fps']) < 15]
        good = [t for t in playing if num(t['fps']) >= 30]
        for name, group in (('slow (<15 fps)', slow), ('good (30+ fps)', good)):
            if not group:
                continue
            avg = lambda key: statistics.mean(num(t.get(key, '0')) for t in group)
            print(f'  {name}: free {avg("free"):.0f} MiB, largest {avg("largest"):.0f}, guest {avg("guest"):.0f}, '
                  f'gpu_rest {avg("gpu_rest"):.0f}, swap_in +{avg("swap_in"):.1f}/2s, swap_out +{avg("swap_out"):.1f}/2s, '
                  f'probe_hits +{avg("probe_hits"):.0f}/2s, short {avg("short"):.2f}')
            lines = [fields(detail[t['t']]) for t in group if t.get('t') in detail]
            if lines:
                idle = [statistics.mean(num(d.get(f'idle{c}', '0')) for d in lines) for c in range(4)]
                worst_swap = max(num(d.get('swap_in_worst_ms', '0')) for d in lines)
                worst_file = max(num(d.get('file_read_worst_ms', '0')) for d in lines)
                file_mib = statistics.mean(num(d.get('file_read_mib', '0')) for d in lines)
                print(f'    guest cores idle %: ' + ' '.join(f'{v:.0f}' for v in idle)
                      + f'; slowest swap read {worst_swap:.0f} ms; game files read {file_mib:.1f} MiB/2s, '
                      f'slowest {worst_file:.0f} ms')
                if name.startswith('slow') and worst_file >= 300:
                    verdict.append(f'Reading the game\'s files took up to {worst_file:.0f} ms in slow windows: '
                                   'the SSD (shared with the swap file) holds the game back.')
                worst_pool = max(num(d.get('pool_query_worst_ms', '0')) for d in lines)
                print(f'    slowest look at the pool (PoolWatch, off the GPU thread): {worst_pool:.0f} ms')
                if name.startswith('slow') and worst_pool >= 300:
                    verdict.append(f'Asking the system for free memory took up to {worst_pool:.0f} ms: the kernel\'s '
                                   'direct memory calls are slow (they no longer stop the GPU thread).')
                if name.startswith('slow') and worst_swap >= 300:
                    verdict.append(f'A swap read took {worst_swap:.0f} ms in a slow window.')
                calls = collections.defaultdict(float)
                for d in lines:
                    for key, value in d.items():
                        if value.endswith(tuple('0123456789')) and 'ms/' in value:
                            calls[key] += num(value.split('ms/')[0])
                if calls:
                    top = sorted(calls.items(), key=lambda kv: -kv[1])[:8]
                    print('    Vulkan ms per 2 s: ' + ', '.join(f'{k} {v / len(lines):.0f}' for k, v in top))
        if slow and good and detail:
            s_idle = [statistics.mean(num(fields(detail[t['t']]).get(f'idle{c}', '0')) for t in slow if t['t'] in detail) for c in range(4)]
            if all(v > 70 for v in s_idle):
                verdict.append('In the slow windows the guest cores mostly wait (idle > 70%): the game is held '
                               'back by something it waits for (GPU, disk, swap), not by its own CPU work.')
            elif min(s_idle) < 15:
                verdict.append('In the slow windows a guest core is busy almost all the time: the game\'s CPU '
                               'work (JIT code, services) is the limit.')

    # Hitches --------------------------------------------------------------------------------------
    hitches = [l for l in stderr if l.startswith('EDEN_HITCH n=')]
    ends = [int(m.group(1)) for l in stderr for m in [re.search(r'EDEN_HITCH end n=\d+ lasted_ms=(\d+)', l)] if m]
    section('Stops (EDEN_HITCH)')
    if not hitches:
        print('  none sampled (lab file tirones=700 or medir=on)')
    else:
        print(f'  {len(ends)} stops, {sum(ends) / 1000:.1f} s in all; ' +
              ', '.join(f'{lo}-{hi} ms: {sum(lo <= e < hi for e in ends)}'
                        for lo, hi in ((0, 1000), (1000, 2000), (2000, 5000), (5000, 10 ** 9))))
        addresses = {int(t[6:], 16) for l in hitches for t in re.findall(r'eboot\+0x[0-9a-f]+', l)}
        symbols.load(addresses)
        per_thread = collections.defaultdict(collections.Counter)
        doing = collections.Counter()
        silent = collections.Counter()
        for line in hitches:
            m = re.match(r'EDEN_HITCH n=(\d+) still_ms=(\d+) frames=\d+ (\S+) (.*)', line)
            if not m:
                continue
            thread, rest = m.group(3), m.group(4)
            what = re.search(r'doing="([^"]*)" for_ms=(\d+)', rest)
            if what:
                doing[(thread, what.group(1))] += 1
            if rest.startswith('did not answer'):
                silent[(thread, what.group(1) if what else 'no mark')] += 1
                per_thread[thread]['(did not answer: stuck in the system)'] += 1
                continue
            if rest.startswith('busy'):
                continue
            at = re.search(r'at (\S+)', rest)
            calls = re.search(r'calls (.*?)(?: doing=|$)', rest)
            chain = [at.group(1)] if at else []
            chain += [c for c in (calls.group(1).split() if calls else []) if c != 'none']
            per_thread[thread][' <- '.join(symbols.name(c) for c in chain[:4])] += 1
        for thread, counter in per_thread.items():
            total = sum(counter.values())
            print(f'  {thread} ({total} samples):')
            for key, count in counter.most_common(3):
                print(f'    {count:3} {key}')
        if doing:
            print('  marked as doing (eden_doing.h), samples:')
            for (thread, what), count in doing.most_common(10):
                print(f'    {count:3} {thread}: {what}')
        if silent:
            print('  threads that did not answer (stuck in a system call):')
            for (thread, what), count in silent.most_common(8):
                print(f'    {count:3} {thread}: {what}')
            top_thread, top_what = silent.most_common(1)[0][0]
            verdict.append(f'Stops: most often {top_thread} did not answer while "{top_what}".')
        if doing:
            (thread, what), _ = doing.most_common(1)[0]
            verdict.append(f'Stops: the most frequent long call is "{what}" on {thread}.')

    # Swap -----------------------------------------------------------------------------------------
    swaps = [fields(l) for l in stderr if l.startswith('EDEN_SWAP ')]
    section('Swap (EDEN_SWAP)')
    if swaps:
        last = swaps[-1]
        outs, ins = num(last.get('swap_outs', '0')), num(last.get('swap_ins', '0'))
        probes, hits = num(last.get('probes', '0')), num(last.get('probe_hits', '0'))
        print(f"  out {outs:.0f}, back {ins:.0f} ({ins / outs * 100 if outs else 0:.0f}%), probes {probes:.0f}, "
              f"touched again {hits:.0f} ({hits / probes * 100 if probes else 0:.0f}%), in the file "
              f"{last.get('swapped', '?')} slots, emergencies {last.get('emergencies', '0')}, "
              f"slow reads {last.get('slow_swap_ins', '?')}, hot_seconds {last.get('hot_seconds', '?')}")
        worst = max(num(s.get('swap_in_worst_ms', '0')) for s in swaps)
        print(f'  slowest read back: {worst:.0f} ms')
        trips = [fields(l) for l in stderr if l.startswith('EDEN_SWAP_IO ')]
        if trips:
            t = trips[-1]
            print(f"  SSD: writes {t.get('write_mib_s')} MiB/s, reads {t.get('read_mib_s')} MiB/s; slowest write "
                  f"{max(num(x.get('write_worst_ms', '0')) for x in trips):.0f} ms, read "
                  f"{max(num(x.get('read_worst_ms', '0')) for x in trips):.0f} ms; copies to/from the bounce buffers "
                  f"{t.get('copy_out_total_ms')}/{t.get('copy_in_total_ms')} ms in all")
            if num(t.get('write_mib_s', '0')) and num(t.get('write_mib_s', '0')) < 20:
                verdict.append(f"The SSD writes the swap file at {t.get('write_mib_s')} MiB/s even from plain memory: "
                               'the file system is the slow part (a swap in compressed memory would avoid it).')
        if outs and ins / outs > 0.3:
            verdict.append(f'Swap: {ins / outs * 100:.0f}% of what went to the SSD came back: it sends out memory '
                           'the game still uses (raise swap_caliente / swap_frio).')
        if worst >= 200:
            verdict.append(f'Swap: a read back took {worst:.0f} ms, a stop by itself.')
    else:
        print('  no swap (swap=on in the lab file)')
    for line in stderr:
        if 'EDEN_GRAPHICS_MEMORY' in line or 'terminate:' in line:
            print('  ' + line[:200])

    # eden_log -------------------------------------------------------------------------------------
    section('GPU thread by zone (eden_log.txt, Nx2Profile, ms per second)')
    zones = collections.defaultdict(list)
    busy = []
    for line in eden:
        if 'GPU thread per second:' not in line:
            continue
        for name, ms in re.findall(r'\| ([a-z /]+) ([0-9.]+) ms', line):
            zones[name.strip()].append(float(ms))
        m = re.search(r'host_cpu_busy_ms_per_s=([0-9.]+)', line)
        if m:
            busy.append(float(m.group(1)))
    if zones:
        top = sorted(((statistics.mean(v), k) for k, v in zones.items()), reverse=True)[:10]
        print('  ' + ', '.join(f'{k} {v:.0f}' for v, k in top))
        if busy:
            print(f'  GPU thread on a CPU: {statistics.mean(busy):.0f} ms per second (max {max(busy):.0f})')
        idle = statistics.mean(zones.get('idle', [0]))
        if idle < 100:
            verdict.append(f'The GPU thread is hardly ever idle ({idle:.0f} ms/s): it is the limit; '
                           f'its largest zone is "{top[0][1]}".')
    else:
        print('  not measured (lab file medir=on)')

    section('Texture cache, ASTC, pipelines (eden_log.txt)')
    created = deleted = costly = 0
    for line in eden:
        m = re.search(r'created (\d+) images, deleted (\d+) \(collector \d+, (\d+) costly', line)
        if m:
            created += int(m.group(1)); deleted += int(m.group(2)); costly += int(m.group(3))
    builds = [float(m.group(1)) for l in eden for m in [re.search(r'built on the GPU thread in ([0-9.]+) ms', l)] if m]
    pressure = sum('Out of device memory: keeping' in l for l in eden)
    over_budget = sum('over the memory budget' in l for l in eden)
    print(f'  images created {created}, deleted {deleted} ({costly} costly to make again); '
          f'memory pressure events {pressure}; images over the budget {over_budget}')
    print(f'  pipelines built on the GPU thread: {len(builds)}, {sum(builds):.0f} ms in all, '
          f'longest {max(builds) if builds else 0:.0f} ms')
    if costly > 1000:
        verdict.append(f'Texture cache: {costly} costly images deleted and made again: it evicts what the '
                       'game uses (thresholds too low for its working set).')
    if eden:
        print(f'  eden_log.txt ends at {eden[-1][:15]}')

    section('Verdict')
    for line in verdict or ['nothing stands out: send the logs of a run with medir=on']:
        print('  - ' + line)
    return 0


if __name__ == '__main__':
    sys.exit(main())
