# Pipeline ETL — Exportaciones Provinciales del NEA

Este repositorio contiene un pipeline ETL (*Extract, Transform, Load*) modular desarrollado en Python, diseñado para consultar, transformar y persistir datos históricos sobre las exportaciones provinciales de la región NEA (Chaco, Corrientes, Formosa y Misiones) desglosadas por país de destino y rubro exportador.

---

## 🚀 ¿Qué hace este pipeline?

El pipeline sigue una arquitectura modular clásica dividida en tres etapas:

1. **Extract (`src/extract.py`):**
   - Descarga series temporales desde la API oficial de series de tiempo.
   - Realiza consultas en formato ancho (*wide*) para destinos y rubros de cada provincia.
   - Almacena las respuestas sin alterar en archivos JSON locales (`data/raw/`), permitiendo trabajar offline o reproducir corridas sin sobrecargar la API.

2. **Transform (`src/transform.py`):**
   - Transforma los datos crudos de formato **ancho a largo** (*tidy data*), generando una fila por cada combinación de año, provincia y destino.
   - Aplica reglas de negocio e ingeniería de variables: asignación de región geoeconómica, cálculo de la década, porcentaje de participación sobre el total provincial, variación interanual y ranking de principales destinos por año/provincia (marcando el top 3).
   - Realiza un *left join* con el dataset de rubros para incorporar el rubro preponderante y la participación de productos primarios (`pp_participacion_pct`).
   - Normaliza y ordena el dataset final según el esquema analítico acordado (13 columnas).

3. **Load (`src/load.py`):**
   - **Quality Checks:** Realiza validaciones previas de integridad (volumen mínimo de filas, esquema de columnas, unicidad de claves `provincia-anio-destino` y consistencia de rangos numéricos). Si un chequeo crítico falla, el proceso se aborta de forma segura.
   - **Persistencia idempotente:** Genera el archivo CSV final para consumo analítico y una ficha técnica en JSON (`resumen.json`) con metadatos descriptivos y estadísticas del proceso.
   - **Auditoría:** Registra la ejecución de forma incremental en `pipeline.log`.

---

## 📦 Instalación y Ejecución
### Prerrequisitos
- Python 3.9 o superior.
- Git.

1. Clonar el repositorio y entrar a la carpeta:

Bash
git clone https://github.com/juaninz/tp-final-etl.git
cd tp-final-etl

2. Crear y activar el entorno virtual:
En Windows:

Bash
python -m venv venv
venv\Scripts\activate
En Linux o Mac:

Bash
python3 -m venv venv
source venv/bin/activate

3. Instalar dependencias:

Bash
pip install -r requirements.txt

4. Correr los tests unitarios:
Bash
python tests/test_transform.py

5. Ejecutar el pipeline ETL:
Bash
python src/main.py

Al terminar, los datos descargados estarán en data/raw/ y el archivo CSV final junto a su resumen.json se guardarán en data/processed/.

## 🌐 Fuente de los Datos

Los datos provienen de la **API de Series de Tiempo del Ministerio de Economía de la República Argentina** (`https://apis.datos.gob.ar/series/api/`).

Se extraen las series anuales del período 1993 a la actualidad correspondientes a:

* **Exportaciones provinciales por grandes rubros:** Productos Primarios, Manufacturas de Origen Agropecuario (MOA), Manufacturas de Origen Industrial (MOI) y Combustibles/Energía.
* **Exportaciones provinciales por destino:** Principales países y bloques económicos receptores.
* **Total provincial:** Monto consolidado exportado anual por provincia en millones de dólares FOB.

---

## 🔍 Hallazgos en los Datos

Al explorar el dataset analítico resultante, se observa un marcado cambio estructural en la orientación geográfica de las exportaciones del NEA a partir de la década de 2000:

* **Desplazamiento del Mercosur por Asia:** Durante la década de 1990, los destinos regionales (particularmente Brasil y el bloque Mercosur) concentraban de forma casi absoluta el podio del ranking en provincias como Misiones y Corrientes. A partir de mediados de los 2000 y consolidándose en los 2010s, **China irrumpe sostenidamente como el destino #1 en Chaco**, traccionado casi con exclusividad por la alta concentración de **Productos Primarios** en su matriz productiva.
* **Volatilidad y caídas abruptas:** Se identifican años atípicos con caídas interanuales superiores al **40%** (notorias en las crisis de 2001-2002 y en las sequías severas de 2012), lo que evidencia la alta exposición y vulnerabilidad de las economías provinciales ante shocks climáticos y macroeconómicos.

