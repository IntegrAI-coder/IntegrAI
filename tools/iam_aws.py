#!/usr/bin/env python3
"""Rol IAM mínimo privilegio para la EC2 de IntegrAI (F0).

    python tools/iam_aws.py auditar
    python tools/iam_aws.py crear
    python tools/iam_aws.py asociar

Requiere credenciales AWS. No guarda secretos en repo.
"""
from __future__ import annotations

import os
import sys

REGION = os.getenv("AWS_REGION", "us-east-1")
IID = os.getenv("INTEGRA_INSTANCE_ID", "")
ROLE_NAME = "integrai-ec2"
INSTANCE_PROFILE = "integrai-ec2-profile"
POLICY_NAME = "integrai-ec2-minimo"


def _iam():
    import boto3

    return boto3.Session(region_name=REGION).client("iam")


def _ec2():
    import boto3

    return boto3.Session(region_name=REGION).client("ec2")


def _assume_role_doc() -> str:
    return """{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {"Service": "ec2.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }
  ]
}"""


# Modelos que usa el sistema (src/config.py, src/matcher.py, bench/). Con inference profiles "us.*" Bedrock
# exige permiso sobre el PROFILE y sobre el foundation-model de cada región a la que enruta.
MODELOS = [
    "anthropic.claude-sonnet-5",            # U2 conductas, OCR post-it, juez de la rúbrica
    "anthropic.claude-haiku-4-5",           # generación de casos de evaluación
    "amazon.nova-pro-v1",                   # OCR del servicio y respaldo de video
    "amazon.nova-2-lite-v1",                # router de imagen y verificación del post-it
    "amazon.nova-lite-v1",
    "twelvelabs.pegasus-1-2",               # análisis visual de video
    "amazon.titan-embed-text-v2",           # embeddings del matcher (sin inference profile)
]
POLITICA_SSM = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"   # sin ella se pierde el acceso por SSM


def _policy_doc() -> str:
    import json
    recursos = []
    for m in MODELOS:
        recursos.append(f"arn:aws:bedrock:*::foundation-model/{m}*")
        recursos.append(f"arn:aws:bedrock:*:*:inference-profile/us.{m}*")
    return json.dumps({
        "Version": "2012-10-17",
        "Statement": [
            {"Sid": "SecretosIntegrAI", "Effect": "Allow", "Action": ["secretsmanager:GetSecretValue"],
             "Resource": ["arn:aws:secretsmanager:*:*:secret:integrai/*"]},
            {"Sid": "BedrockModelosUsados", "Effect": "Allow",
             "Action": ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
             "Resource": recursos},
        ],
    }, indent=1)


def auditar() -> None:
    iam = _iam()
    try:
        r = iam.get_role(RoleName=ROLE_NAME)
        print("OK ", ROLE_NAME, r["Role"]["Arn"])
    except Exception as e:
        print("-- ", ROLE_NAME, str(e))
    try:
        ip = iam.get_instance_profile(InstanceProfileName=INSTANCE_PROFILE)
        print("OK ", INSTANCE_PROFILE)
    except Exception as e:
        print("-- ", INSTANCE_PROFILE, str(e))
    if IID:
        try:
            inst = _ec2().describe_instances(InstanceIds=[IID])
            prof = inst["Reservations"][0]["Instances"][0].get("IamInstanceProfile", {})
            print("INST", IID, prof.get("Arn"))
        except Exception as e:
            print("INST ERR", e)


def crear() -> None:
    iam = _iam()
    try:
        iam.create_role(RoleName=ROLE_NAME, AssumeRolePolicyDocument=_assume_role_doc())
        print("creado rol:", ROLE_NAME)
    except iam.exceptions.EntityAlreadyExistsException:
        print("rol ya existe:", ROLE_NAME)
    try:
        iam.create_instance_profile(InstanceProfileName=INSTANCE_PROFILE)
        print("creado perfil:", INSTANCE_PROFILE)
    except iam.exceptions.EntityAlreadyExistsException:
        print("perfil ya existe:", INSTANCE_PROFILE)
    try:
        iam.add_role_to_instance_profile(InstanceProfileName=INSTANCE_PROFILE, RoleName=ROLE_NAME)
        print("rol añadido a perfil")
    except iam.exceptions.LimitExceededException:
        pass
    try:
        iam.create_policy(PolicyName=POLICY_NAME, PolicyDocument=_policy_doc())
        print("creada política:", POLICY_NAME)
    except iam.exceptions.EntityAlreadyExistsException:
        arn_existente = f"arn:aws:iam::{_get_account_id()}:policy/{POLICY_NAME}"
        versiones = iam.list_policy_versions(PolicyArn=arn_existente)["Versions"]
        if len(versiones) >= 5:   # IAM permite 5 versiones: borrar la más antigua no vigente
            vieja = sorted((v for v in versiones if not v["IsDefaultVersion"]), key=lambda v: v["CreateDate"])[0]
            iam.delete_policy_version(PolicyArn=arn_existente, VersionId=vieja["VersionId"])
        iam.create_policy_version(PolicyArn=arn_existente, PolicyDocument=_policy_doc(), SetAsDefault=True)
        print("política ya existía: actualizada a la versión vigente del repo")
    arn = f"arn:aws:iam::{_get_account_id()}:policy/{POLICY_NAME}"
    try:
        iam.attach_role_policy(RoleName=ROLE_NAME, PolicyArn=arn)
        print("attach:", arn)
    except Exception as e:
        print("attach err:", e)
    iam.attach_role_policy(RoleName=ROLE_NAME, PolicyArn=POLITICA_SSM)
    print("attach:", POLITICA_SSM)


def _get_account_id() -> str:
    import boto3

    return boto3.client("sts").get_caller_identity()["Account"]


def asociar() -> None:
    if not IID:
        sys.exit("define INTEGRA_INSTANCE_ID")
    ec2 = _ec2()
    actuales = ec2.describe_iam_instance_profile_associations(
        Filters=[{"Name": "instance-id", "Values": [IID]}, {"Name": "state", "Values": ["associated"]}]
    )["IamInstanceProfileAssociations"]
    if actuales:
        ec2.replace_iam_instance_profile_association(
            IamInstanceProfile={"Name": INSTANCE_PROFILE}, AssociationId=actuales[0]["AssociationId"])
        print("perfil reemplazado en", IID, "(antes:", actuales[0]["IamInstanceProfile"]["Arn"].split("/")[-1] + ")")
    else:
        ec2.associate_iam_instance_profile(IamInstanceProfile={"Name": INSTANCE_PROFILE}, InstanceId=IID)
        print("asociado a", IID)
    print("Verifica en la EC2: Bedrock (clasificar), SSM y Secrets Manager. Para revertir, vuelve a asociar el perfil anterior.")


if __name__ == "__main__":
    cmd = (sys.argv[1:] or ["auditar"])[0]
    if cmd == "auditar":
        auditar()
    elif cmd == "crear":
        crear()
    elif cmd == "asociar":
        asociar()
    else:
        sys.exit(__doc__)
