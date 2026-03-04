"""
vector_db/ingest.py — Cria o Index no Azure AI Search e ingere documentos.

Uso:
    python vector_db/ingest.py --docs docs/          # ingere todos PDFs/TXTs de uma pasta
    python vector_db/ingest.py --docs file.pdf       # ingere um arquivo específico

O script:
  1. Cria (ou recria) o Index com campos text + vector (1536 dims para ada-002)
  2. Lê e divide os documentos em chunks
  3. Gera embeddings via ada-002 (Azure OpenAI / Foundry)
  4. Faz upload dos documentos para o Index

Parâmetros de chunking otimizados para documentos técnicos/científicos:
  - CHUNK_SIZE    = 1000 chars — preserva parágrafos e tabelas inteiras
  - CHUNK_OVERLAP = 150  chars — mantém contexto entre seções adjacentes
  - Limpeza de texto ativa — remove ruído típico de PDFs escaneados
"""

import os
import re
import sys
import uuid
import argparse
from pathlib import Path
from typing import List, Dict

from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex,
    SearchField,
    SearchFieldDataType,
    SimpleField,
    SearchableField,
    VectorSearch,
    HnswAlgorithmConfiguration,
    VectorSearchProfile,
)
from openai import AzureOpenAI
from dotenv import load_dotenv

load_dotenv(override=True)

index_client = SearchIndexClient(
    endpoint=os.getenv("AZURE_SEARCH_ENDPOINT"),
    credential=AzureKeyCredential(os.getenv("AZURE_SEARCH_KEY")),
)

search_client = SearchClient(
    endpoint=os.getenv("AZURE_SEARCH_ENDPOINT"),
    index_name=os.getenv("AZURE_SEARCH_INDEX", "rag-index"),
    credential=AzureKeyCredential(os.getenv("AZURE_SEARCH_KEY")),
)

openai_client = AzureOpenAI(
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_KEY"),
    api_version="2024-05-01-preview",
)

INDEX_NAME         = os.getenv("AZURE_SEARCH_INDEX", "rag-index")
EMBEDDING_DEPLOYMENT = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-ada-002")
VECTOR_DIMS  = 1536
CHUNK_SIZE   = 1000   # chunks maiores preservam parágrafos e tabelas técnicas inteiras
CHUNK_OVERLAP = 150   # overlap maior mantém contexto entre seções adjacentes


# criar index

def create_index():
    print(f"Criando Index '{INDEX_NAME}'...")

    fields = [
        SimpleField(name="id",     type=SearchFieldDataType.String, key=True),
        SearchableField(name="content", type=SearchFieldDataType.String),
        SimpleField(name="source", type=SearchFieldDataType.String, filterable=True),
        SimpleField(name="title",  type=SearchFieldDataType.String, filterable=True),
        SearchField(
            name="content_vector",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            searchable=True,
            vector_search_dimensions=VECTOR_DIMS,
            vector_search_profile_name="hnsw-profile",
        ),
    ]

    vector_search = VectorSearch(
        algorithms=[HnswAlgorithmConfiguration(name="hnsw-algo")],
        profiles=[VectorSearchProfile(name="hnsw-profile", algorithm_configuration_name="hnsw-algo")],
    )

    try:
        index_client.delete_index(INDEX_NAME)
        print(f"Index anterior apagado.")
    except Exception:
        pass

    index_client.create_index(SearchIndex(name=INDEX_NAME, fields=fields, vector_search=vector_search))
    print(f"Index '{INDEX_NAME}' criado com sucesso.")


# ler documentos

def clean_text(text: str) -> str:
    """
    Limpa ruídos comuns de PDFs escaneados/técnicos:
      - múltiplos espaços e tabs colapsados
      - hifenização quebrada entre linhas (ex: "climato-\nlogia" → "climatologia")
      - linhas em branco excessivas reduzidas a uma só
      - caracteres de controle removidos
    """
    text = re.sub(r'(\w+)-\n(\w+)', r'\1\2', text)       # hifenização quebrada
    text = re.sub(r'[ \t]+', ' ', text)                   # espaços múltiplos
    text = re.sub(r'\n{3,}', '\n\n', text)                # linhas em branco excessivas
    text = re.sub(r'[^\x20-\x7E\xA0-\xFF\n]', '', text)  # caracteres de controle
    return text.strip()


def read_file(path: Path) -> str:
    suffix = path.suffix.lower()

    if suffix == ".txt":
        return path.read_text(encoding="utf-8", errors="ignore")

    if suffix == ".pdf":
        try:
            import pypdf
            reader = pypdf.PdfReader(str(path))
            raw = "\n".join(page.extract_text() or "" for page in reader.pages)
            return clean_text(raw)
        except ImportError:
            print("pypdf não instalado")
            return ""

    print(f"Formato não suportado: {suffix} — ignorando {path.name}")
    return ""


def chunk_text(text: str, source: str, title: str) -> List[Dict]:
    """
    Divide o texto em chunks respeitando quebras de parágrafo sempre que possível.
    Isso evita cortar tabelas e seções técnicas no meio.
    """
    paragraphs = re.split(r'\n{2,}', text)  # divide por parágrafos
    chunks = []
    current = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        # se adicionar o parágrafo estoura o chunk, salva o atual e começa novo
        if len(current) + len(para) > CHUNK_SIZE and current:
            chunks.append({
                "id": str(uuid.uuid4()),
                "content": current.strip(),
                "source": source,
                "title": title,
            })
            # overlap: mantém os últimos CHUNK_OVERLAP chars do chunk anterior
            current = current[-CHUNK_OVERLAP:] + "\n\n" + para
        else:
            current = (current + "\n\n" + para).strip() if current else para

    # salva o último chunk
    if current.strip():
        chunks.append({
            "id": str(uuid.uuid4()),
            "content": current.strip(),
            "source": source,
            "title": title,
        })

    return chunks


def load_documents(path_str: str) -> List[Dict]:
    path = Path(path_str)
    docs = []

    if path.is_file():
        files = [path]
    elif path.is_dir():
        files = list(path.glob("**/*.pdf")) + list(path.glob("**/*.txt"))
    else:
        print(f"Caminho não encontrado: {path_str}")
        sys.exit(1)

    print(f"{len(files)} arquivo(s) encontrado(s).")

    for f in files:
        print(f"Lendo: {f.name}")
        text = read_file(f)
        if text:
            chunks = chunk_text(text, source=str(f), title=f.stem)
            docs.extend(chunks)
            print(f"{len(chunks)} chunks gerados.")

    return docs


# gerar embeddings

def embed_documents(docs: List[Dict]) -> List[Dict]:
    print(f"\nGerando embeddings para {len(docs)} chunks...")

    batch_size = 16   # limite do Azure OpenAI por request
    for i in range(0, len(docs), batch_size):
        batch = docs[i: i + batch_size]
        texts = [d["content"] for d in batch]

        response = openai_client.embeddings.create(
            input=texts,
            model=EMBEDDING_DEPLOYMENT,
        )

        for j, emb in enumerate(response.data):
            docs[i + j]["content_vector"] = emb.embedding

        print(f"Batch {i // batch_size + 1}/{-(-len(docs) // batch_size)} processado.")

    return docs


# upload para o index

def upload_documents(docs: List[Dict]):
    print(f"\nEnviando {len(docs)} documento(s) para o Index...")

    batch_size = 100  # limite do Azure AI Search por request
    for i in range(0, len(docs), batch_size):
        batch  = docs[i: i + batch_size]
        result = search_client.upload_documents(documents=batch)
        succeeded = sum(1 for r in result if r.succeeded)
        print(f"Batch {i // batch_size + 1}: {succeeded}/{len(batch)} documentos enviados.")


def main():
    parser = argparse.ArgumentParser(description="Ingere documentos PDF/TXT no Azure AI Search.")
    parser.add_argument("--docs", required=True, help="Caminho para um arquivo ou pasta (PDF/TXT).")
    parser.add_argument("--recreate-index", action="store_true", default=True,
                        help="Recriar o Index antes de ingerir (padrão: True).")
    args = parser.parse_args()

    print("Iniciando ingestão de documentos...\n")

    if args.recreate_index:
        create_index()

    docs = load_documents(args.docs)

    if not docs:
        print("Nenhum conteúdo extraído. Verifique os arquivos.")
        sys.exit(1)

    docs = embed_documents(docs)
    upload_documents(docs)

    print(f"\nIngestão concluída! {len(docs)} chunk(s) indexado(s) em '{INDEX_NAME}'.")


if __name__ == "__main__":
    main()
