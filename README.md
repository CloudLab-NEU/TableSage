# TableSage

> TableSage is an intelligent table-based question answering system built on multi-dimensional knowledge bases. It leverages similar question retrieval and hierarchical answering strategies to provide accurate and interpretable responses for tabular data queries.

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- pip or conda

### Installation

1. **Install Dependencies**

```bash
cd app
pip install -r requirements.txt
```

2. **Environment Configuration**

```bash
# Create .env file and configure the following variables
cp .env.example .env
```

Configure the following in your `.env` file:

```env
# OpenAI API Configuration
OPENAI_API_KEY=your_openai_api_key
OPENAI_API_BASE=your_api_base_url
LLM_MODEL=your_chosen_model
DB_HOST=your_db_ip
DB_PORT=your_port
DB_USER=db_user
DB_PASSWORD=db_password
```

**MCP Service Configuration**

This project utilizes MCP (Model Context Protocol) services for statistical chart generation. For detailed information, please refer to: https://github.com/antvis/mcp-server-chart

You can deploy and connect through cloud services like ModelScope Community, or deploy locally and configure the service endpoint in `./mcp_client/mcp.json`.

3. **Spacy Language Model Download**

```bash
python -m spacy download en_core_web_sm

# If you encounter network issues, please refer to:
# https://github.com/explosion/spacy-models/releases/tag/en_core_web_sm-3.8.0
# Install via pip install method
```

### Table Header Type Prediction Model

We have constructed a small-scale dataset based on raw data and trained a table header type prediction model.

The model weights can be downloaded from the following link:
https://drive.google.com/drive/folders/1Hgu8Utm_YlQGyzT_ucMTHa40XxQiipbE?usp=sharing

Place the downloaded weight files in the `./table_structure_type_model` directory, then start the backend service:

```bash
python inference.py
```

### Database Configuration

The system uses MongoDB to construct multi-dimensional knowledge bases, including learning records, error records, and teaching records databases.

For implementation details, please refer to `./db/db_manager.py`:

```python
# Initialize collections
self.knowledge_db = self.db["MutiKnowledgeDataBase"]
self.learning_records = self.db["LearningRecordsDataBase"]
self.teaching_records = self.db["GuidanceRecordsDataBase"] 
self.error_records = self.db["ErrorRecordsDataBase"]
```

### Running the Services

**Start Backend Service:**

```bash
# Start FastAPI service
python main.py

# Or use uvicorn
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

After starting the service, visit http://localhost:8000/docs to view the API documentation.

**Start Frontend Service:**

```bash
# Install dependencies and start frontend service
npm install 
npm run build
npm run dev
```

Alternatively, you can use our pre-packaged executable file for local installation.

## 🏗️ Project Architecture

```
TableSage/
├── app/                          # Main application directory
│   ├── main.py                   # FastAPI application entry point
│   ├── requirements.txt          # Dependencies file
│   ├── backend_api/              # API routing modules
│   │   ├── core_processor_api.py # Core Q&A interface
│   │   ├── muti_knowledge_visual_api.py # Knowledge base visualization
│   │   ├── any_record_visual_api.py     # Record statistics
│   │   ├── file_service_api.py   # File services
│   │   └── config_api.py         # Configuration management
│   ├── core_progress/            # Core processing logic
│   │   ├── tablesage_processor.py # Main processor
│   │   ├── answer_processor.py   # Answer processor
│   │   ├── guidance_processor.py # Guidance processor
│   │   ├── final_processor.py    # Final answer processor
│   │   └── search_similar_question.py # Similar question retrieval
│   ├── mcp_client/               # MCP client
│   ├── openai_api/               # OpenAI API wrapper
│   ├── db/                       # Database management
│   ├── document_general/         # Document generation
│   └── utils/                    # Utility functions
```


