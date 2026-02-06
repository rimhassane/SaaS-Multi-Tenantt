from fastapi import FastAPI, Header, HTTPException, Depends
import os

app = FastAPI(title="Mini SaaS Multi-Tenant")
TENANTS = {
    "tenantA_key": "tenantA",
    "tenantB_key": "tenantB",
}
def get_tenant(x_api_key: str = Header(...)):
    if x_api_key not in TENANTS:
        raise HTTPException(status_code=401, detail="API Key invalide")
    return TENANTS[x_api_key]
def load_documents(tenant: str):
    docs = []
    base_path = f"data/{tenant}"

    if not os.path.exists(base_path):
        raise Exception(f"Dossier introuvable : {base_path}")

    for filename in os.listdir(base_path):
        file_path = os.path.join(base_path, filename)
        with open(file_path, encoding="utf-8") as f:
            docs.append({
                "source": filename,
                "content": f.read()
            })

    return docs

@app.post("/ask")
def ask(question: str, tenant: str = Depends(get_tenant)):
    documents = load_documents(tenant)
    
 
    question_lower = question.lower()
    for doc in documents:
        if question_lower in doc["content"].lower():
            return {
                "answer": doc["content"],
                "source": doc["source"]
            }
    
    scored_docs = []
    for doc in documents:
        content_lower = doc["content"].lower()
        matches = [word for word in question.split() if word.lower() in content_lower]
        score = sum(len(word) for word in matches)
        
        if matches:
            scored_docs.append({
                "doc": doc,
                "score": score,
                "match_count": len(matches)
            })
    if scored_docs:
        best_match = max(scored_docs, key=lambda x: (x["match_count"], x["score"]))
        return {
            "answer": best_match["doc"]["content"],
            "source": best_match["doc"]["source"]
        }

    return {
        "answer": "Aucune information disponible pour ce client.",
        "source": None
    }
