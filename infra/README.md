# infra/ — Infraestructura como código (Ivan)

Plantilla **CloudFormation** para el servidor de la demo. No recrea la EC2: endurece su
Security Group, crea el rol de mínimo privilegio, log groups, alarmas y un plan de respaldos.
Ver [`../docs/INFRA.md`](../docs/INFRA.md).

## Archivos

| Archivo | Qué crea |
|---|---|
| `integra-server.yaml` | Ingress 80/8000 solo desde el prefix list de CloudFront, rol IAM `integrai-ec2` + instance profile, log groups `/integra/app` y `/integra/auditoria`, alarmas (DLQ, status check, CPU) a SNS, vault + plan AWS Backup |

## Antes de desplegar

```bash
# 1. Prefix list de CloudFront de la region
aws ec2 describe-managed-prefix-lists \
  --filters Name=prefix-list-name,Values=com.amazonaws.global.cloudfront.origin-facing \
  --query "PrefixLists[0].PrefixListId" --output text

# 2. Security group y VPC de integra-server
aws ec2 describe-instances --instance-ids "$INTEGRA_INSTANCE_ID" \
  --query "Reservations[0].Instances[0].{sg:SecurityGroups[0].GroupId,vpc:VpcId,id:InstanceId}"
```

## Desplegar

```bash
aws cloudformation deploy \
  --template-file infra/integra-server.yaml \
  --stack-name integrai-server \
  --parameter-overrides \
      SecurityGroupId=<sg-de-integra-server> \
      CloudFrontPrefixListId=<pl-de-cloudfront> \
      InstanceId="$INTEGRA_INSTANCE_ID" \
      VpcId=<vpc-de-integra-server> \
      AlarmEmail=<correo-del-equipo> \
  --capabilities CAPABILITY_NAMED_IAM
```

## Después de desplegar

```bash
# OJO: el rol integrai-ec2 lo crea ESTA plantilla o tools/iam_aws.py crear, NO ambos (mismos nombres).
# Revocar el acceso directo 0.0.0.0/0 de 80/8000 y cerrar 22/8501 (CloudFormation no revoca reglas existentes)
INTEGRA_INSTANCE_ID=<id> python tools/seguridad_aws.py corte

# Asociar el instance profile nuevo a la instancia en ejecucion
INTEGRA_INSTANCE_ID=<id> python tools/iam_aws.py asociar

# Etiquetar el volumen para el plan de respaldo
aws ec2 create-tags --resources <vol-id> --tags Key=Backup,Value=integrai

# En la EC2 (por SSM): token de la API + servicios sin root
sudo bash tools/desplegar_seguridad_ec2.sh
sudo bash tools/endurecer_servicios_ec2.sh
```

## Verificar

```bash
python tools/seguridad_aws.py auditar
python tools/cloudwatch_aws.py auditar
python tools/backup_aws.py auditar
```

Sin secretos ni IDs en el repo: todos los valores entran por parámetros o variables de entorno.
