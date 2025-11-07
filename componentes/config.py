#!/usr/bin/env python3
"""
Configurações do Sistema
========================
Arquivo centralizado com todas as configurações do sistema.
"""

import os
import warnings
from typing import Dict, List

LOGIN_CONFIG = {
    "url": os.getenv("LOGIN_URL", "LINK DO RETAGUARDA"),
    "username": os.getenv("LOGIN_USERNAME", os.getenv("USER", "USUÁRIO")),
    "password": os.getenv("LOGIN_PASSWORD", "")
}

def warn_if_insecure_login():
    if not LOGIN_CONFIG.get("password"):
        warnings.warn(
            "LOGIN_PASSWORD não está definida. Configure via variável de ambiente antes de executar em produção.",
            UserWarning,
        )

# Configurações de WhatsApp
WHATSAPP_CONFIG = {
    "group_links": [
        "LINK FINAL DO 1º GRUPO",  
        "LINK FINAL DO 2º GRUPO CASO NECESSÁRIO"   
    ],
    "delay_seconds": 15
}

# Configurações de Meta
META_CONFIG = {
    "vd_group_link": "LINK FINAL DO 1º GRUPO",
    "loja_group_link": "LINK FINAL DO 2º GRUPO CASO NECESSÁRIO",
    "search_terms": {
        "vd": "META DIARIA",
        "loja": "segue nossa meta de hoje"
    }
}

# Configurações de Arquivos
FILE_CONFIG = {
    "output_dir": "extracoes",
    "log_dir": "log",
    "files": {
        "meta_dia": "meta_dia.csv",
        "resultado_loja": "resultado_loja.csv",
        "resultado_vd": "resultado.csv"
    },
    "patterns": {
        "resultado_pef": "resultado_pef_*.csv",
        "resultado_eud": "resultado_eud_*.csv"
    }
}

# Configurações de Navegação (Seletores CSS)
NAVIGATION_CONFIG = {
    "login": {
        "username_field": "#username > div:nth-child(2) input",
        "password_field": "#password > div:nth-child(2) input",
        "submit_button": ".LoginGB_formulario_1LJpp > button:nth-child(3)"
    },
    "loja": {
        "menu_items": ["#sidemenu-item-6", "#sidemenu-item-602", "#sidemenu-item-20423"],
        "query_button": "#app > div.App_layout_3o3R1 > div > main > div > section > section > div > div > footer > button.flora-button.flora-button--icon-left.flora-button--standard.flora-button--shape-small.flora-button--size-standard.flora-body-small.FiltrosIniciais_botaoConsultar_OBWUZ",
        "table": ".flora-table",
        "table_row": ".flora-table-row",
        "loja_cell": "div.flora-table-cell:nth-child(1)",
        "gmv_cell": "div.flora-table-cell:nth-child(3)"
    },
    "vd": {
        "menu_items": ["#sidemenu-item-6", "#sidemenu-item-602", "#sidemenu-item-20423"],
        "query_button": "button.flora-button:nth-child(4)",
        "table": ".flora-table",
        "table_row": ".flora-table-row",
        "empresa_cell": "div.flora-table-cell:nth-child(1)",
        "gmv_cell": "div.flora-table-cell:nth-child(3)"
    }
}

# Configurações de Logging
LOGGING_CONFIG = {
    "level": "INFO",
    "format": "%(asctime)s [%(levelname)s] %(message)s",
    "file_mode": "w",
    "encoding": "utf-8"
}

# Configurações de Timing
TIMING_CONFIG = {
    "login_wait": 7,
    "navigation_wait": 1,
    "table_wait": 2,
    "between_extractions": 3,
    "before_send": 5
}


def get_file_path(filename: str) -> str:
    """Retorna o caminho completo para um arquivo"""
    return os.path.join(FILE_CONFIG["output_dir"], filename)

def get_result_files(tipo: str) -> list:
    """Retorna lista de arquivos de resultado para o tipo especificado"""
    import glob
    pattern = FILE_CONFIG["patterns"].get(tipo)
    if pattern:
        return glob.glob(os.path.join(FILE_CONFIG["output_dir"], pattern))
    return []

def ensure_directories():
    """Cria os diretórios necessários se não existirem"""
    os.makedirs(FILE_CONFIG["output_dir"], exist_ok=True)
    os.makedirs(FILE_CONFIG["log_dir"], exist_ok=True)

