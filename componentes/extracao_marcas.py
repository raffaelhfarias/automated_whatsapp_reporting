"""
Extração de Marcas - BOT, OUI, QDB
Extrai totais gerais por marca para envio às 18h.
"""

import os
import sys
import time
import csv
import logging
import subprocess
from datetime import datetime

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException


LOGIN_URL = "https://sgi.e-boticario.com.br/Paginas/Acesso/Entrar.aspx?ReturnUrl=%2fDefault.aspx"

# Configuração das marcas
MARCAS_CONFIG = {
    'BOT': {'codigo': '1', 'nome': 'BOT'},
    'OUI': {'codigo': '26367', 'nome': 'OUI'},
    'QDB': {'codigo': '38489', 'nome': 'QDB'}
}

def setup_logging():
    """Configura o logger para arquivo e console."""
    os.makedirs("log", exist_ok=True)
    logger = logging.getLogger("extracao_marcas")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    file_handler = logging.FileHandler("log/extracao_marcas.log", mode="w", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    # Removido console_handler para evitar duplicação no terminal
    logger.addHandler(file_handler)
    
    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        logger.critical("Erro não tratado:", exc_info=(exc_type, exc_value, exc_traceback))
    sys.excepthook = handle_exception
    return logger

logger = setup_logging()

def _tem_processo(nome):
    try:
        out = subprocess.check_output(['tasklist'], creationflags=subprocess.CREATE_NO_WINDOW).decode('utf-8', errors='ignore')
        return nome.lower() in out.lower()
    except Exception:
        return False

def _matar_processo(imagem):
    try:
        subprocess.run(['taskkill', '/F', '/IM', imagem], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
    except Exception as e:
        logger.debug(f"Falha ao matar {imagem}: {e}")

def limpar_processos_zumbis():
    """Fecha processos chromedriver.exe remanescentes."""
    if _tem_processo('chromedriver.exe'):
        logger.info('🔧 Encontrado chromedriver.exe residual. Encerrando...')
        _matar_processo('chromedriver.exe')
        time.sleep(1)
    if os.environ.get('KILL_ALL_CHROME') == '1' and _tem_processo('chrome.exe'):
        logger.info('⚠️ Encerrando chrome.exe residual (KILL_ALL_CHROME=1)')
        _matar_processo('chrome.exe')
        time.sleep(1)

def iniciar_navegador(retries: int = 3, wait_ready: int = 15):
    """Inicializa o navegador Chrome de forma resiliente."""
    limpar_processos_zumbis()
    last_err = None
    for tentativa in range(1, retries + 1):
        driver = None
        try:
            logger.info(f"🧪 Iniciando navegador (tentativa {tentativa}/{retries})...")
            options = uc.ChromeOptions()
            options.add_argument('--start-maximized')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_argument('--disable-infobars')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-gpu')
            options.add_argument('--disable-extensions')
            
            if os.environ.get('HEADLESS') == '1':
                options.add_argument('--headless=new')
            
            driver = uc.Chrome(options=options, use_subprocess=True, headless=False)
            
            try:
                driver.maximize_window()
            except Exception:
                pass
            
            try:
                handles = driver.window_handles
                if not handles:
                    raise Exception("Nenhuma janela disponível após inicialização")
            except Exception as e:
                logger.warning(f"Falha na verificação de janelas: {e}")
                if driver:
                    try:
                        driver.quit()
                    except Exception:
                        pass
                raise
            
            try:
                driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            except Exception:
                pass
            
            logger.info(f"✅ Navegador iniciado (tentativa {tentativa})")
            return driver
        except Exception as e:
            last_err = e
            logger.warning(f"Falha ao iniciar navegador na tentativa {tentativa}: {e}")
            try:
                if driver:
                    driver.quit()
            except Exception:
                pass
            time.sleep(2)
    
    logger.error(f"❌ Falha ao iniciar navegador após {retries} tentativas: {last_err}")
    raise RuntimeError(f"Selenium não conseguiu iniciar controle do navegador: {last_err}")

def aguardar_e_clicar(driver, seletor, by=By.CSS_SELECTOR, timeout=10):
    """Aguarda o elemento estar clicável e clica."""
    elem = WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable((by, seletor))
    )
    elem.click()
    return elem

def aguardar_loader_flexivel(driver, timeout=30):
    """Aguarda o loader .sgi-loading sumir (aria-hidden='true')."""
    def loader_inativo(d):
        try:
            loader = d.find_element(By.CSS_SELECTOR, "#UpdateProgress1")
            aria = loader.get_attribute("aria-hidden")
            return aria == "true"
        except Exception:
            return True
    WebDriverWait(driver, timeout).until(loader_inativo)

def realizar_login(driver):
    """Realiza o login no site alvo."""
    try:
        if not driver or not driver.window_handles:
            raise Exception("Driver inválido ou sem janelas ativas")
            
        driver.get(LOGIN_URL)
        logger.info("Aguardando página de login carregar...")
        
        WebDriverWait(driver, 15).until(
            lambda d: d.current_url.startswith(LOGIN_URL) and 
            d.find_element(By.CSS_SELECTOR, "#ctl00 > main").is_displayed()
        )
        
        aguardar_e_clicar(driver, "#ctl00 > main > div.login__content > div > div.mdc-card__content > div.login__bottom > div")
        logger.info("Clicando em 'entrar como colaborador de franqueado'...")
        aguardar_e_clicar(driver, "#GoogleExchange")
        logger.info("Iniciando processo de login do Gmail...")
        
        email_field = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "#identifierId"))
        )
        google_email = os.getenv('GOOGLE_EMAIL', '')
        if not google_email:
            logger.warning('GOOGLE_EMAIL não definido no ambiente; login pode falhar')
        email_field.send_keys(google_email)
        logger.info("Clicando em avançar após email...")
        aguardar_e_clicar(driver, "#identifierNext > div > button > span")
        time.sleep(1)
        
        password_field = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "#password > div.aCsJod.oJeWuf > div > div.Xb9hP > input"))
        )
        google_password = os.getenv('GOOGLE_PASSWORD', '')
        if not google_password:
            logger.warning('GOOGLE_PASSWORD não definido no ambiente; login pode falhar')
        password_field.send_keys(google_password)
        time.sleep(1)
        
        logger.info("Clicando em avançar após senha...")
        aguardar_e_clicar(driver, "#passwordNext > div > button")
        logger.info("Aguardando redirecionamento após login...")
        
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "#menu-cod-8 > a:nth-child(1)"))
        )
        logger.info("Login realizado com sucesso!")
        
    except Exception as e:
        logger.error(f"Erro durante o login: {str(e)}")
        try:
            if driver:
                driver.quit()
                logger.info("Driver fechado após falha no login")
        except Exception as fe:
            logger.error(f"Erro ao fechar driver após falha no login: {fe}")
        raise

def navegar_para_ranking_vendas(driver):
    """Navega para a página de Ranking de Vendas."""
    aguardar_e_clicar(driver, "#menu-cod-8 > a:nth-child(1)")
    time.sleep(2)
    aguardar_e_clicar(driver, "#submenu-cod-8 > div:nth-child(1) > div:nth-child(1) > ul:nth-child(1) > li:nth-child(10)")
    time.sleep(2)
    aguardar_e_clicar(driver, ".submenu-select > ul:nth-child(2) > li:nth-child(5)")
    aguardar_loader_flexivel(driver)

def ler_ciclos_de_hoje(meta_csv_path=os.path.join("extracoes", "meta_dia.csv")):
    """Lê os ciclos de hoje no meta_dia.csv. Retorna lista ordenada de inteiros únicos."""
    ciclos = set()
    if not os.path.exists(meta_csv_path):
        return []
    hoje = datetime.now().strftime("%d/%m/%Y")
    try:
        with open(meta_csv_path, "r", encoding="utf-8") as f:
            for line in f:
                partes = [p.strip() for p in line.strip().split(";")]
                if len(partes) == 4:
                    tipo, data_str, ciclo_str, _valor = partes
                else:
                    continue
                tipo = (tipo or "").upper()
                if tipo not in ("PEF", "EUD", "EUDORA"):
                    continue
                if data_str != hoje:
                    continue
                if ciclo_str and ciclo_str.isdigit():
                    try:
                        ciclos.add(int(ciclo_str))
                    except Exception:
                        pass
    except Exception as e:
        logger.warning(f"Falha ao ler ciclos do meta_dia.csv: {e}")
    return sorted(ciclos)

def extrair_marca(driver, marca_key, ciclo):
    """Extrai uma marca específica por código de estrutura de produto."""
    marca_info = MARCAS_CONFIG[marca_key]
    codigo = marca_info['codigo']
    nome = marca_info['nome']
    
    logger.info(f"Extraindo {nome} (código {codigo}) para ciclo {ciclo}...")
    
    try:
        # Navega para Ranking de Vendas
        navegar_para_ranking_vendas(driver)
        
        # Preenche código da estrutura de produto
        campo_cod = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "#ContentPlaceHolder1_txtEstruturaProdutoCodigo_T2"))
        )
        campo_cod.clear()
        campo_cod.send_keys(codigo)
        campo_cod.send_keys(Keys.TAB)
        time.sleep(1)
        
        # Configura data início (hoje)
        aguardar_e_clicar(driver, "#ContentPlaceHolder1_cedDataFaturamentoInicio_s1a")
        aguardar_e_clicar(driver, ".ajax__calendar_container > span:nth-child(3)")
        
        # Configura data fim (hoje)
        aguardar_e_clicar(driver, "#ContentPlaceHolder1_cedDataFaturamentoFim_s1a")
        aguardar_e_clicar(driver, "div.linha_form:nth-child(2) > span:nth-child(4) > span:nth-child(6) > div:nth-child(1) > span:nth-child(3)")
        
        # Configura ciclo usando value ao invés de nth-child
        from datetime import datetime
        ano_atual = datetime.now().year
        ciclo_formatado = f"{ciclo:02d}"
        value_esperado = f"{ano_atual}{ciclo_formatado}"
        
        aguardar_e_clicar(driver, "#ContentPlaceHolder1_ddlCicloFaturamentoInicial_d1")
        opc_inicio = f"#ContentPlaceHolder1_ddlCicloFaturamentoInicial_d1 > option[value='{value_esperado}']"
        aguardar_e_clicar(driver, opc_inicio)
        
        aguardar_e_clicar(driver, "#ContentPlaceHolder1_ddlCicloFaturamentoFinal_d1")
        opc_fim = f"#ContentPlaceHolder1_ddlCicloFaturamentoFinal_d1 > option[value='{value_esperado}']"
        aguardar_e_clicar(driver, opc_fim)
        
        # Situação Fiscal: Só Faturados
        aguardar_e_clicar(driver, "#ContentPlaceHolder1_ddlSituacaoFiscal_d1")
        aguardar_e_clicar(driver, "#ContentPlaceHolder1_ddlSituacaoFiscal_d1 > option:nth-child(3)")
        
        # Agrupamento: Total Geral (não por VD)
        # Mantém o agrupamento padrão (Total Geral)
        
        # Clica em Buscar
        aguardar_e_clicar(driver, "#ContentPlaceHolder1_btnBuscar_btn")
        
        # Aguarda loader
        def loader_ok(d):
            try:
                el = d.find_element(By.CSS_SELECTOR, "#UpdateProgress1")
                return el.get_attribute("aria-hidden") == "true"
            except Exception:
                return True
        WebDriverWait(driver, 60).until(loader_ok)
        
        # Verifica se há mensagem de "sem resultados"
        try:
            painel_mensagem = WebDriverWait(driver, 3).until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, "#mensagemPanel"))
            )
            try:
                ok_btn = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "#popupOkButton"))
                )
                ok_btn.click()
            except Exception:
                pass
            logger.info(f"Nenhum resultado para {nome} no ciclo {ciclo}")
            return 0.0
        except Exception:
            pass
        
        # Extrai valor da tabela
        try:
            tabela = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "#ContentPlaceHolder1_grdRankingVendas"))
            )
            linhas = tabela.find_elements(By.CSS_SELECTOR, "tr")
            
            # Procura pela primeira linha com dados (ignora cabeçalho)
            for linha in linhas:
                tds = linha.find_elements(By.CSS_SELECTOR, "td.grid_celula")
                
                # Log para debug: mostra quantidade de colunas
                logger.debug(f"Linha com {len(tds)} colunas para {nome}")
                
                if len(tds) >= 4:
                    # A tabela sempre tem as seguintes colunas:
                    # [0]=Qtd. Itens, [1]=Qtd. Revendedor, [2]=Faturamento, [3]=Valor Praticado, [4]=Valor Venda
                    # O "Valor Praticado" está sempre na coluna 3 (tds[3])
                    
                    valor_praticado = tds[3].text.strip()
                    logger.debug(f"Extraindo Valor Praticado da coluna 3: {valor_praticado}")
                    
                    valor_praticado_num = valor_praticado.replace('.', '').replace(',', '.')
                    try:
                        valor_float = float(valor_praticado_num)
                        logger.info(f"{nome} ciclo {ciclo}: R$ {valor_float:,.2f}")
                        return valor_float
                    except ValueError:
                        logger.warning(f"Valor inválido para {nome}: '{valor_praticado}'")
                        return 0.0
            
            logger.warning(f"Nenhuma linha de dados encontrada para {nome}")
            return 0.0
            
        except Exception as e:
            logger.error(f"Erro ao extrair valor de {nome}: {e}")
            return 0.0
            
    except Exception as e:
        logger.error(f"Erro ao extrair {nome} ciclo {ciclo}: {e}", exc_info=True)
        return 0.0

def salvar_resultados_marcas(resultados, ciclo):
    """Salva os resultados das marcas em CSV."""
    os.makedirs("extracoes", exist_ok=True)
    output_path = os.path.join("extracoes", f"resultado_marcas_C{ciclo}.csv")
    
    with open(output_path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Marca", "Valor"])
        for marca, valor in resultados.items():
            writer.writerow([marca, valor])
    
    logger.info(f"Resultados de marcas salvos em {output_path}")

def main():
    """Função principal de execução."""
    logger.info("🚀 Iniciando extração de MARCAS (BOT, OUI, QDB)")
    print("Iniciando extração de MARCAS...")
    
    driver = None
    sucesso = False
    
    try:
        # Inicia navegador
        driver = iniciar_navegador()
        realizar_login(driver)
        logger.info("Login realizado com sucesso!")
        print("Login realizado com sucesso!")
        
        # Lê ciclos do dia
        ciclos = ler_ciclos_de_hoje()
        if not ciclos:
            ciclos = [15]  # Ciclo padrão
        
        logger.info(f"Ciclos capturados: {ciclos}")
        print(f"Ciclos capturados: {ciclos}")
        
        # Extrai cada ciclo
        for ciclo in ciclos:
            logger.info(f"Processando ciclo {ciclo}...")
            print(f"\nProcessando ciclo {ciclo}...")
            
            resultados = {}
            for marca_key in ['BOT', 'OUI', 'QDB']:
                valor = extrair_marca(driver, marca_key, ciclo)
                resultados[marca_key] = valor
                time.sleep(2)  # Pausa entre extrações
            
            # Salva resultados do ciclo
            salvar_resultados_marcas(resultados, ciclo)
            print(f"Ciclo {ciclo} concluído: BOT={resultados['BOT']:.2f}, OUI={resultados['OUI']:.2f}, QDB={resultados['QDB']:.2f}")
        
        sucesso = True
        logger.info("✅ Extração de MARCAS finalizada com sucesso!")
        print("\n✅ Extração de MARCAS finalizada com sucesso!")
        
    except Exception as e:
        logger.error(f"❌ Erro durante a extração de MARCAS: {e}", exc_info=True)
        print(f"\n❌ Erro durante a extração: {e}")
    
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass
        logger.info("Navegador fechado.")
        
        if sucesso:
            print("✅ Processo concluído com sucesso.")
        else:
            print("❌ Processo finalizado com erro. Consulte o log.")

if __name__ == "__main__":
    main()
