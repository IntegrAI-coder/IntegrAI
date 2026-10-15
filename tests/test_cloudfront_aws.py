"""Tests de la configuración de CloudFront/WAF (sin credenciales AWS).

Solo cubre las funciones puras: construcción de la distribución y del WebACL.
La ejecución contra la cuenta se verifica con `tools/cloudfront_aws.py auditar`.
"""

import importlib.util
from pathlib import Path

RUTA = Path(__file__).resolve().parent.parent / "tools" / "cloudfront_aws.py"
_spec = importlib.util.spec_from_file_location("cloudfront_aws", RUTA)
cf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cf)


def test_distribucion_origenes_y_tls():
    config = cf._configuracion("ec2.example.com", "cache-id", "origin-id", "headers-id")

    origenes = {o["Id"]: o["CustomOriginConfig"]["HTTPPort"] for o in config["Origins"]["Items"]}
    assert origenes == {"dashboard": 80, "api": 8000}
    assert config["ViewerCertificate"]["MinimumProtocolVersion"] == "TLSv1.2_2021"
    assert config["PriceClass"] == "PriceClass_All"
    assert config["DefaultCacheBehavior"]["ViewerProtocolPolicy"] == "https-only"


def test_la_api_va_al_origen_8000():
    config = cf._configuracion("ec2.example.com", "cache-id", "origin-id", "headers-id")

    comportamientos = {b["PathPattern"]: b for b in config["CacheBehaviors"]["Items"]}
    assert "/procesar*" in comportamientos
    assert "/clasificar" in comportamientos
    assert "/health" in comportamientos
    for comportamiento in comportamientos.values():
        assert comportamiento["TargetOriginId"] == "api"
        assert comportamiento["CachePolicyId"] == "cache-id"
        assert comportamiento["ResponseHeadersPolicyId"] == "headers-id"
        assert comportamiento["ViewerProtocolPolicy"] == "https-only"


def test_cabeceras_hsts():
    hsts = cf._cabeceras_seguridad()["SecurityHeadersConfig"]["StrictTransportSecurity"]
    assert hsts["Override"] is True
    assert hsts["AccessControlMaxAgeSec"] >= 31536000
    assert hsts["IncludeSubdomains"] is True


def test_wacl_tiene_reglas_administradas_y_rate_limit():
    reglas = {r["Name"]: r for r in cf._wacl_reglas()}
    rate = reglas["RateLimitPorIP"]["Statement"]["RateBasedStatement"]
    assert rate["Limit"] == cf.RATE_LIMIT
    assert reglas["RateLimitPorIP"]["Action"] == {"Block": {}}

    grupos = {
        r["Statement"]["ManagedRuleGroupStatement"]["Name"]
        for r in reglas.values()
        if "ManagedRuleGroupStatement" in r["Statement"]
    }
    assert grupos == {"AWSManagedRulesCommonRuleSet", "AWSManagedRulesKnownBadInputsRuleSet"}
