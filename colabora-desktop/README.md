# Nexo — modelo NoSQL

La aplicación usa **MongoDB Atlas**. El código Python se conecta con PyMongo. Los adjuntos se guardan dentro de Atlas con GridFS (`fs.files` y `fs.chunks`). No depende de un servidor web ni de un servicio de almacenamiento de pago.

## Colecciones

| Colección | Contenido |
| --- | --- |
| `users` | Usuarios de Nexo con contraseñas derivadas por PBKDF2 y sal individual. |
| `workspaces` | Espacios de colaboración. |
| `memberships` | Relación usuario-espacio y rol. |
| `channels` | Canales dentro de cada espacio. |
| `posts` | Actualizaciones, preguntas, anuncios e hitos; arreglo de reacciones y referencias a adjuntos. |
| `comments` | Conversación vinculada a una publicación. |
| `tasks` | Tareas con estado, prioridad y responsable. |
| `notifications` | Avisos para miembros del espacio. |
| `attachments` | Metadatos de archivos alojados en GridFS. |

Se crean índices únicos para usuarios y canales, y otros índices para filtrar publicaciones, tareas y avisos. La app restringe lectura y cambios a miembros de cada espacio; solo quien es propietario puede crear cuentas para otros miembros.

## Conectar Atlas

1. Crea un clúster gratuito M0 en tu cuenta de MongoDB Atlas.
2. Crea un usuario de base de datos con permiso de lectura y escritura para `nexo_colabora`.
3. Permite en *Network Access* la IP desde la que ejecutarás Nexo. Evita abrir acceso a todo Internet si puedes usar tu IP.
4. Copia la URI `mongodb+srv://...` desde **Connect → Drivers → Python**. Sustituye la contraseña por la de tu usuario de base de datos y codifica caracteres especiales de la contraseña como indica Atlas.
5. Ejecuta `iniciar.bat`, pega la URI y crea el primer usuario de Nexo.

La URI queda en `.env` local, excluido por `.gitignore`. Las contraseñas de usuarios de Nexo se almacenan como derivaciones, no en texto claro. Al crear el propietario se agregan datos de demostración.

## Consultas de práctica

En `consultas_mongo.py` hay agregaciones para contar publicaciones por canal, tareas por estado y archivos por tipo. Ejecútalo con `python consultas_mongo.py` cuando la app ya esté conectada.
