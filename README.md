# Pipeline de Otimização de Poços de Petróleo e Gás

Projeto de análise de dados e machine learning para estimar a margem
operacional diária de poços. O dashboard também apresenta agregações calculadas
a partir do conjunto de dados.



## Estrutura

```text
backend/
  api/          API FastAPI
  artifacts/    artefato do modelo treinado
  dataset/      conjuntos CSV
  src/          preparação e treinamento
  requirements.txt
frontend/
  frontend/     aplicação React + Vite
notebook/       análise exploratória
```

## Backend

No PowerShell, a partir da raiz deste repositório:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r .\backend\requirements.txt
$env:CORS_ALLOWED_ORIGINS = "http://localhost:5173"
Set-Location .\backend\api
python -m uvicorn app:app --reload
```

A documentação interativa fica em `http://127.0.0.1:8000/docs`.

Endpoints principais:

- `GET /health`: prontidão da API e do artefato.
- `GET /dashboard/summary`: agregações usadas pelos gráficos.
- `POST /predict`: estimativa de margem líquida diária.

O dashboard lê `backend/dataset/well_data.csv`. A coluna
`daily_revenue_usd` do CSV corresponde à margem líquida calculada pela receita
de petróleo e gás menos o OPEX, apesar do nome da coluna.

## Frontend

Em outro terminal, a partir da raiz do repositório:

```powershell
Set-Location .\frontend\frontend
Copy-Item .env.example .env
npm install
npm run dev
```

possível inferir tendências temporais com esse conjunto de dados.

Os conjuntos alternativos em `backend/dataset/` não alimentam o dashboard
principal automaticamente.
