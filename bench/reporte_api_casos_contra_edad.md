# Clasificador desplegado · `casos_contra_edad.jsonl` · 60 casos (adelanto: 10, control: 10, real_bajo: 20, rezago: 20)

| Variante | Exacto | ±1 | A revisión | Exactos en aceptados | Exacto `adelanto` | Exacto `control` | Exacto `real_bajo` | Exacto `rezago` | Recall alerta rezago | Precisión alerta |
|---|---|---|---|---|---|---|---|---|---|---|
| solo edad (sin texto) | 17% | 62% | 0% | 10/60 | 0% | 100% | 0% | 0% | 0% | — |
| ensemble con edad | 47% | 73% | 38% | 17/37 | 30% | 80% | 45% | 40% | 50% | 95% |
| ensemble sin edad | 48% | 70% | 50% | 19/30 | 20% | 30% | 70% | 50% | 78% | 76% |
| ensemble con edad + conductas U2 | 72% | 88% | 23% | 37/46 | 70% | 90% | 65% | 70% | 80% | 97% |

Alerta de rezago = nivel predicho bajo el nivel típico de la edad.
