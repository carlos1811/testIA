# Arquitectura inicial de citasIA

## 1. Visión funcional

Flujo principal del MVP:
1. El usuario crea cuenta y hace login.
2. Con sesión activa, accede al chat con IA.
3. El sistema extrae y guarda rasgos psicológicos.
4. Se calcula compatibilidad con otros perfiles.
5. Se habilita mensajería entre usuarios con match.

## 2. Arquitectura lógica

### Capas
- **API Layer**: endpoints REST para auth, chat y matches.
- **Service Layer**: lógica de negocio (análisis de perfil y matching).
- **Persistence Layer**: PostgreSQL + SQLAlchemy.

### Módulos del backend
- `auth`: registro, login, control de roles.
- `profile`: ingesta del chat y actualización de perfil psicológico.
- `matching`: cálculo de score de compatibilidad.
- `messaging` (base futura): chat entre matches.

## 3. Modelo de datos (MVP)

### `users`
- `id` (UUID)
- `email` (único)
- `username` (único)
- `password_hash`
- `role` (`user`, `admin`)
- `created_at`

### `psychological_profiles`
- `id` (UUID)
- `user_id` (FK -> users)
- `summary_text`
- `writing_style_score`
- `empathy_score`
- `openness_score`
- `updated_at`

### `matches`
- `id` (UUID)
- `user_a_id` (FK -> users)
- `user_b_id` (FK -> users)
- `compatibility_score` (0-100)
- `status` (`suggested`, `accepted`, `rejected`)
- `created_at`

## 4. Seguridad y autenticación

- JWT para sesiones.
- Contraseñas con hash seguro (bcrypt/argon2).
- Endpoints protegidos para chat IA y matches.
- Roles base para diferenciar capacidades administrativas.

## 5. API inicial (propuesta)

- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `POST /api/v1/chat/message`
- `GET /api/v1/matches`

## 6. Plan de evolución recomendado

### Fase 1 (actual)
- Estructura base del proyecto.
- Endpoints esqueleto.
- Modelo de datos inicial.

### Fase 2
- Persistencia real de usuarios y login JWT.
- Almacenamiento de mensajes de chat.
- Motor básico de extracción de rasgos.

### Fase 3
- Algoritmo de matching configurable.
- Chat entre matches.
- Métricas básicas y hardening.
