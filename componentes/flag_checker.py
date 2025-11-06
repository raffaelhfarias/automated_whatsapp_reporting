"""
Módulo para verificar flags de captura de metas e determinar comportamento de envio.
"""
import os
import re
from datetime import datetime

def parse_flag_envio(flag_path):
    """
    Verifica o flag e retorna o status para decisão de envio.
    
    Returns:
        dict: {
            'deve_tentar_captura': bool,  # True se deve tentar capturar metas
            'deve_enviar_sem_meta': bool, # True se deve enviar sem meta
            'metas_disponiveis': set,     # Metas que estão disponíveis para uso
            'status': str,                # Status do flag
            'motivo': str                 # Explicação da decisão
        }
    """
    if not os.path.exists(flag_path):
        return {
            'deve_tentar_captura': True,
            'deve_enviar_sem_meta': False,
            'metas_disponiveis': set(),
            'status': 'NENHUM_FLAG',
            'motivo': 'Nenhum flag encontrado - primeira tentativa do dia'
        }
    
    try:
        with open(flag_path, 'r', encoding='utf-8') as f:
            conteudo = f.read().strip()
        
        data_hoje = datetime.now().strftime('%d/%m/%Y')
        
        # Flag de metas capturadas
        if conteudo.startswith("Metas capturadas"):
            match = re.search(r'Metas capturadas em (\d{2}/\d{2}/\d{4})\s+status=(COMPLETO|PARCIAL)', conteudo)
            if not match:
                return {
                    'deve_tentar_captura': True,
                    'deve_enviar_sem_meta': False,
                    'metas_disponiveis': set(),
                    'status': 'FLAG_INVALIDO',
                    'motivo': 'Flag de captura mal formatado'
                }
            
            data_flag = match.group(1)
            status = match.group(2)
            
            if data_flag != data_hoje:
                return {
                    'deve_tentar_captura': True,
                    'deve_enviar_sem_meta': False,
                    'metas_disponiveis': set(),
                    'status': 'FLAG_ANTIGO',
                    'motivo': f'Flag de outro dia ({data_flag})'
                }
            
            # Extrai metas disponíveis
            if ': ' in conteudo:
                metas_str = conteudo.split(': ', 1)[1]
                metas_disponiveis = set([x.strip().upper() for x in metas_str.split(',') if x.strip()])
            else:
                metas_disponiveis = set()
            
            if status == 'COMPLETO':
                return {
                    'deve_tentar_captura': False,
                    'deve_enviar_sem_meta': False,
                    'metas_disponiveis': metas_disponiveis,
                    'status': 'METAS_DISPONIVEIS',
                    'motivo': 'Metas já capturadas com sucesso'
                }
            else:  # PARCIAL
                return {
                    'deve_tentar_captura': True,
                    'deve_enviar_sem_meta': False,
                    'metas_disponiveis': metas_disponiveis,
                    'status': 'METAS_PARCIAIS',
                    'motivo': 'Metas parciais - pode tentar capturar novamente'
                }
        
        # Flag de tentativas sem sucesso total
        elif conteudo.startswith("Tentativas") and "status=SEM_META_FINAL" in conteudo:
            match = re.search(r'Tentativas em (\d{2}/\d{2}/\d{4})\s+status=SEM_META_FINAL', conteudo)
            if not match:
                return {
                    'deve_tentar_captura': True,
                    'deve_enviar_sem_meta': False,
                    'metas_disponiveis': set(),
                    'status': 'FLAG_INVALIDO',
                    'motivo': 'Flag de tentativas mal formatado'
                }
            
            data_flag = match.group(1)
            
            if data_flag != data_hoje:
                return {
                    'deve_tentar_captura': True,
                    'deve_enviar_sem_meta': False,
                    'metas_disponiveis': set(),
                    'status': 'FLAG_ANTIGO',
                    'motivo': f'Flag de tentativas de outro dia ({data_flag})'
                }
            
            return {
                'deve_tentar_captura': False,
                'deve_enviar_sem_meta': True,
                'metas_disponiveis': set(),
                'status': 'SEM_META_FINAL',
                'motivo': 'Janela de captura encerrada - enviar sem metas'
            }
        
        # Flag de tentativas com metas parciais finais (novo)
        elif conteudo.startswith("Tentativas") and "status=METAS_PARCIAIS_FINAL" in conteudo:
            match = re.search(r'Tentativas em (\d{2}/\d{2}/\d{4})\s+status=METAS_PARCIAIS_FINAL', conteudo)
            if not match:
                return {
                    'deve_tentar_captura': True,
                    'deve_enviar_sem_meta': False,
                    'metas_disponiveis': set(),
                    'status': 'FLAG_INVALIDO',
                    'motivo': 'Flag de tentativas parciais mal formatado'
                }
            
            data_flag = match.group(1)
            
            if data_flag != data_hoje:
                return {
                    'deve_tentar_captura': True,
                    'deve_enviar_sem_meta': False,
                    'metas_disponiveis': set(),
                    'status': 'FLAG_ANTIGO',
                    'motivo': f'Flag de tentativas parciais de outro dia ({data_flag})'
                }
            
            # Extrai metas disponíveis
            if ': ' in conteudo:
                metas_str = conteudo.split(': ', 1)[1]
                metas_disponiveis = set([x.strip().upper() for x in metas_str.split(',') if x.strip()])
            else:
                metas_disponiveis = set()
            
            return {
                'deve_tentar_captura': False,
                'deve_enviar_sem_meta': False,
                'metas_disponiveis': metas_disponiveis,
                'status': 'METAS_PARCIAIS_FINAL',
                'motivo': f'Janela encerrada - usar metas disponíveis: {", ".join(sorted(metas_disponiveis))}'
            }
        
        else:
            return {
                'deve_tentar_captura': True,
                'deve_enviar_sem_meta': False,
                'metas_disponiveis': set(),
                'status': 'FLAG_DESCONHECIDO',
                'motivo': 'Formato de flag não reconhecido'
            }
            
    except Exception as e:
        return {
            'deve_tentar_captura': True,
            'deve_enviar_sem_meta': False,
            'metas_disponiveis': set(),
            'status': 'ERRO_LEITURA',
            'motivo': f'Erro ao ler flag: {e}'
        }

def verificar_janela_captura():
    """Verifica se estamos dentro da janela de captura de metas (10h-10:35h)."""
    agora = datetime.now()
    hora_atual = agora.hour
    minuto_atual = agora.minute
    
    # Janela de captura: 10:00 às 10:35 (margem de 5 min após última tentativa)
    if hora_atual == 10 and minuto_atual <= 35:
        return True
    elif hora_atual < 10:
        return True  # Antes das 10h, ainda pode tentar
    else:
        return False  # Após 10:35h, não tenta mais
