# ResumeLens: Formal Language-Based Resume Screening

Proyecto integrador de **Computación y Estructuras Discretas III (2026-2)**, Universidad Icesi.
Profesor: Andrés Aristizábal.

**Integrantes:** Juan Restrepo, Samuel Granda, Daniel Varela.

## Pipeline formal de 4 etapas

1. **Regex** — extracción de campos (contacto, fechas, habilidades) del texto crudo del currículum.
2. **FST** (transductores de estado finito) — normalización de los datos extraídos.
3. **Autómatas** (`pyformlang`) — clasificación y validación de habilidades/secciones.
4. **textX DSL** — gramática para definir reglas de evaluación de candidatos.

## Estructura

```
resumelens/
  core/  extraction/  normalization/  classification/  grammar/  visualization/
docs/  tests/  data/input_resumes/  data/templates/
```

## Configuración del entorno

```bash
python -m venv .venv
# Windows (PowerShell): .venv\Scripts\Activate.ps1
# Linux/macOS:          source .venv/bin/activate
pip install -r requirements.txt
pytest
```

Dependencias autorizadas: `pyformlang`, `textx`, `pytest`, `pydot`.
