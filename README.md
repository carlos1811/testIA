# citasIA (MVP)

Aplicación web de citas asistida por IA. El objetivo del MVP es que una persona se registre, inicie sesión y converse con una IA para construir un perfil psicológico que permita generar compatibilidades con otros usuarios.

## Objetivo

- Mejorar las apps de citas tradicionales incorporando variables humanas más profundas (estilo de escritura, patrones de pensamiento y rasgos psicológicos).
- Entregar una base técnica mantenible para iterar rápidamente.

## Alcance del MVP

### Incluye
- Registro de usuario.
- Login de usuario.
- Chat con IA para capturar señales psicológicas.
- Base para cálculo de compatibilidad entre usuarios.
- Base para chat entre matches.

### No incluye (por ahora)
- Integraciones externas complejas.
- Algoritmo avanzado de matching en producción.
- Aplicación móvil nativa.

## Arquitectura propuesta (resumen)

- **Backend:** FastAPI (Python), modular por dominios.
- **Base de datos:** PostgreSQL.
- **Autenticación:** JWT (access token) con roles de usuario.
- **Frontend:** UI simple (HTML/CSS/JS) para prototipo.
- **Despliegue inicial:** local con Docker Compose.

Más detalle en [`docs/architecture.md`](docs/architecture.md).

## Estructura de proyecto

```text
backend/
  app/
    api/routes/      # endpoints (auth, chat IA, matches)
    core/            # configuración global
    db/              # conexión y sesión DB
    models/          # entidades SQLAlchemy
    schemas/         # modelos Pydantic
    services/        # lógica de negocio
    main.py          # entrypoint FastAPI
  Dockerfile         # imagen del backend
frontend/
  index.html         # interfaz base del prototipo
docs/
  architecture.md    # arquitectura, datos y roadmap
docker-compose.yml   # levanta postgres + backend
tests/               # pruebas (pendiente de completar)
```

## Cómo ejecutarlo (rápido con Docker)

Sí: para facilitarte el arranque ya quedó agregado PostgreSQL con Docker Compose.

1. Desde la raíz del proyecto (`/workspace/testIA`), levantar servicios:

```bash
docker compose up --build
```

Si haces cambios nuevos en el código y quieres asegurarte de levantar la última versión:

```bash
docker compose down
docker compose up --build --remove-orphans
```

2. Verificar backend:

- Healthcheck: <http://localhost:8000/health>
- Docs Swagger: <http://localhost:8000/docs>

Esto levanta:
- `postgres` en `localhost:5432`
- `backend` FastAPI en `localhost:8000`

La configuración Docker del backend se toma desde `backend/.env.docker` para mantener separados los valores de contenedor frente a local.

## Arranque local sin Docker (opcional)

1. Crear entorno virtual.
2. Instalar dependencias desde `backend/requirements.txt`.
3. Exportar variables de entorno (ejemplo en `backend/.env.example`).
4. Tener PostgreSQL corriendo localmente.
5. Ejecutar servidor desde `backend/`:

```bash
uvicorn app.main:app --reload
```
