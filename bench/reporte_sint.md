# IntegrAI-MM · medios `sint` · decisor `hibrido`

| Pipeline | n | Error etapa 1 (WER audio / CER post-it) | Recall@5 manifestaciones | Nivel exacto | Nivel ±1 | Latencia p50 / p95 |
|---|---:|---:|---:|---:|---:|---:|
| oraculo | 30 | 0 % | 18 % | 37 % | 40 % | 0.4 s / 0.7 s |
| oraculo+conductas | 30 | 0 % | 55 % | 83 % | 93 % | 3.5 s / 5.9 s |
| postit_legacy | 30 | 96 % | 1 % | 0 % | 7 % | 3.3 s / 3.9 s |
| postit_v2 | 30 | 1 % | 51 % | 83 % | 87 % | 8.4 s / 12.0 s |
