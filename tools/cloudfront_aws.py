#!/usr/bin/env python3
"""CloudFront + WAF de IntegrAI (docs/SEGURIDAD.md §3, ítem 7 y F1).

    python tools/cloudfront_aws.py auditar       # solo lectura: distribución, TLS, WAF
    python tools/cloudfront_aws.py crear         # crea la distribución TLS (dashboard :80, API :8000)
    python tools/cloudfront_aws.py waf           # crea/asocia el WebACL (reglas administradas + rate limit)
    python tools/cloudfront_aws.py revertir-waf  # desasocia y borra el WebACL (emergencia)

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


def _auth_function() -> dict:
    return {
        "Name": "integrai-basic-auth",
        "Comment": "IntegrAI: Basic auth paliativo (F0)",
        "Runtime": "cloudfront-js-2.0",
        "KeyValueStoreAssociations": {"Quantity": 0},
        "FunctionConfig": {
            "Comment": "Basic auth viewer-request",
            "Runtime": "cloudfront-js-2.0",
        },
        "FunctionCode": """function handler(event) {
  var request = event.request;
  var headers = request.headers;
  var auth = headers['authorization'];
  if (!auth) {
    return {
      statusCode: 401,
      statusDescription: 'Unauthorized',
      headers: {
        'www-authenticate': { value: 'Basic realm=\"IntegrAI\"' }
      }
    };
  }
  return request;
}
""",
    }


def auth_basica() -> None:
    cf = _cloudfront()
    # Intenta crear función (idempotente por nombre: AWS no permite duplicado si existe)
    try:
        resp = cf.create_function(Name="integrai-basic-auth", FunctionConfig=_auth_function()["FunctionConfig"], FunctionCode=_auth_function()["FunctionCode"])
        fn = resp["FunctionSummary"]
        print("función creada:", fn["Name"], fn["FunctionARN"])
    except Exception as e:
        print("crear función err (puede ya existir):", e)
    dist = _distribucion(cf)
    resp = cf.get_distribution_config(Id=dist["Id"])
    cfg = resp["DistributionConfig"]
    try:
        # Asociar a default cache behavior (viewer-request)
        cfg["DefaultCacheBehavior"]["FunctionAssociations"] = {
            "Quantity": 1,
            "Items": [{"EventType": "viewer-request", "FunctionARN": _fn_arn("integrai-basic-auth", cf)}],
        }
    except Exception as e:
        print("asociar err:", e)
    try:
        cf.update_distribution(Id=dist["Id"], IfMatch=resp["ETag"], DistributionConfig=cfg)
        print("auth básica asociada (viewer-request)")
    except Exception as e:
        print("update err:", e)


def _fn_arn(name: str, cf):
    # Buscar ARN de función existente
    try:
        for page in [cf.list_functions()]:
            for item in page.get("FunctionList", {}).get("Items", []):
                if item["Name"] == name:
                    return item["FunctionARN"]
    except Exception:
        pass
    raise SystemExit("no se encontró función; revísala en CloudFront Functions")


def quitar_auth() -> None:
    cf = _cloudfront()
    dist = _distribucion(cf)
    resp = cf.get_distribution_config(Id=dist["Id"])
    cfg = resp["DistributionConfig"]
    try:
        cfg["DefaultCacheBehavior"]["FunctionAssociations"] = {"Quantity": 0, "Items": []}
    except Exception:
        pass
    try:
        cf.update_distribution(Id=dist["Id"], IfMatch=resp["ETag"], DistributionConfig=cfg)
        print("auth básica desasociada")
    except Exception as e:
        print("update err:", e)


if __name__ == "__main__":
    {"auditar": auditar, "crear": crear, "waf": waf, "revertir-waf": revertir_waf, "auth-basica": auth_basica, "quitar-auth": quitar_auth}.get(
        (sys.argv[1:] or ["auditar"])[0], lambda: sys.exit(__doc__)
    )()
