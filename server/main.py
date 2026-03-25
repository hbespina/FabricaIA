from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import boto3
import json
import os
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

app = FastAPI(title="Modernization Factory API")

# Configurar CORS para el Dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class AnalysisRequest(BaseModel):
    raw_data: str

# El Mega Prompt V2.1 se inyecta como contexto del sistema
SYSTEM_PROMPT = """
Actúa como el Agente Autónomo de Modernización de OTSOrchestrAI (SRE Architect).
Tu objetivo es transformar inventarios legacy en Blueprints Cloud-Native.
Responde estrictamente en JSON con la estructura definida en el esquema V2.1.
"""

@app.post("/analyze")
async def analyze_legacy(request: AnalysisRequest):
    try:
        bedrock = boto3.client(
            service_name='bedrock-runtime',
            region_name=os.getenv("AWS_REGION", "us-east-1")
        )

        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 4096,
            "system": SYSTEM_PROMPT,
            "messages": [
                {
                    "role": "user",
                    "content": f"Analiza el siguiente inventario y genera el blueprint JSON:\n\n{request.raw_data}"
                }
            ]
        })

        response = bedrock.invoke_model(
            body=body,
            modelId="anthropic.claude-3-5-sonnet-20240620-v1:0"
        )

        response_body = json.loads(response.get('body').read())
        return response_body['content'][0]['text']

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
