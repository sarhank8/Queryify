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
    columns_info = [f"- `{col}` ({dtype})" for col, dtype in zip(df.columns, df.dtypes)]
    schema_str = "\n".join(columns_info)
    sample_data_str = df.head(3).to_string(index=False)
    
    prompt = f"""
You are an expert SQL translator and database assistant.
Your task is to convert English questions into valid SQLite SQL queries for table `{table_name}`.

### Database Schema for `{table_name}`:
{schema_str}

### Sample Rows:
{sample_data_str}

### CRITICAL RULES:
1. ONLY answer questions that can be directly answered using the table `{table_name}` and its provided columns ({', '.join(df.columns)}).
2. OUT-OF-CONTEXT GUARDRAIL: If the user's question:
   - Asks about general knowledge, recipes, weather, coding, or topics outside this dataset
   - References entities, columns, or attributes NOT present in the schema
   - Cannot be answered using the data in `{table_name}`
   THEN you MUST respond ONLY with:
   OUT_OF_CONTEXT: <brief explanation of why this question cannot be answered from the dataset>
3. If the question IS relevant to the dataset:
   - Return ONLY the executable SQLite SQL query.
   - Do NOT include any explanations, greetings, or markdown code block markers (like ```sql or ```).
   - Use SQLite-compatible syntax.
   - Ensure table name `{table_name}` and exact column names are used.
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
