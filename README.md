# Proyecto final de bases de datos — dos productos independientes

Este directorio contiene dos aplicaciones completas con modelos de datos distintos:

| Producto | Interfaz | Base de datos | Ejecución |
| --- | --- | --- | --- |
| **Inventario Studio** | Web con presentación y panel de gestión | Oracle FreeSQL (relacional) | `inventario-web/iniciar.bat` |
| **Nexo** | Escritorio Python, temas blanco y negro | MongoDB Atlas (documental) | `colabora-desktop/iniciar.bat` |

Los datos de las dos apps no se mezclan. Las credenciales van en archivos `.env` locales y nunca en GitHub.

## Inventario Studio

Funciones: productos, categorías, proveedores, clientes, entradas y salidas, ventas con comprobante interno imprimible, reportes de existencias, ingresos y ganancia bruta. Cada venta crea partidas y movimientos, y actualiza existencias en una transacción. Incluye 16 productos, 4 clientes, 3 proveedores, 5 categorías y 5 ventas de ejemplo al crear un esquema vacío. El comprobante sirve para practicar relaciones y ventas; no sustituye una factura fiscal CFDI.

**Inicio local:** en `inventario-web`, instala Python 3.13 y ejecuta `pip install -r requirements.txt`. Copia `.env.example` a `.env` y escribe la conexión de tu esquema Oracle FreeSQL:

```text
FREESQL_USER=tu_usuario_del_esquema
FREESQL_PASSWORD=tu_contraseña_del_esquema
FREESQL_DSN=host:puerto/servicio
```

Ejecuta `iniciar.bat` y abre `http://127.0.0.1:8050`. Sin `FREESQL_DSN`, la app usa una base SQLite local **solo para practicar y verificar**; la interfaz indica este modo. Para presentar el producto conectado, configura Oracle y comprueba que la interfaz diga `Oracle FreeSQL`.

**Despliegue:** `render.yaml` define un servicio web gratuito con Python. GitHub Pages solo publica archivos estáticos y no ejecuta el servidor que conecta de forma segura con Oracle; por eso el código se guarda en GitHub y la URL web pública se sirve desde Render. En Render configura las cinco variables secretas del manifiesto. El servicio exige usuario y contraseña de acceso cuando se publica fuera de `localhost`.

El esquema está en `inventario-web/schema.oracle.sql`; consultas para demostrar SQL en `inventario-web/consultas.oracle.sql`.

## Nexo

Aplicación Python con espacios, canales, publicaciones generales o dirigidas a una persona, preguntas, hitos, comentarios, reacciones, tablero de tareas, miembros, notificaciones y biblioteca de archivos. Las fotos y documentos se guardan en GridFS, con límite de 5 MB por archivo para cuidar el nivel gratuito de Atlas.

**Inicio:** en `colabora-desktop`, ejecuta `pip install -r requirements.txt` y después `iniciar.bat`. La primera pantalla pide la cadena de conexión de MongoDB Atlas. Al conectar se guarda solo en `.env` local; los siguientes inicios conectan automáticamente y muestran el acceso a Nexo. Crea el usuario propietario de Nexo y la app generará un espacio con cuatro canales, tres publicaciones y tres tareas de ejemplo. Para que otros participen, crea sus usuarios desde **Personas**; todos deben usar la misma base Atlas y ejecutar su propia copia de la app. Cada persona puede cambiar su contraseña desde el control junto a su nombre.

La instancia de Atlas de este proyecto tiene cuatro usuarios de demostración, once publicaciones, siete tareas y un adjunto. Sus accesos están únicamente en el archivo local `colabora-desktop/.nexo-owner`, excluido de GitHub.

El modelo y las consultas de agregación están documentados en `colabora-desktop/README.md`.

## Nota de evaluación

En Oracle se pueden demostrar claves primarias y foráneas, integridad referencial, transacciones, `JOIN`, `GROUP BY` y agregados. En MongoDB se pueden demostrar documentos, subdocumentos y arreglos, índices, consultas por filtros, agregaciones y GridFS.
