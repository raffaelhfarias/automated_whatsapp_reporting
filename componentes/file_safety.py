"""
Módulo de Segurança de Arquivos
================================

Funções para garantir integridade de dados e evitar uso de arquivos obsoletos.
"""

import os
import glob
import logging
from datetime import datetime

def limpar_arquivo_especifico(arquivo_path, descricao="arquivo"):
    logger = logging.getLogger(__name__)
    
    if not os.path.exists(arquivo_path):
        return True      
    try:
        os.remove(arquivo_path)
        logger.info(f"✅ Removido {descricao}: {os.path.basename(arquivo_path)}")
        return True
    except Exception as e:
        logger.error(f"❌ Erro ao remover {descricao} {os.path.basename(arquivo_path)}: {e}")
        return False

def limpar_arquivos_por_padrao(diretorio, padrao, descricao="arquivos"):
    """Remove arquivos que correspondem a um padrão glob.
    
    Args:
        diretorio: Diretório onde buscar
        padrao: Padrão glob (ex: "resultado_*.csv")
        descricao: Descrição para logs
        
    Returns:
        int: Número de arquivos removidos
    """
    logger = logging.getLogger(__name__)
    
    if not os.path.exists(diretorio):
        logger.warning(f"⚠️ Diretório não existe: {diretorio}")
        return 0
    
    caminho_padrao = os.path.join(diretorio, padrao)
    arquivos = glob.glob(caminho_padrao)
    
    removidos = 0
    for arquivo in arquivos:
        if limpar_arquivo_especifico(arquivo, f"{descricao}"):
            removidos += 1
    
    if removidos > 0:
        logger.info(f"🗑️ Total de {descricao} removidos: {removidos}")
    
    return removidos

def validar_data_arquivo_csv(arquivo_path, data_esperada=None):
    """Valida se o arquivo foi modificado hoje (sem ler conteúdo).
    
    Args:
        arquivo_path: Caminho do arquivo CSV
        data_esperada: Data no formato DD/MM/YYYY (padrão: hoje)
        
    Returns:
        dict: {'valido': bool, 'data_encontrada': str, 'erro': str ou None}
    """
    logger = logging.getLogger(__name__)
    
    if data_esperada is None:
        data_esperada = datetime.now().strftime("%d/%m/%Y")
    
    if not os.path.exists(arquivo_path):
        return {
            'valido': False,
            'data_encontrada': None,
            'erro': 'Arquivo não encontrado'
        }
    
    try:
        # Obtém a data de modificação do arquivo
        timestamp_modificacao = os.path.getmtime(arquivo_path)
        data_modificacao = datetime.fromtimestamp(timestamp_modificacao)
        data_modificacao_str = data_modificacao.strftime("%d/%m/%Y")
        
        valido = data_modificacao_str == data_esperada
        
        if not valido:
            logger.warning(
                f"⚠️ Arquivo {os.path.basename(arquivo_path)} foi modificado em data diferente: "
                f"'{data_modificacao_str}', esperada '{data_esperada}'"
            )
        
        return {
            'valido': valido,
            'data_encontrada': data_modificacao_str,
            'erro': None if valido else f'Arquivo modificado em: {data_modificacao_str} != {data_esperada}'
        }
        
    except Exception as e:
        logger.error(f"❌ Erro ao validar data de {os.path.basename(arquivo_path)}: {e}")
        return {
            'valido': False,
            'data_encontrada': None,
            'erro': str(e)
        }

def salvar_timestamp_extracao(arquivo_csv_path):
    """Salva o horário atual em um arquivo .timestamp correspondente ao CSV.
    
    Args:
        arquivo_csv_path: Caminho do arquivo CSV gerado
        
    Returns:
        str: Horário salvo no formato HH:MM:SS
    """
    logger = logging.getLogger(__name__)
    
    try:
        # Gera nome do arquivo timestamp (ex: resultado_loja.csv.timestamp)
        timestamp_file = f"{arquivo_csv_path}.timestamp"
        
        # Horário atual
        horario_extracao = datetime.now().strftime("%H:%M:%S")
        
        # Salva no arquivo
        with open(timestamp_file, 'w', encoding='utf-8') as f:
            f.write(horario_extracao)
        
        logger.debug(f"✅ Timestamp salvo: {os.path.basename(timestamp_file)} = {horario_extracao}")
        return horario_extracao
        
    except Exception as e:
        logger.warning(f"⚠️ Erro ao salvar timestamp para {os.path.basename(arquivo_csv_path)}: {e}")
        return None

def ler_timestamp_extracao(arquivo_csv_path):
    """Lê o horário de extração de um arquivo .timestamp correspondente.
    
    Args:
        arquivo_csv_path: Caminho do arquivo CSV
        
    Returns:
        str: Horário de extração no formato HH:MM:SS, ou None se não existir
    """
    logger = logging.getLogger(__name__)
    
    try:
        timestamp_file = f"{arquivo_csv_path}.timestamp"
        
        if not os.path.exists(timestamp_file):
            # Fallback: usa data de modificação do CSV
            if os.path.exists(arquivo_csv_path):
                timestamp_modificacao = os.path.getmtime(arquivo_csv_path)
                horario = datetime.fromtimestamp(timestamp_modificacao).strftime("%H:%M:%S")
                logger.debug(f"⏰ Timestamp não encontrado, usando data de modificação: {horario}")
                return horario
            return None
        
        with open(timestamp_file, 'r', encoding='utf-8') as f:
            horario = f.read().strip()
        
        logger.debug(f"✅ Timestamp lido: {os.path.basename(timestamp_file)} = {horario}")
        return horario
        
    except Exception as e:
        logger.warning(f"⚠️ Erro ao ler timestamp de {os.path.basename(arquivo_csv_path)}: {e}")
        return None

