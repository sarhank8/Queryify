import os
import sys
import sqlite3
import re
import warnings
import pandas as pd
import streamlit as st

warnings.filterwarnings("ignore")

from dotenv import load_dotenv
import google.generativeai as genai

# Load environment variables
load_dotenv()

# Page configuration
st.set_page_config(
    page_title="SQL Data Assistant",
    layout="wide"
)

# Clean, professional light theme styling
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    /* Global Light Theme */
    .stApp {
        background-color: #ffffff;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        color: #0f172a;
    }
    
    [data-testid="stSidebar"] {
        background-color: #f8fafc;
        border-right: 1px solid #e2e8f0;
    }
    
    .app-title {
        font-size: 1.85rem;
        font-weight: 700;
        letter-spacing: -0.025em;
        color: #0f172a;
        margin-bottom: 0.25rem;
    }
    
    .app-subtitle {
        font-size: 0.95rem;
        color: #64748b;
        margin-bottom: 1.75rem;
    }
    
    .section-label {
        font-size: 0.8rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: #64748b;
        margin-top: 1.25rem;
        margin-bottom: 0.5rem;
    }
    
    /* Input & Search Box - Gray */
    .stTextInput > div > div > input {
        background-color: #f1f5f9;
        color: #0f172a;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 0.65rem 0.9rem;
        font-size: 0.95rem;
    }
    
    .stTextInput > div > div > input:focus {
        background-color: #ffffff;
        border-color: #94a3b8;
        box-shadow: 0 0 0 1px #94a3b8;
    }
    
    .stButton > button {
        background-color: #0f172a;
        color: #ffffff;
        font-weight: 500;
        border-radius: 6px;
        border: none;
        padding: 0.55rem 1.4rem;
        transition: background-color 0.15s ease;
    }
    
    .stButton > button:hover {
        background-color: #1e293b;
        color: #ffffff;
    }
    
    /* Expander Box - Gray */
    [data-testid="stExpander"] {
        background-color: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
    }
    
    [data-testid="stExpander"] details summary {
        background-color: #f8fafc;
        border-radius: 8px;
    }
    
    /* Code Blocks & Pre - Gray */
    .stCodeBlock, pre, code {
        background-color: #f1f5f9 !important;
        border: 1px solid #e2e8f0 !important;
        border-radius: 6px !important;
        color: #0f172a !important;
    }
    
    /* File Uploader Container - Gray */
    [data-testid="stFileUploader"] section {
        background-color: #f1f5f9 !important;
        border: 1px dashed #cbd5e1 !important;
        border-radius: 8px !important;
    }
    
    /* Metric Card Boxes - Gray */
    [data-testid="stMetric"] {
        background-color: #f1f5f9;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 12px 16px;
    }
    
    [data-testid="stMetricValue"] {
        font-weight: 600;
        color: #0f172a;
    }
    
    [data-testid="stMetricLabel"] {
        color: #64748b;
        font-size: 0.85rem;
    }
</style>
""", unsafe_allow_html=True)

# Helper function to sanitize column names for SQL
def sanitize_columns(df):
    clean_cols = []
    for col in df.columns:
        c = re.sub(r'[^\w\s]', '', str(col)).strip()
        c = re.sub(r'\s+', '_', c)
        if not c or c[0].isdigit():
            c = f"col_{c}"
        clean_cols.append(c)
    df.columns = clean_cols
    return df

# Create dynamic prompt based on dataframe schema
def build_prompt_from_df(df, table_name="DATASET"):
    columns_info = []
    for col, dtype in zip(df.columns, df.dtypes):
        columns_info.append(f"- {col} ({dtype})")
    
    schema_str = "\n".join(columns_info)
    sample_data_str = df.head(3).to_string(index=False)
    
    prompt = f"""
You are a precise SQL translator for SQLite databases.
Your task is to convert natural language questions into valid SQLite SQL queries for the table named `{table_name}`.

Table Schema:
{schema_str}

Sample Rows:
{sample_data_str}

Rules:
1. Only answer questions that can be answered using `{table_name}` and its existing columns: {', '.join(df.columns)}.
2. Out-of-Context Rule: If the question:
   - Asks about general knowledge, external facts, weather, coding tutorials, recipes, or topics unrelated to the dataset
   - References columns or entities not in this table
   - Cannot be answered using this dataset
   You MUST reply ONLY with:
   OUT_OF_CONTEXT: <brief reason>
3. If the question is valid and relevant:
   - Return ONLY the executable SQLite SQL statement.
   - Do not include markdown code block formatting (no ``` or ```sql).
   - Use SQLite syntax.
"""
    return prompt

# Configure Gemini with environment variable
api_key = os.getenv("GOOGLE_API_KEY")
if api_key:
    genai.configure(api_key=api_key)

def get_gemini_response(question, system_prompt):
    model = genai.GenerativeModel('gemini-3.6-flash')
    response = model.generate_content([system_prompt, question])
    return response.text.strip()

def clean_sql_query(query_text):
    query = re.sub(r'```sql\s*', '', query_text, flags=re.IGNORECASE)
    query = re.sub(r'```\s*', '', query)
    return query.strip()

def execute_sql_query(conn, sql):
    cur = conn.cursor()
    cur.execute(sql)
    rows = cur.fetchall()
    columns = [col[0] for col in cur.description] if cur.description else []
    return rows, columns

# Sidebar
with st.sidebar:
    st.markdown("### Data Source")
    uploaded_file = st.file_uploader("Upload CSV Dataset", type=["csv"], label_visibility="collapsed")
    
    if not uploaded_file:
        st.caption("Active dataset: Default Student Database")

# App Header
st.markdown('<div class="app-title">Data Query Engine</div>', unsafe_allow_html=True)
st.markdown('<div class="app-subtitle">Query structured tabular data using natural language.</div>', unsafe_allow_html=True)

# Load data into DataFrame and SQLite connection
df = None
table_name = "DATASET"
conn = sqlite3.connect(":memory:")

if uploaded_file is not None:
    try:
        df = pd.read_csv(uploaded_file)
        df = sanitize_columns(df)
        table_name = "DATASET"
        df.to_sql(table_name, conn, index=False, if_exists="replace")
    except Exception as e:
        st.error(f"Error loading CSV: {e}")
else:
    if not os.path.exists("student.db"):
        import subprocess
        subprocess.run([sys.executable, "sqlite.py"])
    try:
        sample_conn = sqlite3.connect("student.db")
        df = pd.read_sql_query("SELECT * FROM STUDENT", sample_conn)
        sample_conn.close()
        table_name = "STUDENT"
        df.to_sql(table_name, conn, index=False, if_exists="replace")
    except Exception as e:
        st.error(f"Error loading default database: {e}")

if df is not None:
    # Dataset Schema Overview
    with st.expander("Dataset Details & Preview", expanded=False):
        c1, c2, c3 = st.columns(3)
        c1.metric("Rows", f"{len(df):,}")
        c2.metric("Columns", f"{len(df.columns)}")
        c3.metric("Table", table_name)
        
        st.markdown("**Columns:** " + " ".join([f"`{c}`" for c in df.columns]))
        st.dataframe(df.head(10), width="stretch")

    system_prompt = build_prompt_from_df(df, table_name=table_name)

    # Question Input
    user_question = st.text_input(
        "Ask a question about this data:",
        placeholder=f"e.g., What is the average {df.columns[-1]} by {df.columns[0]}?",
        key="query_input"
    )

    if st.button("Run Query", type="primary"):
        if not api_key:
            st.error("GOOGLE_API_KEY environment variable is missing or invalid.")
        elif not user_question.strip():
            st.warning("Please enter a question.")
        else:
            with st.spinner("Processing query..."):
                try:
                    raw_response = get_gemini_response(user_question, system_prompt)
                    
                    if raw_response.startswith("OUT_OF_CONTEXT") or "OUT_OF_CONTEXT:" in raw_response:
                        reason = raw_response.replace("OUT_OF_CONTEXT:", "").replace("OUT_OF_CONTEXT", "").strip()
                        st.warning(f"Out of context: {reason if reason else 'This query cannot be resolved using the current dataset.'}")
                        st.caption(f"Valid columns: {', '.join(df.columns)}")
                    else:
                        sql_query = clean_sql_query(raw_response)
                        
                        st.markdown('<div class="section-label">Generated SQL</div>', unsafe_allow_html=True)
                        st.code(sql_query, language="sql")
                        
                        rows, columns = execute_sql_query(conn, sql_query)
                        
                        st.markdown('<div class="section-label">Query Results</div>', unsafe_allow_html=True)
                        if rows:
                            if columns:
                                result_df = pd.DataFrame(rows, columns=columns)
                                st.dataframe(result_df, width="stretch")
                                st.caption(f"{len(result_df)} row(s) returned.")
                            else:
                                for r in rows:
                                    st.write(r)
                        else:
                            st.info("Query executed successfully, returning 0 records.")
                            
                except Exception as e:
                    st.error(f"Execution Error: {e}")
