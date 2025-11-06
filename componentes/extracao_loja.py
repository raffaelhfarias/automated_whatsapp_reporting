import os
import sys
import time
import logging
import csv
import subprocess
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

from componentes.config import LOGIN_CONFIG, warn_if_insecure_login

# Configuração avançada de logging
def setup_logging():
    os.makedirs("log", exist_ok=True)
    
    # Cria um logger específico para o script
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    
    # Remove handlers existentes para evitar duplicação
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Formato dos logs
    formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
    
    # Handler para arquivo (DEBUG level) - modo 'w' para sobrescrever o arquivo a cada execução
    file_handler = logging.FileHandler("log/extracao_loja.log", mode='w', encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    
    # Handler para console (INFO level) - REMOVIDO para evitar duplicação no terminal
    # console_handler = logging.StreamHandler()
    # console_handler.setLevel(logging.INFO)
    # console_handler.setFormatter(formatter)
    
    # Adiciona os handlers ao logger
    logger.addHandler(file_handler)
    # logger.addHandler(console_handler)
    
    # Captura exceções não tratadas
    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
            
        logger.critical("Erro não tratado:", exc_info=(exc_type, exc_value, exc_traceback))
    
    sys.excepthook = handle_exception
    
    return logger

# Configura o logging
logger = setup_logging()

# Inicializa credenciais a partir do componentes.config (lê variáveis de ambiente)
LOGIN_URL = LOGIN_CONFIG.get("url")
USERNAME = LOGIN_CONFIG.get("username")
PASSWORD = LOGIN_CONFIG.get("password")

# Emite aviso se a senha não estiver definida (evita executar em produção sem configuração)
warn_if_insecure_login()

def _tem_processo(nome: str) -> bool:
    try:
        out = subprocess.check_output(['tasklist'], creationflags=subprocess.CREATE_NO_WINDOW).decode('utf-8', errors='ignore')
        return nome.lower() in out.lower()
    except Exception:
        return False

def _matar_processo(imagem: str):
    try:
        subprocess.run(['taskkill', '/F', '/IM', imagem], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
    except Exception as e:
        logger.debug(f"Falha ao matar {imagem}: {e}")

def limpar_processos_zumbis():
    if _tem_processo('chromedriver.exe'):
        logger.info('🔧 chromedriver.exe residual detectado. Encerrando...')
        _matar_processo('chromedriver.exe')
        time.sleep(1)
    if os.environ.get('KILL_ALL_CHROME') == '1' and _tem_processo('chrome.exe'):
        logger.info('⚠️ chrome.exe residual detectado (KILL_ALL_CHROME=1). Encerrando...')
        _matar_processo('chrome.exe')
        time.sleep(1)

def initialize_driver(retries: int = 3, wait_ready: int = 15):
    """Inicializa o driver com retries, limpeza de zumbis e readiness ativa."""
    limpar_processos_zumbis()
    last_err = None
    for tentativa in range(1, retries + 1):
        driver = None
        try:
            logger.info(f"🧪 Iniciando Chrome (tentativa {tentativa}/{retries})...")
            options = uc.ChromeOptions()
            # Opções seguras recomendadas
            options.add_argument('--start-maximized')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_argument('--disable-infobars')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-gpu')
            options.add_argument('--disable-extensions')
            options.add_argument('--disable-background-network')
            options.add_argument('--disable-background-timer-throttling')
            options.add_argument('--disable-client-side-phishing-detection')
            options.add_argument('--disable-popup-blocking')
            options.add_argument('--disable-default-apps')
            options.add_argument('--disable-hang-monitor')
            options.add_argument('--disable-prompt-on-repost')
            options.add_argument('--disable-sync')
            options.add_argument('--disable-translate')
            options.add_argument('--disable-features=TranslateUI')
            options.add_argument('--log-level=3')
            if os.environ.get('HEADLESS') == '1':
                options.add_argument('--headless=new')
            driver = uc.Chrome(options=options, use_subprocess=True, headless=False)
            try:
                driver.maximize_window()
            except Exception:
                pass
            # Evita detecção
            try:
                driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            except Exception:
                pass
            try:
                from selenium.webdriver.support.ui import WebDriverWait as _W
                _W(driver, wait_ready).until(lambda d: len(d.window_handles) > 0)
                _W(driver, wait_ready).until(lambda d: d.execute_script('return document.readyState') in ('interactive', 'complete'))
            except Exception:
                logger.debug('Readiness parcial atingida.')
            try:
                ua = driver.execute_script("return navigator.userAgent")
                if 'Headless' in ua:
                    ua = ua.replace('Headless', '')
                driver.execute_cdp_cmd('Network.setUserAgentOverride', {"userAgent": ua})
            except Exception:
                pass
            try:
                titulo = driver.title
            except Exception:
                titulo = '(sem título)'
            # Checagem extra: janela aberta
            if not driver.window_handles:
                logger.warning("Nenhuma janela aberta após inicialização. Reiniciando driver...")
                try:
                    driver.quit()
                except Exception:
                    pass
                time.sleep(2)
                continue
            logger.info(f"✅ Chrome iniciado (tentativa {tentativa}). Título inicial: {titulo}")
            return driver
        except Exception as e:
            last_err = e
            logger.warning(f"Falha ao iniciar Chrome na tentativa {tentativa}: {e}")
            if driver:
                try:
                    driver.quit()
                except Exception:
                    pass
            time.sleep(2)
    logger.error(f"❌ Falha ao iniciar Chrome após {retries} tentativas: {last_err}")
    raise RuntimeError(f"Não foi possível iniciar o Chrome: {last_err}")

def aguardar_elemento_visivel(driver, by, value, timeout=20):
    """Função auxiliar para aguardar elemento visível"""
    return WebDriverWait(driver, timeout).until(
        EC.visibility_of_element_located((by, value))
    )

def realizar_login(driver, usuario, senha, timeout=30):
    """Realiza o login no sistema com tratamento de erros e verificações"""
    try:
        # 1. Acessa a página de login
        logger.info(f"Acessando {LOGIN_URL}...")
        driver.get(LOGIN_URL)

        # 2. Aguarda carregar a página de login (verifica URL e elemento de usuário)
        WebDriverWait(driver, timeout).until(
            lambda d: d.current_url == LOGIN_URL and 
                     d.find_element(By.CSS_SELECTOR, "#username > div:nth-child(2) input").is_displayed()
        )

        # 3. Preenche usuário e senha
        logger.info("Preenchendo credenciais...")
        campo_usuario = aguardar_elemento_visivel(driver, By.CSS_SELECTOR, "#username > div:nth-child(2) input")
        campo_senha = aguardar_elemento_visivel(driver, By.CSS_SELECTOR, "#password > div:nth-child(2) input")

        # Limpa e preenche os campos um de cada vez
        for campo, valor in [(campo_usuario, usuario), (campo_senha, senha)]:
            campo.clear()
            time.sleep(0.5)
            campo.send_keys(valor)
            time.sleep(0.5)

        # 4. Clica no botão de login
        botao_entrar = aguardar_elemento_visivel(driver, By.XPATH, "//*[@id='app']/div[1]/section[2]/div/form/button")
        botao_entrar.click()
        logger.info("Login submetido. Aguardando redirecionamento...")

        # 5. Aguarda a mudança de URL (login bem-sucedido)
        WebDriverWait(driver, timeout).until(
            lambda d: d.current_url == "https://cp10356.retaguarda.grupoboticario.com.br/app/#/"
        )
        logger.info("Login realizado com sucesso!")
        time.sleep(2)  # Pequena pausa para estabilização

    except Exception as e:
        logger.error(f"Erro durante o login: {str(e)}")
        try:
            driver.quit()
            logger.info("Driver fechado após falha no login.")
        except Exception as fe:
            logger.error(f"Erro ao fechar driver após falha no login: {fe}")
        raise

def navegar_e_extrair(driver):
    logger.info("Navegando pelo menu lateral...")
    # Clicar nos menus
    for sidemenu in ["#sidemenu-item-6", "#sidemenu-item-602", "#sidemenu-item-20423"]:
        WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, sidemenu))
        )
        driver.find_element(By.CSS_SELECTOR, sidemenu).click()
        time.sleep(1)
    # Clicar no botão de consulta
    WebDriverWait(driver, 20).until(
        EC.element_to_be_clickable((By.XPATH, "//*[@id='app']/div[1]/div/main/div/section/section/div/div/footer/button[2]"))
    )
    driver.find_element(By.XPATH, "//*[@id='app']/div[1]/div/main/div/section/section/div/div/footer/button[2]").click()
    logger.info("Consulta submetida. Aguardando tabela de resultados...")
    # Espera a tabela aparecer
    WebDriverWait(driver, 30).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, ".flora-table"))
    )
    time.sleep(2)  # Pequeno delay para garantir renderização
    logger.info("Extraindo dados da tabela...")
    tabela = driver.find_element(By.CSS_SELECTOR, ".flora-table")
    linhas = tabela.find_elements(By.CSS_SELECTOR, ".flora-table-row")
    resultados = []
    
    # Exclui a última linha (que contém o total) e processa as demais
    for i, linha in enumerate(linhas[:-1]):  # Exclui a última linha com [:-1]
        try:
            loja = linha.find_element(By.CSS_SELECTOR, "div.flora-table-cell:nth-child(1)").text.strip()
            gmv = linha.find_element(By.CSS_SELECTOR, "div.flora-table-cell:nth-child(3)").text.strip()

            # Limpa o valor GMV removendo R$, espaços e convertendo vírgula para ponto
            if gmv:
                gmv_limpo = gmv.replace('R$', '').replace(' ', '').strip()
                gmv_limpo = gmv_limpo.replace('.', '').replace(',', '.')
                try:
                    float(gmv_limpo)
                    gmv = gmv_limpo
                except ValueError:
                    logger.warning(f"Valor GMV não pôde ser convertido: '{gmv}' -> '{gmv_limpo}'")

            # Só adiciona se tiver dados válidos
            if loja and gmv:
                resultados.append([loja, gmv])
        except Exception as e:
            logger.warning(f"Linha ignorada por erro: {e}")
    
    logger.info(f"Total de linhas extraídas (excluindo total): {len(resultados)}")
    logger.info("Última linha (total) foi excluída - o total será calculado automaticamente")
    
    # Salva em CSV
    os.makedirs("extracoes", exist_ok=True)
    output_file = "extracoes/resultado_loja.csv"
    with open(output_file, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["Loja", "GMV"])
        writer.writerows(resultados)
    logger.info("Resultados salvos em extracoes/resultado_loja.csv")

def main():
    driver = None
    sucesso = False
    try:
        logger.info("Iniciando o processo de extração de dados...")
        driver = initialize_driver()

        logger.info("Iniciando login...")
        realizar_login(driver, USERNAME, PASSWORD)
        logger.info("Login realizado com sucesso!")

        logger.info("Iniciando navegação e extração de dados...")
        navegar_e_extrair(driver)
        logger.info("Processo de extração concluído com sucesso!")
        sucesso = True

    except Exception as e:
        logger.critical(f"Falha crítica no processo: {str(e)}", exc_info=True)
    finally:
        if driver:
            try:
                driver.quit()
                logger.info("Navegador fechado com sucesso.")
            except Exception as e:
                logger.error(f"Erro ao fechar o navegador: {e}")
        if sucesso:
            print("✅ Resultado extraído com sucesso!")
        else:
            print("❌ Ocorreu um erro durante a extração. Veja o log para detalhes.")

if __name__ == "__main__":
    main() 