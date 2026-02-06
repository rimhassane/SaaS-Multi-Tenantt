#  SaaS Multi-Tenant 

Un système simple où chaque client (Client A, Client B) a ses propres documents. Quand un client pose une question, le système répond uniquement en se basant sur **ses propres documents** - pas ceux des autres.


##  Comment ça marche (approche simple)

1. **Authentification par clé API** : Chaque client a une clé unique (tenantA_key, tenantB_key)
2. **Documents isolés par dossier** : Les docs du client A sont dans `data/tenantA/`, ceux du B dans `data/tenantB/`
3. **Backend intelligent** : Quand le client pose une question, le backend cherche la réponse **uniquement** dans ses documents
4. **Interface web** : Frontend Streamlit simple pour choisir le client et poser des questions


**RAG = Retrieval Augmented Generation** (

### Pourquoi RAG dans ce projet ?

**Réponses précises** - Basées sur les vrais documents, pas des hallucinations IA
**Sécurisé** - Pas d'accès à des informations externes
**Multi-tenant** - Isolation garantie par tenant
**Traçabilité** - On sait d'où vient chaque réponse (sources)

### Comment fonctionne le RAG ici

```
┌────────────────────────────────────────────────────────────┐
│ 1. INDEXATION (au démarrage)                               │
│    - Lis les documents de chaque tenant                    │
│    - Découpe en chunks de 500 caractères                   │
│    - Convertit en vecteurs (embeddings) avec              │
│      SentenceTransformer (all-MiniLM-L6-v2)               │
│    - Stocke dans ChromaDB                                  │
└────────────────────────────────────────────────────────────┘
                            ↓
┌────────────────────────────────────────────────────────────┐
│ 2. RETRIEVAL (quand l'utilisateur pose une question)      │
│    - Encode la question en vecteur                         │
│    - Cherche les 3 documents les plus similaires           │
│      (similarité cosinus) dans ChromaDB                    │
│    - Retourne les documents pertinents                     │
└────────────────────────────────────────────────────────────┘
                            ↓
┌────────────────────────────────────────────────────────────┐
│ 3. AUGMENTATION (préparation du prompt)                    │
│    - Crée un prompt avec :                                 │
│      * Les documents trouvés comme contexte                │
│      * La question de l'utilisateur                        │
│      * Instructions au modèle                              │
└────────────────────────────────────────────────────────────┘
                            ↓
┌────────────────────────────────────────────────────────────┐
│ 4. GENERATION (avec Ollama)                                │
│    - Envoie le prompt à Ollama (LLM local)                │
│    - Le modèle génère une réponse basée sur le contexte   │
│    - Retourne réponse + sources                            │
└────────────────────────────────────────────────────────────┘
```

### Exemple concret

```
Question: "Quelle est la procédure de résiliation ?"
Tenant: Client A

↓↓↓

RETRIEVAL: 
- Trouve dans docA1_procedure_resiliation.txt:
  "La résiliation doit être demandée par écrit..."

AUGMENTATION:
- Crée ce prompt:
  "Basé sur le document fourni : [doc]
   Réponds à la question: Quelle est la procédure de résiliation?"

GENERATION:
- Ollama génère:
  "La procédure de résiliation selon le document fourni est..."

RÉSULTAT:
{
  "answer": "La procédure de résiliation...",
  "sources": ["docA1_procedure_resiliation.txt"]
}
```


##  Installation



### Étapes

```bash
# 1. Cloner ou télécharger le repo
cd saas-multitenant-test

# 2. Installer les dépendances
pip install -r requirements.txt
```



##  Lancer le système

### Terminal 1 : Lancer le Backend (API)

```bash
cd backend
uvicorn main:app --reload
```

 Vous devez voir :
```
Uvicorn running on http://127.0.0.1:8000
```

### Terminal 2 : Lancer le Frontend (Interface Web)

```bash
cd frontend
streamlit run app.py
```

 Vous devez voir :
```
Local URL: http://localhost:8501
```

---

##  Comment tester

### 1 Ouvrir l'interface web
Allez sur : **http://localhost:8501**

### 2 Tester Client A

1. **Sélectionnez** "Client A" dans la dropdown
2. **Tapez** : `Quelles sont les conditions de resiliation?`
3. **Cliquez** "Envoyer"

 **Résultat attendu** :
```json
{
  "answer": "Procédure résiliation\nLa résiliation doit être...",
  "source": "docA1_procedure_resiliation.txt"
}
```

### 3 Tester Client B

1. **Sélectionnez** "Client B"
2. **Tapez** : `Comment signaler un sinistre?`
3. **Cliquez** "Envoyer"

 **Résultat attendu** :
```json
{
  "answer": "Procédure sinistre\nTout sinistre doit être déclaré...",
  "source": "docB1_procedure_sinistre.txt"
}
```

### 4 Vérifier l'isolation (IMPORTANT!)

Testez que **Client A n'accède pas aux docs de Client B** :

1. Sélectionnez "Client A"
2. Tapez : `sinistre` (mot qui existe dans docB1, pas dans docA)
3. Cliquez "Envoyer"

 **Devrait répondre** : "Aucune information disponible pour ce client."

---

##  Tester directement l'API (avancé)

### Client A
```bash
curl -X POST "http://127.0.0.1:8000/ask?question=resiliation" \
  -H "X-API-KEY: tenantA_key"
```

### Client B
```bash
curl -X POST "http://127.0.0.1:8000/ask?question=sinistre" \
  -H "X-API-KEY: tenantB_key"
```

---

##  Structure du Projet

```
saas-multitenant-test/          
│
├── backend/
│   ├── main.py                  
│   ├── rag_model.py             
│   └── data/
│        ├── tenantA/                 
│        │   ├── docA1_procedure_resiliation.txt
│        │   └── docA2_produit_rc_pro_a.txt
│        │
│        └── tenantB/                 
│           ├── docB1_procedure_sinistre.txt
│           └── docB2_produit_rc_pro_b.txt
├── frontend/
│   └── app.py                   
├── README.md                    
├── requirements.txt  
└── .env                         
```

### Fichiers clés du RAG

| Fichier | Rôle |
|---------|------|
| `backend/rag_model.py` | Classe RAGModel - gère indexation, retrieval, génération |
| `backend/main.py` | API endpoint `/ask` qui utilise RAGModel |
| `backend/data/` | Documents source par tenant (indexés au démarrage) |

---

##  Authentification & Isolation

| Client | Clé API | Dossier | Accès à |
|--------|---------|---------|--------|
| **A** | `tenantA_key` | `data/tenantA/` | docA1, docA2 uniquement |
| **B** | `tenantB_key` | `data/tenantB/` | docB1, docB2 uniquement |

Le backend valide la clé API et charge **uniquement les documents du tenant**.

---



##  Stack Technologique

### Core
- **Backend** : FastAPI (framework API Python ultra-rapide)
- **Frontend** : Streamlit (interface web en Python, super simple)
- **Auth** : API Keys dans Headers
- **DB** : Fichiers texte (pas de DB, c'est volontaire pour la démo!)

### RAG Components
- **Embedding Model** : `sentence-transformers/all-MiniLM-L6-v2` (convertit texte → vecteurs 384D)
- **Vector DB** : ChromaDB (stockage et recherche vectorielle)
- **LLM** : Ollama (modèles locaux, pas d'API externe)
- **Processing** : 
  - Text chunking (découpe intelligente des documents)
  - Cosine similarity (recherche des documents pertinents)
  - Prompt engineering (augmentation du contexte)

---
