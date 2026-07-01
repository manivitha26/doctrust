# DocuTrust

DocuTrust is an Enterprise Advanced RAG (Retrieval-Augmented Generation) Platform with Automated Self-Correction.

## Overview

Basic AI Document search portals suffer from heavy "hallucinations" and provide insecure or completely unsourced text outputs when parsing complex corporate policy packets.

DocuTrust solves this via a self-correcting RAG platform that cross-references vector data chunks, validates retrieval quality before displaying text, and outputs strict citations.

## Features

- **Corrective RAG (CRAG)**: Built with LangGraph. Includes a grading agent that checks document relevance using a local cross-encoder (`ms-marco-MiniLM`).
- **Web Search Fallback**: If retrieved documents are irrelevant, the agent automatically rewrites the query and searches DuckDuckGo.
- **Strict Citations**: Answers are generated with enforced citations linking back to specific chunks/pages.
- **Local LLM Support**: Toggle between OpenAI and local Ollama instances (`llama3`, `nomic-embed-text`) for complete data privacy.
- **MongoDB Atlas Vector Search**: Real-time semantic similarity search.
- **Premium Frontend UI**: A sleek HTML/CSS/JS split-pane interface with glassmorphism, dynamic animations, chat persistence, and secure authentication.

## Getting Started

### Prerequisites
- Python 3.9+
- MongoDB Atlas account (or local MongoDB with vector capabilities)
- (Optional) Ollama installed locally if you want to run offline.

### Installation

1. Navigate to the `backend` directory:
   ```bash
   cd backend
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Configure the environment variables in `backend/.env`.

### Running the App

1. **Start the Backend**:
   ```bash
   uvicorn main:app --reload
   ```
2. **Start the Frontend**:
   Open `frontend/index.html` in your browser, or serve it:
   ```bash
   cd frontend
   python -m http.server 8080
   ```

### Testing
Run the automated test suite from the root directory:
```bash
pytest backend/test_main.py
```
