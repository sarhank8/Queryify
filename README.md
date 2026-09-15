# Queryify 🔍

Queryify is an AI-powered text-to-SQL data assistant built with Python, Streamlit, and Google Gemini. It allows users to query SQL databases and custom CSV datasets using natural language questions, with built-in contextual guardrails to prevent hallucinated or out-of-scope responses.

---

## Features

- **Natural Language to SQL**: Converts plain English questions into valid, optimized SQLite queries using Google Gemini (`gemini-3.6-flash`).
- **Dynamic CSV Dataset Upload**: Upload any CSV dataset on the fly; Queryify automatically parses the schema and enables natural language querying.
- **Out-of-Context Guardrails**: Prevents hallucinations by identifying and refusing questions that fall outside the scope of the active dataset.
- **Interactive Web Interface**: Minimalist, clean light-themed UI built with Streamlit.
- **CLI Mode**: Run queries directly in the terminal via `python sql.py`.

---

## Getting Started

### Prerequisites

- Python 3.9 or higher
- Google Gemini API Key ([Get one here](https://aistudio.google.com/))

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/sarhank8/Queryify.git
   cd Queryify
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure API Key:**
   Create a `.env` file in the root directory:
   ```env
   GOOGLE_API_KEY=your_gemini_api_key_here
   ```

4. **Initialize sample database (optional):**
   ```bash
   python sqlite.py
   ```

---

## Usage

### Web Application (Streamlit)
```bash
streamlit run app.py
```
Open your browser at `http://localhost:8501`.

### Command Line Interface (CLI)
```bash
# Query default student database
python sql.py

# Query a custom CSV file
python sql.py path/to/dataset.csv
```

---

## Project Structure

```
Queryify/
├── .streamlit/
│   └── config.toml       # Streamlit theme configuration
├── app.py                # Streamlit web application
├── sql.py                # Terminal / CLI interactive interface
├── sqlite.py             # Sample SQLite database creator
├── requirements.txt      # Python dependencies
├── .env.example          # Environment variable template
├── .gitignore            # Excluded sensitive/unnecessary files
└── README.md             # Project documentation
```

---

## License
MIT License
