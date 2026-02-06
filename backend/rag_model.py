import sys
import os
import logging
from typing import List, Dict, Tuple
import chromadb
import requests
from sentence_transformers import SentenceTransformer
from openai import OpenAI
from dotenv import load_dotenv

if sys.stdin is not None and sys.stdin.isatty():
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

load_dotenv()

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class RAGModel:
    def __init__(self):
        self.chroma_client = chromadb.Client()
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        self.openai_api_base = os.getenv("OPENAI_API_BASE", "http://localhost:11434/v1")
        self.llm_model = os.getenv("LLM_MODEL", "neural-chat")
        self._check_ollama_connection()
        self.client = OpenAI(api_key="ollama", base_url=self.openai_api_base)
        logger.info(f"RAG Model initialisé - LLM: {self.llm_model} @ {self.openai_api_base}")
    
    def _check_ollama_connection(self) -> bool:
        try:
            tags_url = self.openai_api_base.replace("/v1", "/api/tags")
            response = requests.get(tags_url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                models = [model['name'].split(':')[0] for model in data.get('models', [])]
                logger.info(f"Modèles Ollama disponibles: {', '.join(set(models))}")
                if self.llm_model not in [m.split(':')[0] for m in models]:
                    logger.warning(f"Modèle '{self.llm_model}' non trouvé. Utilisation d'un autre modèle.")
                    if models:
                        self.llm_model = models[0].split(':')[0]
                return True
            else:
                logger.warning(f"Ollama API retourne: {response.status_code}")
                return False
        except requests.exceptions.ConnectionError:
            logger.warning(f"Impossible de se connecter à Ollama sur {self.openai_api_base}")
            return False
        except Exception as e:
            logger.warning(f"Erreur vérification Ollama: {str(e)}")
            return False
    
    def get_or_create_collection(self, tenant: str) -> chromadb.Collection:
        collection_name = f"tenant_{tenant}"
        try:
            return self.chroma_client.get_collection(name=collection_name)
        except:
            return self.chroma_client.create_collection(name=collection_name)
    
    def chunk_text(self, text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
        chunks, start = [], 0
        step = max(1, chunk_size - overlap)
        while start < len(text):
            end = min(start + chunk_size, len(text))
            chunks.append(text[start:end])
            start += step
        return chunks
    
    def index_documents(self, tenant: str) -> int:
        collection = self.get_or_create_collection(tenant)
        base_path = f"data/{tenant}"
        if not os.path.exists(base_path):
            raise Exception(f"Dossier introuvable : {base_path}")
        if collection.count() > 0:
            return collection.count()
        doc_id, total_chunks = 0, 0
        for filename in os.listdir(base_path):
            file_path = os.path.join(base_path, filename)
            if not filename.lower().endswith(('.txt', '.md')):
                continue
            try:
                try:
                    with open(file_path, encoding="utf-8") as f:
                        content = f.read()
                except UnicodeDecodeError:
                    with open(file_path, encoding="latin-1") as f:
                        content = f.read()
                if not content.strip():
                    continue
                chunks = self.chunk_text(content, chunk_size=500)
                for i, chunk in enumerate(chunks):
                    if not chunk.strip():
                        continue
                    embedding = self.embedding_model.encode(chunk)
                    collection.add(
                        ids=[f"{doc_id}_{i}"],
                        embeddings=[embedding.tolist()],
                        metadatas=[{"source": filename, "chunk_index": i, "tenant": tenant}],
                        documents=[chunk]
                    )
                    total_chunks += 1
                doc_id += 1
            except Exception:
                continue
        return total_chunks
    
    def retrieve_documents(self, question: str, tenant: str, top_k: int = 3) -> List[Dict]:
        collection = self.get_or_create_collection(tenant)
        question_embedding = self.embedding_model.encode(question).tolist()
        results = collection.query(query_embeddings=[question_embedding], n_results=top_k)
        retrieved_docs = []
        if results and results['documents']:
            for i, doc in enumerate(results['documents'][0]):
                retrieved_docs.append({
                    "document": doc,
                    "source": results['metadatas'][0][i].get('source', 'unknown'),
                    "distance": results['distances'][0][i] if results['distances'] else 0
                })
        return retrieved_docs
    
    def generate_response(self, question: str, context_docs: List[Dict]) -> Tuple[str, List[str]]:
        context_text = "\n\n---\n\n".join([f"[Source: {doc['source']}]\n{doc['document']}" for doc in context_docs])
        system_prompt = """Tu es un assistant expert spécialisé dans l'analyse de documents.
Réponds uniquement sur la base des documents fournis."""
        user_prompt = f"Documents:\n{context_text}\n\nQuestion: {question}\nRéponds en français."
        try:
            response = self.client.chat.completions.create(
                model=self.llm_model,
                messages=[{"role": "system", "content": system_prompt},
                          {"role": "user", "content": user_prompt}],
                temperature=0.3,
                max_tokens=1000,
                timeout=60
            )
            answer = response.choices[0].message.content
            sources = list(set([doc['source'] for doc in context_docs]))
            return answer, sources
        except Exception as e:
            return f"Erreur génération LLM: {str(e)}", []
    
    def answer_question(self, question: str, tenant: str, top_k: int = 3) -> Dict:
        context_docs = self.retrieve_documents(question, tenant, top_k)
        answer, sources = self.generate_response(question, context_docs)
        return {"question": question, "answer": answer, "sources": sources, "documents_used": len(context_docs)}

rag_model = RAGModel()

if __name__ == "__main__":
    rag_model.index_documents("tenantA")
    result = rag_model.answer_question("Qu'est-ce qu'une procédure de résiliation?", "tenantA")
    print(f"Question: {result['question']}")
    print(f"Réponse: {result['answer']}")
    print(f"Sources: {result['sources']}")

