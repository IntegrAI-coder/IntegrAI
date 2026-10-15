# Compuerta de revisión por margen · `casos_300.jsonl`

casos=300 · exactitud exacta=0.940 (282/300) · ±1=0.973 · errores=18

| Umbral | Auto-registradas | Exact. auto | Errores escapados | Detecta errores | A revisión (tía) | Exact. final* |
|---:|---:|---:|---:|---:|---:|---:|
| 0.00 | 100% | 94.0% | 18 | 0% | 0% | 94.0% |
| 0.03 | 96% | 95.8% | 12 | 33% | 4% | 96.0% |
| 0.05 | 95% | 95.8% | 12 | 33% | 5% | 96.0% |
| 0.08 | 91% | 96.4% | 10 | 44% | 9% | 96.7% |
| 0.10 | 89% | 96.3% | 10 | 44% | 11% | 96.7% |
| 0.12 | 86% | 97.3% | 7 | 61% | 14% | 97.7% |
| 0.15 | 83% | 98.0% | 5 | 72% | 17% | 98.3% |
| 0.18 | 79% | 97.9% | 5 | 72% | 21% | 98.3% |
| 0.20 | 75% | 98.2% | 4 | 78% | 25% | 98.7% |
| 0.25 | 69% | 98.6% | 3 | 83% | 31% | 99.0% |
| 0.30 | 62% | 98.4% | 3 | 83% | 38% | 99.0% |

\* *Exactitud final* = si la tía corrige el 100 % de la cola «por verificar».

## Muestreo de auditoría

Umbral operativo 0.15: auto-registradas 249 (83%), errores 5 (28% de todos), tasa de error 2.01%.

Regla de tres (0 errores en n ⇒ cota superior 95 % = 3/n):
| Cota buscada | n a auditar |
|---:|---:|
| ≤ 10% | 30 |
| ≤ 5% | 60 |
| ≤ 3% | 100 |
| ≤ 2% | 150 |

Estimación con precisión ±e (n = 1,96²·p(1−p)/e²), con p observada:
- ±1% → n ≈ 756
- ±2% → n ≈ 189
- ±3% → n ≈ 84
