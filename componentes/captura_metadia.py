
import os
import re
import csv
import time
import logging
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException

# --- CONFIGURAÇÕES CENTRALIZADAS ---
CHROME_PATH = r"CAMINHO DO SEU CHROMEDRIVERWEB"
USER_DATA_DIR = r"CAMINHO DO SEU GOOGLE CHROME PARA CAPUTRA DE PERFIL"
PROFILE_DIR = "Profile 1"
CHROMEDRIVER_PATH = r"CAMINHO DO SEU CHROMEDRIVERWEB"

GRUPOS = [
    ("VD", "LINK DO 1º GRUPO"), 
    ("LOJA", "LINK DO 2º CASO NECESSÁRIO")
]

LOG_FILE = 'log/captura_metaDia.log'
CSV_FILE = 'extracoes/meta_dia.csv'
FLAG_FILE = "extracoes/meta_capturada.flag"

def parse_flag(flag_path):
    """Retorna dict com dados do flag ou None se inválido.
    Formato esperado: 
    - Metas capturadas em DD/MM/AAAA status=COMPLETO|PARCIAL: PEF,EUD,LOJA
    - Tentativas em DD/MM/AAAA status=SEM_META_FINAL tentativas=HH:MM,HH:MM,HH:MM: 
    - Tentativas em DD/MM/AAAA status=METAS_PARCIAIS_FINAL tentativas=HH:MM,HH:MM,HH:MM: PEF,EUD
    """
    if not os.path.exists(flag_path):
        return None
    try:
        with open(flag_path, 'r', encoding='utf-8') as f:
            conteudo = f.read().strip()
        
        # Formato 1: Metas capturadas (comportamento atual)
        if conteudo.startswith("Metas capturadas"):
            if ': ' not in conteudo:
                return None
            cabecalho, lista = conteudo.split(': ', 1)
            # Extrai data e status
            m = re.search(r'Metas capturadas em (\d{2}/\d{2}/\d{4})\s+status=(COMPLETO|PARCIAL)', cabecalho, re.IGNORECASE)
            if not m:
                return None
            data_str = m.group(1)
            status = m.group(2).upper()
            metas = set([x.strip().upper() for x in lista.split(',') if x.strip()])
            return {'data': data_str, 'status': status, 'metas': metas, 'tipo': 'CAPTURA'}
        
        # Formato 2: Tentativas sem sucesso total
        elif conteudo.startswith("Tentativas") and "status=SEM_META_FINAL" in conteudo:
            if ': ' not in conteudo:
                return None
            cabecalho, lista = conteudo.split(': ', 1)
            # Extrai data, status e tentativas
            m = re.search(r'Tentativas em (\d{2}/\d{2}/\d{4})\s+status=(SEM_META_FINAL)\s+tentativas=([0-9:,]+)', cabecalho, re.IGNORECASE)
            if not m:
                return None
            data_str = m.group(1)
            status = m.group(2).upper()
            tentativas_str = m.group(3)
            tentativas = [h.strip() for h in tentativas_str.split(',') if h.strip()]
            return {'data': data_str, 'status': status, 'tentativas': tentativas, 'tipo': 'TENTATIVAS'}
        
        # Formato 3: Tentativas com metas parciais finais (novo)
        elif conteudo.startswith("Tentativas") and "status=METAS_PARCIAIS_FINAL" in conteudo:
            if ': ' not in conteudo:
                return None
            cabecalho, lista = conteudo.split(': ', 1)
            # Extrai data, status e tentativas
            m = re.search(r'Tentativas em (\d{2}/\d{2}/\d{4})\s+status=(METAS_PARCIAIS_FINAL)\s+tentativas=([0-9:,]+)', cabecalho, re.IGNORECASE)
            if not m:
                return None
            data_str = m.group(1)
            status = m.group(2).upper()
            tentativas_str = m.group(3)
            tentativas = [h.strip() for h in tentativas_str.split(',') if h.strip()]
            # As metas disponíveis estão na lista após o ':'
            metas = set([x.strip().upper() for x in lista.split(',') if x.strip()])
            return {'data': data_str, 'status': status, 'tentativas': tentativas, 'metas': metas, 'tipo': 'TENTATIVAS_PARCIAIS'}
            
        return None
    except Exception:
        return None

def escrever_flag(flag_path, metas_capturadas, completas_esperadas):
    status = 'COMPLETO' if set(completas_esperadas).issubset(metas_capturadas) else 'PARCIAL'
    conteudo = f"Metas capturadas em {datetime.now().strftime('%d/%m/%Y')} status={status}: {','.join(sorted(metas_capturadas))}"
    with open(flag_path, 'w', encoding='utf-8') as f:
        f.write(conteudo)
    return status

def escrever_flag_tentativa(flag_path, tentativas_horarios, metas_capturadas=None):
    """Escreve flag de tentativas sem sucesso, indicando quais metas foram capturadas.
    
    Args:
        flag_path: Caminho do arquivo de flag
        tentativas_horarios: Lista de horários das tentativas
        metas_capturadas: Set/lista das metas que foram capturadas (pode ser None se nenhuma)
    """
    horarios_str = ','.join(tentativas_horarios)
    data_hoje = datetime.now().strftime('%d/%m/%Y')
    
    if not metas_capturadas:
        # Nenhuma meta capturada - não tenta mais nada
        conteudo = f"Tentativas em {data_hoje} status=SEM_META_FINAL tentativas={horarios_str}: "
        status = 'SEM_META_FINAL'
    else:
        # Algumas metas foram capturadas - especifica quais estão disponíveis
        metas_str = ','.join(sorted(metas_capturadas))
        conteudo = f"Tentativas em {data_hoje} status=METAS_PARCIAIS_FINAL tentativas={horarios_str}: {metas_str}"
        status = 'METAS_PARCIAIS_FINAL'
    
    with open(flag_path, 'w', encoding='utf-8') as f:
        f.write(conteudo)
    
    return status

def verificar_janela_captura():
    """Verifica se estamos dentro da janela de captura de metas (10h-10:30h)."""
    agora = datetime.now()
    hora_atual = agora.hour
    minuto_atual = agora.minute
    
    # Janela de captura: 10:00 às 10:55 (margem de 5 min após última tentativa)
    if hora_atual == 10 and minuto_atual <= 55:
        return True
    elif hora_atual < 10:
        return True  # Antes das 10h, ainda pode tentar
    else:
        return False  # Após 10:55h, não tenta mais

def obter_tentativas_existentes(flag_path):
    """Obtém lista de horários de tentativas já realizadas."""
    dados_flag = parse_flag(flag_path)
    if dados_flag and dados_flag.get('tipo') in ['TENTATIVAS', 'TENTATIVAS_PARCIAIS']:
        return dados_flag.get('tentativas', [])
    return []

METAS_ESPERADAS = ["PEF", "EUD", "LOJA"]
_dados_flag = parse_flag(FLAG_FILE)

# Verificação de flags existentes
if _dados_flag:
    data_hoje = datetime.now().strftime('%d/%m/%Y')
    
    if _dados_flag['data'] == data_hoje:
        # Flag do mesmo dia
        if _dados_flag.get('tipo') == 'CAPTURA':
            # Flag de captura bem-sucedida
            if _dados_flag['status'] == 'COMPLETO' and set(METAS_ESPERADAS).issubset(_dados_flag['metas']):
                print("✅ Todas as metas do dia já capturadas (flag COMPLETO). Encerrando execução.")
                exit(0)
            else:
                print("ℹ️ Flag PARCIAL encontrado. Nova tentativa de captura será realizada.")
        
        elif _dados_flag.get('tipo') == 'TENTATIVAS':
            # Flag de tentativas sem sucesso total
            if _dados_flag['status'] == 'SEM_META_FINAL':
                if not verificar_janela_captura():
                    print("⏰ Janela de captura encerrada (após 10:35h) e flag SEM_META_FINAL encontrado.")
                    print("🚫 Nenhuma meta será mais tentada hoje. Encerrando execução.")
                    exit(0)
                else:
                    print("⚠️ Flag SEM_META_FINAL encontrado, mas ainda dentro da janela de captura. Tentando novamente.")
        
        elif _dados_flag.get('tipo') == 'TENTATIVAS_PARCIAIS':
            # Flag de tentativas com metas parciais finais (novo)
            if _dados_flag['status'] == 'METAS_PARCIAIS_FINAL':
                if not verificar_janela_captura():
                    metas_disponiveis = _dados_flag.get('metas', set())
                    print(f"⏰ Janela de captura encerrada e flag METAS_PARCIAIS_FINAL encontrado.")
                    print(f"✅ Metas disponíveis para envio: {', '.join(sorted(metas_disponiveis))}")
                    print("🚫 Não tentará capturar mais metas hoje. Encerrando execução.")
                    exit(0)
                else:
                    print("⚠️ Flag METAS_PARCIAIS_FINAL encontrado, mas ainda dentro da janela de captura. Tentando novamente.")
    else:
        print("ℹ️ Flag de outro dia encontrado. Nova tentativa de captura será realizada.")
else:
    print("ℹ️ Nenhum flag encontrado. Iniciando captura de metas.")

# --- CONFIGURAÇÃO DE LOGGING ---
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
logging.basicConfig(
    filename=LOG_FILE,
    filemode='w',  # Agora sobrescreve o log a cada execução
    level=logging.INFO, # Mude para logging.DEBUG se precisar de mais detalhes
    format='%(asctime)s - %(levelname)s - %(message)s',
    encoding='utf-8'
)

def configurar_driver():
    """Configura e retorna uma instância do WebDriver do Chrome."""
    options = webdriver.ChromeOptions()
    options.binary_location = CHROME_PATH
    options.add_argument(f"--profile-directory={PROFILE_DIR}")
    options.add_argument(f"user-data-dir={USER_DATA_DIR}")
    options.add_argument('--disable-extensions')
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--start-maximized')  # Abre maximizado
    options.add_argument('--disable-infobars')  # Remove barra "Chrome está sendo controlado"
    #options.add_argument('--headless') # Descomente para executar em modo headless
    service = Service(CHROMEDRIVER_PATH)
    driver = webdriver.Chrome(service=service, options=options)
    
    # Garante maximização (fallback caso --start-maximized não funcione)
    try:
        driver.maximize_window()
    except Exception:
        pass
    
    return driver

# --- Funções de extração ---
def extrair_metas_vd(texto):
    """Extrai metas PEF e EUD, suportando múltiplos ciclos (ex.: CICLO 11, CICLO 12).

    Retorna: lista de dicts no formato:
      [{ 'tipo': 'PEF'|'EUD', 'ciclo': '11'|'12'|'' , 'valor': float }]
    """
    # Normaliza quebras de linha e espaços
    texto_norm = re.sub(r"\u00A0", " ", texto)  # non-breaking space
    # Identifica blocos por ciclo: "CICLO NN"
    ciclo_pattern = re.compile(r"(?i)CICLO\s*(\d{1,2})")
    # Aceita 1 ou 2 casas decimais (ou nenhuma) e tanto EUD quanto EUDORA
    # Agora aceita R$ ou apenas R (para casos onde o $ é omitido)
    valor_pattern_pef = re.compile(r"(?i)PEF\s*-?\s*R\$?\s*([\d\.]+(?:,\d{1,2})?)")
    valor_pattern_eud = re.compile(r"(?i)\bEUD(?:ORA)?\b\s*-?\s*R\$?\s*([\d\.]+(?:,\d{1,2})?)")

    def parse_valor(br):
        try:
            if ',' in br:
                inteiro, dec = br.split(',')
                if dec == '':
                    dec = '00'
                elif len(dec) == 1:
                    dec = dec + '0'
            else:
                inteiro, dec = br, '00'
            return float(inteiro.replace('.', '') + '.' + dec)
        except Exception:
            logging.warning(f"Falha ao converter valor '{br}'")
            return None

    metas = []

    # Encontra todos os cabeçalhos de ciclo e delimita blocos
    matches = list(ciclo_pattern.finditer(texto_norm))
    if matches:
        for idx, m in enumerate(matches):
            ciclo = m.group(1)
            start = m.end()
            end = matches[idx + 1].start() if idx + 1 < len(matches) else len(texto_norm)
            bloco = texto_norm[start:end]

            # Extrai valores dentro do bloco do ciclo
            pef_m = valor_pattern_pef.search(bloco)
            eud_m = valor_pattern_eud.search(bloco)

            if pef_m:
                v = parse_valor(pef_m.group(1))
                if v is not None:
                    metas.append({'tipo': 'PEF', 'ciclo': ciclo, 'valor': v})
                    logging.debug(f"Meta PEF extraída (C{ciclo}): {v}")
            if eud_m:
                v = parse_valor(eud_m.group(1))
                if v is not None:
                    metas.append({'tipo': 'EUD', 'ciclo': ciclo, 'valor': v})
                    logging.debug(f"Meta EUD extraída (C{ciclo}): {v}")

    else:
        # Fallback: sem cabeçalho de ciclo, aplica regex simples (ciclo vazio)
        # Regex flexível que aceita R$ ou apenas R
        pef_m = re.search(r"(?i)PEF\s*-?\s*R\$?\s*([\d\.]+(?:,\d{1,2})?)", texto_norm)
        if pef_m:
            v = parse_valor(pef_m.group(1))
            if v is not None:
                metas.append({'tipo': 'PEF', 'ciclo': '', 'valor': v})
                logging.debug(f"Meta PEF extraída (sem ciclo): {v}")
        
        eud_m = re.search(r"(?i)\bEUD(?:ORA)?\b\s*-?\s*R\$?\s*([\d\.]+(?:,\d{1,2})?)", texto_norm)
        if eud_m:
            v = parse_valor(eud_m.group(1))
            if v is not None:
                metas.append({'tipo': 'EUD', 'ciclo': '', 'valor': v})
                logging.debug(f"Meta EUD extraída (sem ciclo): {v}")

    logging.debug(f"Metas VD extraídas: {metas}")
    return metas

def extrair_meta_loja(texto):
    """Extrai a meta LOJA considerando formatos antigos e novos.

    Suporta:
    - Formato antigo: "Meta de hoje DD/MM R$50.000,00"
    - Formato novo: "Meta do dia DD/MM 43.000" (sem R$, decimais opcionais)
    - Formato com "Nossa meta do dia DD/MM/YYYY" e "Total: XX.XXX"
    """
    # Regex flexível para capturar:
    # 1. "Meta de hoje", "Meta do dia" ou "Nossa meta do dia"
    # 2. Data no formato DD/MM ou DD/MM/YYYY
    # 3. Valor com ou sem R$, com ponto para milhares e vírgula opcional para decimais
    meta_regex = r'(?i)(?:Nossa\s+)?Meta\s+(?:de\s+hoje|do\s+dia)\s+(\d{2}/\d{2}(?:/\d{4})?)\s*(?:R?\$?\s*)?([\d\.]+(?:,\d{1,2})?)'
    match = re.search(meta_regex, texto, re.IGNORECASE)
    
    if match:
        try:
            valor_str = match.group(3)  # O valor está no grupo 3 agora
            # Normaliza números para o formato float independente do formato de entrada:
            # R$50.000,00 -> 50000.00
            # R$50.000 -> 50000.00
            # 43.000 -> 43000.00
            # 43000 -> 43000.00
            
            # Remove caracteres não numéricos (exceto . e ,)
            valor_str = re.sub(r'[^\d\.,]', '', valor_str)
            
            # Trata caso com vírgula decimal
            if ',' in valor_str:
                inteiro, dec = valor_str.split(',', 1)
                # Padroniza casas decimais
                if dec == '':
                    dec = '00'
                elif len(dec) == 1:
                    dec = dec + '0'
            else:
                # Sem decimais, assume .00
                inteiro, dec = valor_str, '00'
            
            # Remove pontos de milhar e monta o float final
            valor = float(inteiro.replace('.', '') + '.' + dec)
            
            logging.debug(f"Meta LOJA extraída (formato direto): {valor}")
            return valor
        except (ValueError, AttributeError) as e:
            logging.error(f"Erro ao converter valor da meta LOJA '{match.group(3)}': {e}")
            return None
    
    # Fallback: procurar por "Total:" se o regex principal não encontrou
    total_regex = r'(?i)Total:\s*([\d\.]+(?:,\d{1,2})?)'
    total_match = re.search(total_regex, texto)
    if total_match:
        try:
            valor_str = total_match.group(1)
            # Mesmo processamento de valor
            valor_str = re.sub(r'[^\d\.,]', '', valor_str)
            
            if ',' in valor_str:
                inteiro, dec = valor_str.split(',', 1)
                if dec == '':
                    dec = '00'
                elif len(dec) == 1:
                    dec = dec + '0'
            else:
                inteiro, dec = valor_str, '00'
            
            valor = float(inteiro.replace('.', '') + '.' + dec)
            
            logging.debug(f"Meta LOJA extraída (formato Total): {valor}")
            return valor
        except (ValueError, AttributeError) as e:
            logging.error(f"Erro ao converter valor Total da meta LOJA '{total_match.group(1)}': {e}")
            return None
    
    logging.debug(f"Nenhuma meta LOJA encontrada no padrão esperado.")
    return None

# --- Funções de Interação com a UI ---
def fechar_mensagem_fixada(driver, wait):
    """Tenta fechar a mensagem fixada, se existir, usando o seletor fornecido."""
    try:
        seletor_fixada = "#main > span.x1c4vz4f.x2lah0s.xdl72j9.x1q0q8m5.xa93pmm.x42zw1d.x178xt8z.x13fuv20.xx42vgk.x1h3rtpe.x1qhh985 > div > button"
        logging.info(f"Tentando localizar botão de mensagem fixada com seletor: {seletor_fixada}")
        botao_fixada = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, seletor_fixada))
        )
        logging.info("Botão de mensagem fixada encontrado. Clicando...")
        botao_fixada.click()
        logging.info("Mensagem fixada fechada com sucesso.")
        time.sleep(2) # Esperar um pouco para garantir que desapareça
    except TimeoutException:
        logging.info("Nenhuma mensagem fixada visível para fechar (Timeout).")
    except Exception as e:
        logging.warning(f"Erro ao tentar fechar mensagem fixada: {e}")

# --- Função de Busca Principal Atualizada com Retry ---
def buscar_meta_no_grupo(driver, wait, url, nome_grupo):
    """Busca e extrai a meta do dia em um grupo específico."""
    try:
        logging.info(f"--- Iniciando busca no grupo: {nome_grupo} ({url}) ---")
        driver.get(url)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#main")))
        logging.info("Página do grupo carregada.")
        
        # SOLUÇÃO: Forçar atualização do cache do WhatsApp Web (sem recarregar página)
        logging.info("Limpando cache de busca do WhatsApp Web...")
        try:
            # Limpa localStorage e sessionStorage do WhatsApp de forma agressiva
            driver.execute_script("""
                // Limpa TODOS os dados de storage do WhatsApp (mais agressivo)
                if (window.localStorage) {
                    // Remove especificamente chaves relacionadas a busca/índice
                    Object.keys(localStorage).forEach(key => {
                        if (key.includes('search') || key.includes('index') || 
                            key.includes('cache') || key.includes('query') || 
                            key.includes('result')) {
                            localStorage.removeItem(key);
                            console.log('Removed localStorage key:', key);
                        }
                    });
                }
                if (window.sessionStorage) {
                    sessionStorage.clear();
                    console.log('sessionStorage cleared');
                }
                
                // Força garbage collection se disponível
                if (window.gc) {
                    window.gc();
                }
            """)
            logging.info("Cache de busca limpo com sucesso (modo agressivo).")
            time.sleep(1.5)
        except Exception as e:
            logging.warning(f"Falha ao limpar cache (não crítico): {e}")
        
        logging.info("⏳ Aguardando 5 segundos para estabilização do WhatsApp Web...")
        print("⏳ Aguardando 5 segundos para estabilização do WhatsApp Web...")
        time.sleep(5) # Aumentado para 5 segundos para estabilização mais visível

        # --- Etapa 1: Fechar mensagem fixada ---
        logging.info("Tentando fechar mensagem fixada...")
        fechar_mensagem_fixada(driver, wait)
        logging.info("⏳ Aguardando 3 segundos após fechar mensagem fixada...")
        print("⏳ Aguardando 3 segundos após fechar mensagem fixada...")
        time.sleep(3) # Aumentado para 3 segundos após fechar mensagem fixada

        # --- Função auxiliar para realizar a busca e extração ---
        def _tentar_extrair_meta():
            logging.info("=== INICIANDO PREPARAÇÃO PARA PESQUISA ===")
            logging.info("⏳ Aguardando tempo total de 15 segundos para atualização completa das mensagens...")
            print("⏳ Aguardando 15 segundos para atualização completa das mensagens antes de pesquisar...")
            time.sleep(15)  # Pausa total de 15 segundos antes de começar a pesquisa
            logging.info("✅ Tempo de espera concluído. Iniciando extração de meta...")
            print("✅ Tempo de espera concluído. Iniciando pesquisa das metas...")
            
            # SOLUÇÃO: Scroll automático para forçar indexação de mensagens recentes
            logging.info("Rolando mensagens para forçar atualização do índice de busca...")
            try:
                # Encontra o container de mensagens
                container_msgs = driver.find_element(By.CSS_SELECTOR, "#main > div._amid")
                
                # Scroll até o topo (mensagens antigas)
                logging.info("Scroll para o topo (mensagens antigas)...")
                driver.execute_script("arguments[0].scrollTop = 0;", container_msgs)
                time.sleep(1.5)
                
                # Scroll até o fundo (mensagens recentes) - MÚLTIPLAS VEZES para garantir
                logging.info("Scroll para o fundo (mensagens recentes)...")
                for _ in range(3):
                    driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight;", container_msgs)
                    time.sleep(0.5)
                
                # Pequeno scroll adicional para forçar renderização final
                driver.execute_script("arguments[0].scrollBy(0, 200);", container_msgs)
                time.sleep(1)
                
                logging.info("Scroll completo realizado. Aguardando indexação...")
                logging.info("⏳ Aguardando 8 segundos para indexação completa das mensagens...")
                print("⏳ Aguardando 8 segundos para indexação completa das mensagens...")
                time.sleep(8)  # Tempo adicional aumentado para WhatsApp indexar completamente
                
            except Exception as e:
                logging.warning(f"Falha ao realizar scroll automático (não crítico): {e}")
            
            # --- Etapa 2: Clicar na lupa (ícone de pesquisa) com múltiplas alternativas ---
            logging.info("Procurando ícone de pesquisa (lupa)...")
            
            # Lista de seletores em ordem de prioridade
            seletores_lupa = [
                "#main > header > div.x1c4vz4f.x2lah0s.xdl72j9.xqsn43r > div > div._ajv7.x1n2onr6.x1okw0bk.x5yr21d.x1c9tyrk.xeusxvb.x1pahc9y.x1ertn4p.xlkovuz.x16j0l1c.x1hm9lzh.x11xlx4c.x17gydlx > button",  # Seletor principal da lupa
                "#main > header > div.x1c4vz4f.x2lah0s.xdl72j9.xqsn43r > div > div._ajv7.x1n2onr6.x1okw0bk.x5yr21d.x1c9tyrk.xeusxvb.x1pahc9y.x1ertn4p.xlkovuz.x16j0l1c.x1hm9lzh.xyklrzc.x1z0qo99",                
            ]
            
            lupa_encontrada = False
            for i, seletor_lupa in enumerate(seletores_lupa):
                try:
                    logging.info(f"Tentando seletor {i+1}/3: {seletor_lupa}")
                    lupa_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, seletor_lupa)))
                    logging.info(f"Ícone de pesquisa encontrado com seletor {i+1}. Clicando...")
                    lupa_btn.click()
                    logging.info("Lupa (pesquisa) clicada com sucesso.")
                    lupa_encontrada = True
                    break
                except TimeoutException:
                    logging.warning(f"Seletor {i+1} não funcionou. Tentando próximo...")
                    continue
            
            if not lupa_encontrada:
                logging.warning("Nenhum seletor de lupa funcionou. Tentando continuar...")
                pass # Continua mesmo assim
            logging.info("⏳ Aguardando 4 segundos para campo de busca aparecer...")
            print("⏳ Aguardando 4 segundos para campo de busca aparecer...")
            time.sleep(4) # Esperar mais tempo para o campo de busca aparecer

            # --- Etapa 3: Digitar termo na caixa de busca (condicional por grupo) ---
            logging.info("Procurando caixa de busca...")
            seletor_caixa_busca = "._akmh > div:nth-child(2) > div:nth-child(3) > div:nth-child(1) > div:nth-child(1) > p:nth-child(1)"
            logging.info(f"Usando seletor para caixa de busca: {seletor_caixa_busca}")
            try:
                search_box = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, seletor_caixa_busca)))
            except TimeoutException:
                logging.error("Caixa de busca não encontrada a tempo.")
                return None, None, None

            try:
                search_box.click()
            except Exception:
                pass

            try:
                termos_busca = ["meta de hoje"] if nome_grupo == "VD" else ["meta de hoje", "meta do dia"]

                for termo in termos_busca:
                    logging.info(f"Tentando buscar por '{termo}'...")
                    
                    # Limpa a caixa de busca
                    for _ in range(2):
                        search_box.send_keys(Keys.CONTROL, 'a')
                        search_box.send_keys(Keys.DELETE)
                        search_box.send_keys(Keys.BACK_SPACE)
                    time.sleep(0.5)
                    
                    # Realiza a busca
                    search_box.send_keys(termo)
                    search_box.send_keys(Keys.ENTER)
                    logging.info(f"Pesquisa realizada por '{termo}' (limpeza + Enter).")
                    logging.info("⏳ Aguardando 6 segundos para resultados da pesquisa carregarem...")
                    print(f"⏳ Aguardando 6 segundos para resultados da pesquisa '{termo}' carregarem...")
                    time.sleep(6)

                    # Verifica se há resultados
                    try:
                        container_resultados_tmp = WebDriverWait(driver, 5).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, "#pane-side > div:nth-child(1) > div > div"))
                        )
                        resultados = container_resultados_tmp.find_elements(By.XPATH, "./div")
                        
                        if not resultados:
                            logging.info(f"Nenhum resultado encontrado para '{termo}'. Tentando próximo termo...")
                            continue
                            
                        # Itera pelos resultados procurando uma mensagem de hoje
                        for resultado in resultados:
                            try:
                                elemento_periodo = resultado.find_element(By.CSS_SELECTOR, "div._ak8l > div._ak8o")
                                texto_periodo = elemento_periodo.text.strip()
                                
                                # Verifica se é uma mensagem de hoje (tem horário)
                                if re.match(r'^\d{1,2}:\d{2}(:\d{2})?$', texto_periodo):
                                    elemento_mensagem = resultado.find_element(By.CSS_SELECTOR, "div._ak8l > div._ak8j")
                                    texto_mensagem = elemento_mensagem.text.strip()
                                    
                                    # Tenta extrair a meta
                                    if nome_grupo == "LOJA":
                                        meta = extrair_meta_loja(texto_mensagem)
                                        if meta is not None:
                                            logging.info(f"Meta encontrada usando termo '{termo}'")
                                            return datetime.now().strftime("%d/%m/%Y"), None, meta
                                    
                                    elif nome_grupo == "VD":
                                        metas = extrair_metas_vd(texto_mensagem)
                                        if isinstance(metas, list) and len(metas) > 0:
                                            logging.info(f"Metas encontradas usando termo '{termo}'")
                                            return datetime.now().strftime("%d/%m/%Y"), metas, None
                            except (NoSuchElementException, StaleElementReferenceException):
                                continue
                            
                        logging.info(f"Nenhuma meta válida encontrada nos resultados de '{termo}'. Tentando próximo termo...")
                            
                    except TimeoutException:
                        logging.info(f"Timeout ao buscar resultados para '{termo}'. Tentando próximo termo...")
                        continue

                logging.warning("Nenhuma meta encontrada com nenhum dos termos de busca.")
            except Exception as e:
                logging.warning(f"Falha ao digitar na caixa de busca: {e}")
                return None, None, None

            # --- Etapa 4: Identificar resultados da pesquisa ---
            logging.info("Procurando resultados da pesquisa...")
            
            # Selector para o container dos resultados da pesquisa
            seletor_container_resultados = "#pane-side > div:nth-child(1) > div > div"
            
            logging.info(f"Usando seletor para container de resultados: {seletor_container_resultados}")

            # Espera até que o container de resultados esteja presente
            try:
                container_resultados = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, seletor_container_resultados)))
            except TimeoutException:
                 logging.warning(f"Container de resultados não encontrado a tempo no grupo {nome_grupo}")
                 return None, None, None # Retorna None para indicar falha nesta tentativa
            
            # Encontra todos os elementos filhos diretos do container (cada um é uma mensagem)
            resultados = container_resultados.find_elements(By.XPATH, "./div") 
            
            logging.info(f"Resultados encontrados: {len(resultados)}")

            if not resultados:
                logging.warning(f"⚠️ Nenhum resultado encontrado para 'meta de hoje' nesta tentativa no grupo {nome_grupo}")
                return None, None, None # Retorna None para indicar falha nesta tentativa

            data_atual_str = datetime.now().strftime("%d/%m/%Y")
            logging.info(f"Procurando metas para a data de hoje: {data_atual_str} (critério: horário)")

            # --- Etapa 5: Iterar pelos resultados e encontrar a mensagem mais recente de hoje ---
            for i, resultado in enumerate(resultados):
                try:
                    logging.debug(f"Analisando resultado #{i+1}...")
                    
                    # Selector mais direto para o texto da mensagem dentro do resultado.
                    elemento_periodo = None
                    elemento_mensagem = None
                    try:
                        elemento_periodo = resultado.find_element(By.CSS_SELECTOR, "div._ak8l > div._ak8o")
                        elemento_mensagem = resultado.find_element(By.CSS_SELECTOR, "div._ak8l > div._ak8j")
                    except NoSuchElementException:
                         logging.warning(f"Elementos de período ou mensagem não encontrados no resultado #{i+1}.")
                         continue

                    texto_periodo = elemento_periodo.text.strip()
                    
                    # Tentar extrair o texto da mensagem (focando nos spans que contêm o texto principal)
                    spans_mensagem = elemento_mensagem.find_elements(By.CSS_SELECTOR, "span")
                    if spans_mensagem:
                        texto_mensagem_parts = []
                        for s in spans_mensagem:
                            # Filtrar spans que parecem conter o conteúdo principal da mensagem
                            if s.get_attribute("class") and ("_ao3e" in s.get_attribute("class") or s.get_attribute("dir")):
                                texto_mensagem_parts.append(s.text.strip())
                        
                        if texto_mensagem_parts:
                             texto_mensagem = " ".join(texto_mensagem_parts)
                        else:
                            # Fallback se os filtros acima não funcionarem
                            texto_mensagem = " ".join([s.text.strip() for s in spans_mensagem if s.text.strip()])
                    else:
                        texto_mensagem = elemento_mensagem.text.strip()

                    if not texto_mensagem:
                        logging.warning(f"Texto da mensagem vazio no resultado #{i+1}.")
                        continue

                    logging.debug(f"Resultado #{i+1} - Período: '{texto_periodo}', Mensagem (início): '{texto_mensagem[:100]}...'")

                    # --- Etapa 6: Verificar se o período é um horário (indica mensagem de hoje) ---
                    if re.match(r'^\d{1,2}:\d{2}(:\d{2})?$', texto_periodo):
                        logging.info(f"Mensagem #{i+1} identificada como de hoje (período = horário: {texto_periodo}). Processando...")
                        
                        # --- Etapa 7: Extrair dados da mensagem identificada ---
                        if nome_grupo == "VD":
                            metas = extrair_metas_vd(texto_mensagem)
                            # Agora 'metas' é uma lista de dicts com possíveis múltiplos ciclos
                            if isinstance(metas, list) and len(metas) > 0:
                                logging.info(f"Metas VD extraídas com sucesso da mensagem #{i+1}: {metas}")
                                return data_atual_str, metas, None # Retorna lista, meta_loja é None para VD

                        elif nome_grupo == "LOJA":
                            meta_loja = extrair_meta_loja(texto_mensagem)
                            if meta_loja is not None:
                                logging.info(f"Meta LOJA extraída com sucesso da mensagem #{i+1}: {meta_loja}")
                                return data_atual_str, None, meta_loja # Retorna com a data de hoje, metas é None para LOJA
                    else:
                        logging.debug(f"Mensagem #{i+1} não é de hoje (período: {texto_periodo}). Ignorando.")

                except StaleElementReferenceException:
                    logging.warning(f"Elemento de resultado #{i+1} ficou obsoleto. Pulando...")
                    continue
                except Exception as e:
                    logging.warning(f"Erro ao analisar resultado #{i+1}: {e}", exc_info=True)
                    continue

            # Se o loop terminar sem encontrar e extrair dados válidos
            logging.warning(f"Nenhuma mensagem válida (com horário) encontrada nesta tentativa para o grupo {nome_grupo}.")
            return None, None, None # Retorna None para indicar falha nesta tentativa

        # --- Fim da função auxiliar _tentar_extrair_meta ---

        # --- Etapa Principal: Única tentativa ---
        logging.info("=== Iniciando tentativa única de extração ===")
        data_meta, metas, meta_loja = _tentar_extrair_meta()

        sucesso = False
        if nome_grupo == "VD":
            sucesso = isinstance(metas, list) and len(metas) > 0
        elif nome_grupo == "LOJA":
            sucesso = meta_loja is not None

        if sucesso:
            logging.info("✅ Tentativa única bem-sucedida. Retornando os dados.")
            try:
                botao_fechar_pesquisa = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "div[role='button'][title*='Fechar' i], div[role='button'][title*='Close' i]"))
                )
                botao_fechar_pesquisa.click()
                logging.info("Caixa de pesquisa fechada com sucesso após encontrar a meta.")
            except Exception as e:
                logging.debug(f"Não foi possível fechar a caixa de pesquisa após sucesso: {e}")
            return data_meta, metas, meta_loja
        else:
            logging.warning("❌ Nenhuma meta encontrada na tentativa única.")
        logging.info("--- Fim da busca no grupo ---")
        return None, None, None

    except TimeoutException as te:
        logging.error(f"❌ Timeout ao acessar ou interagir com elementos no grupo {nome_grupo} ({url}): {te}")
    except Exception as e:
        logging.error(f"❌ Erro ao capturar meta de {nome_grupo} ({url}): {e}", exc_info=True)
    logging.info("--- Fim da busca no grupo (com erro) ---")
    return None, None, None

# --- Funções de Persistência ---
def salvar_metas_csv(dados):
    """Salva as metas no arquivo CSV no formato: tipo;data;ciclo;valor

    Compatibilidade: se o CSV existente tiver 3 colunas (tipo;data;valor), assume ciclo = ''.
    """
    os.makedirs(os.path.dirname(CSV_FILE), exist_ok=True)
    if not dados:
        logging.warning("Nenhuma meta para salvar no arquivo.")
        print("⚠️ Nenhuma meta para salvar no arquivo.")
        return
    try:
        with open(CSV_FILE, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f, delimiter=';')
            for meta in dados:
                tipo = meta.get('tipo', '')
                data = meta.get('data', '')
                ciclo = meta.get('ciclo', '') if 'ciclo' in meta else ''
                valor = meta.get('valor', '')
                writer.writerow([tipo, data, ciclo, valor])
        logging.info(f"Arquivo CSV sobrescrito com {len(dados)} metas do dia.")
        print(f"✅ Arquivo CSV sobrescrito com {len(dados)} metas do dia.")
    except Exception as e:
        logging.error(f"Erro ao escrever no arquivo CSV: {e}")
        print(f"❌ Erro ao escrever no arquivo CSV: {e}")

# --- Função Principal ---
def main():
    """Função principal que orquestra a captura das metas."""
    driver = None
    try:
        # Não encerra apenas por existir flag; lógica já tratada no topo com parse_flag
        driver = configurar_driver()
        wait = WebDriverWait(driver, 30) # Timeout padrão
        logging.info("=== Chrome iniciado com perfil de automação dedicado. ===")
        print("🚀 Chrome iniciado com perfil de automação dedicado.")

        metas_para_salvar = []
        tipos_capturados = set()
        for nome_grupo, url in GRUPOS:
            try:
                data_meta, metas, meta_loja = buscar_meta_no_grupo(driver, wait, url, nome_grupo)

                tem_dados_para_salvar = False
                if nome_grupo == "VD" and metas:
                    if isinstance(metas, list) and len(metas) > 0:
                        tem_dados_para_salvar = True
                        for m in metas:
                            tipo_meta = m.get('tipo')
                            valor_meta = m.get('valor')
                            ciclo_meta = (m.get('ciclo') or '').strip()
                            if tipo_meta in ['PEF', 'EUD'] and valor_meta is not None:
                                metas_para_salvar.append({
                                    'tipo': tipo_meta,
                                    'data': data_meta if data_meta else datetime.now().strftime("%d/%m/%Y"),
                                    'ciclo': ciclo_meta,
                                    'valor': valor_meta
                                })
                                tipos_capturados.add(tipo_meta.upper())
                                logging.info(f"Adicionada meta {tipo_meta} (C{ciclo_meta}): {valor_meta}")
                                print(f"  ➕ Adicionada meta {tipo_meta} (C{ciclo_meta}): {valor_meta}")
                elif nome_grupo == "LOJA" and meta_loja is not None:
                    tem_dados_para_salvar = True
                    metas_para_salvar.append({
                        'tipo': 'LOJA',
                        'data': data_meta if data_meta else datetime.now().strftime("%d/%m/%Y"),
                        'valor': meta_loja
                    })
                    tipos_capturados.add('LOJA')
                    logging.info(f"Adicionada meta LOJA: {meta_loja}")
                    print(f"  ➕ Adicionada meta LOJA: {meta_loja}")

                if not tem_dados_para_salvar:
                    logging.warning(f"⚠️ Nenhuma meta significativa encontrada para o grupo {nome_grupo}")
                    print(f"⚠️ Nenhuma meta significativa encontrada para o grupo {nome_grupo}")
                    continue

            except Exception as e:
                logging.error(f"Erro ao processar grupo {nome_grupo}: {e}", exc_info=True)
                print(f"❌ Erro ao processar grupo {nome_grupo}: {e}")
                continue

        if metas_para_salvar:
            salvar_metas_csv(metas_para_salvar)
            
            # Verifica se está fora da janela de captura para decidir o tipo de flag
            if not verificar_janela_captura():
                # Fora da janela - criar flag METAS_PARCIAIS_FINAL ou COMPLETO baseado nas metas
                tentativas_existentes = obter_tentativas_existentes(FLAG_FILE)
                horario_atual = datetime.now().strftime("%H:%M")
                
                if horario_atual not in tentativas_existentes:
                    tentativas_existentes.append(horario_atual)
                
                if set(METAS_ESPERADAS).issubset(tipos_capturados):
                    # Todas as metas - flag COMPLETO normal
                    status = escrever_flag(FLAG_FILE, tipos_capturados, METAS_ESPERADAS)
                    logging.info("✅ Todas as metas capturadas. Flag COMPLETO gerado.")
                    print("✅ Todas as metas capturadas. Flag COMPLETO gerado.")
                else:
                    # Metas parciais após janela - flag METAS_PARCIAIS_FINAL
                    status = escrever_flag_tentativa(FLAG_FILE, tentativas_existentes, tipos_capturados)
                    logging.info(f"🔄 Metas parciais capturadas após janela de captura. Flag METAS_PARCIAIS_FINAL gerado: {sorted(tipos_capturados)}")
                    print(f"🔄 Metas parciais capturadas após janela de captura.")
                    print(f"✅ Metas disponíveis: {', '.join(sorted(tipos_capturados))}")
                    print(f"🚫 Metas não capturadas: {', '.join(sorted(set(METAS_ESPERADAS) - tipos_capturados))}")
                    print(f"📝 Flag METAS_PARCIAIS_FINAL criado.")
            else:
                # Dentro da janela - flag normal de captura
                status = escrever_flag(FLAG_FILE, tipos_capturados, METAS_ESPERADAS)
                if status == 'COMPLETO':
                    logging.info("✅ Todas as metas capturadas. Flag COMPLETO gerado.")
                    print("✅ Todas as metas capturadas. Flag COMPLETO gerado.")
                else:
                    logging.info("✅ Metas parciais capturadas. Flag PARCIAL gerado (haverá nova tentativa futura).")
                    print("✅ Metas parciais capturadas. Flag PARCIAL gerado (haverá nova tentativa futura).")
        else:
            # Nenhuma meta capturada - gerenciar tentativas
            tentativas_existentes = obter_tentativas_existentes(FLAG_FILE)
            horario_atual = datetime.now().strftime("%H:%M")
            
            # Adiciona horário atual às tentativas
            if horario_atual not in tentativas_existentes:
                tentativas_existentes.append(horario_atual)
            
            # Verifica se ainda está na janela de captura
            if verificar_janela_captura():
                # Dentro da janela - escreve flag de tentativa para permitir novas tentativas
                escrever_flag(FLAG_FILE, tipos_capturados, METAS_ESPERADAS)  # Flag PARCIAL
                logging.warning(f"⚠️ Nenhuma meta capturada na tentativa {horario_atual}. Tentativas realizadas: {tentativas_existentes}")
                print(f"⚠️ Nenhuma meta capturada na tentativa {horario_atual}. Tentativas: {tentativas_existentes}")
                print("⏰ Ainda dentro da janela de captura. Novas tentativas serão permitidas.")
            else:
                # Fora da janela - decide o tipo de flag baseado no que foi capturado
                if tipos_capturados:
                    # Algumas metas foram capturadas - flag METAS_PARCIAIS_FINAL
                    status = escrever_flag_tentativa(FLAG_FILE, tentativas_existentes, tipos_capturados)
                    logging.warning(f"⚠️​ Janela de captura encerrada. Metas capturadas: {sorted(tipos_capturados)}. Tentativas realizadas: {tentativas_existentes}")
                    print(f"⚠️​ Janela de captura encerrada (após 10:35h).")
                    print(f"✅ Metas capturadas: {', '.join(sorted(tipos_capturados))}")
                    print(f"🚫 Metas não capturadas: {', '.join(sorted(set(METAS_ESPERADAS) - tipos_capturados))}")
                    print(f"📝 Flag METAS_PARCIAIS_FINAL criado. Futuras execuções usarão apenas as metas disponíveis.")
                else:
                    # Nenhuma meta capturada - flag SEM_META_FINAL
                    status = escrever_flag_tentativa(FLAG_FILE, tentativas_existentes, None)
                    logging.warning(f"🚫 Janela de captura encerrada. Nenhuma meta capturada. Tentativas realizadas: {tentativas_existentes}")
                    print(f"🚫 Janela de captura encerrada (após 10:35h). Nenhuma meta capturada.")
                    print(f"📝 Flag SEM_META_FINAL criado. Futuras execuções não tentarão capturar metas hoje.")

    except Exception as e:
        logging.critical(f"Erro crítico na execução do script: {e}", exc_info=True)
        print(f"❌ Erro crítico: {e}")
    finally:
        if driver:
            try:
                driver.quit()
                logging.info("=== Chrome finalizado. ===")
                print("🛑 Chrome finalizado.")
            except Exception as e:
                logging.error(f"Erro ao finalizar o Chrome: {e}")
                print(f"⚠️ Erro ao finalizar o Chrome: {e}")

if __name__ == "__main__":
    print("Iniciando captura de metas (com retry)...")
    main()
