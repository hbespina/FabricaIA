"""
Script de diagnostico para Bedrock - ejecutar desde el directorio server/
  cd server && python test_bedrock.py
"""
import os
import sys
import json
from dotenv import load_dotenv

load_dotenv()

print("=" * 60)
print("DIAGNOSTICO BEDROCK - Modernization Factory")
print("=" * 60)

# 1. Verificar variables de entorno
print("\n[1] Variables de entorno:")
region = os.getenv("AWS_REGION", "us-east-1")
key_id = os.getenv("AWS_ACCESS_KEY_ID", "")
secret = os.getenv("AWS_SECRET_ACCESS_KEY", "")
model_id = os.getenv("MODEL_ID", "amazon.nova-pro-v1:0")

print(f"  AWS_REGION:            {region}")
print(f"  AWS_ACCESS_KEY_ID:     {'OK (' + key_id[:8] + '...)' if key_id else 'FALTA'}")
print(f"  AWS_SECRET_ACCESS_KEY: {'OK (configurado)' if secret else 'FALTA'}")
print(f"  MODEL_ID:              {model_id}")

if not key_id or not secret:
    print("\n  ERROR: Credenciales AWS no encontradas en .env")
    sys.exit(1)

# 2. Verificar boto3
print("\n[2] Verificando boto3:")
try:
    import boto3
    import botocore
    print(f"  boto3 version: {boto3.__version__}")
except ImportError as e:
    print(f"  ERROR: boto3 no instalado - {e}")
    print("  Ejecuta: pip install boto3")
    sys.exit(1)

# 3. Verificar conectividad al endpoint de Bedrock
print("\n[3] Creando cliente Bedrock Runtime:")
try:
    import botocore.config
    bedrock = boto3.client(
        service_name='bedrock-runtime',
        region_name=region,
        aws_access_key_id=key_id,
        aws_secret_access_key=secret,
        config=botocore.config.Config(read_timeout=60, connect_timeout=10)
    )
    print("  Cliente creado OK")
except Exception as e:
    print(f"  ERROR creando cliente: {e}")
    sys.exit(1)

# 4. Verificar si el modelo tiene acceso habilitado
print("\n[4] Verificando acceso al modelo (Bedrock management):")
try:
    bedrock_mgmt = boto3.client(
        service_name='bedrock',
        region_name=region,
        aws_access_key_id=key_id,
        aws_secret_access_key=secret,
    )
    # Listar modelos fundacionales disponibles
    response = bedrock_mgmt.list_foundation_models(byOutputModality='TEXT')
    models = response.get('modelSummaries', [])
    nova_models = [m for m in models if 'nova' in m.get('modelId', '').lower()]

    if nova_models:
        print(f"  Modelos Nova disponibles en {region}:")
        for m in nova_models:
            print(f"    - {m['modelId']} | Status: {m.get('modelLifecycle', {}).get('status', 'N/A')}")
    else:
        print(f"  AVISO: No se encontraron modelos Nova en region {region}")
        print("  Los modelos disponibles son:")
        for m in models[:5]:
            print(f"    - {m['modelId']}")
except botocore.exceptions.ClientError as e:
    code = e.response['Error']['Code']
    msg = e.response['Error']['Message']
    print(f"  ERROR ({code}): {msg}")
    if code == 'AccessDeniedException':
        print("  -> El usuario IAM no tiene permiso 'bedrock:ListFoundationModels'")
    elif code == 'InvalidClientTokenId':
        print("  -> AWS_ACCESS_KEY_ID invalida")
    elif code == 'SignatureDoesNotMatch':
        print("  -> AWS_SECRET_ACCESS_KEY incorrecta")
except Exception as e:
    print(f"  ERROR inesperado: {e}")

# 5. Test real de invocacion al modelo
print(f"\n[5] Test de invocacion al modelo '{model_id}':")
TEST_PROMPT = "Responde solo con este JSON exacto: {\"status\": \"ok\", \"model\": \"nova-pro\"}"

try:
    response = bedrock.converse(
        modelId=model_id,
        messages=[{"role": "user", "content": [{"text": TEST_PROMPT}]}],
        system=[{"text": "Eres un asistente que responde solo en JSON."}],
        inferenceConfig={"maxTokens": 100, "temperature": 0.0}
    )

    output_text = response['output']['message']['content'][0]['text']
    usage = response.get('usage', {})

    print(f"  EXITO!")
    print(f"  Respuesta: {output_text[:200]}")
    print(f"  Tokens usados - input: {usage.get('inputTokens', '?')}, output: {usage.get('outputTokens', '?')}")

except botocore.exceptions.ClientError as e:
    code = e.response['Error']['Code']
    msg = e.response['Error']['Message']
    print(f"  ERROR ({code}): {msg}")

    if code == 'AccessDeniedException':
        print("\n  CAUSA PROBABLE: Model Access no habilitado")
        print("  SOLUCION:")
        print("    1. Ir a AWS Console -> Amazon Bedrock -> Model access")
        print(f"    2. Buscar 'Nova Pro' y hacer clic en 'Request access'")
        print("    3. Esperar aprobacion (generalmente inmediata)")
    elif code == 'ValidationException':
        print(f"\n  CAUSA: ID del modelo invalido o incorrecto")
        print(f"  Model ID usado: {model_id}")
        print("  Prueba con: amazon.nova-pro-v1:0")
    elif code == 'InvalidClientTokenId':
        print("\n  CAUSA: AWS_ACCESS_KEY_ID invalida o expirada")
        print("  SOLUCION: Generar nuevas credenciales en AWS IAM Console")
    elif code == 'ThrottlingException':
        print("\n  CAUSA: Rate limit alcanzado")
        print("  SOLUCION: Esperar unos minutos e intentar de nuevo")
    elif code == 'ResourceNotFoundException':
        print(f"\n  CAUSA: Modelo no encontrado en region {region}")
        print("  Nova Pro esta disponible en: us-east-1, us-west-2, eu-west-1")

except Exception as e:
    print(f"  ERROR inesperado: {type(e).__name__}: {e}")

print("\n" + "=" * 60)
print("Diagnostico completado.")
