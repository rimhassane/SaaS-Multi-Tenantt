from fastapi import FastAPI, Header, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
import os
import chromadb
from sentence_transformers import SentenceTransformer
from openai import OpenAI
from dotenv import load_dotenv
import logging
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()

app = FastAPI(title="Mini SaaS Multi-Tenant RAG")

TENANTS = {
    "tenantA_key": "tenantA",
    "tenantB_key": "tenantB",
}

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

chroma_client = chromadb.Client()
embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
openai_api_key = os.getenv("OPENAI_API_KEY", "sk-test")
openai_api_base = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
llm_model = os.getenv("LLM_MODEL", "gpt-3.5-turbo")
client = OpenAI(api_key=openai_api_key, base_url=openai_api_base)

def get_tenant(x_api_key: str = Header(...)):
    if x_api_key not in TENANTS:
        raise HTTPException(status_code=401, detail="API Key invalide")
    return TENANTS[x_api_key]

def get_or_create_collection(tenant: str):
    collection_name = f"tenant_{tenant}"
    try:
        return chroma_client.get_collection(name=collection_name)
    except:
        return chroma_client.create_collection(name=collection_name)

def index_documents(tenant: str):
    collection = get_or_create_collection(tenant)
    base_path = f"data/{tenant}"
    if not os.path.exists(base_path):
        raise Exception(f"Dossier introuvable : {base_path}")
    if collection.count() > 0:
        return
    doc_id = 0
    for filename in os.listdir(base_path):
        file_path = os.path.join(base_path, filename)
        with open(file_path, encoding="utf-8") as f:
            content = f.read()
            chunks = chunk_text(content, chunk_size=500)
            for i, chunk in enumerate(chunks):
                embedding = embedding_model.encode(chunk)
                collection.add(
                    ids=[f"{doc_id}_{i}"],
                    embeddings=[embedding.tolist()],
                    metadatas=[{"source": filename, "chunk": i}],
                    documents=[chunk]
                )
                doc_id += 1

def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50):
    chunks = []
    start = 0
    step = max(1, chunk_size - overlap)
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end])
        start += step
    return chunks

def retrieve_documents(question: str, tenant: str, top_k: int = 3):
    collection = get_or_create_collection(tenant)
    question_embedding = embedding_model.encode(question).tolist()
    results = collection.query(query_embeddings=[question_embedding], n_results=top_k)
    return results

def generate_answer(question: str, context: str):
    start_time = time.time()
    try:
        response = client.chat.completions.create(
            model=llm_model,
            messages=[
                {"role": "system", "content": "Tu es un assistant expert. Réponds basé uniquement sur le contexte fourni."},
                {"role": "user", "content": f"Contexte:\n{context}\n\nQuestion: {question}"}
            ],
            temperature=0.7,
            max_tokens=500
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Erreur LLM: {str(e)}"

@app.post("/ask")
def ask(question: str, tenant: str = Depends(get_tenant)):
    start_time = time.time()
    try:
        index_documents(tenant)
        search_results = retrieve_documents(question, tenant, top_k=3)
        if not search_results["documents"] or len(search_results["documents"][0]) == 0:
            return {"answer": "Aucune information disponible pour cette question.", "sources": [], "confidence": 0}
        documents = search_results["documents"][0]
        metadatas = search_results["metadatas"][0]
        distances = search_results["distances"][0]
        context = "\n\n".join(documents)
        sources = list(set([meta["source"] for meta in metadatas]))
        answer = generate_answer(question, context)
        return {"answer": answer, "sources": sources, "confidence": float(1 - distances[0]) if distances else 0}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health():
    return {"status": "ok"}
