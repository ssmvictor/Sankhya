import oracledb
import os
import getpass
from pathlib import Path

# Tentar carregar variáveis de ambiente de um arquivo .env
def load_env_file():
    """Carrega variáveis de ambiente de um arquivo .env se existir"""
    env_file = Path('.env')
    if env_file.exists():
        print("Carregando configurações do arquivo .env...")
        with open(env_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key] = value

# Carregar configurações do .env
load_env_file()

# --- Configuração da Conexão ---
# Recomenda-se usar variáveis de ambiente para segurança
db_user = os.environ.get("DB_USER")
db_host = os.environ.get("DB_HOST")
db_port = os.environ.get("DB_PORT", "1521")
db_service = os.environ.get("DB_SERVICE", "prodpdb")
db_password = os.environ.get("DB_PASSWORD")

if not db_password:
    db_password = getpass.getpass(f"Enter password for {db_user}: ")

# Configurar o modo thin para evitar problemas de bequeath
oracledb.init_oracle_client()

# --- Lógica de Extração do Schema ---
def extract_sankhya_schema(connection):
    """
    Extrai o schema de tabelas do Sankhya (TGF, TSI, TCB) e formata em Markdown.
    """
    schema_markdown = "# Dicionário de Dados Sankhya\n\n"
    cursor = connection.cursor()

    # 1. Obter a lista de tabelas relevantes (ex: TGF, TSI)
    print("Fetching tables...")
    cursor.execute("""
        SELECT NOMETAB, DESCRTAB
        FROM TDDTAB
        WHERE NOMETAB LIKE 'TGF%' OR NOMETAB LIKE 'TSI%' OR NOMETAB LIKE 'TCB%'
        ORDER BY NOMETAB
    """)
    tables = cursor.fetchall()

    for table_name, table_desc in tables:
        print(f"Processing table: {table_name}")
        schema_markdown += f"## Tabela: `{table_name}`\n\n"
        if table_desc:
            schema_markdown += f"**Descrição:** {table_desc}\n\n"
        
        schema_markdown += "| Coluna | Descrição | Tipo de Dado |\n"
        schema_markdown += "|---|---|---|\n"

        # 2. Para cada tabela, obter suas colunas
        cursor.execute("""
            SELECT NOMECAMPO, DESCRCAMPO, TIPCAMPO, TAMANHO
            FROM TDDCAM
            WHERE NOMETAB = :table_name
            ORDER BY ORDEM
        """, table_name=table_name)
        
        columns = cursor.fetchall()
        
        for col_name, col_desc, col_type, col_size in columns:
            data_type = f"{col_type}({col_size})" if col_size else col_type
            
            # Limpeza para evitar quebras na tabela Markdown
            clean_col_desc = col_desc.replace('|', '\\|') if col_desc else ''

            schema_markdown += f"| `{col_name}` | {clean_col_desc} | {data_type} |\n"
            
        schema_markdown += "\n"

    cursor.close()
    return schema_markdown

# --- Execução Principal ---
if __name__ == "__main__":
    try:
        # Verificar se as variáveis de ambiente estão configuradas
        if not db_host:
            print("Erro: DB_HOST não está configurado. Configure a variável de ambiente DB_HOST.")
            print("Exemplo: set DB_HOST=seu_servidor_oracle")
            exit(1)
            
        print(f"Tentando conectar ao Oracle Database:")
        print(f"  Host: {db_host}")
        print(f"  Port: {db_port}")
        print(f"  Service: {db_service}")
        print(f"  User: {db_user}")
        
        # Tentar conexão com string de conexão explícita
        connection_string = f"{db_host}:{db_port}/{db_service}"
        with oracledb.connect(user=db_user, password=db_password, dsn=connection_string) as connection:
            print(f"Successfully connected to Oracle Database version {connection.version}")
            
            markdown_content = extract_sankhya_schema(connection)
            
            output_filename = "sankhya_schema.md"
            with open(output_filename, "w", encoding="utf-8") as f:
                f.write(markdown_content)
                
            print(f"\nSchema successfully extracted to '{output_filename}'")

    except oracledb.Error as e:
        print(f"Error connecting to or fetching from Oracle Database: {e}")
        print("\nDicas para resolver:")
        print("1. Verifique se o Oracle Client está instalado")
        print("2. Verifique se as variáveis de ambiente estão corretas")
        print("3. Verifique se o servidor Oracle está acessível")
        print("4. Tente usar uma string de conexão completa")