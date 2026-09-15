import os
import sys
import sqlite3
import re
import warnings
import pandas as pd

# Ensure immediate console output flushing
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(line_buffering=True)

# Suppress deprecation warnings
warnings.filterwarnings("ignore")

from dotenv import load_dotenv
import google.generativeai as genai

# Load environment variables
load_dotenv()

api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    raise ValueError("GOOGLE_API_KEY is missing! Please set it in your .env file or environment.")

genai.configure(api_key=api_key)

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

def build_prompt_from_df(df, table_name="DATASET"):
    columns_info = []
    for col, dtype in zip(df.columns, df.dtypes):
        sample_vals = df[col].dropna().unique()[:2].tolist()
        sample_vals_str = ", ".join([repr(v) for v in sample_vals])
        columns_info.append(f"- {col} ({dtype}): [{sample_vals_str}]")
    
    schema_str = "\n".join(columns_info)
    sample_data_str = df.head(3).to_string(index=False)
    
    prompt = f"""
Act as a Principal Database Engineer and SQL specialist. Generate a bulletproof, optimized SQL query for the scenario below.

### 1. Target Engine
- Dialect: SQLite

### 2. Schema Definition & Sample Data
Table: {table_name}
{schema_str}

Sample Rows:
{sample_data_str}

### 3. Objective & Output Requirements
- Goal: Accurately translate the user's natural language question into an executable SQL query.
- Target Columns: Select only the required columns or appropriate aggregations matching the question.
- Granularity: Ensure output rows match the required aggregation level (e.g. 1 row per group/category).

### 4. CRITICAL CONSTRAINT: OUT-OF-CONTEXT QUESTIONS ARE STRICTLY NOT ALLOWED
- You are ONLY permitted to answer questions that directly query table `{table_name}` and its existing columns: {', '.join(df.columns)}.
- If the user question asks about ANY external topic (general knowledge, current events, programming, recipes, weather, personal advice) OR refers to non-existent columns/entities, you MUST REFUSE and reply ONLY with:
  OUT_OF_CONTEXT: <brief reason explaining why this question is outside the dataset scope>
- Do NOT answer or attempt to generate SQL for out-of-context queries.

### 5. Technical Constraints
- Step-by-step logic: Structure complex logic using readable Common Table Expressions (WITH clauses / CTEs) rather than deeply nested subqueries.
- Safe Math: Use NULLIF or CASE statements to prevent division-by-zero errors on calculated ratios/percentages.
- Filter Discipline: Base filters strictly on the column values and formats demonstrated in the sample data (e.g., casing, exact string matching).
- Window Functions: Keep window functions (RANK, DENSE_RANK, ROW_NUMBER, LAG/LEAD) isolated in CTEs if they need to be filtered by WHERE clauses.

### 6. Execution & Output Format
- Return ONLY the raw executable SQLite SQL query without markdown code blocks, backticks (no ``` or ```sql), or explanations (unless OUT_OF_CONTEXT).
"""
    return prompt

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

def load_data(csv_path=None):
    conn = sqlite3.connect(":memory:")
    if csv_path and os.path.exists(csv_path):
        print(f"[*] Loading CSV from: {csv_path}")
        df = pd.read_csv(csv_path)
        df = sanitize_columns(df)
        table_name = "UPLOADED_DATA"
    else:
        if not os.path.exists("student.db"):
            import subprocess
            subprocess.run([sys.executable, "sqlite.py"])
        sample_conn = sqlite3.connect("student.db")
        df = pd.read_sql_query("SELECT * FROM STUDENT", sample_conn)
        sample_conn.close()
        table_name = "STUDENT"

    df.to_sql(table_name, conn, index=False, if_exists="replace")
    return conn, df, table_name

def main():
    csv_path = sys.argv[1] if len(sys.argv) > 1 else None
    conn, df, table_name = load_data(csv_path)
    system_prompt = build_prompt_from_df(df, table_name)

    print("=" * 65)
    print(f"  AI SQL & CSV Assistant (Table: {table_name})")
    print(f"  Columns: {', '.join(df.columns)}")
    print(f"  Total records: {len(df)}")
    print("  Type your question or 'exit'/'quit' to quit.")
    print("=" * 65)

    while True:
        try:
            print()
            question = input("Ask a question: ").strip()
            if not question:
                continue
            if question.lower() in ("exit", "quit", "q"):
                print("Goodbye!")
                break

            print("\nGenerating SQL query with Gemini...")
            raw_response = get_gemini_response(question, system_prompt)
            
            if raw_response.startswith("OUT_OF_CONTEXT") or "OUT_OF_CONTEXT:" in raw_response:
                reason = raw_response.replace("OUT_OF_CONTEXT:", "").replace("OUT_OF_CONTEXT", "").strip()
                print(f"\n[!] Out of Context: {reason}")
                print(f"    Available columns are: {', '.join(df.columns)}")
                continue

            sql_query = clean_sql_query(raw_response)
            print(f"\n[Generated SQL]: {sql_query}")
            
            rows, columns = execute_sql_query(conn, sql_query)
            
            print("\n[Query Results]:")
            if not rows:
                print("  No records found matching query criteria.")
            else:
                if columns:
                    header = " | ".join(f"{col:<15}" for col in columns)
                    print("  " + header)
                    print("  " + "-" * len(header))
                for row in rows:
                    row_str = " | ".join(f"{str(val):<15}" for val in row)
                    print("  " + row_str)

        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"\n[!] Error: {e}")

if __name__ == "__main__":
    main()
