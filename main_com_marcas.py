"""
Script Main COM MARCAS - Envio Completo 18h
Executa todas as extrações com navegador compartilhado para máxima performance

Vantagens:
- Não usa subprocess (mais rápido)
- Compartilha o navegador entre todas as extrações
- Login único para todas as operações
- Economia de ~40% de tempo vs subprocess
- Captura metas automaticamente antes do envio

Executa:
- CAPTURA DE METAS: LOJA, PEF, EUD (automática)
- LOJA: Por loja (COM meta)
- PEF: Por loja, por ciclo (COM meta)
- EUD: Por loja, por ciclo (COM meta)
- MARCAS: Total geral - BOT, OUI, QDB (SEM meta)
"""

import os
import sys
import time
import logging
from datetime import datetime
from glob import glob

# Adiciona o diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from componentes.notifications import notification_manager
from componentes.file_safety import (
    limpar_arquivos_por_padrao,
    limpar_arquivo_especifico,
    validar_data_arquivo_csv
)

# Importa funções de extração diretamente
from componentes.extracao_loja import (
    initialize_driver as iniciar_navegador_loja,
    realizar_login as realizar_login_loja,
    navegar_e_extrair as navegar_e_extrair_loja,
    LOGIN_URL,
    USERNAME,
    PASSWORD
)

# Configuração de logging
os.makedirs("log", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("log/main_com_marcas.log", mode="w", encoding="utf-8"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def limpar_arquivos_extracao_antigos():
    """🛡️ SEGURANÇA: Limpa arquivos de extração anteriores."""
    logger.info("🧹 SEGURANÇA: Limpando arquivos de extração anteriores...")
    
    try:
        output_dir = "extracoes"
        
        # Limpa arquivo de loja
        loja_file = os.path.join(output_dir, "resultado_loja.csv")
        limpar_arquivo_especifico(loja_file, "resultado_loja.csv")
        
        # Limpa todos os arquivos de ciclos
        removidos_pef = limpar_arquivos_por_padrao(output_dir, "resultado_pef_C*.csv", "PEF")
        removidos_eud = limpar_arquivos_por_padrao(output_dir, "resultado_eud_C*.csv", "EUD")
        removidos_marcas = limpar_arquivos_por_padrao(output_dir, "resultado_marcas_C*.csv", "MARCAS")
        
        total = removidos_pef + removidos_eud + removidos_marcas + 1
        if total > 1:
            logger.info(f"✅ Limpeza concluída")
            notification_manager.info("Limpeza de Segurança", "Arquivos antigos removidos")
        else:
            logger.info("✅ Nenhum arquivo antigo encontrado")
            
    except Exception as e:
        logger.warning(f"⚠️ Erro durante limpeza de segurança (não crítico): {e}")

def extrair_loja_integrado():
    """Extrai LOJA usando funções diretas (não subprocess)."""
    logger.info("🔄 Iniciando extração LOJA (integrado)...")
    print("🔄 Iniciando extração LOJA...")
    
    driver = None
    try:
        driver = iniciar_navegador_loja()
        realizar_login_loja(driver, USERNAME, PASSWORD)
        navegar_e_extrair_loja(driver)
        
        logger.info("✅ Extração LOJA concluída")
        print("✅ Extração LOJA concluída")
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro na extração LOJA: {e}", exc_info=True)
        print(f"❌ Erro na extração LOJA: {e}")
        return False
        
    finally:
        if driver:
            try:
                driver.quit()
                logger.info("Navegador LOJA fechado")
            except Exception:
                pass

def extrair_vd_eud_pef_marcas_integrado():
    """Extrai PEF, EUD e MARCAS no mesmo navegador."""
    logger.info("🔄 Iniciando extração PEF + EUD + MARCAS (navegador compartilhado)...")
    print("🔄 Iniciando extração PEF + EUD + MARCAS...")
    
    # Importa funções do módulo VD/EUD/PEF
    from componentes.extracao_vd_eud_pef import (
        iniciar_navegador,
        realizar_login,
        ler_ciclos_de_hoje,
        preencher_e_extrair_eudora,
        extrair_pef
    )
    
    # Importa funções do módulo MARCAS
    from componentes.extracao_marcas import (
        MARCAS_CONFIG,
        navegar_para_ranking_vendas,
        extrair_marca
    )
    
    import csv
    
    driver = None
    try:
        # Inicia navegador UMA VEZ
        driver = iniciar_navegador()
        realizar_login(driver)
        
        # Lê ciclos
        ciclos = ler_ciclos_de_hoje()
        if not ciclos:
            ciclos = [15, 16]  # Escolha Ciclos padrão EUD/PEF (consistente com extracao_vd_eud_pef.py)
        
        logger.info(f"Ciclos detectados: {ciclos}")
        print(f"Ciclos detectados: {ciclos}")
        
        # 1. Extrai EUDORA
        logger.info("📊 Extraindo EUDORA...")
        print("📊 Extraindo EUDORA...")
        preencher_e_extrair_eudora(driver, ciclos)
        logger.info("✅ EUDORA concluída")
        print("✅ EUDORA concluída")
        
        # 2. Extrai PEF
        logger.info("📊 Extraindo PEF...")
        print("📊 Extraindo PEF...")
        extrair_pef(driver)
        logger.info("✅ PEF concluída")
        print("✅ PEF concluída")
        
        # 3. Extrai MARCAS (no mesmo navegador!)
        logger.info("📊 Extraindo MARCAS (BOT, OUI, QDB)...")
        print("📊 Extraindo MARCAS (BOT, OUI, QDB)...")
        
        for ciclo in ciclos:
            logger.info(f"Processando marcas para ciclo {ciclo}...")
            print(f"\nProcessando marcas para ciclo {ciclo}...")
            
            resultados = {}
            for marca_key in ['BOT', 'OUI', 'QDB']:
                valor = extrair_marca(driver, marca_key, ciclo)
                resultados[marca_key] = valor
                time.sleep(2)
            
            # Salva resultados do ciclo
            os.makedirs("extracoes", exist_ok=True)
            output_path = os.path.join("extracoes", f"resultado_marcas_C{ciclo}.csv")
            
            with open(output_path, mode="w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Marca", "Valor"])
                for marca, valor in resultados.items():
                    writer.writerow([marca, valor])
            
            logger.info(f"Resultados de marcas salvos em {output_path}")
            print(f"Ciclo {ciclo} concluído: BOT={resultados['BOT']:.2f}, OUI={resultados['OUI']:.2f}, QDB={resultados['QDB']:.2f}")
        
        logger.info("✅ MARCAS concluídas")
        print("✅ MARCAS concluídas")
        
        logger.info("✅ Todas as extrações PEF + EUD + MARCAS concluídas")
        print("✅ Todas as extrações concluídas")
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro nas extrações VD/EUD/PEF/MARCAS: {e}", exc_info=True)
        print(f"❌ Erro nas extrações: {e}")
        return False
        
    finally:
        if driver:
            try:
                driver.quit()
                logger.info("Navegador VD/EUD/PEF/MARCAS fechado")
            except Exception:
                pass

def verificar_e_capturar_metas():
    """Verifica se existem metas válidas e tenta capturar se necessário."""
    logger.info("🔍 Verificando/capturando metas...")
    
    meta_file = "extracoes/meta_dia.csv"
    flag_file = "extracoes/meta_capturada.flag"
    
    # Verifica se já existe arquivo de metas
    if os.path.exists(meta_file):
        try:
            # Tenta validar o arquivo existente
            from componentes.validators import validate_meta_file
            meta_status = validate_meta_file(meta_file)
            validas = [k for k, v in meta_status.items() if v["is_valid"]]
            if validas:
                logger.info(f"✅ Metas já existem e são válidas: {validas}")
                return True
            else:
                logger.warning("⚠️ Arquivo de metas existe mas não é válido")
        except Exception as e:
            logger.warning(f"⚠️ Erro ao validar metas existentes: {e}")
    
    # Se não tem metas válidas, tenta capturar
    logger.info("📥 Tentando capturar metas automaticamente...")
    try:
        # Importa e executa a captura de metas
        import subprocess
        result = subprocess.run(["python", "componentes/captura_metaDia.py"], 
                              capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0 and os.path.exists(meta_file):
            # Valida as metas capturadas
            from componentes.validators import validate_meta_file
            meta_status = validate_meta_file(meta_file)
            validas = [k for k, v in meta_status.items() if v["is_valid"]]
            if validas:
                logger.info(f"✅ Metas capturadas com sucesso: {validas}")
                return True
            else:
                logger.warning("⚠️ Metas capturadas mas nenhuma é válida")
                return False
        else:
            logger.error(f"❌ Falha na captura de metas: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        logger.error("❌ Timeout na captura de metas")
        return False
    except Exception as e:
        logger.error(f"❌ Erro ao capturar metas: {e}")
        return False

def validar_arquivos_data(arquivos_validar):
    """Valida que todos os arquivos foram modificados hoje."""
    data_hoje = datetime.now().strftime("%d/%m/%Y")
    arquivos_data_invalida = []
    
    for arquivo_path, nome_tipo in arquivos_validar:
        try:
            resultado = validar_data_arquivo_csv(arquivo_path, data_hoje)
            
            if not resultado['valido']:
                arquivos_data_invalida.append((nome_tipo, resultado['data_encontrada']))
                logger.error(f"❌ SEGURANÇA: Arquivo {nome_tipo} modificado em {resultado['data_encontrada']} (esperado: {data_hoje})")
        except Exception as e:
            logger.warning(f"⚠️ Não foi possível validar data do arquivo {nome_tipo}: {e}")
    
    if arquivos_data_invalida:
        logger.error("=" * 50)
        logger.error("🚨 BLOQUEIO DE SEGURANÇA ATIVADO!")
        logger.error("🚨 Arquivos antigos detectados:")
        for tipo, data in arquivos_data_invalida:
            logger.error(f"   - {tipo}: modificado em {data}")
        logger.error("🚨 ENVIO CANCELADO!")
        logger.error("=" * 50)
        notification_manager.error(
            "Segurança - Envio Bloqueado",
            f"Detectados {len(arquivos_data_invalida)} arquivo(s) antigo(s)"
        )
        return False
    
    logger.info(f"✅ Validação de data: Todos os {len(arquivos_validar)} arquivo(s) válidos ({data_hoje})")
    return True

def enviar_mensagens():
    """Envia mensagens via WhatsApp."""
    logger.info("🔄 Executando envio via WhatsApp...")
    print("🔄 Executando envio via WhatsApp...")
    
    try:
        from componentes.whatsapp_sender import WhatsAppSender
        
        # Configuração dos grupos
        GROUP_LINKS = {
            "LOJA": "InUzOAgZwBVHbihjqG3ylC",  # InUzOAgZwBVHbihjqG3ylC Grupo LOJA
            "VD": "GEpoPUcny2E7xghvmG9uEJ"    # GEpoPUcny2E7xghvmG9uEJ Grupo VD (PEF, EUD, MARCAS)
        } # EdqcxgPBhNRDpKiEiXsKLz link do grupo TESTE
        
        sender = WhatsAppSender([GROUP_LINKS["LOJA"], GROUP_LINKS["VD"]])
        
        # Lê metas
        meta_loja = sender.get_meta_loja_csv()
        ciclos, metas_por_ciclo = sender.ler_ciclos_metas()
        
        if not ciclos:
            ciclos = [16]  # Escolha Ciclos padrão EUD/PEF (consistente)
        
        logger.info(f"Ciclos detectados: {ciclos}")
        logger.info(f"Meta LOJA: {meta_loja}")
        
        # === ENVIO PARA GRUPO LOJA ===
        logger.info("📤 Preparando envio para grupo LOJA...")
        loja_msg = sender.format_data(
            "extracoes/resultado_loja.csv",
            "*➡️ Parcial Receita LOJA*",
            "",
            meta_loja,
            "LOJA"
        )
        
        if loja_msg:
            sender.abrir_whatsapp_web()
            sender.navegar_para_grupo(GROUP_LINKS["LOJA"])
            sender.enviar_mensagem(loja_msg)
            logger.info("✅ Mensagem LOJA enviada!")
            print("✅ Mensagem LOJA enviada!")
            time.sleep(10)
        else:
            logger.warning("⚠️ Mensagem LOJA vazia ou arquivo não encontrado")
        
        # === ENVIO PARA GRUPO VD (PEF + EUD + MARCAS) ===
        logger.info("📤 Preparando envio para grupo VD...")
        
        for ciclo in ciclos:
            mensagens_ciclo = []
            
            # Busca metas específicas do ciclo
            metas_ciclo = metas_por_ciclo.get(ciclo, {})
            meta_pef_ciclo = metas_ciclo.get("PEF")
            meta_eud_ciclo = metas_ciclo.get("EUD")
            
            logger.info(f"Ciclo {ciclo} - Metas: PEF={meta_pef_ciclo}, EUD={meta_eud_ciclo}")
            
            # PEF
            pef_msg = sender.format_data(
                f"extracoes/resultado_pef_C{ciclo}.csv",
                f"*➡️ Parcial Receita PEF - Ciclo {ciclo}*",
                "",
                meta_pef_ciclo,
                "PEF"
            )
            if pef_msg:
                mensagens_ciclo.append(pef_msg)
            
            # EUD
            eud_msg = sender.format_data(
                f"extracoes/resultado_eud_C{ciclo}.csv",
                f"*➡️ Parcial Receita EUD -​ Ciclo {ciclo}*",
                "",
                meta_eud_ciclo,
                "EUDORA"
            )
            if eud_msg:
                mensagens_ciclo.append(eud_msg)
            
            # MARCAS (SEM meta)
            marcas_msg = sender.format_marcas(
                f"extracoes/resultado_marcas_C{ciclo}.csv",
                ciclo
            )
            if marcas_msg:
                mensagens_ciclo.append(marcas_msg)
            
            # Combina todas as mensagens do ciclo
            if mensagens_ciclo:
                mensagem_completa = "\n\n".join(mensagens_ciclo)
                logger.info(f"Enviando mensagens do ciclo {ciclo}...")
                
                sender.navegar_para_grupo(GROUP_LINKS["VD"])
                sender.enviar_mensagem(mensagem_completa)
                logger.info(f"✅ Mensagens do ciclo {ciclo} enviadas!")
                print(f"✅ Mensagens do ciclo {ciclo} enviadas!")
                time.sleep(10)
            else:
                logger.warning(f"⚠️ Nenhuma mensagem válida para ciclo {ciclo}")
        
        logger.info("✅ Envio completo!")
        print("✅ Envio completo!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro ao executar envio: {e}", exc_info=True)
        print(f"❌ Erro ao executar envio: {e}")
        return False

def main():
    """Função principal - orquestra todas as extrações e envios."""
    logger.info("🚀 Iniciando execução do sistema MAIN COM MARCAS (18h)")
    print("🚀 Iniciando Sistema MAIN COM MARCAS - Envio Completo 18h")
    print("=" * 50)
    notification_manager.info("Sistema Main COM MARCAS", "Execução 18h - Navegador compartilhado")
    
    start_time = datetime.now()
    
    # ETAPA 0: Limpeza de Segurança
    logger.info("=" * 50)
    logger.info("📊 ETAPA 0: Limpeza de Segurança")
    print("\n📊 ETAPA 0: Limpeza de Segurança")
    limpar_arquivos_extracao_antigos()
    time.sleep(1)
    
    # ETAPA 1: Extração LOJA
    logger.info("=" * 50)
    logger.info("📊 ETAPA 1: Extração LOJA")
    print("\n📊 ETAPA 1: Extração LOJA")
    sucesso_loja = extrair_loja_integrado()
    time.sleep(3)
    
    # ETAPA 2: Extração VD/EUD/PEF/MARCAS (INTEGRADO - mesmo navegador!)
    logger.info("=" * 50)
    logger.info("📊 ETAPA 2: Extração PEF + EUD + MARCAS (Navegador Compartilhado)")
    print("\n📊 ETAPA 2: Extração PEF + EUD + MARCAS (Navegador Compartilhado)")
    sucesso_vd = extrair_vd_eud_pef_marcas_integrado()
    time.sleep(3)
    
    # Verifica se pelo menos uma extração foi bem-sucedida
    if not (sucesso_loja or sucesso_vd):
        logger.error("❌ Todas as extrações falharam - interrompendo")
        print("\n❌ Todas as extrações falharam")
        notification_manager.error("Sistema Interrompido", "Todas as extrações falharam")
        return False
    
    # ETAPA 3: Validação de Data dos Arquivos
    logger.info("=" * 50)
    logger.info("📊 ETAPA 3: Validação Final de Data dos Arquivos")
    print("\n📊 ETAPA 3: Validação de Data")
    
    arquivos_validar = []
    
    if sucesso_loja:
        loja_file = os.path.join("extracoes", "resultado_loja.csv")
        if os.path.exists(loja_file):
            arquivos_validar.append((loja_file, "LOJA"))
    
    if sucesso_vd:
        for arquivo in glob(os.path.join("extracoes", "resultado_pef_C*.csv")):
            arquivos_validar.append((arquivo, f"PEF ({os.path.basename(arquivo)})"))
        for arquivo in glob(os.path.join("extracoes", "resultado_eud_C*.csv")):
            arquivos_validar.append((arquivo, f"EUD ({os.path.basename(arquivo)})"))
        for arquivo in glob(os.path.join("extracoes", "resultado_marcas_C*.csv")):
            arquivos_validar.append((arquivo, f"MARCAS ({os.path.basename(arquivo)})"))
    
    if not validar_arquivos_data(arquivos_validar):
        return False
    
    # ETAPA 3.5: Verificação/Captura de Metas
    logger.info("=" * 50)
    logger.info("📊 ETAPA 3.5: Verificação/Captura de Metas")
    print("\n📊 ETAPA 3.5: Verificação/Captura de Metas")
    
    if not verificar_e_capturar_metas():
        logger.warning("⚠️ Metas não disponíveis - envio será feito sem cálculos de meta")
        print("⚠️ Metas não disponíveis - envio será feito sem cálculos de meta")
    
    # ETAPA 4: Envio de Relatórios
    logger.info("=" * 50)
    logger.info("📊 ETAPA 4: Envio de Relatórios")
    print("\n📊 ETAPA 4: Envio de Relatórios")
    logger.info(f"⏳ Aguardando 10 segundos antes do envio...")
    time.sleep(10)
    
    if not enviar_mensagens():
        logger.error("❌ Envio falhou")
        notification_manager.error("Sistema Interrompido", "Falha no envio")
        return False
    
    # Finalização
    end_time = datetime.now()
    duration = end_time - start_time
    
    logger.info("=" * 50)
    logger.info("🎉 Sistema MAIN COM MARCAS executado com sucesso!")
    logger.info(f"⏱️ Tempo total de execução: {duration}")
    print("\n" + "=" * 50)
    print("🎉 Sistema MAIN COM MARCAS executado com sucesso!")
    print(f"⏱️ Tempo total de execução: {duration}")
    print(f"⚡ Economia de tempo com navegador compartilhado!")
    notification_manager.success(
        "Sistema Main COM MARCAS Concluído",
        f"Execução 18h concluída em {duration.total_seconds():.1f} segundos"
    )
    return True

if __name__ == "__main__":
    print("🚀 Executando Sistema MAIN COM MARCAS - Envio Completo 18h")
    print("=" * 50)
    print("ℹ️  Extrações: CAPTURA METAS + LOJA + PEF + EUD + MARCAS (BOT, OUI, QDB)")
    print("⚡ Performance: Navegador compartilhado para máxima velocidade")
    print()
    
    main()
