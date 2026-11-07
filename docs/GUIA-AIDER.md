# Guía del proyecto EglantinePS5 para Aider

Esta guía es para un asistente de código (Aider) que trabaja en este repositorio en otra computadora. Explica qué es la app, cómo está organizada, cómo se compila y prueba, qué se ha hecho hasta ahora y qué reglas hay que respetar.

**El dueño del proyecto habla español: responde siempre en español, simple y directo.**

---

## 1. Qué es EglantinePS5

- Es un **emulador de Nintendo Switch 2 que corre como app nativa (homebrew) en una PS5 con jailbreak**.
- El núcleo del emulador es **Lichii** (antes llamado Eglantine, de zortos293), una variante de **Eden** (emulador de Switch) que soporta Switch 2. Está en el submódulo `Eglantine/` (https://github.com/zortos293/Lichii, rama `nx2`; desde noviembre de 2026 en la build 88, commit `55532f2`).
- EglantinePS5 aporta:
  - el "frontend" para PS5 (`headless/`);
  - el lanzador con menús;
  - la gestión de memoria propia (`src/`);
  - el empaquetado y los scripts de compilación (`tools/`);
  - los parches que se aplican a Eglantine (`tools/eglantine-patches/`).
- La GPU se usa con **Vulkan** a través de **RADV (Mesa) portado a la PS5** (PS5_Mesa / PS5_Vulkan de Mihawk). También existe un renderizador OpenGL (ps5-opengl), pero el recomendado es Vulkan.
- El ID de la app en la PS5 es **PPSA98515**. Se instala en `/data/homebrew/PPSA98515`.
- En la consola, los logs quedan en `/data/eglantineps5/logs`.

### Objetivo actual
Que **Mario Kart World** (título `0400c3f00006e000`) sea jugable en PS5: estable, fluido y con buena imagen.

### Repositorios
- Fork de trabajo: **https://github.com/Sebaneg/EglantinePS5** (remoto `origin`).
- Rama de trabajo: **`update/eglantine-nov4`**.
- Original: `upstream` = https://github.com/heydemoura/EglantinePS5. **No se escribe ahí** (da HTTP 403).
- Referencia útil con soluciones de otro desarrollador: https://github.com/viejunerd/Eglantine-PS5- (de ahí vinieron los parches 0015, 0016 y 0017).

---

## 2. Reglas de trabajo (obligatorias)

1. **No compilar, no hacer commit y no hacer push sin la orden explícita del dueño.** La frase que autoriza es del estilo "Sí, sube y compila". Antes de eso, solo se edita y se revisa.
2. **Nunca hacer commit del submódulo `Eglantine`.** Los cambios al núcleo van siempre como archivos `.patch` en `tools/eglantine-patches/`.
3. **No subir** `tools/diagnose-logs.py` (tiene cambios locales), `docs/AGRUPAR-BLOQUES-VACIOS.md` ni `docs/GEMINI-TERRENOS.md`: son locales.
4. Con Aider, usar **`--no-auto-commits`**: Aider hace commit solo por defecto, y aquí eso está prohibido.
5. Cada vez que cambie `laboratorio.txt`, entregar **el texto completo**, nunca solo las líneas nuevas. El dueño lo copia entero a la consola.
6. Nada de compilaciones que solo midan. Cada compilación debe traer mejoras reales, agrupadas.
7. Comentarios de código cortos y en inglés, como el resto del proyecto. Las explicaciones al dueño, en español.

---

## 3. Mapa del repositorio

```
EglantinePS5/
├── Eglantine/            Submódulo: núcleo del emulador (Eden/Eglantine). NO hacer commit aquí.
├── headless/             Frontend PS5: main, lanzador, gráficos, audio, mandos, laboratorio, medición
├── src/                  Memoria propia: memoria directa de la PS5, swap del juego, páginas
├── tools/                Compilación, dependencias, parches, pruebas y análisis de logs
│   ├── eglantine-patches/   Parches que se aplican a Eglantine, en orden numérico
│   ├── ci/                  Preparación de la máquina de GitHub Actions
│   ├── deps.json / deps.py  Dependencias fijadas (commits/hashes) y su descarga
│   └── check-*.py           Pruebas locales (muchas compilan fragmentos con g++)
├── docs/                 Documentación (LABORATORIO.md es la referencia de opciones)
├── sce_sys/              Íconos y metadatos del paquete PS5
├── third_party/, fixtures/
├── Makefile              Entrada de la compilación (Linux)
├── UPSTREAM.json         Origen del núcleo y versiones fijadas
└── .github/workflows/    release.yml (compilación oficial), build.yml, build-cache.yml
```

### 3.1 `headless/` (frontend de la PS5)
| Archivo | Qué hace |
|---|---|
| `main.cpp` | Arranque: lanzador, ajustes, carga del juego, bucle principal. Aplica los ajustes de rendimiento (por ejemplo, `async shaders`). |
| `lab.h` | **El "laboratorio"**: lee `laboratorio.txt` de la consola y convierte cada línea en ajustes o variables de entorno (`SetVariable("EDEN_...")`). Aquí se agregan las opciones nuevas. |
| `crash_report.cpp/.h` | Informes de cierre y **HitchWatch** (vigilancia de tirones): con `tirones=N`, si un hilo clave tarda más de N ms, toma muestras de pila (SIGUSR1) y escribe `EDEN_HITCH` en stderr. |
| `eden_doing.h` | Etiquetas "qué está haciendo este hilo" (`EdenDoingScope`), que se ven en los informes de tirones. |
| `performance.cpp/.h` | Medición: líneas `EDEN_TIMELINE` y `EDEN_TIMELINE2` cada 2 s, costes de Vulkan, lecturas de archivos, hilo PoolWatch (consulta la memoria libre cada 100 ms fuera del hilo de la GPU). |
| `graphics.cpp/.h` | Ventana gráfica, Vulkan, presentación en la tele. |
| `audio.cpp`, `pad.cpp` | Audio y mandos DualSense. |
| `preferences.h` | Ajustes guardados (JSON en `/data/eglantineps5`). |
| `multiplayer*` | Multijugador local por salas de Eden (experimental). |
| `macro_recovery.cmake`, `native_gpu_thread.inc` | Adaptaciones del hilo de la GPU y de las macros (MME). |
| `check*.py`, `*_check.cpp` | Pruebas del frontend. |

### 3.2 `src/` (memoria)
| Archivo | Qué hace |
|---|---|
| `direct_memory.c`, `host_memory.cpp` | Memoria directa de la PS5 (12 GiB compartidos entre CPU y GPU). |
| `memory_pages.cpp` | Páginas de la memoria del juego. |
| `guest_memory_service.inc` | **Swap del juego**: saca a disco (o comprime en memoria) la memoria del juego que no se usa. Ver sección 6. |
| `lifecycle.c`, `aligned_alloc.c`, `fastmem.h` | Ciclo de vida, asignador, acceso rápido a memoria. |

### 3.3 `tools/` (los más usados)
| Archivo | Qué hace |
|---|---|
| `apply-eglantine-patches.sh` | Aplica en orden los parches de `tools/eglantine-patches/` sobre el submódulo. Recuerda qué conjunto aplicó. |
| `prepare-vulkan-port.py` | Toma el código de Eglantine y lo adapta al port de PS5 buscando **anclas de texto**. Si una ancla cambia, falla. Ojo: cuenta las llamadas `scheduler.Finish()/Wait()` por archivo, por ejemplo `('vk_texture_cache', 8, 4)`. Si un parche agrega o quita una, hay que actualizar ese número. |
| `build-radv-dependencies.sh`, `patch-radv-wsi.py` | Compilan RADV con la revisión de Mesa fijada en `deps.json` (ps5-mesa `f5610fe27…`). |
| `deps.json`, `deps.py` | Dependencias fijadas; `make deps` las descarga. |
| `analyze-run.py` | **Analizador de logs.** Uso: `python -I tools/analyze-run.py <carpeta LOGS>`. Resume sesión, cuadros por segundo, tirones, swap, hilo de la GPU, caché de texturas y terrenos, y da un veredicto. |
| `diagnose-logs.py` | Otro analizador (con cambios locales sin subir). |
| `symbolize-crash.py`, `symbolize-sites.py` | Traducen direcciones `eboot+0x…` a funciones, con los símbolos de la compilación. |
| `check-guest-swap.py`, `check-gpu-sync-stop.py`, … | Pruebas. Muchas necesitan g++ (Linux/WSL). |

---

## 4. Cómo se compila

- **No se compila en Windows.** La compilación es en Linux (Ubuntu; WSL sirve) con `make`. Ver `docs/BUILDING.md`.
- En la práctica, **se compila en GitHub Actions** con el workflow `release.yml`, sobre la rama de trabajo:
  ```bash
  gh workflow run release.yml -R Sebaneg/EglantinePS5 --ref update/eglantine-nov4
  gh run list -R Sebaneg/EglantinePS5 --workflow release.yml --branch update/eglantine-nov4 --limit 1
  ```
  - Siempre con `-R Sebaneg/EglantinePS5`, porque sin eso apunta al upstream y da 403.
  - Con caché tarda unos 10 a 20 minutos; sin caché, alrededor de 1 hora.
  - El ZIP queda como artefacto. Los símbolos, en el artefacto `EglantinePS5-symbols`:
    ```bash
    gh run download <run_id> -R Sebaneg/EglantinePS5 -n EglantinePS5-symbols -D sym
    ```
- La compilación de CI aplica los parches sobre un Eglantine limpio. Por eso **todo cambio al núcleo debe estar en un `.patch`**: si solo existe en la copia local del submódulo, CI no lo ve.
- **Solo se lanza con la orden del dueño** (regla 1).

### Verificaciones sin compilar (sí permitidas)
1. **Que los parches apliquen en orden sobre Eglantine limpio:**
   ```bash
   mkdir /tmp/clean && git -C Eglantine -c core.autocrlf=false archive HEAD | tar -x -C /tmp/clean
   cd /tmp/clean && git init -q . && for p in <repo>/tools/eglantine-patches/*.patch; do git apply "$p" || echo "FALLA $p"; done
   ```
2. **Que las anclas de `prepare-vulkan-port.py` sigan encontrándose:**
   ```bash
   python tools/prepare-vulkan-port.py --report /tmp/clean /tmp/port-out
   ```
   Necesita `glslangValidator` y `spirv-val`. Sin ellos se pueden simular, porque esos programas solo generan los shaders del HUD.
3. Las pruebas `tools/check-*.py` que se puedan correr.

---

## 5. Parches de Eglantine (`tools/eglantine-patches/`)

Se aplican en orden numérico. No existe el 0002, y el 0020 se quitó; los huecos son normales.

| Parche | Qué hace |
|---|---|
| 0001 | Contenido extraído y versionado. |
| 0003 | Duración de la sesión de salida de audio. |
| 0004 | Compatibilidad libc++ de la PS5. |
| 0005 | Las zonas de texturas "solo GPU" toman los trozos del juego. |
| 0006 | Conversión ASTC→BC por partes. |
| 0007 | Subida de capas en grupos. |
| 0008 | Tamaño de pila de las fibras. |
| 0009 | Tope de capas del terreno (`capas_max`). |
| 0010 | Tope de imágenes temporales de conversión (`EDEN_NX2_TRANSCODE_INFLIGHT_MIB`). |
| 0011 | Tamaño de la cola de descriptores. |
| 0012 | La presión de memoria de texturas baja con el tiempo. |
| 0013 | Lectura tardía del perfil de la GPU (Nx2Profile). |
| 0014 | Lecturas de archivos marcadas y cronometradas. |
| 0015 | Límite al juntar búferes (`bufer_max`, 256 MiB por defecto; de viejunerd). |
| ~~0016~~ | *Quitado* al pasar a Lichii, que ya se salta los búferes sin cambios. `atajos_bufer=off` ya no hace nada. |
| 0017 | El segundo hilo de la GPU ya no se queda dormido (de viejunerd). |
| 0018 | Stub del comando 201 de vi2. |
| 0019 | Log de búferes grandes. |
| ~~0020~~ | *Quitado*: hacía que el juego se cerrara al cargar con la GPU en dos hilos (SIGSEGV en `Scheduler::SubmitExecution`). |
| 0021 | **Terrenos en BC3/BC1** en lugar de RGBA8 (ver 7.1). Opción `terrenos_bc=off|bc1`. |
| 0022 | **La caché de texturas conserva las texturas usadas en los últimos 2 s** (ver 7.2). Opción `texturas_recientes=N`. |
| 0023 | El búfer de índices solo se sincroniza desde `first` (el menú pedía 2,3 GB y se cerraba), y las subidas de búfer grandes van en trozos de 128 MB (`EDEN_BUFFER_UPLOAD_PIECE_MIB`). |

### Cómo crear o regenerar un parche
- La copia de trabajo en Windows tiene **finales de línea CRLF** en algunos archivos (por ejemplo `vk_texture_cache.h`, `texture_cache_base.h`) y LF en otros. Los parches deben ir **en LF**.
- Método seguro:
  1. guardar una copia del archivo original;
  2. editar;
  3. normalizar ambas copias con `tr -d '\r'`;
  4. generar con `git diff --no-index a b`;
  5. corregir las rutas `a/a/src` → `a/src` y `b/b/src` → `b/src`.
- Si una edición se hace por script en Python, respetar el final de línea del archivo (abrir en binario y comprobar `\r\n`).
- Después de crear un parche, siempre hacer las verificaciones de la sección 4.

---

## 6. Sistemas importantes (lo que más se ha trabajado)

### 6.1 Memoria de la PS5
- Hay 12 GiB compartidos entre CPU y GPU. El juego y el emulador usan unos 11 GB: va muy justo.
- Errores típicos de falta de memoria: `0x8002000C`, búferes o imágenes que no caben, cierres al cargar.

### 6.2 Swap del juego (`src/guest_memory_service.inc`)
- Saca a disco la memoria del juego que no se usa:
  - con período de prueba;
  - con protección "caliente": lo que vuelve del disco queda 120 s en memoria (`swap_caliente`);
  - con escritura suave.
- **Swap comprimido**: los bloques se comprimen con LZ4 en memoria antes de ir al SSD. Si quedan bajo 3/4 de su tamaño se quedan en memoria; si no, van al archivo. La proporción típica es 0,23 a 0,46. Se apaga con `swap_comprimido=off`.
- Usa búferes intermedios para leer y escribir el SSD, porque copiar desde memoria directa era lento. Se apagan con `swap_intermedio=off`.
- Emergencias con tope de 4 s (`EDEN_SWAP_EMERGENCY_MS`).
- Logs: `EDEN_SWAP`, `EDEN_SWAP_PACK`, `EDEN_SWAP_IO`.

### 6.3 Hilo de la GPU
- **Es el cuello de botella actual.** Casi nunca está libre (menos de 100 ms libres por segundo). Sus zonas más pesadas: `method`, `push`, `macro`.
- La división del hilo de la GPU en dos ("GPU split") solo se activa con `gpu_accuracy=low`, pero **`gpu_accuracy=low` estropea la imagen** (ruido, blanco, brillos). Por eso se usa `gpu_accuracy=high` y `gpu_dos_hilos=off`.

### 6.4 Caché de texturas
- La GPU de la PS5 **no soporta ASTC**: las texturas ASTC se convierten en la GPU a BC1/BC3 (`TranscodeAstcToBcn` + `BcEncoderPass`).
- `astc_bc1=on` usa BC1 en lugar de BC3 para ahorrar memoria.
- Los terrenos de Mario Kart World son arrays ASTC de **8192x8192 con 68 capas**: 23 GB sin comprimir. Solo se guardan desde cierto nivel de detalle (`TrimmedHostInfo`, límite `EDEN_NX2_ASTC_ARRAY_MIB`).
- El recolector borra texturas cuando la memoria gráfica pasa los umbrales `EDEN_NX2_TC_EXPECTED_MIB` y `EDEN_NX2_TC_CRITICAL_MIB`.
- Ojo: "device memory" incluye búferes y no solo texturas. En una carrera había ~6,1 GB de memoria, pero solo 2,2 GB eran texturas.

### 6.5 Medición
- `medir=on` activa todas las mediciones.
- `tirones=N` activa HitchWatch.
- `env=EDEN_NX2_TC_LOG=60` muestra el estado de la caché cada 60 cuadros.
- Con los logs de la consola (`stderr.log`, `eden_log.txt`, `heap.log`, `boot-trace.txt`), correr siempre `tools/analyze-run.py` antes de opinar.

---

## 7. Últimos cambios (aún sin compilar ni subir)

### 7.1 Terrenos en BC3 (parche 0021)
- **Archivos:**
  - `Eglantine/src/video_core/renderer_vulkan/vk_texture_cache.cpp` y `.h`.
  - Funciones nuevas: `HugeAstcModeOf`, `HugeAstcAsBc`, `HugeAstcVkFormat`, `HugeAstcViews`, `HugeAstcBlockBytes`/`HugeAstcBlockSide`, `AcquireTranscodeImage` (extraída de `TranscodeAstcToBcn`) y `TranscodeHugeAstcLayers`.
- **Formato y tamaño:**
  - Los arrays enormes se guardan en BC3; en BC1 si son opacos (`astc_opaque`) o con `terrenos_bc=bc1`.
  - `TrimmedHostInfo` cuenta los bytes por bloques BC, así que con el mismo límite caben dos niveles más.
  - Con `EDEN_NX2_ASTC_ARRAY_MIB=256` cada capa pasa de 512x512 a 1024x1024; con 384 llega a 2048x2048.
- **Subida:**
  1. se decodifica por grupos de capas a una imagen RGBA8 temporal reutilizada (topes de 192 MiB decodificado y 32 MiB codificado);
  2. se codifica con `BcEncoderPass`;
  3. se copia a cada capa.
- **Imagen y memoria dispersa:**
  - La imagen BC no lleva uso STORAGE.
  - La memoria dispersa por capas usa bloques de 4x4 y 16 u 8 bytes.
- **Log:** `ASTC image would be … MiB as BC3; keeping mip levels …` y `Huge ASTC arrays as BC3: …`.
- **Para volver atrás sin compilar:** `terrenos_bc=off`.

### 7.2 Caché de texturas conserva texturas recientes (parche 0022)
- **Archivos:** `Eglantine/src/video_core/texture_cache/texture_cache.h` y `texture_cache_base.h`.
- **El problema:** antes, la edad mínima de una textura para borrarla se contaba en cuadros (10 en modo agresivo). A 14 cuadros por segundo eso es menos de 1 s, y en una carrera hubo 78 310 texturas borradas y vueltas a crear (destellos y lag).
- **El cambio:**
  - Se guarda la hora de inicio de los últimos 1024 cuadros (`frame_starts`).
  - No se borran texturas usadas en los últimos `EDEN_NX2_TC_KEEP_MS` (2000 ms por defecto).
  - Excepción: si la memoria pasa el umbral crítico + `EDEN_NX2_TC_KEEP_SLACK_MIB` (512), se borra igual.
- **Log:** `… passes kept recent ones`.

### 7.3 Otros
- Se quitó el parche 0020 y su simulación en `tools/check-gpu-sync-stop.py`.
- `prepare-vulkan-port.py`: el conteo de esperas de `vk_texture_cache` pasó de 3 a 4.
- `analyze-run.py` ahora muestra los terrenos y sugiere `async_shaders=on` cuando los shaders compilados en el hilo de la GPU suman más de 1 s.
- `docs/LABORATORIO.md` documenta `terrenos_bc` y `texturas_recientes`.

---

## 8. El archivo `laboratorio.txt`

- Está en la consola. Cada línea es una opción.
- La referencia completa es `docs/LABORATORIO.md`. El código que lo lee es `headless/lab.h`.
- `env=NOMBRE=valor` fija variables de entorno del núcleo.

Configuración actual recomendada:
```
vsync=mailbox
memoria_compacta=on
bloques_repetidos=on
heap_bloque_propio=4
heap_arenas=32
pila_hilos=512
jit_nucleos=48
dispersas=on
zonas_gpu_trozos=on
capas_max=384
cola_descriptores=4
juego_arriba=on
swap=on
swap_bloque=on
reserva_juego=32
memoria_util=on
memoria_corta=384
margen_texturas=256
nitidez_fsr=60
aa=smaa
async_shaders=on
medir=on
tirones=700
gpu_accuracy=high
gpu_dos_hilos=off
atajos_bufer=off
env=EDEN_NX2_SPARSE_UNBACKED=1
env=EDEN_NX2_ASTC_ARRAY_MIB=256
env=EDEN_NX2_TC_EXPECTED_MIB=5632
env=EDEN_NX2_TC_CRITICAL_MIB=5888
env=EDEN_NX2_TC_LOG=60
log_filter=*:Info
```

- En el menú de la app: resolución **0.5x**, filtro **AMD FSR**.
- Lecciones aprendidas:
  - `anisotropico=N` pone la imagen blanca.
  - `gpu_accuracy=low` estropea la imagen.
  - El botón de foto del juego provoca brillos.
  - `astc_bc1=on` era la causa de las manchas del suelo y del público en Mario Kart World (transparencia de 1 bit): no usarla.

### Cómo agregar una opción al laboratorio
1. En `headless/lab.h`, junto a las demás:
   ```cpp
   else if (entry == "mi_opcion=off") SetVariable("EDEN_MI_VARIABLE", "0");
   ```
   Para números: `entry.starts_with("x=") && Number(entry, <largo de "x=">, n)`.
2. El código del núcleo lee la variable con `std::getenv` (normalmente una sola vez, en un `static`).
3. Documentar la opción en `docs/LABORATORIO.md` (tabla, en español: qué hace, valor por defecto, en qué línea del log se ve).

---

## 9. Historial de problemas resueltos (para no repetirlos)

| Problema | Causa | Solución |
|---|---|---|
| Juego pegado varios segundos | Escrituras del swap al SSD lentas y emergencias largas | Búferes intermedios, swap comprimido, tope de emergencia de 4 s |
| Tirones al consultar la memoria libre | Consulta en el hilo de la GPU | Hilo PoolWatch aparte |
| `medir=on` frenaba la GPU | Se vaciaba el log en cada línea | Se quitó ese vaciado |
| Cierre por búferes juntados enormes (478→908 MB) | La caché de búferes juntaba sin límite | Parche 0015 (`bufer_max`) |
| Cierre por búfer de índices >838 MiB | Búfer demasiado grande para el driver | El driver nuevo (Mesa f5610fe27) parte los búferes grandes |
| Imagen con ruido, blanca o con brillos | `gpu_accuracy=low` | `gpu_accuracy=high` |
| Cierre al cargar con dos hilos de GPU | Parche 0020 | Quitado |
| CI: RADV con otra versión de Mesa | PS5_Vulkan fija otra revisión | `build-radv-dependencies.sh` usa la de `deps.json` |
| Parches que no aplican | Finales de línea CRLF | Normalizar a LF (sección 5) |

---

## 10. Pendientes e ideas

1. **Probar el paquete actual** (0021 y 0022, `async_shaders=on`) y analizar los logs.
2. Si los terrenos en BC3 funcionan, subir `EDEN_NX2_ASTC_ARRAY_MIB` a 384 (2048x2048 por capa). Antes, revisar en el log que aparezca `Sparse layered image … block 256x256`.
3. **Hilo de la GPU (fps):** reducir el coste de `method`, `push` y `macro`, o lograr que el hilo dividido funcione con `gpu_accuracy=high`.
4. Revisar qué ocupa los ~4 GB de memoria gráfica que no son texturas (búferes, staging).
5. Revalorar el parche 0016 (`atajos_bufer`), hoy apagado por el laboratorio.
6. Posible mejora de calidad: codificar a BC7 en lugar de BC3 (mismo tamaño, mejor imagen). Requiere un shader nuevo.

---

## 11. Cómo trabajar en paralelo en dos computadoras

- **Conviene clonar desde GitHub, no copiar la carpeta**, y trabajar en una **rama propia** para no pisar el trabajo de la otra computadora:
  ```bash
  git clone --recursive https://github.com/Sebaneg/EglantinePS5.git
  cd EglantinePS5
  git checkout update/eglantine-nov4
  git checkout -b pruebas-aider
  bash tools/apply-eglantine-patches.sh   # deja el submódulo con los parches aplicados
  ```
- Los cambios que no se han subido a GitHub **no viajan con el clon**. Si se necesitan, copiar la carpeta completa (incluye `.git` y el submódulo, ~115 MB), o subirlos antes con la autorización del dueño.
- Para compilar las pruebas de esa rama en GitHub Actions:
  ```bash
  gh workflow run release.yml -R Sebaneg/EglantinePS5 --ref pruebas-aider
  ```
  Siempre con la orden del dueño.
- Iniciar Aider sin commits automáticos y con los archivos relevantes:
  ```bash
  aider --no-auto-commits headless/lab.h docs/LABORATORIO.md
  ```
  El submódulo Eglantine es grande. Agregar al chat solo los archivos que se van a tocar, y usar `/read` para los de consulta.
