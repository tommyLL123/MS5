import os
import time
from typing import Optional
from fastapi import FastAPI, HTTPException, Query
import boto3
from botocore.exceptions import BotoCoreError, ClientError

app = FastAPI(
    title="Microservicio 5 - Consultas Analíticas (AWS Athena)",
    description="API REST que ejecuta consultas SQL sobre el Catálogo de Datos de AWS Glue mediante AWS Athena.",
    version="1.0.0"
)

# Configuración por variables de entorno
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
ATHENA_DATABASE = os.getenv("ATHENA_DATABASE", "db_glue_catalog")
ATHENA_S3_OUTPUT = os.getenv("ATHENA_S3_OUTPUT", "s3://proyecto-bucket-g5/athena-results/")

# Cliente de Athena con boto3
athena_client = boto3.client('athena', region_name=AWS_REGION)


def ejecutar_consulta_athena(sql_query: str) -> list[dict]:
    """Inicia y espera la ejecución de una consulta SQL en Athena, transformando los resultados a JSON."""
    try:
        # 1. Iniciar ejecución
        response = athena_client.start_query_execution(
            QueryString=sql_query,
            QueryExecutionContext={'Database': ATHENA_DATABASE},
            ResultConfiguration={'OutputLocation': ATHENA_S3_OUTPUT}
        )
        execution_id = response['QueryExecutionId']

        # 2. Esperar respuesta de Athena (polling)
        while True:
            status_resp = athena_client.get_query_execution(QueryExecutionId=execution_id)
            state = status_resp['QueryExecution']['Status']['State']

            if state in ['SUCCEEDED']:
                break
            elif state in ['FAILED', 'CANCELLED']:
                reason = status_resp['QueryExecution']['Status'].get('StateChangeReason', 'Error desconocido')
                raise HTTPException(status_code=500, detail=f"Error en Athena ({state}): {reason}")

            time.sleep(1)

        # 3. Obtener resultados de la consulta
        results = athena_client.get_query_results(QueryExecutionId=execution_id)
        rows = results.get('ResultSet', {}).get('Rows', [])

        if not rows:
            return []

        # 4. Formatear la primera fila como encabezados (columnas) y el resto como objetos JSON
        headers = [col.get('VarCharValue', '') for col in rows[0]['Data']]
        formatted_results = []

        for row in rows[1:]:
            row_dict = {}
            for idx, col in enumerate(row['Data']):
                header_name = headers[idx]
                val = col.get('VarCharValue', None)
                row_dict[header_name] = val
            formatted_results.append(row_dict)

        return formatted_results

    except (BotoCoreError, ClientError) as e:
        raise HTTPException(status_code=500, detail=f"Error de AWS SDK: {str(e)}")


@app.get("/health", tags=["Health Check"])
def health_check():
    """Endpoint para verificar que el microservicio está activo."""
    return {"status": "ok", "service": "ms5-analitica"}


@app.get("/analitica/vista-resumen", tags=["Consultas Analíticas"])
def obtener_resumen_ventas(limit: int = Query(100, ge=1, le=1000)):
    """Consulta la vista analítica creada en Athena."""
    query = f"SELECT * FROM vista_resumen_ventas LIMIT {limit};"
    datos = ejecutar_consulta_athena(query)
    return {
        "status": "success",
        "total_registros": len(datos),
        "data": datos
    }


@app.get("/analitica/query-custom", tags=["Consultas Analíticas"])
def ejecutar_query_personalizada(sql: str = Query(..., description="Consulta SQL a ejecutar en Athena")):
    """Ejecuta cualquier consulta SQL personalizada en Athena[cite: 1]."""
    # Seguridad básica: permitir solo consultas de lectura
    if not sql.strip().upper().startswith("SELECT"):
        raise HTTPException(status_code=400, detail="Solo se permiten consultas de tipo SELECT.")
    
    datos = ejecutar_consulta_athena(sql)
    return {
        "status": "success",
        "total_registros": len(datos),
        "data": datos
    }
