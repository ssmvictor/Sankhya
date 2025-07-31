import oracledb
import os
import getpass
import logging
from pathlib import Path
from typing import Optional, Dict, Any

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('sankhya_extractor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class SankhyaSchemaExtractor:
    """Classe para extração do schema do Sankhya"""
    
    def __init__(self):
        self.config = self._load_config()
        self.stats = {
            'tables_processed': 0,
            'columns_processed': 0,
            'errors': 0
        }
    
    def _load_env_file(self) -> None:
        """Carrega variáveis de ambiente de um arquivo .env se existir"""
        env_file = Path('.env')
        if env_file.exists():
            logger.info("Carregando configurações do arquivo .env...")
            with open(env_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        os.environ[key] = value
        else:
            logger.warning("Arquivo .env não encontrado. Usando variáveis de ambiente do sistema.")

    def _load_config(self) -> Dict[str, Any]:
        """Carrega e valida configurações"""
        self._load_env_file()
        
        config = {
            'db_user': os.environ.get("DB_USER"),
            'db_host': os.environ.get("DB_HOST"),
            'db_port': os.environ.get("DB_PORT", "1521"),
            'db_service': os.environ.get("DB_SERVICE", "prodpdb"),
            'db_password': os.environ.get("DB_PASSWORD")
        }
        
        # Validação de configurações obrigatórias
        missing_configs = []
        for key, value in config.items():
            if key in ['db_user', 'db_host'] and not value:
                missing_configs.append(key.upper())
        
        if missing_configs:
            raise ValueError(f"Configurações obrigatórias não encontradas: {', '.join(missing_configs)}")
        
        return config

    def _get_password(self) -> str:
        """Solicita senha de forma segura se não fornecida"""
        if not self.config['db_password']:
            logger.info("Senha não fornecida. Solicitando interativamente...")
            self.config['db_password'] = getpass.getpass(f"Digite a senha para {self.config['db_user']}: ")
        return self.config['db_password']

    def _create_connection(self) -> oracledb.Connection:
        """Cria conexão com o banco Oracle"""
        try:
            # Configurar o modo thin para evitar problemas de bequeath
            oracledb.init_oracle_client()
            
            connection_string = f"{self.config['db_host']}:{self.config['db_port']}/{self.config['db_service']}"
            
            logger.info(f"Conectando ao Oracle Database:")
            logger.info(f"  Host: {self.config['db_host']}")
            logger.info(f"  Port: {self.config['db_port']}")
            logger.info(f"  Service: {self.config['db_service']}")
            logger.info(f"  User: {self.config['db_user']}")
            
            connection = oracledb.connect(
                user=self.config['db_user'],
                password=self._get_password(),
                dsn=connection_string
            )
            
            logger.info(f"Conexão estabelecida com sucesso! Versão Oracle: {connection.version}")
            return connection
            
        except oracledb.Error as e:
            logger.error(f"Erro ao conectar ao Oracle Database: {e}")
            self._print_troubleshooting_tips()
            raise

    def _print_troubleshooting_tips(self) -> None:
        """Exibe dicas para resolução de problemas"""
        logger.error("\n=== DICAS PARA RESOLUÇÃO ===")
        logger.error("1. Verifique se o Oracle Client está instalado")
        logger.error("2. Verifique se as variáveis de ambiente estão corretas")
        logger.error("3. Verifique se o servidor Oracle está acessível")
        logger.error("4. Tente usar uma string de conexão completa")
        logger.error("5. Verifique se o usuário tem permissões necessárias")

    def extract_schema(self, connection: oracledb.Connection) -> str:
        """
        Extrai o schema de tabelas do Sankhya e formata em Markdown.
        
        Args:
            connection: Conexão ativa com o banco Oracle
            
        Returns:
            String formatada em Markdown com o dicionário de dados
        """
        schema_markdown = "# Dicionário de Dados Sankhya\n\n"
        cursor = connection.cursor()

        try:
            # 1. Obter a lista de tabelas relevantes
            logger.info("Buscando tabelas do Sankhya...")
            cursor.execute("""
                SELECT NOMETAB, DESCRTAB
                FROM TDDTAB
                WHERE NOMETAB LIKE 'TGF%' OR NOMETAB LIKE 'TSI%' OR NOMETAB LIKE 'TCB%'
                ORDER BY NOMETAB
            """)
            tables = cursor.fetchall()
            
            logger.info(f"Encontradas {len(tables)} tabelas para processar")

            for table_name, table_desc in tables:
                try:
                    logger.info(f"Processando tabela: {table_name}")
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
                        self.stats['columns_processed'] += 1
                    
                    schema_markdown += "\n"
                    self.stats['tables_processed'] += 1
                    
                except Exception as e:
                    logger.error(f"Erro ao processar tabela {table_name}: {e}")
                    self.stats['errors'] += 1
                    continue

        except Exception as e:
            logger.error(f"Erro durante a extração do schema: {e}")
            raise
        finally:
            cursor.close()

        return schema_markdown

    def save_schema(self, schema_content: str, filename: str = "sankhya_schema.md") -> None:
        """Salva o schema extraído em arquivo Markdown"""
        try:
            with open(filename, "w", encoding="utf-8") as f:
                f.write(schema_content)
            
            logger.info(f"Schema salvo com sucesso em '{filename}'")
            logger.info(f"Estatísticas: {self.stats['tables_processed']} tabelas, "
                       f"{self.stats['columns_processed']} colunas processadas")
            
            if self.stats['errors'] > 0:
                logger.warning(f"{self.stats['errors']} erros encontrados durante o processamento")
                
        except Exception as e:
            logger.error(f"Erro ao salvar arquivo: {e}")
            raise

    def run(self) -> None:
        """Executa o processo completo de extração"""
        try:
            connection = self._create_connection()
            
            with connection:
                schema_content = self.extract_schema(connection)
                self.save_schema(schema_content)
                
        except Exception as e:
            logger.error(f"Erro durante a execução: {e}")
            raise

def main():
    """Função principal"""
    try:
        extractor = SankhyaSchemaExtractor()
        extractor.run()
        
    except ValueError as e:
        logger.error(f"Erro de configuração: {e}")
        logger.error("Configure as variáveis de ambiente necessárias ou crie um arquivo .env")
        exit(1)
        
    except Exception as e:
        logger.error(f"Erro inesperado: {e}")
        exit(1)

if __name__ == "__main__":
    main()