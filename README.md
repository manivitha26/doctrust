# 🛡️ DocuTrust: Enterprise Advanced RAG Platform

DocuTrust is a production-grade **Corrective Retrieval-Augmented Generation (CRAG)** platform designed for secure, self-correcting document question-answering with strict citations, multi-tenant workspace isolation, and real-time streaming feedback.

---

## 📊 System Architecture & Data Flow

### 1. High-Level Architecture Diagram
```mermaid
graph TD
    User([Browser Client]) <-->|Static Site| Vercel[Vercel Frontend]
    User <-->|SSE / REST| Backend[FastAPI Backend Gateway]
    
    subgraph Backend Services
        Backend <--> Auth[Auth & Workspaces]
        Backend <--> DocService[Document Ingestion & OCR]
        Backend <--> RAGService[RAG Coordination Service]
    end
    
    subgraph AI LangGraph Engine
        RAGService <--> LangGraph[CRAG StateGraph Execution]
        LangGraph <--> Grader[Cross-Encoder Grader]
        LangGraph <--> VectorDB[(Vector DB / In-Memory Store)]
        LangGraph <--> WebSearch[DuckDuckGo Web Search Fallback]
        LangGraph <--> LLM[Local Ollama / OpenAI GPT]
    end
```

---

### 2. Corrective RAG (CRAG) Pipeline Flowchart
```mermaid
flowchart TD
    Start([User Chat Question]) --> Retrieve[Retrieve Matches from Selected PDFs]
    Retrieve --> Grade{Cross-Encoder Grading}
    
    Grade -->|Relevance >= 0.8| Generate[Generate Response from Citations]
    Grade -->|Relevance < 0.8| Rewrite[Rewrite Question Query]
    
    Rewrite --> Search[Execute DuckDuckGo Web Search]
    Search --> Combine[Merge Web Search Context]
    Combine --> Generate
    
    Generate --> Confidence[Calculate Confidence Score]
    Confidence --> Stream[Stream SSE Tokens & Metadata to UI]
    Stream --> End([Display Cited Answer in Chat])
```

---

## 🌟 Key Features

*   **🛡️ Multi-User Workspaces:** Toggle between segregated virtual directories (e.g. `Finance`, `Legal`, `HR`) to isolate index libraries, document queries, and chat history.
*   **📑 Multi-PDF Context Filters:** Checkbox filters next to your indexed file library let you restrict Q&A context to specific documents.
*   **📷 Scanned PDF OCR Fallback:** Automatically detects non-text PDF pages and activates a simulated OCR extraction layer to recover data without crashing.
*   **🌊 Token-by-Token Streaming:** Streams assistant text word-by-word via Server-Sent Events (SSE) for a premium ChatGPT-like interface.
*   **🎯 Answer Confidence Gauge:** Dynamically calculates relevance metrics and prints a color-coded confidence score (Green/Orange/Red) next to the response.
*   **🔍 Interactive Source Preview:** Click citation tags `[Source: document, Page X]` to open a sliding inspector side-drawer displaying raw context chunks with matching keywords highlighted.
*   **💬 Chat History Sessions:** Collapsible left panel manages multiple chat sessions backed by local storage.
*   **👍 User Feedback Collection:** Thumbs up/down icons record helpfulness metrics via a backend analytics endpoint.
*   **📥 Chat Export to PDF:** Formatted CSS media rules render a clean, print-ready document log on PDF export.
*   **⚙️ Offline Ollama Option:** Switch between OpenAI and local Ollama instances (`llama3` / `nomic-embed-text`) in one `.env` setting.

---

## 🚀 Getting Started

### 1. Setup Environment
Rename or edit `backend/.env` with your active variables:
```env
OPENAI_API_KEY="your_openai_key_here"
USE_OLLAMA="false"

# MongoDB Vector Settings (Optional)
MONGODB_URI="your_mongodb_atlas_uri_here"
MONGODB_DB_NAME="docutrust_db"
MONGODB_COLLECTION="documents"
```

### 2. Launch Platform (Local)
Run the startup script in PowerShell:
```powershell
.\start.ps1
```
*   **Frontend Dashboard:** <http://127.0.0.1:8080>
*   **Backend FastAPI Server:** <http://127.0.0.1:8005>

---

## 🌐 Deployments
*   **GitHub Repository:** [manivitha26/doctrust](https://github.com/manivitha26/doctrust)
*   **Vercel Live Production URL:** [DocuTrust Frontend](https://frontend-rouge-eight-rvcpn8bwmz.vercel.app)
