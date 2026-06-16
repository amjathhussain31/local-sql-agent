# 📊 SQL Agent

An AI-powered **Natural Language to SQL Analytics Agent** that enables users to query databases using plain English, generate insights, visualize results, and interact conversationally with their data.

Built with **LangChain**, **Google Gemini**, **FAISS**, **SQLAlchemy**, and **Streamlit**, the project combines Agentic AI, Retrieval-Augmented Generation (RAG), memory systems, guardrails, and observability into a unified analytics platform.

---

## 🚀 Features

### 💬 Natural Language to SQL

Ask questions in plain English and automatically generate SQL queries.

**Example:**

```text
What were the top 5 products by revenue last month?
```

The agent converts the request into SQL, executes it, and returns results.

---

### 🤖 ReAct AI Agent

The system uses a LangChain ReAct Agent that can:

* Understand user intent
* Retrieve schema information
* Access business glossary definitions
* Generate SQL queries
* Execute queries
* Generate insights
* Create charts

---

### 🔍 Retrieval-Augmented Generation (RAG)

The agent uses FAISS vector search and Sentence Transformers to retrieve:

* Business glossary definitions
* Database schema documentation
* Domain-specific context

This helps improve SQL accuracy and business understanding.

---

### 🧠 Conversational Memory

#### Short-Term Memory

Maintains recent conversation context for follow-up questions.

#### Long-Term Memory

Stores previous interactions to improve user experience and query continuity.

Example:

```text
User: Show sales by region.
User: Which region performed best?
```

The agent understands the reference without needing the original query again.

---

### 🛡️ Guardrails

Input and output safety mechanisms help:

* Block harmful queries
* Prevent unsafe database operations
* Improve response quality
* Enforce analytical boundaries

---

### 📈 Automated Visualization

The agent can automatically generate charts from query results:

* Bar Charts
* Line Charts
* Pie Charts
* Trend Visualizations

---

### 💡 AI-Generated Insights

Beyond raw SQL results, the agent generates business insights such as:

* Growth trends
* Performance summaries
* Comparative analysis
* Key observations

---

### 📡 Observability

Integrated tracing and monitoring support through Langfuse to help analyze:

* Agent reasoning
* Tool usage
* Execution flow
* Performance metrics

---

## 🏗️ Architecture

```text
User
 │
 ▼
Streamlit Interface
 │
 ▼
LangChain ReAct Agent
 │
 ├── Schema Fetcher
 ├── RAG Retriever
 ├── SQL Executor
 ├── Insight Generator
 └── Chart Builder
 │
 ▼
Google Gemini
 │
 ▼
Database
(SQLite / PostgreSQL / MySQL)
```

---

## 📂 Project Structure

```text
local-sql-agent/
│
├── app.py
├── config.py
├── requirements.txt
│
├── agent/
│   ├── react_agent.py
│   └── error_handler.py
│
├── rag/
│   ├── embedder.py
│   ├── ingestor.py
│   └── retriever.py
│
├── guardrails/
│   ├── input_rails.py
│   ├── output_rails.py
│   └── pipeline.py
│
├── memory/
│   ├── short_term.py
│   └── long_term.py
│
├── tools/
│   ├── sql_executor.py
│   ├── schema_fetcher.py
│   ├── chart_builder.py
│   └── insight_generator.py
│
├── observability/
│   └── langfuse_client.py
│
└── data/
    ├── docs/
    │   ├── business_glossary.txt
    │   └── schema_docs.txt
    └── faiss_index/
```

---

## 🛠️ Tech Stack

| Category        | Technology              |
| --------------- | ----------------------- |
| Language        | Python                  |
| LLM             | Google Gemini           |
| Agent Framework | LangChain ReAct         |
| Vector Database | FAISS                   |
| Embeddings      | Sentence Transformers   |
| Database Layer  | SQLAlchemy              |
| Frontend        | Streamlit               |
| Memory          | LangChain Memory        |
| RAG             | FAISS + Semantic Search |
| Observability   | Langfuse                |
| Analytics       | Pandas                  |

---

## ⚙️ Installation

### 1. Clone Repository

```bash
git clone https://github.com/amjathhussain31/local-sql-agent.git

cd local-sql-agent
```

---

### 2. Create Virtual Environment

```bash
python -m venv venv
```

Activate:

**Windows**

```bash
venv\Scripts\activate
```

**Linux / macOS**

```bash
source venv/bin/activate
```

---

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

---

### 4. Configure Environment Variables

Create a `.env` file:

```env
GEMINI_API_KEY=your_api_key
GEMINI_MODEL=gemini-1.5-pro
```

---

### 5. Run the Application

```bash
streamlit run app.py
```

---

## 📊 Supported Databases

The agent is designed to work with:

* SQLite
* PostgreSQL
* MySQL

---

## 🔄 Workflow

```text
User Query
     │
     ▼
Input Guardrails
     │
     ▼
ReAct Agent
     │
     ├── Schema Retrieval
     ├── Business Context Retrieval
     ├── SQL Generation
     ├── SQL Execution
     ├── Insight Generation
     └── Chart Creation
     │
     ▼
Output Guardrails
     │
     ▼
Final Response
```

---

## 📸 Example Queries

```text
Show total revenue by region.
```

```text
Which product category generated the highest profit?
```

```text
Display monthly sales trends for the last year.
```

```text
Compare customer growth between 2023 and 2024.
```

---

## 🎯 Key Learning Outcomes

This project demonstrates:

* Agentic AI Development
* Natural Language to SQL Systems
* Retrieval-Augmented Generation (RAG)
* LangChain ReAct Agents
* Vector Search with FAISS
* Conversational Memory
* AI Guardrails
* Database Analytics
* Data Visualization
* LLM-powered Business Intelligence

---

## 🔮 Future Enhancements

* Multi-agent architecture
* Voice-based querying
* Enterprise database connectors
* Dashboard export functionality
* Role-based access control
* Real-time data streaming support
* Cloud deployment on AWS/Azure/GCP

---

## 👨‍💻 Author

**Amjath Hussain**

AI Engineer | Generative AI Developer | Data Analytics Enthusiast

---
