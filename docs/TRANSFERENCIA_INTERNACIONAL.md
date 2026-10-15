# Transferencia internacional de datos — IntegrAI (F2)

> Responsable: Integra + Ivan. Revisión sugerida: antes de entrar a producción y/o al superar el piloto.

## Contexto
La infraestructura actual puede procesar observaciones de niños/as utilizando servicios AWS ubicados fuera de Chile (ej. `us-east-1`) y terceros (Meta WhatsApp, operadores del webhook). Esto activa consideraciones de transferencia internacional (arts. 27–28 de la Ley 19.628, modificada por Ley 21.719, con referencia a normas sobre transferencia internacional y cláusulas contractuales tipo).

## Objetivo
Determinar el mecanismo adecuado (cláusulas contractuales tipo conforme a resolución del Ministerio de Economía, o migración a región AWS Chile si Bedrock ya está disponible allí) y dejar un checklist verificable.

## Checklist
- [ ] Identificar todos los servicios que procesan datos personales sensibles (niños/as): Bedrock, S3, CloudTrail, DynamoDB, Transcribe/Nova, EC2, CloudFront, Secrets Manager.
- [ ] Mapear región por recurso (auditar con `python tools/region_audit.py auditar`).
- [ ] Verificar disponibilidad de Bedrock en región Chile (AWS región chilena) al momento de la decisión; si no existe, evaluar cronograma.
- [ ] Evaluar necesidad de transferencia internacional: ¿los datos salen efectivamente a otro país? Documentar flujos (WhatsApp → webhook → AWS → Bedrock).
- [ ] Aplicar cláusulas contractuales tipo (SCCs) para transferencias a terceros fuera de Chile, conforme a la normativa aplicable. Registrar DPA/EIPD y fechas.
- [ ] Si se migra a región chilena: validar que todos los modelos usados por IntegrAI estén disponibles en esa región antes de migrar.
- [ ] Actualizar inventario de datos, flujos y responsables en `docs/GOBIERNO_DATOS.md`.
- [ ] Verificar que los logs/auditoría no contienen PII (mantener enmascarado como en código).
- [ ] Decisión registrada (fecha, responsable Integra+Ivan) y vinculada a este documento.

## Notas
- El repo es público; este documento no contiene IDs, URLs internas ni secretos.
- Prioritario: confirmar disponibilidad de Bedrock en la región objetivo antes de comprometer migración. En caso contrario, usar cláusulas contractuales tipo como ruta transitoria.
- Ver también: `docs/SEGURIDAD.md` (F2), `docs/GOBIERNO_DATOS.md`. 
