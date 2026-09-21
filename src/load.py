"""
LOAD — Quality checks y persistencia   *** PARCIALMENTE RESUELTO ***
=====================================================================

Dos responsabilidades, en este orden:

  1. CHEQUEAR: validar el dataset antes de publicarlo. Si algo crítico
     falla, cortamos: mejor no entregar nada que entregar un reporte roto.
  2. GUARDAR: escribir el CSV (para personas), el resumen JSON (para
     programas) y el log (para auditar).

Te dejamos resuelto el guardado del CSV y dos de los quality checks.
Faltan 4 TODOs (9 a 12), todos cortos.

Idempotencia: el CSV y el JSON van en modo "w", así que correr el pipeline
dos veces deja el mismo resultado. El log va en modo "a" porque un log ES
un historial: ahí sí queremos que crezca.
"""

import csv
import json
import logging
import os
from datetime import datetime

import config
from transform import COLUMNAS


# ======================================================================
# QUALITY CHECKS
# ======================================================================
def chequear_cantidad(filas, minimo=None):
    """¿Tenemos todas las filas que esperábamos?  [RESUELTO — de ejemplo]

    Fijate el patrón: devuelve una tupla (bool, mensaje). Todos los
    checks tienen que devolver lo mismo para que validar() los trate igual.
    """
    if minimo is None:
        minimo = config.MINIMO_FILAS_ESPERADAS
    ok = len(filas) >= minimo
    return ok, f"cantidad: {len(filas)} filas (mínimo esperado {minimo})"


def chequear_columnas(filas):
    """¿Todas las filas tienen exactamente las columnas del contrato?
    [RESUELTO — de ejemplo]
    """
    esperadas = set(COLUMNAS)
    for fila in filas:
        if set(fila.keys()) != esperadas:
            faltan = esperadas - set(fila.keys())
            return False, f"columnas: una fila no cumple el esquema (faltan {faltan})"
    return True, f"columnas: las {len(COLUMNAS)} del contrato en todas las filas"


def chequear_unicidad(filas):
    """¿Hay duplicados? La clave del dataset es (provincia, anio, destino).

    Debe devolver (bool, mensaje), igual que los checks de arriba.
    """
    claves = [(f["provincia"], f["anio"], f["destino"]) for f in filas]
    claves_unicas = set(claves)
    
    duplicados = len(claves) - len(claves_unicas)
    ok = duplicados == 0
    
    if ok:
        mensaje = "unicidad: no se encontraron filas duplicadas"
    else:
        mensaje = f"unicidad: se encontraron {duplicados} filas duplicadas"
        
    return ok, mensaje


def chequear_rangos(filas):
    """¿Los valores son plausibles?

    Un valor negativo o mayor a config.VALOR_MAXIMO_RAZONABLE es
    sospechoso: no existen exportaciones negativas.
    """
    maximo = config.VALOR_MAXIMO_RAZONABLE
    fuera_de_rango = [
        f for f in filas 
        if f["valor"] < 0 or f["valor"] > maximo
    ]
    
    ok = len(fuera_de_rango) == 0
    
    if ok:
        mensaje = f"rangos: todos los valores entre 0 y {maximo}"
    else:
        mensaje = f"rangos: {len(fuera_de_rango)} filas con valores sospechosos (< 0 o > {maximo})"
        
    return ok, mensaje


def chequear_cobertura(filas):
    """Advertencia (no crítica): ¿cuántos nulos quedaron en las derivadas?
    [RESUELTO]
    """
    sin_variacion = sum(1 for f in filas if f["var_interanual_pct"] is None)
    sin_rubro = sum(1 for f in filas if f["rubro_principal"] is None)
    ok = sin_rubro == 0
    return ok, (f"cobertura: {sin_variacion} filas sin variación interanual "
                f"(esperable en el primer año), {sin_rubro} sin rubro")


def validar(filas):
    """Corre todos los checks.  [RESUELTO]

    Los CRÍTICOS cortan el pipeline lanzando una excepción ("fallar
    temprano y ruidosamente"). La cobertura solo deja una advertencia.

    Retorna una lista de dicts con el detalle, para el resumen JSON.
    """
    criticos = [
        chequear_cantidad(filas),
        chequear_columnas(filas),
        chequear_unicidad(filas),
        chequear_rangos(filas),
    ]

    detalle = []
    for ok, mensaje in criticos:
        detalle.append({"check": mensaje, "estado": "OK" if ok else "FALLO"})
        if ok:
            logging.info("  check OK    | %s", mensaje)
        else:
            logging.error("  check FALLO | %s", mensaje)
            raise ValueError(f"Quality check crítico falló -> {mensaje}")

    ok, mensaje = chequear_cobertura(filas)
    detalle.append({"check": mensaje, "estado": "OK" if ok else "AVISO"})
    if ok:
        logging.info("  check OK    | %s", mensaje)
    else:
        logging.warning("  check AVISO | %s", mensaje)

    return detalle


# ======================================================================
# PERSISTENCIA
# ======================================================================
def guardar_csv(filas, carpeta=None, nombre=None):
    """Escribe el dataset final. Modo 'w': cada corrida lo reemplaza.
    [RESUELTO — usalo de modelo para el resto]
    """
    carpeta = carpeta or config.DIR_PROCESSED
    nombre = nombre or config.ARCHIVO_SALIDA_CSV
    os.makedirs(carpeta, exist_ok=True)
    ruta = os.path.join(carpeta, nombre)

    with open(ruta, "w", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=COLUMNAS)
        escritor.writeheader()
        escritor.writerows(filas)

    logging.info("  CSV: %s (%s filas)", ruta, len(filas))
    return ruta


def construir_resumen(filas, detalle_checks):
    """Arma el resumen del proceso: metadatos + estadísticas descriptivas.

    Este JSON es la "ficha técnica" del dataset: quien lo reciba tiene que
    poder saber de dónde salió, cuándo y qué contiene, SIN abrir el CSV.

    CONTRATO: devolvé un dict que incluya al menos estas claves:

        dataset            (str)  nombre descriptivo
        fuera              (str)  de dónde salieron los datos
        unidad             (str)  "millones de dólares FOB"
        generado           (str)  fecha y hora de esta corrida
        filas              (int)
        columnas           (int)
        periodo            (dict) {"desde": anio_min, "hasta": anio_max}
        provincias         (list) ordenada
        valor_musd         (dict) {"minimo":…, "maximo":…, "promedio":…}
        quality_checks     (list) el detalle_checks que recibís
    """
    # 1. Extracción de listas para cálculos numéricos y temporales
    anios = [int(f["anio"]) for f in filas]
    valores = [f["valor_musd"] for f in filas]

    # 2. Cálculos estadísticos descriptivos
    min_val = min(valores) if valores else 0.0
    max_val = max(valores) if valores else 0.0
    prom_val = round(sum(valores) / len(valores), 2) if valores else 0.0

    # 3. Construcción del diccionario bajo el contrato requerido
    resumen = {
        "dataset": "Exportaciones Provinciales por Destino y Rubro",
        "fuente": config.API_BASE,
        "unidad": "millones de dólares FOB",
        "generado": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "filas": len(filas),
        "columnas": len(COLUMNAS),
        "periodo": {
            "desde": min(anios) if anios else None,
            "hasta": max(anios) if anios else None,
        },
        "provincias": sorted({f["provincia"] for f in filas}),
        "valor_musd": {
            "minimo": min_val,
            "maximo": max_val,
            "promedio": prom_val,
        },
        "quality_checks": detalle_checks,
    }

    return resumen


def guardar_resumen(resumen, carpeta=None, nombre=None):
    """Escribe el resumen en JSON, legible por humanos y por programas.

    Acordate de los dos argumentos que vimos: ensure_ascii=False para que
    las tildes se guarden bien, e indent=2 para que sea legible.
    """
    # TODO 12a ------------------------------------------------------------
    if carpeta is None:
        carpeta = config.DIR_PROCESSED
    if nombre is None:
        nombre = "resumen.json"

    os.makedirs(carpeta, exist_ok=True)
    ruta = os.path.join(carpeta, nombre)

    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(resumen, f, ensure_ascii=False, indent=2)

    return ruta
    # ---------------------------------------------------------------------

def escribir_log_corrida(resumen, carpeta=None, nombre=None):
    """Agrega UNA línea al historial del pipeline.

    Modo "a" (append): nunca borra lo anterior. Cada corrida deja su rastro.
    Sugerencia de formato:

        2026-08-02 14:30 | OK | 1408 filas | 1993-2024
    """
    # TODO 12b ------------------------------------------------------------
    if carpeta is None:
        carpeta = config.DIR_PROCESSED
    if nombre is None:
        nombre = "pipeline.log"

    os.makedirs(carpeta, exist_ok=True)
    ruta = os.path.join(carpeta, nombre)

    # 1. Extraer los datos del resumen
    fecha = resumen["generado"]
    filas = resumen["filas"]
    desde = resumen["periodo"]["desde"]
    hasta = resumen["periodo"]["hasta"]

    # 2. Armar la línea de texto con el formato pedido y salto de línea (\n)
    linea = f"{fecha} | OK | {filas} filas | {desde}-{hasta}\n"

    # 3. Escribir en modo "a" (append) para no borrar corridas anteriores
    with open(ruta, "a", encoding="utf-8") as f:
        f.write(linea)

    return ruta
    # ---------------------------------------------------------------------

def cargar(filas):
    """CONTRATO: recibe las filas finales; valida y persiste las 3 salidas.
    [RESUELTO]
    """
    logging.info("LOAD: validando")
    detalle = validar(filas)

    logging.info("LOAD: guardando")
    guardar_csv(filas)
    resumen = construir_resumen(filas, detalle)
    guardar_resumen(resumen)
    escribir_log_corrida(resumen)

    logging.info("LOAD OK")
    return resumen
