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
| `teselacion=off` | No dibuja lo que usa teselación (terreno, agua...). Faltarán partes de la escena; sirve para saber si la teselación cuelga la GPU. |
| `dispersas=on` | Activa las texturas "dispersas" gigantes de Eglantine (vienen apagadas: colgaron la consola). |
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
