#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Resume en español los logs de una sesión de EglantinePS5 copiados de la consola.

    python tools/diagnose-logs.py CARPETA_DE_LOGS            el último informe de error de la carpeta
    python tools/diagnose-logs.py crash-YYYYMMDD-HHMMSS.txt  ese informe y sus logs
    python tools/diagnose-logs.py CARPETA --elf SIMBOLOS.elf  también nombra las funciones del fallo

Lee lo que la app deja en /data/eglantineps5/logs: el informe (crash-*.txt) y, con el mismo
nombre, -stderr.log, -eden_log.txt y -heap.log (sin informe: stderr.log, eden_log.txt, heap.log).
Muestra la sesión, el error, los FPS y la memoria a lo largo del tiempo, los avisos que más se
repiten y una lista de problemas conocidos con qué hacer en cada caso.

SIMBOLOS.elf es el ejecutable con símbolos de la misma compilación: el artefacto
"EglantinePS5-symbols" de la ejecución de "Release build" que hizo el ZIP instalado
(gh run download <id> -n EglantinePS5-symbols). Si hay un .elf en la carpeta de logs o junto a
ella, se usa solo.
"""
import argparse
import bisect
import re
import struct
import sys
from collections import Counter
from pathlib import Path

# ---------------------------------------------------------------- reading the files


def read(path):
    return path.read_text(encoding='utf-8', errors='replace') if path and path.exists() else ''


def find_files(target):
    """(crash report or None, stderr, eden log, heap log) for a folder or a report."""
    target = Path(target)
    if target.is_file():
        report = target
        folder = target.parent
    else:
        folder = target
        reports = sorted(folder.glob('crash-*.txt'))
        reports = [r for r in reports if re.fullmatch(r'crash-\d{8}-\d{6}\.txt', r.name)]
        report = reports[-1] if reports else None
    if report:
        stem = report.stem
        return report, folder / f'{stem}-stderr.log', folder / f'{stem}-eden_log.txt', folder / f'{stem}-heap.log'
    return None, folder / 'stderr.log', folder / 'eden_log.txt', folder / 'heap.log'


def find_elf(folder, given):
    if given:
        return Path(given)
    for place in (folder, folder.parent):
        found = sorted(place.glob('*.elf'))
        if found:
            return found[-1]
    return None

# ---------------------------------------------------------------- function names


def elf_functions(path):
    """(text start, text size, text bytes offset, data, sorted [(address, size, name)])."""
    data = path.read_bytes()
    if data[:4] != b'\x7fELF' or data[4] != 2:
        raise ValueError('no es un ELF de 64 bits')
    shoff, = struct.unpack_from('<Q', data, 0x28)
    shentsize, shnum, shstrndx = struct.unpack_from('<HHH', data, 0x3A)
    headers = [struct.unpack_from('<IIQQQQIIQQ', data, shoff + i * shentsize) for i in range(shnum)]
    names_at = headers[shstrndx][4]

    def name_at(offset):
        return data[offset:data.index(b'\0', offset)].decode(errors='replace')
    sections = {name_at(names_at + h[0]): h for h in headers}
    text = sections['.text']
    symtab = sections['.symtab']
    strtab = headers[symtab[6]][4]
    functions = []
    for i in range(symtab[5] // 24):
        name, info, _other, _index, value, size = struct.unpack_from('<IBBHQQ', data, symtab[4] + i * 24)
        if info & 0xF == 2 and value:
            functions.append((value, size, name_at(strtab + name)))
    functions.sort()
    return text[3], text[5], text[4], data, functions


def after_call(code):
    """Whether the eight bytes that end at an address end with a call (as symbolize-crash.py checks)."""
    if len(code) != 8:
        return False
    if code[3] == 0xE8:
        return True
    for length in (2, 3, 4, 6, 7):
        at = code[8 - length:]
        if at[0] == 0xFF and at[1] & 0x38 == 0x10:
            return True
        if length >= 3 and at[0] & 0xF0 == 0x40 and at[1] == 0xFF and at[2] & 0x38 == 0x10:
            return True
    return False


def readable(name):
    """A C++ symbol as Namespace::Class::function (no arguments), without a demangler."""
    if not name.startswith('_Z'):
        return name
    text, at, parts = name, 2, []
    if text.startswith('_ZZ'):
        at = 3
    if at < len(text) and text[at] == 'N':
        at += 1
    while at < len(text):
        c = text[at]
        if c.isdigit():
            digits = re.match(r'\d+', text[at:]).group()
            at += len(digits)
            parts.append(text[at:at + int(digits)])
            at += int(digits)
        elif text.startswith('St', at):
            parts.append('std')
            at += 2
        elif c == 'I':  # template arguments: skipped to the matching E
            depth, at = 1, at + 1
            while at < len(text) and depth:
                if text[at] in 'IN':  # nested arguments and nested names both end with E
                    depth += 1
                elif text[at] == 'E':
                    depth -= 1
                elif text[at].isdigit():
                    digits = re.match(r'\d+', text[at:]).group()
                    at += len(digits) + int(digits) - 1
                at += 1
        elif text.startswith(('C1', 'C2', 'D0', 'D1', 'D2'), at):
            parts.append(('~' if c == 'D' else '') + (parts[-1] if parts else '?'))
            at += 2
        elif c in 'KVrL':
            at += 1
        else:
            break
    parts = [p for p in parts if p] or [name[:80]]
    return '::'.join(parts)


def name_stack(stack, elf):
    start, size, offset, data, functions = elf_functions(elf)
    addresses = [f[0] for f in functions]
    named, dropped = [], 0
    for index, value in enumerate(stack):
        if index > 0 and not (8 <= value <= size and after_call(data[offset + value - 8:offset + value])):
            dropped += 1
            continue
        address = start + value - (1 if index > 0 else 0)
        at = bisect.bisect_right(addresses, address) - 1
        name = '?'
        if at >= 0 and address < functions[at][0] + max(functions[at][1], 1):
            name = readable(functions[at][2])
        if not named or named[-1][1] != name:
            named.append((value, name))
    return size, named, dropped

# ---------------------------------------------------------------- parsing


def parse_report(text):
    fields = dict(re.findall(r'(?m)^(\w[\w ]*): (.*)$', text))
    stack = [int(v, 16) for v in re.findall(r'(?m)^  eboot\+0x([0-9a-f]+)', text)]
    where = re.search(r'where: eboot\+0x([0-9a-f]+)', text)
    if where:
        stack.insert(0, int(where.group(1), 16))
    size = re.search(r'code size 0x([0-9a-f]+)', text)
    return fields, stack, int(size.group(1), 16) if size else None


def numbers(pattern, text, cast=float):
    return [tuple(cast(v) for v in m) if isinstance(m, tuple) else cast(m) for m in re.findall(pattern, text)]


def eden_messages(text):
    """(seconds, level, where, message) for each line of eden_log.txt."""
    out = []
    for m in re.finditer(r'(?m)^\[\s*([\d.]+)\] (\S+) <(\w+)> (\S+?):(?:\d+:)?([^:\s]*): (.*)$', text):
        out.append((float(m.group(1)), m.group(3), m.group(4).split('/')[-1] + ':' + m.group(5), m.group(6)))
    return out


def shape(message):
    """A message with its numbers and addresses blanked, so repeats are counted together."""
    return re.sub(r'0x[0-9a-fA-F]+|\b\d+(\.\d+)?\b', '#', message)[:150]

# ---------------------------------------------------------------- report


def bar(value, top, width=30):
    filled = int(round(width * min(value, top) / top)) if top else 0
    return '#' * filled + '.' * (width - filled)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('target', help='carpeta de logs o un crash-*.txt')
    parser.add_argument('--elf', help='ejecutable con símbolos de la misma compilación')
    parser.add_argument('--top', type=int, default=12, help='cuántos avisos repetidos mostrar')
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='replace')
    args = parser.parse_args()

    report_path, stderr_path, eden_path, heap_path = find_files(args.target)
    report, stderr, eden, heap = read(report_path), read(stderr_path), read(eden_path), read(heap_path)
    if not (report or stderr or eden or heap):
        sys.exit(f'No encontré logs en {args.target}')
    print('=' * 72)
    print('DIAGNÓSTICO DE EGLANTINEPS5')
    for label, path in (('informe', report_path), ('stderr', stderr_path), ('eden', eden_path), ('heap', heap_path)):
        if path and path.exists():
            print(f'  {label:8} {path.name}')
    problems = []  # (importance 1-3, text, what to do)

    # -- session
    print('\n--- SESIÓN ' + '-' * 61)
    fields, stack, code_size = parse_report(report) if report else ({}, [], None)
    for key in ('version', 'time', 'running', 'memory'):
        if key in fields:
            print(f'  {key:8} {fields[key]}')
    for line in re.findall(r'(?m)^\[EglantinePS5\] launch: (.*)$', stderr):
        print(f'  ajuste   {line}')
    game = re.search(r'running: game main \(([0-9a-f]{16})\)', report)
    if game:
        print(f'  juego    {game.group(1)}')

    # -- the error
    print('\n--- ERROR ' + '-' * 62)
    if report:
        print(f"  qué      {fields.get('what', '?')}")
        print(f"  motivo   {fields.get('reason', '?')}")
        print(f"  hilo     {fields.get('thread', '?')}")
    for line in re.findall(r'(?m)^\[EglantinePS5\] (?:Vulkan failure|terminate): .*$', stderr):
        print(f'  {line}')
    critical = [m for m in eden_messages(eden) if m[1] == 'Critical']
    for seconds, _level, where, message in critical[-3:]:
        print(f'  [{seconds:8.1f} s] {where}: {message[:110]}')
    if not report and not critical:
        print('  No hay informe de error: la sesión no terminó por un fallo.')

    elf = find_elf(Path(args.target) if Path(args.target).is_dir() else Path(args.target).parent, args.elf)
    if stack and elf and elf.exists():
        try:
            size, named, dropped = name_stack(stack, elf)
            if code_size and size != code_size:
                print(f'  AVISO: {elf.name} es de otra compilación (código 0x{size:x}, el informe dice 0x{code_size:x});'
                      ' los nombres no valen.')
            print(f'  funciones (la más reciente primero; {dropped} valores sueltos de la pila omitidos):')
            for value, name in named[:25]:
                print(f'    eboot+0x{value:<8x} {name[:100]}')
        except (OSError, ValueError, KeyError) as error:
            print(f'  No pude leer los símbolos de {elf}: {error}')
    elif stack:
        print('  (Para ver los nombres de las funciones: --elf con los símbolos de esta compilación.)')

    # -- graphics memory events
    events = re.findall(r'(?m)^(EDEN_(?:IMAGE_REFUSED|SPARSE_IMAGE|SPARSE_CAPPED|STAGING_OOM|GRAPHICS_MEMORY)\b.*)$', stderr)
    probes = re.findall(r'(?m)^EDEN_SPARSE_PROBE (\d+) layers: (-?\d+)$', stderr)
    if events or probes:
        print('\n--- MEMORIA GRÁFICA: PETICIONES RECHAZADAS ' + '-' * 29)
        for line in events[-8:]:
            print(f'  {line[:150]}')
        if probes:
            print('  el driver acepta texturas dispersas de: ' +
                  ', '.join(f"{n} capas {'sí' if r == '0' else 'no'}" for n, r in probes))
    refused = re.search(r'EDEN_IMAGE_REFUSED (\d+)x(\d+)x\d+, (\d+) layers, (\d+) levels.*?texels (\d+)', stderr)
    if refused:
        w, h, layers, levels, texels = (int(v) for v in refused.groups())
        accepted = [int(n) for n, r in probes if r == '0']
        hint = (f' El driver sí acepta {max(accepted)} capas: el parche de capas recortadas (capped_layers.h) cubre'
                ' este caso; si ya lo tienes instalado y sigue fallando, el parche no se activó.') if accepted else ''
        problems.append((3, f'El juego pidió una textura imposible: {w}x{h}, {layers} capas, {levels} niveles '
                            f'({texels / 1e9:.1f} mil millones de texels) y el driver la rechazó.' + hint,
                         'Pasa este diagnóstico y los logs para revisar el código de texturas.'))
    capped = re.findall(r'EDEN_SPARSE_CAPPED .*', stderr)
    if capped:
        problems.append((1, f'El parche de capas recortadas se activó {len(capped)} vez/veces ({capped[-1][19:]}).',
                         'Si ves zonas oscuras o vacías, anota dónde: es el precio del recorte.'))
    if 'EDEN_STAGING_OOM' in stderr:
        problems.append((2, 'Faltó memoria para un búfer de transferencia a la GPU.',
                         'Baja la resolución del juego o la de salida.'))

    # -- frame rate over time
    frames = numbers(r'EDEN_VULKAN_FRAME frames=\d+ seconds=([\d.]+) fps=([\d.]+) worst_ms=([\d.]+)', heap)
    loading = re.search(r'EDEN_LOADING_DONE frames=\d+ seconds=([\d.]+)', heap)
    if frames:
        print('\n--- FPS DURANTE LA PARTIDA (cada ~5 s) ' + '-' * 33)
        if loading:
            print(f'  carga: {float(loading.group(1)):.1f} s')
        elapsed, top = 0.0, max(60.0, max(f[1] for f in frames))
        for seconds, fps, worst in frames:
            elapsed += seconds
            mark = '  <-- muy lento' if fps < 20 else ''
            print(f'  {elapsed:6.0f} s  {fps:6.1f} FPS  {bar(fps, top)}  peor fotograma {worst:7.1f} ms{mark}')
        slow = [f for f in frames if f[1] < 20]
        if slow:
            problems.append((2, f'{len(slow)} de {len(frames)} tramos de 5 s fueron de menos de 20 FPS '
                                f'(el peor: {min(f[1] for f in frames):.1f} FPS).',
                             'Si coincide con la memoria bajando (abajo), es la caché de texturas: pásame los logs.'))
        hitch = [f for f in frames if f[2] > 500]
        if hitch:
            problems.append((1, f'Hubo tirones de más de medio segundo en {len(hitch)} tramos.',
                             'Suele ser compilación de shaders o la caché de texturas liberando memoria.'))

    # -- memory over time
    pool = numbers(r"EDEN_MEMORY pool largest free block (\d+) MiB, short=(\d); the guest's memory holds (\d+) MiB", stderr, int)
    heap_holds = numbers(r'heap: holds (\d+) MiB', stderr, int)
    messages = eden_messages(eden)
    gpu_only = [(s, int(re.search(r'(\d+) MiB of GPU-only memory in use', m).group(1)))
                for s, _l, _w, m in messages if 'MiB of GPU-only memory in use' in m]
    thresholds = [(s, m) for s, _l, _w, m in messages if 'Texture cache thresholds' in m]
    if pool or gpu_only:
        print('\n--- MEMORIA (12 GiB compartidos entre CPU y GPU) ' + '-' * 23)
        for index, (free, short, guest) in enumerate(pool):
            held = f', heap de la app {heap_holds[index]} MiB' if index < len(heap_holds) else ''
            warn = '  <-- poca memoria' if short or free < 1024 else ''
            print(f'  libre (bloque mayor) {free:6} MiB  {bar(free, 12288, 24)}  juego {guest} MiB{held}{warn}')
        if gpu_only:
            print(f'  memoria solo-GPU del juego: de {gpu_only[0][1]} MiB ({gpu_only[0][0]:.0f} s) '
                  f'a {gpu_only[-1][1]} MiB ({gpu_only[-1][0]:.0f} s)')
        for seconds, message in thresholds[-3:]:
            print(f'  [{seconds:6.0f} s] {message}')
        if pool and pool[-1][0] < 2048:
            problems.append((2, f'Al final quedaban solo {pool[-1][0]} MiB libres en un bloque.',
                             'Baja la resolución, desactiva FSR y la generación de fotogramas.'))
        if len(thresholds) >= 2:
            problems.append((1, f'La caché de texturas cambió sus límites {len(thresholds)} veces '
                                '(la memoria libre estaba bajando).', 'Indica presión de memoria.'))

    # -- known problems in the logs
    if 'Game contents not registered' in stderr:
        problems.append((2, 'La actualización del juego no se aplica ("Game contents not registered").',
                         'Revisa cómo está instalada la actualización del juego; algunos juegos la necesitan.'))
    rejected = sum(1 for _s, _l, _w, m in messages if 'Native graphics shader rejected' in m)
    skipped = sum(1 for _s, _l, _w, m in messages if 'Draw skipped' in m)
    if rejected or skipped:
        problems.append((1, f'{rejected} shaders rechazados y {skipped} dibujos omitidos.',
                         'Pueden faltar efectos en pantalla; es una limitación del emulador, no cierra el juego.'))
    jit = re.findall(r'EDEN_JIT_PRESSURE core=(\d+)', heap)
    if jit:
        problems.append((1, f'La caché del traductor de CPU (JIT) se llenó {len(jit)} vez/veces.',
                         'Puede causar tirones; la app la vacía sola.'))
    if 'Could not save recent game' in stderr:
        problems.append((1, 'No pudo guardar el juego en "recientes".', 'Sin importancia.'))

    # -- repeated warnings
    counted = Counter((level, where, shape(message)) for _s, level, where, message in messages
                      if level in ('Warning', 'Error', 'Critical'))
    if counted:
        print(f'\n--- AVISOS MÁS REPETIDOS (eden_log, {sum(counted.values())} en total) ' + '-' * 20)
        for (level, where, message), count in counted.most_common(args.top):
            print(f'  {count:5}x {level[:4]:4} {where[:38]:38} {message[:90]}')

    # -- summary
    print('\n--- PROBLEMAS DETECTADOS (lo más grave primero) ' + '-' * 24)
    if not problems:
        print('  Nada conocido. Si algo falló, pasa los logs completos para revisarlos.')
    for importance, text, todo in sorted(problems, key=lambda p: -p[0]):
        label = {3: 'GRAVE', 2: 'IMPORTANTE', 1: 'info'}[importance]
        print(f'  [{label}] {text}')
        print(f'           Qué hacer: {todo}')
    print('=' * 72)


if __name__ == '__main__':
    main()
