# 🧪 Cursos de prueba del equipo — IntegrAI

> 4 cursos (uno por número de WhatsApp) para testear el sistema end-to-end,
> especialmente el **manejo de homónimos** (nombres repetidos).

**Jardín de pruebas:** `JAR-EQUIPO` — *"Jardín Equipo — Demo"*
**Seed (idempotente):** `tools/seed_equipo.py` → `/opt/integra/.venv/bin/python tools/seed_equipo.py`
**Roster total:** 111 niños (28 + 26 + 30 + 27).

---

## Los 4 cursos

| Sala | Nº de WhatsApp | Educadora | Niños |
|---|---|---|---|
| 🟡 **Sala Girasol** | `+569 58947607` (Wagner) | `EDU-EQ-1` | 28 |
| 🦋 **Sala Mariposa** | `+569 41257056` (equipo 1) | `EDU-EQ-2` | 26 |
| ⭐ **Sala Estrella** | `+549 381 209 0006` (equipo 2 · AR) | `EDU-EQ-3` | 30 |
| ☄️ **Sala Cometa** | `+569 56433264` (equipo 3) | `EDU-EQ-4` | 27 |

> Cada número rutea a **su** sala (mapeo tía→sala). El sistema **no** ve las otras salas.

## Homónimos por curso (para probar la diferenciación)

Cada curso tiene nombres de pila repetidos con **apellidos distintos** → el resolver debe
pedir apellido y luego diferenciar.

| Curso | Nombres repetidos (pila · apellidos) |
|---|---|
| **Sala Girasol** | Amanda (Zúñiga/Molina) · Emilia (Contreras/Castillo) · Fernanda (Fuentes/González) · Javiera (Cáceres/Salazar) · Lucas (Reyes/Tapia) · Sofía (Sepúlveda/Navarro) |
| **Sala Mariposa** | Agustín (Fuentes/Godoy) · Elías (Herrera/Orellana) · Isidora (Cortés/Salazar) · Mateo (Bustos/González) |
| **Sala Estrella** | Alonso (Espinoza/Bustos) · Amanda (Carrasco/Reyes) · Amparo (Godoy/Pinto) · Emilia (Fuentes/Rojas) · Magdalena (Sandoval/Araya) · Paz (Castillo/Riquelme) · Sebastián (Álvarez/Vergara) · Tomás (González/Molina) |
| **Sala Cometa** | Antonia (Rojas/Castillo) · Colomba (Reyes/Vargas) · Diego (Godoy/Tapia) · Matías (Zúñiga/Silva) · Trinidad (Vergara/Orellana) |

---

## Cómo probar

**@tía manda por WhatsApp** (desde su número → su sala):

1. **Nombre único** → registra directo:
   > "Hoy Martina compartió los bloques con sus compañeros"
2. **Homónimo (solo nombre)** → el sistema pide apellido:
   > "Hoy Sofía cantó una canción" → ⚠️ *Hay más de un niño/a con el nombre «Sofía»...*
3. **Homónimo con apellido** → diferencia y registra:
   > "Hoy Sofía Navarro cantó una canción" → ✅ *registrado — Sofía · nivel N*
4. **Nombre que no existe** → pide rectificar:
   > "Hoy Pedro trajo un juguete" → ⚠️ *No pude identificar a «Pedro»...*

### Qué observar
- **Ruteo por número**: la tía de "Sala Girasol" **nunca** ve niños de "Sala Cometa".
- **Determinismo**: ante duda **no adivina**, pide apellido (no registra mal).
- **Gate por margen**: si la decisión es dudosa, el registro queda **"por verificar"**
  (ej. `Sofía Sepúlveda` → nivel 6 con margen 0.04 → *"quedó por confirmar"*).

---
*Shiva · IntegrAI (AWS Breaking Barriers Chile 2026) · 15-oct-2026.*
