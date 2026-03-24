# TableSage

> TableSage is a next-generation **multi-agent tabular data assistant**. It transcends traditional table QA by employing a ReAct-based reasoning loop, semantic RAG caching, and automated visualization to provide high-precision, interpretable insights for complex tabular datasets.

## 🤖 Agentic Workflow (Core System)

TableSage has evolved from a linear processor to a collaborative multi-agent ecosystem:

1.  **Router Agent**: Performs zero-shot intent classification. It distinguishes between new data analysis requests and direct visualization/reporting on existing context, optimizing the execution path.
2.  **TableSage Agent**: The "Brain" of the system. It employs a **ReAct (Reasoning + Acting)** strategy:
    *   **Search**: Mandated `search_knowledge` calls to retrieve patterns and 'Lessons Learned' from the MongoDB knowledge base.
    *   **Think**: Explicit reflection steps to assess context sufficiency and calculate confidence scores.
    *   **Practice**: Targeted `practice_question` execution to verify logic on similar samples before answering the user.
3.  **Visualization Agent**: Selects optimal chart types and generates professional-grade Word/PDF reports based on the analytical findings.

## 🛠️ Key Features

- **Semantic RAG Cache**: Identical question/table patterns are served from a high-confidence cache, reducing latency to milliseconds.
- **Mandatory Pattern Verification**: Enforces a "verification first" culture where the agent must check the knowledge base for previous mistakes or successes.
- **Unified Chat Bridge**: A seamless SSE (Server-Sent Events) interface that streams step-by-step reasoning process directly to the frontend.

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- Node.js 16+
- MongoDB 5.0+

### Installation & Configuration

1. **Install Dependencies**
   ```bash
   cd app && pip install -r requirements.txt
   cd ../web_vue && npm install
   ```

2. **Environment Configuration**
   Create `app/.env` and configure the following:
   ```env
   # API Configuration
   OPENAI_API_KEY=your_api_key
   OPENAI_API_BASE=your_api_base_url
   LLM_MODEL=gpt-4o  # or your chosen model
   EMBEDDING_MODEL=text-embedding-3-small  # Required for RAG
   
   # Database Configuration
   DB_HOST=your_db_ip
   DB_PORT=27017
   DB_USER=db_user
   DB_PASSWORD=db_password
   ```

3. **Start the Services**
   ```bash
   # Backend
   python main.py
   
   # Frontend
   npm run dev
   ```

## 🚜 Services & Models

### MCP Service Configuration
This project utilizes MCP (Model Context Protocol) services for statistical chart generation. For detailed information, please refer to: https://github.com/antvis/mcp-server-chart

You can deploy and connect through cloud services like ModelScope Community, or deploy locally and configure the service endpoint in `./mcp_client/mcp.json`.

### Spacy Language Model Download
```bash
python -m spacy download en_core_web_sm
```

### Table Header Type Prediction Model
We have constructed a small-scale dataset based on raw data and trained a table header type prediction model.
Model weights can be downloaded from: [Google Drive Link](https://drive.google.com/drive/folders/1Hgu8Utm_YlQGyzT_ucMTHa40XxQiipbE?usp=sharing)

Place the downloaded weight files in the `./table_structure_type_model` directory, then start the inference service:
```bash
python inference.py
```

## 🏗️ Project Architecture

```text
TableSage/
├── app/                          # Backend (FastAPI + Agent System)
│   ├── agent/                    # ✨ Agent Core (Router, TableSage, Viz)
│   ├── backend_api/              # Unified API Layer
│   ├── core_progress/            # Underlying RAG & Analysis Logic
│   ├── db/                       # MongoDB Knowledge Base Management
│   └── mcp_client/               # Model Context Protocol for Visuals
├── web_vue/                      # Frontend (Vue 3 + Vite + Tailwind)
└── table_structure_type_model/   # BERT-based Header Type Classifier
```

## 🗄️ Database Configuration

The system uses MongoDB to construct multi-dimensional knowledge bases.
For implementation details, please refer to `./db/db_manager.py`:

```python
# Initialize collections
self.knowledge_db = self.db["MutiKnowledgeDataBase"]
self.learning_records = self.db["LearningRecordsDataBase"]
self.teaching_records = self.db["GuidanceRecordsDataBase"] 
self.error_records = self.db["ErrorRecordsDataBase"]
```
