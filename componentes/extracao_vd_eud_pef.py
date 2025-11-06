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

def setup_logging():
    """Configura o logger para arquivo e console."""
    os.makedirs("log", exist_ok=True)
    logger = logging.getLogger("extracao_vd_eud_pef")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    file_handler = logging.FileHandler("log/extracao_vd_eud_pef.log", mode="w", encoding="utf-8")
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
    """Fecha processos chromedriver.exe remanescentes e (opcional) chrome.exe se variável pedir.

    Para evitar encerrar sessão de usuário, só mata chrome.exe se a env KILL_ALL_CHROME=1.
    """
    if _tem_processo('chromedriver.exe'):
        logger.info('🔧 Encontrado chromedriver.exe residual. Encerrando...')
        _matar_processo('chromedriver.exe')
        time.sleep(1)
    if os.environ.get('KILL_ALL_CHROME') == '1' and _tem_processo('chrome.exe'):
        logger.info('⚠️ Encerrando chrome.exe residual (KILL_ALL_CHROME=1)')
        _matar_processo('chrome.exe')
        time.sleep(1)

def iniciar_navegador(retries: int = 3, wait_ready: int = 15):
    """Inicializa o navegador Chrome de forma resiliente com retries e readiness.

    Passos:
    - Limpa processos zumbis de chromedriver (e opcionalmente chrome se KILL_ALL_CHROME=1)
    - Tenta iniciar o Chrome até 'retries' vezes
    - Ajusta userAgent removendo 'Headless'
    - Aguarda window handle e readyState
    - Injeta script para ocultar navigator.webdriver
    """
    limpar_processos_zumbis()
    last_err = None
    for tentativa in range(1, retries + 1):
        driver = None
        try:
            logger.info(f"🧪 Iniciando navegador (tentativa {tentativa}/{retries})...")
            options = uc.ChromeOptions()
            # Opções seguras recomendadas
            options.add_argument('--start-maximized')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_argument('--disable-infobars')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-gpu')
            options.add_argument('--disable-extensions')
            options.add_argument('--disable-background-networking')
            options.add_argument('--disable-background-timer-throttling')
            options.add_argument('--disable-backgrounding-occluded-windows')
            options.add_argument('--disable-breakpad')
            options.add_argument('--disable-client-side-phishing-detection')
            options.add_argument('--disable-default-apps')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-features=IsolateOrigins,site-per-process,TranslateUI')
            options.add_argument('--disable-hang-monitor')
            options.add_argument('--disable-ipc-flooding-protection')
            options.add_argument('--disable-popup-blocking')
            options.add_argument('--disable-prompt-on-repost')
            options.add_argument('--disable-renderer-backgrounding')
            options.add_argument('--disable-sync')
            options.add_argument('--force-color-profile=srgb')
            options.add_argument('--ignore-certificate-errors')
            options.add_argument('--log-level=3')
            options.add_argument('--metrics-recording-only')
            options.add_argument('--no-first-run')
            if os.environ.get('HEADLESS') == '1':
                options.add_argument('--headless=new')
            # Permitir especificar um perfil custom (mitiga fechamentos imediatos em alguns ambientes)
            user_data_dir = os.environ.get('CHROME_USER_DATA')
            if user_data_dir:
                options.add_argument(f'--user-data-dir={user_data_dir}')
            driver = uc.Chrome(options=options, use_subprocess=True, headless=False)
            # Maximiza (ignora erros em headless)
            try:
                driver.maximize_window()
            except Exception:
                pass
            
            # Verifica se a janela está realmente aberta
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
                
            # Oculta webdriver
            try:
                driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            except Exception:
                pass
            # Readiness
            try:
                from selenium.webdriver.support.ui import WebDriverWait as _W
                _W(driver, wait_ready).until(lambda d: len(d.window_handles) > 0)
                _W(driver, wait_ready).until(lambda d: d.execute_script('return document.readyState') in ('interactive', 'complete'))
            except Exception:
                logger.debug('Readiness parcial atingida.')
            # Ajusta userAgent removendo "Headless"
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
                titulo = '(sem título ainda)'
            logger.info(f"✅ Navegador iniciado (tentativa {tentativa}). Título: {titulo}")
            return driver
        except Exception as e:
            last_err = e
            logger.warning(f"Falha ao iniciar navegador na tentativa {tentativa}: {e}")
            try:
                driver.quit()
            except Exception:
                pass
            time.sleep(2)
    logger.error(f"❌ Falha ao iniciar navegador após {retries} tentativas: {last_err}")
    raise RuntimeError(f"Selenium não conseguiu iniciar controle do navegador: {last_err}")

def fechar_overlays(driver):
    """Tenta fechar/ocultar overlays/modais que podem interceptar cliques."""
    try:
        body = driver.find_element(By.TAG_NAME, "body")
        body.send_keys(Keys.ESCAPE)
    except Exception:
        pass
    try:
        js = (
            "(function(){var ids=['mpeMensagem_backgroundElement'];"
            "ids.forEach(function(id){var el=document.getElementById(id);if(el){el.parentNode&&el.parentNode.removeChild(el);}});"
            "var cls=document.getElementsByClassName('modal_popup_bg');while(cls.length){cls[0].parentNode&&cls[0].parentNode.removeChild(cls[0]);}})();"
        )
        driver.execute_script(js)
    except Exception:
        pass
def ocultar_painel_superior(driver, timeout: int = 3):
    """Tenta fechar o painel superior (aviso) que aparece após o login.

    O painel tem um botão com classe 'btn-close' que chama a função
    `ocultarPainelSuperior()` via onclick. Tentamos clicar no botão; se
    não for possível, executamos o script JS que aciona a função ou
    dispara o botão hidden `ocultarPainelSuperiorButton`.
    """
    try:
        # Tenta clicar no "X" visível
        btn = WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "#painelSuperior .btn-close, .top_panel .btn-close"))
        )
        try:
            btn.click()
            logger.info("Painel superior fechado via clique no botão .btn-close")
            return True
        except Exception:
            pass
    except Exception:
        # Não encontrou o botão clicável no tempo
        pass

    # Fallbacks via JS: tenta invocar a função global ou clicar no input hidden
    try:
        js = (
            "(function(){"
            "var fn = window.ocultarPainelSuperior; if(typeof fn === 'function'){ try{ fn(); return true;}catch(e){} }"
            "var btn = document.querySelector('#painelSuperior .btn-close, .top_panel .btn-close'); if(btn){ try{ btn.click(); return true;}catch(e){} }"
            "var hidden = document.getElementById('ocultarPainelSuperiorButton'); if(hidden){ try{ hidden.click(); return true;}catch(e){} }"
            "return false; })();"
        )
        res = driver.execute_script(js)
        if res:
            logger.info("Painel superior fechado via JS fallback")
            return True
    except Exception as e:
        logger.debug(f"Falha ao tentar ocultar painel superior via JS: {e}")

    logger.info("Nenhum painel superior detectado ou falha ao fechá-lo")
    return False

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
            logger.info(f"Loader encontrado. aria-hidden={aria}")
            return aria == "true"
        except Exception:
            logger.info("Loader .sgi-loading não encontrado no DOM.")
            return True
    WebDriverWait(driver, timeout).until(loader_inativo)

def aguardar_ciclo_loader(driver, appear_timeout=3, disappear_timeout=30):
    """Aguarda o ciclo de processamento sem travar a automação."""
    def loader_visivel(d):
        try:
            el = d.find_element(By.CSS_SELECTOR, "#UpdateProgress1")
            aria = el.get_attribute("aria-hidden")
            return aria is not None and aria.lower() != "true"
        except Exception:
            return False

    def pronto(d):
        try:
            el = d.find_element(By.CSS_SELECTOR, "#UpdateProgress1")
            aria = el.get_attribute("aria-hidden")
            if aria == "true":
                return True
        except Exception:
            return True
        try:
            tabelas = d.find_elements(By.CSS_SELECTOR, "table[id*='grdRankingVendas']")
            for t in tabelas:
                linhas = t.find_elements(By.CSS_SELECTOR, "tr")
                if len(linhas) > 1:
                    return True
                if t.find_elements(By.CSS_SELECTOR, "td.grid_celula"):
                    return True
        except Exception:
            pass
        return False

    try:
        WebDriverWait(driver, appear_timeout).until(loader_visivel)
        logger.info("Loader ficou visível (início do processamento)")
    except Exception:
        logger.info("Loader não ficou visível no tempo de espera; prosseguindo para aguardar prontidão")
    try:
        WebDriverWait(driver, disappear_timeout).until(pronto)
    except TimeoutException:
        logger.warning("Timeout aguardando loader/grid; prosseguindo assim mesmo para evitar travas.")
    logger.info("Condição de prontidão atingida (loader oculto ou grid pronta)")

def realizar_login(driver):
    """Realiza o login no site alvo."""
    try:
        # Verifica se o driver está ativo antes de tentar login
        if not driver or not driver.window_handles:
            raise Exception("Driver inválido ou sem janelas ativas")
            
        driver.get(LOGIN_URL)
        logger.info("Aguardando página de login carregar...")
        
        # Verifica se a página carregou corretamente
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
        # Ler credenciais do ambiente: GOOGLE_EMAIL / GOOGLE_PASSWORD
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
        # Tenta fechar painel superior de aviso caso apareça
        try:
            ocultar_painel_superior(driver)
        except Exception as e:
            logger.debug(f"Falha ao tentar ocultar painel superior após login: {e}")
        
    except Exception as e:
        logger.error(f"Erro durante o login: {str(e)}")
        # Fecha o driver em caso de falha
        try:
            if driver:
                driver.quit()
                logger.info("Driver fechado após falha no login")
        except Exception as fe:
            logger.error(f"Erro ao fechar driver após falha no login: {fe}")
        raise

def navegar_para_ranking_vendas(driver):
    # Menu Marketing
    aguardar_e_clicar(driver, "#menu-cod-8 > a:nth-child(1)")
    # Espera 2 segundo antes de clicar em Consultas
    time.sleep(2)
    # Tópico Consultas
    aguardar_e_clicar(driver, "#submenu-cod-8 > div:nth-child(1) > div:nth-child(1) > ul:nth-child(1) > li:nth-child(10)")
    # Espera 2 segundo antes de clicar em Ranking Vendas
    time.sleep(2)    
    # Subtópico Consultar Ranking Vendas
    aguardar_e_clicar(driver, ".submenu-select > ul:nth-child(2) > li:nth-child(5)")
    aguardar_loader_flexivel(driver)

def extrair_e_salvar_resultados(driver, output_path=os.path.join("extracoes", "resultado.csv")):
    """Extrai a grid de Ranking de Vendas (VD) e salva em CSV. Se não houver resultados, salva CSV vazio."""
    logger.info("Iniciando extração dos resultados da tabela.")
    try:
        aguardar_loader_flexivel(driver)
        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "#ContentPlaceHolder1_grdRankingVendas"))
            )
        except TimeoutException:
            logger.info("Grid não apareceu em 15s, verificando mensagem de vazio...")
            vazio = False
            try:
                msg_vazio = driver.find_elements(
                    By.XPATH,
                    "//*[contains(translate(., 'NENHUM', 'nenhum'), 'nenhum')] | "
                    "//*[contains(translate(., 'REGISTRO', 'registro'), 'registro')] | "
                    "//*[contains(., 'Sem resultados')]",
                )
                if msg_vazio:
                    vazio = True
            except Exception:
                pass
            if vazio:
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                with open(output_path, mode="w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(["VD", "Valor Praticado"])
                logger.warning(f"Sem resultados. Arquivo vazio salvo em {output_path}")
                return
            else:
                raise
    except TimeoutException:
        logger.error("Timeout ao esperar pela tabela de resultados. Possíveis causas: página não carregou corretamente, seletor mudou, ou login falhou.")
        raise

    tabela = driver.find_element(By.CSS_SELECTOR, "#ContentPlaceHolder1_grdRankingVendas")
    linhas = tabela.find_elements(By.CSS_SELECTOR, "tr")
    resultados = []
    for linha in linhas:
        tds = linha.find_elements(By.CSS_SELECTOR, "td.grid_celula")
        if len(tds) >= 5:
            gerencia = tds[0].text.strip()
            valor_praticado = tds[4].text.strip()
            valor_praticado_num = valor_praticado.replace('.', '').replace(',', '.')
            try:
                valor_praticado_float = float(valor_praticado_num)
            except ValueError:
                logger.warning(f"Valor inválido para conversão: '{valor_praticado}' (VD: {gerencia})")
                valor_praticado_float = ''
            resultados.append([gerencia, valor_praticado_float])

    logger.info(f"Total de resultados extraídos: {len(resultados)}")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["VD", "Valor Praticado"])
        writer.writerows(resultados)
    logger.info(f"Resultados salvos em {output_path}")

def ler_ciclos_de_hoje(meta_csv_path=os.path.join("extracoes", "meta_dia.csv")):
    """Lê os ciclos de hoje no meta_dia.csv para tipos PEF/EUD. Retorna lista ordenada crescente de inteiros únicos."""
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

def selecionar_ciclo(driver, ciclo: int):
    """
    Seleciona ciclo pelos dropdowns usando o atributo 'value'.
    
    Args:
        ciclo: Número do ciclo (ex: 12, 13, 15)
    
    O value do option segue o padrão AAAANN onde AAAA é o ano e NN é o ciclo.
    Exemplo: ciclo 15 de 2025 = value "202515"
    """
    # Obtém o ano atual
    ano_atual = datetime.now().year
    ciclo_formatado = f"{ciclo:02d}"  # Garante 2 dígitos (ex: 12 -> "12", 5 -> "05")
    value_esperado = f"{ano_atual}{ciclo_formatado}"
    
    logger.info(f"Selecionando ciclo {ciclo} do ano {ano_atual} (value={value_esperado})")
    
    try:
        # Ciclo INÍCIO
        aguardar_e_clicar(driver, "div.linha_form:nth-child(4) > span:nth-child(3) > span:nth-child(2) > span:nth-child(1)")
        WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, "#ContentPlaceHolder1_ddlCicloFaturamentoInicial_d1"))
        )
        
        # Seleciona pelo value ao invés de nth-child
        seletor_inicio = f"#ContentPlaceHolder1_ddlCicloFaturamentoInicial_d1 > option[value='{value_esperado}']"
        try:
            aguardar_e_clicar(driver, seletor_inicio, timeout=10)
        except TimeoutException:
            elem = driver.find_element(By.CSS_SELECTOR, seletor_inicio)
            driver.execute_script("arguments[0].selected = true; arguments[0].parentNode.dispatchEvent(new Event('change'));", elem)
        
        aguardar_ciclo_loader(driver)
        logger.info(f"Selecionado ciclo INÍCIO: {ciclo}/{ano_atual} (value={value_esperado})")
    except Exception as e:
        logger.warning(f"Falha ao selecionar ciclo INÍCIO {ciclo}: {e}")
    
    time.sleep(0.2)
    
    try:
        # Ciclo FIM
        aguardar_e_clicar(driver, "div.linha_form:nth-child(4) > span:nth-child(3) > span:nth-child(2) > span:nth-child(3)")
        WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, "#ContentPlaceHolder1_ddlCicloFaturamentoFinal_d1"))
        )
        
        # Seleciona pelo value ao invés de nth-child
        seletor_fim = f"#ContentPlaceHolder1_ddlCicloFaturamentoFinal_d1 > option[value='{value_esperado}']"
        try:
            aguardar_e_clicar(driver, seletor_fim, timeout=10)
        except TimeoutException:
            elem = driver.find_element(By.CSS_SELECTOR, seletor_fim)
            driver.execute_script("arguments[0].selected = true; arguments[0].parentNode.dispatchEvent(new Event('change'));", elem)
        
        aguardar_ciclo_loader(driver)
        logger.info(f"Selecionado ciclo FIM: {ciclo}/{ano_atual} (value={value_esperado})")
    except Exception as e:
        logger.warning(f"Falha ao selecionar ciclo FIM {ciclo}: {e}")
    
    try:
        body = WebDriverWait(driver, 2).until(EC.presence_of_element_located((By.CSS_SELECTOR, "body")))
        try:
            body.send_keys(Keys.ESCAPE)
        except Exception:
            pass
        driver.execute_script("document.activeElement && document.activeElement.blur && document.activeElement.blur();")
    except Exception:
        pass
    time.sleep(0.2)

def clicar_buscar_seguro(driver, timeout=15):
    """Tenta clicar no botão Buscar. Se não estiver clicável, usa JavaScript como fallback."""
    seletor = "#ContentPlaceHolder1_btnBuscar_btn"
    try:
        aguardar_e_clicar(driver, seletor, timeout=timeout)
    except TimeoutException:
        try:
            elem = driver.find_element(By.CSS_SELECTOR, seletor)
            driver.execute_script("arguments[0].click();", elem)
        except Exception as e:
            logger.error(f"Falha ao acionar botão Buscar: {e}")
            raise


def preencher_e_extrair_eudora(driver, ciclos):
    """Executa a extração EUDORA para cada ciclo informado."""
    ano_atual = datetime.now().year
    
    for ciclo in ciclos:
        try:
            print(f"Extraindo EUDORA ciclo {ciclo}...")
            aguardar_e_clicar(driver, "#menu-cod-8")
            aguardar_e_clicar(driver, "#submenu-cod-8 > div:nth-child(1) > div:nth-child(1) > ul:nth-child(1) > li:nth-child(10)")
            aguardar_e_clicar(driver, ".submenu-select > ul:nth-child(2) > li:nth-child(5)")
            campo_cod = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "#ContentPlaceHolder1_txtEstruturaProdutoCodigo_T2"))
            )
            campo_cod.clear()
            campo_cod.send_keys("22960")
            campo_cod.send_keys(Keys.TAB)
            aguardar_e_clicar(driver, "#ContentPlaceHolder1_cedDataFaturamentoInicio_s1a")
            aguardar_e_clicar(driver, ".ajax__calendar_container > span:nth-child(3)")
            aguardar_e_clicar(driver, "#ContentPlaceHolder1_cedDataFaturamentoFim_s1a")
            aguardar_e_clicar(driver, "div.linha_form:nth-child(2) > span:nth-child(4) > span:nth-child(6) > div:nth-child(1) > span:nth-child(3)")
            
            # Seleção de ciclo usando value ao invés de nth-child
            ciclo_formatado = f"{ciclo:02d}"
            value_esperado = f"{ano_atual}{ciclo_formatado}"
            
            aguardar_e_clicar(driver, "div.linha_form:nth-child(4) > span:nth-child(3) > span:nth-child(2) > span:nth-child(1)")
            seletor_inicio = f"#ContentPlaceHolder1_ddlCicloFaturamentoInicial_d1 > option[value='{value_esperado}']"
            aguardar_e_clicar(driver, seletor_inicio)
            
            aguardar_e_clicar(driver, "div.linha_form:nth-child(4) > span:nth-child(3) > span:nth-child(2) > span:nth-child(3)")
            seletor_fim = f"#ContentPlaceHolder1_ddlCicloFaturamentoFinal_d1 > option[value='{value_esperado}']"
            aguardar_e_clicar(driver, seletor_fim)
            
            aguardar_e_clicar(driver, "#ContentPlaceHolder1_ddlSituacaoFiscal_d1")
            aguardar_e_clicar(driver, "#ContentPlaceHolder1_ddlSituacaoFiscal_d1 > option:nth-child(3)")
            aguardar_e_clicar(driver, "#divAgrupamento > span:nth-child(1) > span:nth-child(6)")
            aguardar_e_clicar(driver, "#ContentPlaceHolder1_btnBuscar_btn")
            def loader_ok(d):
                try:
                    el = d.find_element(By.CSS_SELECTOR, "#UpdateProgress1")
                    return el.get_attribute("aria-hidden") == "true"
                except Exception:
                    return True
            WebDriverWait(driver, 60).until(loader_ok)
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
                print(f"Nenhum resultado para ciclo {ciclo}. Mensagem exibida pelo sistema.")
                logger.info(f"Nenhum resultado para ciclo {ciclo}. Mensagem exibida pelo sistema.")
                os.makedirs("extracoes", exist_ok=True)
                out_path = os.path.join("extracoes", f"resultado_eud_C{ciclo}.csv")
                with open(out_path, mode="w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(["VD", "Valor Praticado"])
                continue
            except Exception:
                pass
            tabela = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "#ContentPlaceHolder1_grdRankingVendas"))
            )
            linhas = tabela.find_elements(By.CSS_SELECTOR, "tr")
            resultados = []
            for linha in linhas:
                tds = linha.find_elements(By.CSS_SELECTOR, "td.grid_celula")
                if len(tds) >= 5:
                    gerencia = tds[0].text.strip()
                    valor_praticado = tds[4].text.strip()
                    valor_praticado_num = valor_praticado.replace('.', '').replace(',', '.')
                    try:
                        valor_praticado_float = float(valor_praticado_num)
                    except ValueError:
                        valor_praticado_float = ''
                    resultados.append([gerencia, valor_praticado_float])
            os.makedirs("extracoes", exist_ok=True)
            out_path = os.path.join("extracoes", f"resultado_eud_C{ciclo}.csv")
            with open(out_path, mode="w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["VD", "Valor Praticado"])
                writer.writerows(resultados)
            print(f"EUDORA ciclo {ciclo} extraído e salvo em {out_path}!")
            logger.info(f"EUDORA ciclo {ciclo} extraído e salvo em {out_path}!")
                
        except Exception as e:
            print(f"❌ Falha ao extrair EUDORA ciclo {ciclo}: {e}")
            logger.error(f"Falha ao extrair EUDORA ciclo {ciclo}: {e}", exc_info=True)

def ler_ciclos_pef(meta_csv_path=os.path.join("extracoes", "meta_dia.csv")):
    """Lê os ciclos de hoje no meta_dia.csv para tipos PEF/EUD. Retorna lista ordenada crescente de inteiros únicos."""
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

def navegar_para_ranking_vendas_pef(driver, ciclo=None):
    """Navega para Ranking Vendas e aplica filtros PEF."""
    ano_atual = datetime.now().year
    
    aguardar_e_clicar(driver, "#menu-cod-8 > a:nth-child(1)")
    time.sleep(1)
    aguardar_e_clicar(driver, "#submenu-cod-8 > div:nth-child(1) > div:nth-child(1) > ul:nth-child(1) > li:nth-child(10)")
    time.sleep(1)
    aguardar_e_clicar(driver, ".submenu-select > ul:nth-child(2) > li:nth-child(5)")
    aguardar_loader_flexivel(driver)
    aguardar_e_clicar(driver, "#ContentPlaceHolder1_cedDataFaturamentoInicio_I")
    aguardar_e_clicar(driver, ".ajax__calendar_footer")
    aguardar_e_clicar(driver, "#ContentPlaceHolder1_cedDataFaturamentoFim_I")
    aguardar_e_clicar(driver, "div.linha_form:nth-child(2) > span:nth-child(4) > span:nth-child(6) > div:nth-child(1) > span:nth-child(3) > div:nth-child(1)")
    
    # Ciclo Faturamento usando value ao invés de nth-child
    if ciclo:
        ciclo_formatado = f"{ciclo:02d}"
        value_esperado = f"{ano_atual}{ciclo_formatado}"
        
        aguardar_e_clicar(driver, "div.linha_form:nth-child(4) > span:nth-child(3) > span:nth-child(2) > span:nth-child(1)")
        aguardar_e_clicar(driver, f"#ContentPlaceHolder1_ddlCicloFaturamentoInicial_d1 > option[value='{value_esperado}']")
        aguardar_e_clicar(driver, "div.linha_form:nth-child(4) > span:nth-child(3) > span:nth-child(2) > span:nth-child(3)")
        aguardar_e_clicar(driver, f"#ContentPlaceHolder1_ddlCicloFaturamentoFinal_d1 > option[value='{value_esperado}']")
    else:
        # Ciclo padrão 15 se não especificado
        value_padrao = f"{ano_atual}15"
        aguardar_e_clicar(driver, "div.linha_form:nth-child(4) > span:nth-child(3) > span:nth-child(2) > span:nth-child(1)")
        aguardar_e_clicar(driver, f"#ContentPlaceHolder1_ddlCicloFaturamentoInicial_d1 > option[value='{value_padrao}']")
        aguardar_e_clicar(driver, "div.linha_form:nth-child(4) > span:nth-child(3) > span:nth-child(2) > span:nth-child(3)")
        aguardar_e_clicar(driver, f"#ContentPlaceHolder1_ddlCicloFaturamentoFinal_d1 > option[value='{value_padrao}']")
    
    aguardar_e_clicar(driver, "#ContentPlaceHolder1_ddlSituacaoFiscal_d1")
    aguardar_e_clicar(driver, "#ContentPlaceHolder1_ddlSituacaoFiscal_d1 > option:nth-child(3)")
    aguardar_e_clicar(driver, "#ContentPlaceHolder1_rdbAgrupamentoGerencia")
    time.sleep(2)
    aguardar_e_clicar(driver, "#ContentPlaceHolder1_btnBuscar_btn")
    aguardar_loader_flexivel(driver)

def extrair_e_salvar_resultados_pef(driver, output_path):
    """Extrai a grid de Ranking de Vendas (PEF) e salva em CSV. Se não houver resultados, salva CSV vazio."""
    logger.info("Iniciando extração dos resultados da tabela PEF.")
    try:
        aguardar_loader_flexivel(driver)
        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "#ContentPlaceHolder1_grdRankingVendas"))
            )
        except TimeoutException:
            # Tenta identificar painel de mensagem de ausência de resultados
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
                print("Nenhum resultado para ciclo PEF. Mensagem exibida pelo sistema.")
                logger.info("Nenhum resultado para ciclo PEF. Mensagem exibida pelo sistema.")
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                with open(output_path, mode="w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(["VD", "Valor Praticado"])
                return
            except Exception:
                pass
            logger.warning("Grid não apareceu em 15s. Salvando arquivo vazio.")
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, mode="w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["VD", "Valor Praticado"])
            return
        tabela = driver.find_element(By.CSS_SELECTOR, "#ContentPlaceHolder1_grdRankingVendas")
        linhas = tabela.find_elements(By.CSS_SELECTOR, "tr")
        resultados = []
        for linha in linhas:
            tds = linha.find_elements(By.CSS_SELECTOR, "td.grid_celula")
            if len(tds) >= 5:
                gerencia = tds[0].text.strip()
                valor_praticado = tds[4].text.strip()
                valor_praticado_num = valor_praticado.replace('.', '').replace(',', '.')
                try:
                    valor_praticado_float = float(valor_praticado_num)
                except ValueError:
                    valor_praticado_float = ''
                resultados.append([gerencia, valor_praticado_float])
        logger.info(f"Total de resultados extraídos: {len(resultados)}")
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["VD", "Valor Praticado"])
            writer.writerows(resultados)
        logger.info(f"Resultados salvos em {output_path}")
            
    except Exception as e:
        logger.error(f"Erro ao extrair resultados da grid PEF: {e}")
        
def extrair_pef(driver):
    """Executa o fluxo completo de extração PEF para todos os ciclos do dia."""
    ciclos_pef = ler_ciclos_pef()
    if not ciclos_pef:
        ciclos_pef = [16] # Escolha dos Ciclos PEF padrão se nenhum ciclo for encontrado
    logger.info(f"Ciclos capturados para PEF: {ciclos_pef}")
    print(f"Ciclos capturados para PEF: {ciclos_pef}")
    for ciclo in ciclos_pef:
        try:
            print(f"Extraindo PEF ciclo {ciclo}...")
            navegar_para_ranking_vendas_pef(driver, ciclo)
            extrair_e_salvar_resultados_pef(driver, output_path=os.path.join("extracoes", f"resultado_pef_C{ciclo}.csv"))
            print(f"PEF ciclo {ciclo} extraído e salvo!")
            logger.info(f"PEF ciclo {ciclo} extraído e salvo!")
        except Exception as e:
            print(f"❌ Falha ao extrair PEF ciclo {ciclo}: {e}")
            logger.error(f"Falha ao extrair PEF ciclo {ciclo}: {e}", exc_info=True)

def main():
    """Função principal de execução."""
    print("Iniciando extração EUDORA...")
    logger.info("Iniciando extração EUDORA")
    driver = None
    sucesso = False
    try:
        # Tentativa resiliente de iniciar sessão e abrir página de login
        max_init = 3
        for tentativa in range(1, max_init + 1):
            try:
                if driver:
                    try:
                        driver.quit()
                    except Exception:
                        pass
                driver = iniciar_navegador()
                logger.info(f"Acessando URL de login (tentativa {tentativa}/{max_init})...")
                driver.get(LOGIN_URL)
                # Verificação rápida se a janela continua aberta
                _ = driver.window_handles
                break
            except Exception as e:
                logger.warning(f"Falha ao abrir página de login na tentativa {tentativa}: {e}")
                if tentativa == max_init:
                    raise
                time.sleep(2)

        realizar_login(driver)
        logger.info("Login realizado com sucesso!")
        print("Login realizado com sucesso!")
        ciclos = ler_ciclos_de_hoje()
        if not ciclos:
            ciclos = [16] # Escolha dos Ciclos PEF padrão se nenhum ciclo for encontrado
        logger.info(f"Ciclos capturados: {ciclos}")
        print(f"Ciclos capturados: {ciclos}")
        preencher_e_extrair_eudora(driver, ciclos)
        print("✅ Extração EUDORA finalizada!")
        logger.info("Extração EUDORA finalizada!")

        # Extração PEF no mesmo navegador/sessão
        print("Executando extração PEF...")
        logger.info("Executando extração PEF...")
        extrair_pef(driver)
        sucesso = True
    except Exception as e:
        print(f"❌ Erro durante a extração: {e}")
        logger.error(f"Erro durante a extração: {e}", exc_info=True)
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