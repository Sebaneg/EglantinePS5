# Modo laboratorio

El modo laboratorio deja probar opciones en la consola **sin compilar otra versión**. Las opciones
van en un archivo de texto:

```
/data/eglantineps5/laboratorio.txt
```

- Una opción por línea. Lo que va después de `#` es un comentario.
- La app lee el archivo **antes de cada partida**: cambias el archivo (por FTP, por ejemplo),
  vuelves a la biblioteca, empiezas el juego otra vez y ya está.
- Una opción que quitas del archivo vuelve a su valor normal en la siguiente partida. Solo los
  filtros de registro (`log=`, `log_filter=`) duran hasta que se cierra la app.
- `/data/eglantineps5/logs/stderr.log` dice cada opción que leyó, después de las líneas
  `launch:` de la partida: `laboratorio: applied: ...`, o `unknown, ignored: ...` si una línea no
  se entiende. Si no sale ninguna línea `laboratorio`, la app no encontró el archivo.
- Sin archivo, la app funciona como siempre.

Ejemplo:

```
# Mario Kart World: ¿la teselación cuelga la GPU?
teselacion=off
pipeline_trace=on
```

> **Cuidado:** algunas opciones pueden colgar la GPU. Si la consola deja de responder, mantén
> pulsado el botón de encendido unos 10-15 segundos. Prueba **una sola opción nueva cada vez**: si
> cambias varias a la vez, no se sabe cuál hizo efecto.

## Gráficos (GPU)

| Opción | Qué hace |
|---|---|
| `mesh=on` / `off` | Los dibujos con *mesh shaders*. Vienen **apagados** (`off`): con el controlador RADV cuelgan la GPU en Mario Kart World (también en PC con tarjetas AMD). Con `off` faltan algunas partes de la imagen. Cuenta desde el primer juego que se abre después de iniciar la app. |
| `teselacion=off` | No dibuja lo que usa teselación (terreno, agua...). Faltarán partes de la escena; sirve para saber si la teselación cuelga la GPU. |
| `dispersas=on` | Activa las texturas "dispersas" gigantes de Eglantine (vienen apagadas: colgaron la consola). |
| `zonas_gpu_trozos=on` | Las zonas de texturas "solo GPU" de 1 GB o más (en Mario Kart World, las de 5,8 y 1,4 GB) usan los trozos de memoria que el juego pone en ellas, como las zonas dispersas, en vez de memoria aparte. En Mario Kart World eran 1,3 GB de más al empezar la intro. Se lee una vez por arranque de la app. En `eden_log.txt`: `GPU-only region at ... takes the game's tiles`. |
| `zonas_gpu_minimo=N` | El tamaño mínimo (en MB, de 286 a 1024; sin esta línea, 1024) de las zonas que toma `zonas_gpu_trozos=on`. En Mario Kart World hay otra zona "solo GPU" de 341 MB cuya textura se subía entera con un búfer temporal de 352 MB, justo al cargar la carrera. Con `zonas_gpu_minimo=300` entra esa zona, y las de imagen de pantalla (285 MB) siguen fuera. Solo tiene efecto junto a `zonas_gpu_trozos=on`. Se lee una vez por arranque de la app. |
| `capas_max=N` | Cuánta memoria gráfica (en MB, de 128 a 768; sin esta línea, 768) puede ocupar cada textura del terreno por capas. En Mario Kart World cada capa mide 85 MB: con 768 pueden cargarse 9 capas a la vez, con 256 solo 3. Menos memoria, pero el terreno lejano puede verse sin textura mientras carga. Se lee una vez por arranque de la app. |
| `astc_temporal=N` | Cuánta memoria (en MB, de 0 a 2048; sin esta línea, 192) pueden ocupar a la vez las imágenes temporales con que se convierten las texturas ASTC a BC. Cada una ocupa 8 veces lo que la textura final, y antes vivían hasta el fotograma siguiente: al cargar la carrera de Mario Kart World llegaron a 1,7 GB en un segundo y medio, y el juego se cerró. Al llegar al tope, el emulador espera a la GPU y las libera (puede dar un tirón corto al cargar). `0` quita el tope. Se lee una vez por arranque de la app. En `eden_log.txt`: `ASTC transcode waited for the GPU`. |
| `cola_descriptores=N` | Divide entre N (de 1 a 8; sin esta línea, 1) la cola donde el emulador prepara los recursos de cada dibujo: ocupa 96 MB fijos, 24 MB con `4`. Si un fotograma la llena, espera un momento a que se vacíe, sin cerrarse. Se lee al arrancar el juego. |
| (sin línea) | Desde la compilación del parche 0010, cuando la memoria escasea, los búferes temporales que la GPU ya no usa se sueltan en cada fotograma, en vez de esperar a que una petición falle. En `stderr.log`: `EDEN_STAGING_SHORT released ...`. Para volver a lo de antes: `env=EDEN_STAGING_KEEP_WHEN_SHORT=1`. |
| `sparse=off` | Apaga toda la memoria "dispersa" de la GPU (más drástico que lo anterior). |
| `multirange=off` | Une los búferes de varios trozos a la manera antigua. |
| `null_descriptor=off` | Sin descriptores nulos. |
| `descriptor_buffer=off` | Sin búferes de descriptores. |
| `robustness2=on` | Accesos de la GPU fuera de rango, seguros (más lento). |
| `custom_border=on` / `off` | Colores de borde de textura propios (vienen apagados: algunos juegos fallaban). |
| `conditional_rendering=off` / `on` | Dibujo condicional por la GPU. |
| `hcr=eden` / `exact` / `cpu` | Cómo se decide el dibujo condicional (`exact` es el normal). |
| `compute_barriers=off` | Quita las barreras de sincronización de los cálculos de la GPU. |
| `vertex_input_dynamic=off` | Sin entrada de vértices dinámica. |
| `dyna_state=0` … `3` | Nivel de estado dinámico extendido. |
| `astc=cpu` / `gpu` | Dónde se descomprimen las texturas ASTC. |
| `astc_bc1=on` | Las texturas ASTC se recomprimen a BC1 (la mitad de memoria) en vez de BC3. Las transparencias suaves (humo, hojas, cristales) pueden verse con bordes duros. |
| `vram=aggressive` / `conservative` | Cuánta memoria gráfica usa (aggressive es el normal). |
| `gpu_clock=normal` / `boost` / `overclock` | Velocidad de la GPU que ve el juego. |
| `gc_dirty=upstream` | Libera antes las texturas que escribió la GPU. |
| `graphics_usage=driver` | Mide la memoria gráfica como la cuenta el controlador. |
| `dispatch_draws=8` … `512` | Dibujos entre entregas al hilo de Vulkan (potencia de 2). |

## Envío de imágenes a la tele

`stderr.log` dice en cada partida cómo se envían: `present: frames in flight ..., swapchain images ..., vsync mode ..., present thread ...`.

| Opción | Qué hace |
|---|---|
| `vsync=fifo` / `mailbox` / `immediate` / `relaxed` | Cómo espera al refresco de la tele. `fifo` es el normal; si el controlador de la PS5 no admite otro, usa `fifo` igualmente. |
| `presentacion_hilo=on` / `off` | Envía las imágenes desde un hilo aparte (`off` es el normal). |
| `imagenes=1` … `7` | Cuántas imágenes pueden ir en cola a la vez. Menos imágenes: menos ráfagas, pero puede ir más lento. |

## Sincronización

| Opción | Qué hace |
|---|---|
| `atajo=off` | Un canal de la GPU que espera una señal solo sigue cuando la señal tiene de verdad el valor esperado. Por defecto Eglantine lo deja seguir si la señal llegó a ese valor en algún momento (`CanResumeAcquire ... met semaphore` en `eden_log.txt`). Puede volver un congelamiento que ese atajo evitaba. |

## Diagnóstico de la GPU

| Opción | Qué hace |
|---|---|
| `pipeline_trace=on` | Anota en `stderr.log` cada programa gráfico la primera vez que se usa: los de dibujo como `G1 ... vb=... fs=...` y los de cálculo como `C1 cs=...`. El último antes de un cuelgue es el sospechoso. |
| `saltar_programa=HASH` | No ejecuta lo que usa ese programa. `HASH` es uno de los valores que lista `pipeline_trace`: `vb=` o `fs=` de un programa de dibujo, o `cs=` de uno de cálculo. Por ejemplo `saltar_programa=929ba7ee0d94ab75`. Se pueden poner varias líneas. Saltarse un cálculo puede romper el juego de otras formas: es solo para averiguar qué cuelga la GPU. |
| `congelamiento_hilo=NOMBRE` | Si el juego se congela 30 s, el informe muestra dónde estaba ese hilo en vez del de la GPU. Nombres: `GPU` (el normal), `VulkanWorker` (el que envía el trabajo a la GPU), `GPUFencingThread` (el que espera a que la GPU termine), `VulkanPresent` (el que envía imágenes a la tele), `GPUBack`. |
| `medir=on` | Enciende todas las mediciones a la vez (tiempos de Vulkan, hilo de la GPU por zonas, caché de texturas, tirones a 700 ms). Ver "Medir todo de una vez" más abajo. |
| `tirones=N` | Cuando el juego pasa N milisegundos (de 300 a 10000) sin mostrar un cuadro, anota en `stderr.log` dónde está cada hilo principal, sin cerrar el juego: el de la GPU, los de Vulkan y los 4 núcleos del juego (`CPUCore_0` a `CPUCore_3`). Una línea `EDEN_HITCH n=... still_ms=... HILO at ... calls ...` por hilo, hasta 4 rondas por tirón (a N, 2N, 3N y 4N ms), y `EDEN_HITCH end n=... lasted_ms=...` cuando vuelve a haber cuadros. Si el hilo está dentro de una llamada que puede tardar (leer o escribir el swap, un fallo de memoria del juego, entregar trabajo a la GPU, esperar a la GPU o el candado de envío), la línea añade `doing="..." for_ms=...`; eso sale aunque el hilo `did not answer` (atascado en el sistema). Otros hilos ocupados en esas llamadas (`Swapper`, `GuestScan`) salen como `HILO busy doing=...`. Empieza 20 s después de que el juego muestre su primer cuadro. Recomendado: `tirones=700`. Se lee al arrancar el juego. |
| `submit_sync=on` | Espera a la GPU después de cada envío. Muy lento, pero el cuelgue queda en el envío exacto. |
| `gpu_time=on` | Mide el tiempo de la GPU de cada envío. |
| `radv_debug=...` | Opciones del controlador gráfico, separadas por comas. Por ejemplo `radv_debug=syncshaders` (espera a cada programa) o `radv_debug=nodcc,nohiz` (sin compresiones). |
| `env=NOMBRE=valor` | Cualquier otra variable del controlador. No cambies las que pone la propia app. |

## Velocidad y precisión

Estas se aplican **después** de los ajustes del juego (Ajustes > Rendimiento), así que mandan sobre ellos.

| Opción | Qué hace |
|---|---|
| `async_shaders=on` / `off` | Programas gráficos en segundo plano. |
| `reactive_flushing=on` / `off` | Vaciado reactivo. |
| `skip_invalidation=on` / `off` | Saltar invalidaciones de la CPU. |
| `gpu_accuracy=low` / `high` | Precisión de la GPU (`low` = GPU rápida). |
| `cpu_accuracy=unsafe` / `auto` | Precisión de la CPU. |
| `dma_accuracy=unsafe` / `default` | Precisión de las copias de memoria. |

## CPU y memoria

| Opción | Qué hace |
|---|---|
| `memoria_compacta=on` | La memoria del juego se reparte en bloques de 2 MB. Con esto, un bloque con muchas partes vacías (ceros) guarda solo las partes usadas, de 16 KB. Libera memoria; cuando el juego vuelve a escribir en uno de esos bloques espera un momento (unos 0,3 ms). En `stderr.log`: `EDEN_CRAM on: ... fine=1`, y `fine_held=` dice cuánto guarda así. |
| `bloques_repetidos=on` | Los bloques de 2 MB con el mismo contenido se guardan una sola vez. En un juego grande bajó de 30 a 20 FPS. En `stderr.log`: `EDEN_CRAM on: ... dedup=1`, y `dedup=` cuenta los bloques compartidos. |
| `reserva_juego=N` | La reserva de memoria para el juego, en MB (de 32 a 1024; sin esta línea, 1024). Es memoria apartada para cuando el juego escribe de golpe y no queda libre. Mario Kart World nunca la usó mientras a los gráficos les faltaba memoria. En `stderr.log`: `EDEN_CRAM ... reserve_used=` cuenta los bloques que el juego tomó de ella. Para probar: `reserva_juego=256`. |
| `memoria_util=on` | Mide la memoria que puede usar la gráfica como la suma de los huecos libres de 16 MB o más, y no solo el hueco más grande. Con `juego_arriba=on` el hueco más grande es el que queda entre el juego y la gráfica, y en la carrera de Mario Kart World no pasaba de 240 MB: el emulador creía que faltaba memoria todo el rato y el caché de texturas borraba sin parar (0–5 FPS). |
| `memoria_corta=N` | Por debajo de cuántos MB libres el emulador considera que falta memoria (de 128 a 1024; sin esta línea, 1024). Con `memoria_util=on`, un valor como 384 deja trabajar al caché de texturas con normalidad mientras la gráfica tenga sitio para lo que pide (hasta ~96 MB a la vez). |
| `margen_texturas=N` | Cuánta memoria (MB, de 0 a 3072; sin esta línea, 3072) puede llegar a reservar como margen el caché de texturas cuando una textura no cabe. Antes ese margen bajaba cada 600 fotogramas (a 2 FPS, 5 minutos); ahora baja 256 MB cada 5 segundos sin problemas (parche 0012). Un tope más bajo, como 1024, evita que el caché borre texturas de más. |
| `juego_arriba=on` | La memoria del juego (sus bloques de 2 MB) se toma desde el final de la memoria de la consola, y la gráfica sigue tomándola desde el principio. Sin esto se mezclaban: cuando el juego liberaba bloques (por ejemplo, al mandarlos al disco con `swap=on`), quedaban huecos de 2 MB entre la memoria gráfica que la gráfica no puede usar. En Mario Kart World quedaron 1,5 GB libres pero el bloque más grande era de 214 MB, y el juego bajó a 1–5 FPS. Se lee al empezar el juego. |
| `swap=on` | **Intercambio a disco de la memoria del juego.** Cuando la memoria escasea, los bloques de 2 MB del juego que nadie toca desde hace unos segundos se guardan en `/data/eglantineps5/swap_juego.bin` y su memoria vuelve a la consola; si el juego los vuelve a usar, se leen del SSD (~1 ms) y sigue. Así el juego no se cierra cuando su memoria no cabe: en el peor caso da un tirón. Empieza a vigilar bloques con menos de 2,5 GB libres en total y a guardarlos con menos de 1 GB libre en total, hasta volver a 1,5 GB. Si la memoria libre está troceada pero hay bastante en total, no guarda nada (no serviría). Se lee al empezar el juego. En `stderr.log`: `EDEN_SWAP now probation=... swapped=... swap_outs=... swap_ins=...`. Además, si la gráfica pide memoria y no hay, en vez de cerrarse el juego manda al SSD al instante hasta 512 MB del juego (del borde junto a la gráfica) y lo vuelve a intentar hasta 3 veces (en `stderr.log`: `EDEN_GRAPHICS_MEMORY emergency`). Prueba de PC: `tools/check-guest-swap.py`. |
| `swap_frio=N` | Segundos sin que nadie toque un bloque antes de poder guardarlo en el disco (de 2 a 120; sin esta línea, 8). Más bajo libera antes pero puede traer bloques de vuelta más a menudo. Solo con `swap=on`. |
| `swap_bloque=on` | El swap también escribe al SSD para agrandar el bloque libre más grande de la memoria (con `juego_arriba=on`), como antes. Sin esta línea no lo hace: en Mario Kart World ese bloque se quedó en 62 MB mientras el swap escribía 64 MB cada 10 s, con 1,4 GB libres, y el SSD (que escribe a ~1 MB/s) pasaba ocupado todo el tiempo: lecturas del swap de hasta 2,8 s y tirones largos. Si a los gráficos les falta un bloque, el rescate de emergencia saca memoria al momento. Además, salvo urgencia (menos de 512 MB libres, o el juego esperando memoria), el swap escribe un bloque y deja descansar al SSD. Se lee al arrancar el juego. Solo con `swap=on`. |
| `atajos_bufer=off` | La caché de búferes vuelve a revisar, en cada dibujo, todas las páginas de cada búfer que usa. Sin esta línea se salta las que la CPU no ha vuelto a escribir (parche 0016, traído de viejunerd/Eglantine-PS5-: en Donkey Kong Bananza esa revisión era el 7 % del tiempo de dibujo). Si aparecen objetos o modelos que no se actualizan, probar con esta línea. Se lee una vez por arranque de la app. |
| `gpu_dos_hilos=off` | El hilo de la GPU no se parte en dos aunque `gpu_accuracy=low` lo permita. Con `gpu_accuracy=low`, el trabajo de los motores de la GPU va a un segundo hilo (en `eden_log.txt`: `GPU thread split: engine methods run on a second thread`); el parche 0017 (de viejunerd/Eglantine-PS5-) evita que ese segundo hilo se quede dormido, que congelaba Mario Kart World. Se lee una vez por arranque de la app. |
| `bufer_max=N` | El búfer más grande (en MB, de 0 a 4096; sin esta línea, 256) que la caché de búferes crea al juntar búferes que se tocan en memoria. Por encima, en vez de juntarlos, los suelta (después de guardar en la memoria del juego lo que la GPU escribió) y crea solo lo pedido. En Mario Kart World los búferes juntados crecían vuelta a vuelta (478 MB, 908 MB) hasta que no cabían y el juego se cerraba. `0`: sin límite, como antes. Se lee una vez por arranque de la app. En `eden_log.txt`: `Buffer join of ... MiB over the limit`. |
| `swap_comprimido=off` | El swap manda los bloques al SSD, como antes. Sin esta línea, primero los comprime con LZ4 y los guarda en la memoria: un bloque que queda en menos de 3/4 de su tamaño no toca el SSD (sacarlo y traerlo tarda milisegundos y nunca se traba); los que no comprimen van al SSD. En Mario Kart World el SSD a veces escribía a 250 MB/s y otras a 38 MB/s, con escrituras de 3,8 s que congelaron el juego. En `stderr.log`, la línea `EDEN_SWAP_PACK` dice cuántos bloques hay comprimidos, cuánto ocupan (`ratio`) y cuánto tarda comprimir y descomprimir. Solo con `swap=on`. |
| `swap_intermedio=off` | El swap escribe y lee el SSD directamente desde la memoria del juego, como antes. Sin esta línea pasa por cuatro búferes intermedios de memoria normal del sistema, y la línea `EDEN_SWAP_IO` de `stderr.log` dice por separado la velocidad del SSD (`write_mib_s`, `read_mib_s`) y lo que tardan las copias. Así se sabe si lo lento es el SSD o copiar desde la memoria del juego (en Mario Kart World, ~1 MB/s escribiendo directo). Solo con `swap=on`. |
| `swap_caliente=N` | Segundos que un bloque que volvió del disco se queda en memoria sin que el swap lo vuelva a tocar (de 0 a 3600; sin esta línea, 120). Un bloque que el juego tocó mientras estaba "a prueba" queda protegido la cuarta parte de ese tiempo. En la carrera de Mario Kart World el swap sacaba memoria que el juego volvía a usar en la vuelta siguiente: 591 de 1232 bloques volvieron, cada uno con una lectura del SSD dentro del hilo del juego, y la carrera se paraba de 1 a 10 s. `0` deja el swap como antes. El rescate de emergencia de los gráficos sigue pudiendo sacarlos. En `stderr.log`, la línea `EDEN_SWAP` dice `slow_swap_ins=` (lecturas de 50 ms o más) y `swap_in_worst_ms=` (la más lenta desde la línea anterior). Solo con `swap=on`. |
| `heap_bloque_propio=N` | La memoria interna del emulador: los bloques de N MB o más (de 2 a 32; sin esta línea, 32) tienen memoria aparte, que vuelve a la consola al liberarlos. Si no, dejan huecos que solo otro bloque del mismo tamaño puede usar. Puede ir algo más lento. En `stderr.log`, la línea `heap: holds ... MiB, ... MiB of it in use` dice cuánto retiene y cuánto usa. Para probar: `heap_bloque_propio=4`. |
| `heap_trozo=N` | Cuánto crece de golpe la memoria interna del emulador: 32, 64, 96 o 128 MB (sin esta línea, 128). Solo un trozo que se queda completamente vacío vuelve a la consola, y uno de 128 MB casi nunca se vacía: Mario Kart World retenía 2,7 GB con 1,4 GB en uso. Con trozos más pequeños se vacían y se devuelven más a menudo. Puede ir algo más lento. En `stderr.log`, la línea `heap: holds ... MiB, ... MiB of it in use` dice cuánto retiene y cuánto usa. Para probar: `heap_trozo=32`. |
| `pila_hilos=N` | La pila de cada hilo del juego, en KB (de 256 a 2048; sin esta línea, 2048). En la PS5 esa memoria se ocupa entera desde el principio: Mario Kart World tiene 151 hilos, 302 MB con 2048 KB y 75 MB con 512 (lo que usaba yuzu). Si el juego se cierra de golpe al cargar con una pila pequeña, sube el número (1024) o quita la línea. Para probar: `pila_hilos=512`. |
| `jit_nucleos=N` | La memoria para el código traducido de los núcleos 3, 4 y 5, en MB (de 16 a 128, de 16 en 16; sin esta línea, 16). Los juegos de Switch 2 usan esos núcleos: en Mario Kart World se llenaban unas 50 veces cada uno, y cada vez se borra y se vuelve a traducir todo (tirones de segundos). Pasados 16 MB, la memoria se ocupa de 16 en 16 MB solo si hace falta. En `heap.log`, menos líneas `EDEN_JIT_PRESSURE core=3/4/5`. Para probar: `jit_nucleos=64`. |
| `heap_arenas=N` | Cuántas "arenas" (bloques de 8 MB para las peticiones pequeñas de cada hilo, que nunca se devuelven) puede crear la memoria interna del emulador: de 8 a 256 (sin esta línea, 256). Pasado el límite, los hilos comparten las que hay: menos memoria, quizá algo más lento al compilar sombreadores. En `stderr.log`, la línea `heap pieces: N arenas ... MiB` dice cuántas hay y cuánto usan. |
| `jit_list=on` / `off` | La lista de bloques de código ya traducidos (manda sobre Ajustes). |
| `jit_shared=off` | Cada núcleo traduce su propio código. |
| `fastmem=on` / `off` | Acceso directo a la memoria del juego (en la consola suele ir más lento). |
| `cache_spin=N` | Intentos antes de que un núcleo duerma esperando a la caché de la GPU. |
| `idle_spin_us=N` | Microsegundos que un núcleo espera activo antes de dormir. |

## Registros

| Opción | Qué hace |
|---|---|
| `log=render` | Registro detallado de los gráficos. |
| `log_filter=...` | Cualquier filtro de Eden, con `+` en lugar de espacios: `log_filter=*:Info+Render.Vulkan:Debug`. |
| `env=EDEN_NX2_TC_LOG=N` | Cada N fotogramas, en `eden_log.txt`: la memoria de gráficos en uso y las 12 texturas más grandes (`Texture cache: device memory ...`). Con `1` o sin número, cada 600. |

## La línea `EDEN_TIMELINE` (stderr.log, cada 2 s)

Escribe en una sola línea lo que decide cómo va el juego, para ver qué cambia justo cuando se pone lento. Sigue escribiéndose aunque el juego casi no dibuje.

| Campo | Qué es |
|---|---|
| `t` | Segundos desde que empezó el juego. |
| `fps`, `worst_ms` | Fotogramas por segundo en esos 2 s, y la espera más larga entre dos fotogramas. |
| `free`, `largest` | Memoria libre de la consola en total, y su bloque libre más grande (MB). Si `free` es alto pero `largest` bajo, la memoria está troceada. |
| `short` | 1 si el emulador cree que falta memoria (el caché de texturas borra texturas). |
| `guest`, `heap`, `jit`, `gpu_rest` | Memoria del juego, interna del emulador, del código traducido, y el resto (casi todo gráfica), en MB. |
| `swapped` | Memoria del juego guardada en el SSD ahora (`swap=on`). |
| `written` | Bloques de 2 MB que el juego escribió por primera vez en esos 2 s (el juego pidiendo memoria nueva). |
| `waits` | Veces que un hilo esperó a que otro terminara con un bloque. |
| `swap_out`, `swap_in` | Bloques mandados al SSD y traídos de vuelta en esos 2 s. Muchos `swap_in` seguidos = el juego necesita lo que se guardó (tirones). |
| `probe_hits` | Bloques en vigilancia que el juego volvió a tocar. |

## La línea `EDEN_TIMELINE2` (stderr.log, después de cada `EDEN_TIMELINE`)

Dice en qué se fue el tiempo en esos mismos 2 s.

| Campo | Qué es |
|---|---|
| `idle0` … `idle3` | Porcentaje del tiempo que cada núcleo del juego estuvo esperando trabajo. Cerca de 100 en un tirón: el juego espera algo (la GPU, el disco, el swap). Cerca de 0: el propio trabajo del juego es el límite. |
| `swap_in_worst_ms` | La lectura del swap más lenta en esos 2 s. |
| `submit`, `fence_wait`, `semaphore_wait`, `guest_fence`, `buffer_sync`, `texture_sync`, `present_sync`, `pipeline_wait`, `pipeline_build`, … | Solo con `medir=on`: milisegundos pasados en cada llamada de Vulkan que puede bloquear, y cuántas hubo (`ms/llamadas`). Se solapan entre hilos: no se suman. |

## Medir todo de una vez: `medir=on`

Una línea en `laboratorio.txt` enciende todo lo que hace falta para saber dónde se va el tiempo de un juego lento, con un coste pequeño:

- los tiempos de Vulkan en `EDEN_TIMELINE2`;
- el tiempo del hilo de la GPU por zonas, cada 10 s, en `eden_log.txt` (`GPU thread per second: | idle ... | draw ... | texture upload ...`);
- las cifras del caché de texturas cada 60 fotogramas;
- el registro de tirones a los 700 ms (una línea `tirones=N` lo cambia).

`eden_log.txt` no se escribe línea a línea: con el SSD ocupado por el swap, cada línea hacía esperar al hilo de la GPU. Para no perder su final, deja el juego unos segundos antes de salir.

Después de la prueba, en el PC, `tools/analyze-run.py` resume la carpeta de logs: fotogramas, tirones con los nombres de las funciones, swap, hilo de la GPU, caché de texturas, y un veredicto.

```
python3 tools/analyze-run.py CARPETA_DE_LOGS EglantinePS5-v1.000.000.elf
```

El `.elf` es el artefacto `EglantinePS5-symbols` de la compilación que se probó.

## Calidad de imagen

En el menú de la app (Ajustes > Video, o Biblioteca > ajustes del juego > Video):

| Ajuste | Efecto | Coste |
|---|---|---|
| Filtro **AMD FSR** en lugar de Bilinear | Escala la imagen interna a la salida con bordes nítidos, en vez de borrosa. La mejora más grande para 0.5x. | Casi nada: un paso más en la GPU por cuadro, sin memoria extra. |
| Resolución **0.75x** en lugar de 0.5x | Más detalle real. | Unas 2,25 veces los píxeles por cuadro y más memoria de gráficos para las imágenes en las que dibuja el juego. Probar cuando el swap ya no frene. |

En `laboratorio.txt`:

| Opción | Qué hace | Coste |
|---|---|---|
| `anisotropico=N` | Texturas vistas en ángulo (la pista por delante, el suelo) nítidas en vez de borrosas. `N` = 2, 4, 8 o 16; `0` deja lo que pide el juego (sin la línea). | Poco en la GPU, nada de memoria. `anisotropico=8` es un buen punto. |
| `aa=off` / `aa=fxaa` / `aa=smaa` | Suaviza los bordes dentados. Sin la línea: `fxaa`. `smaa` suaviza mejor y emborrona menos. | `smaa` cuesta un poco más de GPU que `fxaa`. |
| `nitidez_fsr=N` | Cuánto enfoca el filtro AMD FSR (de 0 a 200; sin la línea, 25). `50` a `80` se ve más nítido a 0.5x. | Nada. |
| quitar `astc_bc1=on` | Las texturas con transparencias (humo, hojas, cristales) recuperan sus bordes suaves. | El doble de memoria para esas texturas: probar cuando sobre memoria. |
