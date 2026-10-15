#!/usr/bin/env python3
"""CloudFront + WAF de IntegrAI (docs/SEGURIDAD.md §3, ítem 7 y F1).

    python tools/cloudfront_aws.py auditar       # solo lectura: distribución, TLS, WAF
    python tools/cloudfront_aws.py crear         # crea la distribución TLS (dashboard :80, API :8000)
    python tools/cloudfront_aws.py waf           # crea/asocia el WebACL (reglas administradas + rate limit)
    python tools/cloudfront_aws.py revertir-waf  # desasocia y borra el WebACL (emergencia)
    python tools/cloudfront_aws.py auth-basica   # Basic auth real en el dashboard (credencial en Secrets Manager)
    python tools/cloudfront_aws.py quitar-auth   # desasocia el Basic auth

Variables (no se versionan: el repo es público):
    INTEGRA_ORIGIN_DOMAIN      DNS público de la EC2 (origen). Obligatoria para `crear` y `waf`.
    INTEGRA_DISTRIBUTION_ID    Distribución a usar; si no, se busca por comentario.
    AWS_REGION                 us-east-1 (CloudFront es global; el WebACL de CLOUDFRONT vive en us-east-1).
    INTEGRA_CF_COMMENT         Comentario/marcador de la distribución (por defecto "IntegrAI").

`crear` es idempotente (si ya existe la distribución, no hace nada). El WAF es la tarea
F1 del plan; `revertir-waf` lo deja como estaba.
"""
from __future__ import annotations

import os
import sys
import uuid

REGION = os.getenv("AWS_REGION", "us-east-1")
ORIGIN = os.getenv("INTEGRA_ORIGIN_DOMAIN", "")
COMMENT = os.getenv("INTEGRA_CF_COMMENT", "IntegrAI")
DIST_ID = os.getenv("INTEGRA_DISTRIBUTION_ID", "")
HSTS_SECONDS = 31536000

PATRONES_API = ["/procesar*", "/clasificar", "/health"]
CACHE_DISABLED = "Managed-CachingDisabled"
ALL_VIEWER = "Managed-AllViewer"
POLITICA_CABECERAS = "integrai-security-headers"
WACL = "integrai-cloudfront-waf"
RATE_LIMIT = 2000


def _cloudfront():
    import boto3

    return boto3.Session(region_name=REGION).client("cloudfront")


def _waf():
    import boto3

    return boto3.Session(region_name="us-east-1").client("wafv2")


def _id_politica(cliente, metodo: str, clave: str, nombre: str) -> str:
    marcador = None
    while True:
        kwargs = {"Type": "managed"}
        if marcador:
            kwargs["Marker"] = marcador
        respuesta = getattr(cliente, metodo)(**kwargs)
        listado = respuesta[clave]
        for item in listado.get("Items", []):
            for contenedor in ("CachePolicy", "OriginRequestPolicy"):
                if contenedor in item and item[contenedor]["Name"] == nombre:
                    return item[contenedor]["Id"]
        marcador = listado.get("NextMarker")
        if not marcador:
            raise SystemExit(f"no encontré la política administrada {nombre}")


def _cabeceras_seguridad() -> dict:
    return {
        "Name": POLITICA_CABECERAS,
        "Comment": "IntegrAI: HSTS y cabeceras de seguridad",
        "SecurityHeadersConfig": {
            "StrictTransportSecurity": {
                "Override": True,
                "AccessControlMaxAgeSec": HSTS_SECONDS,
                "IncludeSubdomains": True,
                "Preload": False,
            },
            "ContentTypeOptions": {"Override": True},
            "FrameOptions": {"Override": True, "FrameOption": "DENY"},
            "XSSProtection": {"Override": True, "Protection": True, "ModeBlock": True},
            "ReferrerPolicy": {
                "Override": True,
                "ReferrerPolicy": "strict-origin-when-cross-origin",
            },
        },
    }


def _configuracion(origin: str, cache_id: str, origin_id: str, cabeceras_id: str) -> dict:
    def origen(identificador: str, puerto: int) -> dict:
        return {
            "Id": identificador,
            "DomainName": origin,
            "CustomOriginConfig": {
                "HTTPPort": puerto,
                "HTTPSPort": 443,
                "OriginProtocolPolicy": "http-only",
                "OriginReadTimeout": 30,
                "OriginKeepaliveTimeout": 5,
            },
        }

    def comportamiento(target: str) -> dict:
        return {
            "TargetOriginId": target,
            "ViewerProtocolPolicy": "https-only",
            "AllowedMethods": {
                "Quantity": 7,
                "Items": ["GET", "HEAD", "OPTIONS", "PUT", "POST", "PATCH", "DELETE"],
                "CachedMethods": {"Quantity": 2, "Items": ["GET", "HEAD"]},
            },
            "CachePolicyId": cache_id,
            "OriginRequestPolicyId": origin_id,
            "ResponseHeadersPolicyId": cabeceras_id,
            "Compress": False,
        }

    default = comportamiento("dashboard")
    return {
        "CallerReference": f"integrai-{uuid.uuid4().hex}",
        "Comment": COMMENT,
        "Enabled": True,
        "Origins": {
            "Quantity": 2,
            "Items": [origen("dashboard", 80), origen("api", 8000)],
        },
        "DefaultCacheBehavior": default,
        "CacheBehaviors": {
            "Quantity": len(PATRONES_API),
            "Items": [
                {"PathPattern": patron, **comportamiento("api")} for patron in PATRONES_API
            ],
        },
        "ViewerCertificate": {
            "CloudFrontDefaultCertificate": True,
            "MinimumProtocolVersion": "TLSv1.2_2021",
        },
        "HttpVersion": "http2and3",
        "PriceClass": "PriceClass_All",
        "Restrictions": {
            "GeoRestriction": {"RestrictionType": "none", "Quantity": 0}
        },
    }


def _buscar_distribucion(cf) -> dict | None:
    items = cf.list_distributions().get("DistributionList", {}).get("Items", [])
    for dist in items:
        if COMMENT in dist.get("Comment", ""):
            return dist
    return None


def _distribucion(cf) -> dict:
    if DIST_ID:
        return cf.get_distribution(Id=DIST_ID)["Distribution"]
    encontrada = _buscar_distribucion(cf)
    if not encontrada:
        raise SystemExit("no hay distribución de CloudFront (usa `crear` o INTEGRA_DISTRIBUTION_ID)")
    return cf.get_distribution(Id=encontrada["Id"])["Distribution"]


def _cabeceras(cf) -> str:
    for pagina in [cf.list_response_headers_policies(Type="custom")]:
        for item in pagina.get("ResponseHeadersPolicyList", {}).get("Items", []):
            if item["ResponseHeadersPolicy"]["Name"] == POLITICA_CABECERAS:
                return item["ResponseHeadersPolicy"]["Id"]
    creada = cf.create_response_headers_policy(
        ResponseHeadersPolicyConfig=_cabeceras_seguridad()
    )
    return creada["ResponseHeadersPolicy"]["Id"]


def _ok(condicion: bool) -> str:
    return "OK " if condicion else "-- "


def auditar() -> None:
    cf = _cloudfront()
    dist = _distribucion(cf)
    cfg = dist["DistributionConfig"]

    viewer = cfg["ViewerCertificate"]
    certificado = "ACM/custom" if not viewer.get("CloudFrontDefaultCertificate") else "*.cloudfront.net"
    print(_ok(viewer.get("MinimumProtocolVersion") == "TLSv1.2_2021"),
          "TLS:", certificado, viewer.get("MinimumProtocolVersion", "default"))
    print(_ok(dist.get("WebACLId", "") != ""), "WAF asociado:", dist.get("WebACLId") or "(ninguno)")

    for origin in cfg["Origins"]["Items"]:
        puerto = origin["CustomOriginConfig"]["HTTPPort"]
        print(_ok(puerto in (80, 8000)), f"origen {origin['Id']}: {origin['DomainName']}:{puerto}",
              origin["CustomOriginConfig"]["OriginProtocolPolicy"])

    for behavior in [cfg["DefaultCacheBehavior"], *cfg["CacheBehaviors"].get("Items", [])]:
        patron = behavior.get("PathPattern", "(default)")
        print(
            _ok(behavior["ViewerProtocolPolicy"] == "https-only"),
            f"{patron} -> {behavior['TargetOriginId']}",
            "cabeceras:", behavior.get("ResponseHeadersPolicyId"),
        )

    print(_ok(True), "dominio:", f"https://{dist['DomainName']}", dist["Status"])

    wacl_id = dist.get("WebACLId")
    if wacl_id:
        wacl = _waf().get_web_acl(Name=WACL, Scope="CLOUDFRONT", Id=wacl_id)["WebACL"]
        reglas = [r["Name"] for r in wacl["Rules"]]
        print(_ok(True), "reglas WAF:", reglas or "(vacío)")


def crear() -> None:
    if not ORIGIN:
        sys.exit("define INTEGRA_ORIGIN_DOMAIN (DNS de la EC2)")
    cf = _cloudfront()
    existente = _buscar_distribucion(cf)
    if existente:
        print("ya existe:", existente["Id"], f"https://{existente['DomainName']}")
        return

    cache_id = _id_politica(cf, "list_cache_policies", "CachePolicyList", CACHE_DISABLED)
    origin_id = _id_politica(
        cf, "list_origin_request_policies", "OriginRequestPolicyList", ALL_VIEWER
    )
    cabeceras_id = _cabeceras(cf)
    creada = cf.create_distribution(
        DistributionConfig=_configuracion(ORIGIN, cache_id, origin_id, cabeceras_id)
    )
    dist = creada["Distribution"]
    print("distribución creada:", dist["Id"])
    print("INTEGRA_BACKEND=https://" + dist["DomainName"])
    print("estado:", dist["Status"], "(tarda unos minutos en desplegar)")


def _wacl_reglas() -> list[dict]:
    def visibilidad(nombre: str) -> dict:
        return {
            "SampledRequestsEnabled": True,
            "CloudWatchMetricsEnabled": True,
            "MetricName": nombre,
        }

    return [
        {
            "Name": "RateLimitPorIP",
            "Priority": 0,
            "Action": {"Block": {}},
            "Statement": {
                "RateBasedStatement": {"Limit": RATE_LIMIT, "AggregateKeyType": "IP"}
            },
            "VisibilityConfig": visibilidad("integrai-rate-limit"),
        },
        {
            "Name": "ReglasComunesAWS",
            "Priority": 1,
            "OverrideAction": {"None": {}},
            "Statement": {
                "ManagedRuleGroupStatement": {
                    "VendorName": "AWS",
                    "Name": "AWSManagedRulesCommonRuleSet",
                }
            },
            "VisibilityConfig": visibilidad("integrai-common"),
        },
        {
            "Name": "EntradasMaliciosasAWS",
            "Priority": 2,
            "OverrideAction": {"None": {}},
            "Statement": {
                "ManagedRuleGroupStatement": {
                    "VendorName": "AWS",
                    "Name": "AWSManagedRulesKnownBadInputsRuleSet",
                }
            },
            "VisibilityConfig": visibilidad("integrai-known-bad-inputs"),
        },
    ]


def _wacl(cliente) -> dict:
    existentes = cliente.list_web_acls(Scope="CLOUDFRONT").get("WebACLs", [])
    for item in existentes:
        if item["Name"] == WACL:
            return cliente.get_web_acl(Name=WACL, Scope="CLOUDFRONT", Id=item["Id"])["WebACL"]
    creado = cliente.create_web_acl(
        Name=WACL,
        Scope="CLOUDFRONT",
        DefaultAction={"Allow": {}},
        Description="IntegrAI: reglas administradas + rate limit",
        Rules=_wacl_reglas(),
        VisibilityConfig={
            "SampledRequestsEnabled": True,
            "CloudWatchMetricsEnabled": True,
            "MetricName": "integrai-waf",
        },
    )
    return cliente.get_web_acl(Name=WACL, Scope="CLOUDFRONT", Id=creado["Summary"]["Id"])["WebACL"]


def waf() -> None:
    cf = _cloudfront()
    dist = _distribucion(cf)
    cliente = _waf()
    wacl = _wacl(cliente)
    if dist.get("WebACLId") == wacl["Id"]:
        print("WAF ya estaba asociado:", wacl["Id"])
        return
    respuesta = cf.get_distribution_config(Id=dist["Id"])
    config = respuesta["DistributionConfig"]
    config["WebACLId"] = wacl["Id"]
    cf.update_distribution(
        Id=dist["Id"], IfMatch=respuesta["ETag"], DistributionConfig=config
    )
    print("WAF asociado a la distribución:", wacl["Arn"])


def revertir_waf() -> None:
    cf = _cloudfront()
    dist = _distribucion(cf)
    wacl_id = dist.get("WebACLId")
    if wacl_id:
        respuesta = cf.get_distribution_config(Id=dist["Id"])
        config = respuesta["DistributionConfig"]
        config["WebACLId"] = ""
        cf.update_distribution(
            Id=dist["Id"], IfMatch=respuesta["ETag"], DistributionConfig=config
        )
        print("WAF desasociado")
        cliente = _waf()
        nombres = {
            item["Id"]: item["Name"]
            for item in cliente.list_web_acls(Scope="CLOUDFRONT").get("WebACLs", [])
        }
        if nombres.get(wacl_id) == WACL:
            actual = cliente.get_web_acl(Name=WACL, Scope="CLOUDFRONT", Id=wacl_id)["WebACL"]
            cliente.delete_web_acl(
                Name=WACL,
                Scope="CLOUDFRONT",
                Id=wacl_id,
                LockToken=actual["LockToken"],
            )
            print("WebACL borrado")
    else:
        print("no había WAF asociado")


FUNCION_AUTH = "integrai-basic-auth"
SECRETO_AUTH = "integrai/dashboard-basic-auth"   # {"usuario": ..., "clave": ...}; nunca en el repo


def _credencial() -> tuple[str, str]:
    """Lee (o crea con clave aleatoria) la credencial del dashboard en Secrets Manager."""
    import json
    import secrets as _s
    import boto3
    sm = boto3.client("secretsmanager", region_name=REGION)
    try:
        d = json.loads(sm.get_secret_value(SecretId=SECRETO_AUTH)["SecretString"])
    except sm.exceptions.ResourceNotFoundException:
        d = {"usuario": "integra", "clave": _s.token_urlsafe(18)}
        sm.create_secret(Name=SECRETO_AUTH, SecretString=json.dumps(d),
                         Description="Basic auth del dashboard IntegrAI (CloudFront Function)")
        print(f"credencial creada en Secrets Manager: {SECRETO_AUTH} (el valor no se imprime)")
    return d["usuario"], d["clave"]


def _hash_cabecera(usuario: str, clave: str) -> str:
    """SHA-256 de la cabecera exacta que manda el navegador: 'Basic base64(usuario:clave)'."""
    import base64
    import hashlib
    valor = "Basic " + base64.b64encode(f"{usuario}:{clave}".encode()).decode()
    return hashlib.sha256(valor.encode()).hexdigest()


def _codigo_auth(hash_esperado: str, spa: bool = False) -> str:
    """CloudFront Function (cloudfront-js-2.0): solo guarda el HASH, nunca la clave.

    spa=True agrega la reescritura del frontend React (rutas sin extensión -> /index.html): CloudFront
    admite UNA función viewer-request por comportamiento, así que auth y SPA van juntas en la raíz.
    """
    if len(hash_esperado) != 64 or any(c not in "0123456789abcdef" for c in hash_esperado):
        raise ValueError("hash inválido")
    reescritura = "    if (r.uri.indexOf('.') === -1) { r.uri = '/index.html'; }\n" if spa else ""
    return ("const crypto = require('crypto');\n"
            f"var ESPERADO = '{hash_esperado}';\n"
            "function handler(event) {\n"
            "  var r = event.request;\n"
            "  var h = r.headers['authorization'];\n"
            "  if (h && crypto.createHash('sha256').update(h.value).digest('hex') === ESPERADO) {\n"
            + reescritura +
            "    return r;\n"
            "  }\n"
            "  return {\n"
            "    statusCode: 401,\n"
            "    statusDescription: 'Unauthorized',\n"
            "    headers: { 'www-authenticate': { value: 'Basic realm=\"IntegrAI\"' } }\n"
            "  };\n"
            "}\n")


def _publicar(cf, nombre: str, codigo: str, comentario: str) -> str:
    config = {"Comment": comentario, "Runtime": "cloudfront-js-2.0"}
    try:
        etag = cf.describe_function(Name=nombre, Stage="DEVELOPMENT")["ETag"]
        etag = cf.update_function(Name=nombre, IfMatch=etag, FunctionConfig=config, FunctionCode=codigo.encode())["ETag"]
    except cf.exceptions.NoSuchFunctionExists:
        etag = cf.create_function(Name=nombre, FunctionConfig=config, FunctionCode=codigo.encode())["ETag"]
    return cf.publish_function(Name=nombre, IfMatch=etag)["FunctionSummary"]["FunctionMetadata"]["FunctionARN"]


def auth_basica() -> None:
    """Basic auth REAL en el frontend (raíz, con reescritura SPA) y en /streamlit*. La API usa X-Api-Key."""
    cf = _cloudfront()
    h = _hash_cabecera(*_credencial())
    arn_spa = _publicar(cf, FUNCION_AUTH + "-spa", _codigo_auth(h, spa=True), "IntegrAI: Basic auth + SPA (raíz)")
    arn = _publicar(cf, FUNCION_AUTH, _codigo_auth(h), "IntegrAI: Basic auth (/streamlit*)")
    print("funciones publicadas (LIVE)")
    dist = _distribucion(cf)
    resp = cf.get_distribution_config(Id=dist["Id"])
    cfg = resp["DistributionConfig"]
    asociar = lambda a: {"Quantity": 1, "Items": [{"EventType": "viewer-request", "FunctionARN": a}]}
    cfg["DefaultCacheBehavior"]["FunctionAssociations"] = asociar(arn_spa)
    for b in cfg.get("CacheBehaviors", {}).get("Items", []):
        if b["PathPattern"] == "/streamlit*":
            b["FunctionAssociations"] = asociar(arn)
    cf.update_distribution(Id=dist["Id"], IfMatch=resp["ETag"], DistributionConfig=cfg)
    print("auth básica asociada al frontend y a /streamlit*. Verifica: sin credencial -> 401; con la de "
          f"{SECRETO_AUTH} -> 200. La API (/procesar*, /clasificar, /health) no cambia.")


def quitar_auth() -> None:
    """Quita el Basic auth; la raíz vuelve a la reescritura SPA sola (tools/desplegar_frontend.py)."""
    cf = _cloudfront()
    dist = _distribucion(cf)
    resp = cf.get_distribution_config(Id=dist["Id"])
    cfg = resp["DistributionConfig"]
    try:
        arn_spa = cf.describe_function(Name="integrai-spa-rewrite", Stage="LIVE")["FunctionSummary"]["FunctionMetadata"]["FunctionARN"]
        cfg["DefaultCacheBehavior"]["FunctionAssociations"] = {"Quantity": 1, "Items": [{"EventType": "viewer-request", "FunctionARN": arn_spa}]}
    except cf.exceptions.NoSuchFunctionExists:
        cfg["DefaultCacheBehavior"]["FunctionAssociations"] = {"Quantity": 0}
    for b in cfg.get("CacheBehaviors", {}).get("Items", []):
        if b["PathPattern"] == "/streamlit*":
            b["FunctionAssociations"] = {"Quantity": 0}
    cf.update_distribution(Id=dist["Id"], IfMatch=resp["ETag"], DistributionConfig=cfg)
    print("auth básica desasociada")


if __name__ == "__main__":
    {"auditar": auditar, "crear": crear, "waf": waf, "revertir-waf": revertir_waf, "auth-basica": auth_basica, "quitar-auth": quitar_auth}.get(
        (sys.argv[1:] or ["auditar"])[0], lambda: sys.exit(__doc__)
    )()
