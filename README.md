# RAG PDF - Assistente Local

API de RAG (Retrieval-Augmented Generation) para consulta de documentos PDF em linguagem natural, rodando de forma 100% local e gratuita.

## Sobre o projeto

Este projeto implementa um pipeline de RAG seguindo o padrão **Multi-Vector Retriever**: em vez de indexar o conteúdo bruto do documento diretamente, cada elemento extraído do PDF (texto ou tabela) recebe um resumo gerado por um modelo de linguagem. É esse resumo que é convertido em embedding e indexado no banco vetorial, enquanto o conteúdo original correspondente fica guardado à parte, vinculado por um ID.

Essa separação melhora a qualidade da busca semântica (resumos curtos e objetivos tendem a casar melhor com perguntas do usuário do que blocos de texto longos), mantendo o conteúdo completo disponível para montar a resposta final.

Fluxo geral:

1. O PDF é processado e dividido em elementos de texto e de tabela
2. Cada elemento recebe um resumo gerado por um LLM local
3. O resumo é convertido em embedding e salvo no banco vetorial (ChromaDB)
4. O conteúdo original é salvo em um DocStore, vinculado ao resumo por um ID de documento
5. Na consulta, a pergunta do usuário é comparada aos resumos indexados; os documentos originais correspondentes são recuperados e usados como contexto para o LLM gerar a resposta final

## Tecnologias utilizadas

| Camada | Ferramenta | Função no projeto |
|---|---|---|
| Linguagem | Python 3.11+ | Implementação do backend |
| API | FastAPI + Uvicorn | Servidor HTTP e definição dos endpoints |
| Orquestração de RAG | LangChain | Multi-Vector Retriever e integração entre componentes |
| Extração de PDF | Unstructured | Extração de texto e tabelas do documento |
| Banco vetorial | ChromaDB | Armazenamento e busca por similaridade dos embeddings |
| Armazenamento de documentos | LangChain LocalFileStore | Guarda o conteúdo original de cada elemento indexado |
| Execução de modelos | Ollama | Execução local dos modelos de linguagem e embedding |
| Modelo de linguagem | Llama 3.2 | Geração de resumos e respostas finais |
| Modelo de embeddings | Nomic Embed Text | Geração dos vetores usados na busca semântica |
| Frontend | HTML, CSS e JavaScript (sem framework) | Interface de upload de PDF e consulta |
| Versionamento | Git + GitHub (autenticação via SSH) | Controle de versão do projeto |

Toda a stack roda localmente; não há dependência de nenhuma API paga ou chave de acesso externa.

## Estrutura do projeto

```
rag-backend/
├── backend/
│   ├── __init__.py
│   ├── config.py          # Configurações centrais (modelos, paths, host do Ollama)
│   ├── ingest.py           # Pipeline de ingestão do PDF
│   ├── retriever.py        # Monta o MultiVectorRetriever e executa as buscas
│   ├── main.py              # API FastAPI (endpoints)
│   └── requirements.txt
├── frontend/
│   ├── index.html
│   ├── script.js
│   └── style.css
├── .gitignore
└── README.md
```

As pastas `chroma_db/`, `docstore/` e `venv/` são geradas localmente durante o uso e não são versionadas.

## Pré-requisitos

- Python 3.11 ou superior
- [Ollama](https://ollama.com) instalado e em execução
- Git

No Windows, caso a instalação do ChromaDB solicite compilação de dependências nativas, pode ser necessário instalar as [Build Tools do Visual C++](https://visualstudio.microsoft.com/visual-cpp-build-tools/) (workload "Desktop development with C++").

### Modelos do Ollama

```bash
ollama pull llama3.2:3b
ollama pull nomic-embed-text
```

> Em máquinas com 8GB de RAM ou menos, o modelo `llama3.2:1b` é uma alternativa mais leve ao `3b`. A troca é feita ajustando o valor de `CHAT_MODEL` em `backend/config.py`.

## Instalação

```bash
git clone git@github.com:N3t30/rag-backend.git
cd rag-backend

python -m venv venv
venv\Scripts\activate

pip install -r backend/requirements.txt
```

## Como executar

```bash
# 1. Certifique-se de que o Ollama está em execução em segundo plano

# 2. Inicie o backend
.\venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000

# 3. Abra frontend/index.html diretamente no navegador (duplo clique)
```

> Evite servir o `index.html` com uma extensão de live-reload apontando para a raiz do projeto: como o backend grava arquivos em disco durante a ingestão (`chroma_db/`, `docstore/`), o recarregamento automático pode interromper a requisição em andamento. Se for usar live-reload, restrinja-o à pasta `frontend/`.

### Uso

1. Confirme que o indicador no topo do frontend mostra "Backend online"
2. Selecione um arquivo PDF e clique em "Indexar PDF" — o tempo de processamento varia com o tamanho do arquivo e o hardware disponível
3. Após a indexação, digite uma pergunta sobre o conteúdo do documento e clique em "Perguntar"

## Endpoints da API

### `GET /health`

Verifica se o Ollama está acessível e lista os modelos disponíveis.

```json
{
  "status": "ok",
  "ollama_available": true,
  "models": ["llama3.2:3b", "nomic-embed-text:latest"]
}
```

### `POST /ingest`

Recebe um PDF (`multipart/form-data`, campo `file`) e executa o pipeline de ingestão.

```bash
curl -X POST http://127.0.0.1:8000/ingest -F "file=@documento.pdf"
```

```json
{
  "textos_indexados": 16,
  "tabelas_indexadas": 0
}
```

### `POST /query`

Recebe uma pergunta em linguagem natural e retorna a resposta com base no conteúdo indexado.

```bash
curl -X POST http://127.0.0.1:8000/query \
  -H "Content-Type: application/json" \
  -d '{"pergunta": "Do que se trata esse documento?"}'
```

```json
{
  "resposta": "...",
  "fontes": ["id-1", "id-2"]
}
```

## Limitações da versão atual

- Processa apenas texto e tabelas; extração e resumo de imagens ainda não são suportados
- Processamento sequencial (um elemento por vez), priorizando compatibilidade com máquinas de recursos limitados em detrimento de velocidade
- Sem autenticação, testes automatizados ou banco de dados relacional
- Desempenho depende diretamente do hardware disponível; em máquinas com 8GB de RAM, a ingestão de PDFs maiores pode levar alguns minutos

## Próximos passos

- Suporte a extração e resumo de imagens, usando um modelo multimodal local
- Testes automatizados
- Melhorias de desempenho no pipeline de ingestão
