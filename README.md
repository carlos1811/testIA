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
- **Despliegue inicial:** local.

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
frontend/
  index.html         # interfaz base del prototipo
docs/
  architecture.md    # arquitectura, datos y roadmap
tests/               # pruebas (pendiente de completar)
```

## Arranque rápido (local)

1. Crear entorno virtual.
2. Instalar dependencias desde `backend/requirements.txt`.
3. Exportar variables de entorno (ejemplo en `backend/.env.example`).
4. Ejecutar servidor:

```bash
uvicorn app.main:app --reload
```

Desde la carpeta `backend/`.
