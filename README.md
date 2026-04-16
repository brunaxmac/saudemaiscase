# Saúde+ Analytics Dashboard 🏥

Dashboard interativo para análise das prescrições digitais — Case Técnico Analytics.

## Estrutura

```
saude_dashboard/
├── app.py                  # Dashboard principal (Streamlit)
├── requirements.txt
├── .env.example            # Template de variáveis de ambiente
└── data/
    ├── prescricaomedicamento.csv
    ├── medicamentos.csv
    └── medicos.csv
```

## Instalação

```bash
# 1. Crie e ative um ambiente virtual
python -m venv .venv
source .venv/bin/activate        # Linux/Mac
.venv\Scripts\activate           # Windows

# 2. Instale as dependências
pip install -r requirements.txt

# 3. Configure a API Key do Claude
cp .env.example .env
# Edite .env e coloque sua ANTHROPIC_API_KEY

# 4. Rode o dashboard
streamlit run app.py
```

## Páginas

| Página | Conteúdo | Perguntas do Case |
|--------|----------|-------------------|
| 📊 Overview | KPIs, prescrições diárias, sazonalidade, pacientes | Q1, Q2 |
| 👨‍⚕️ Médicos & Especialidades | Top especialidades, open rate por especialidade, perfil médico | Q3 |
| 💊 Medicamentos | Top medicamentos, controle especial, conversão | — |
| 📬 Open Rate & Conversão | Funil, conversão por canal, open rate semanal e por dia da semana | Q4, Q5 |
| 🔍 Insights Adicionais | Tempo para compra, abandono regional, oportunidades | Q6, Q7 |
| 🤖 Agente IA | Chat com Claude para interpretar os dados | — |

## Tecnologias

- **Streamlit** — interface web
- **Plotly** — visualizações interativas
- **Pandas** — manipulação de dados
- **Anthropic Claude** — agente de IA para interpretação dos dados
