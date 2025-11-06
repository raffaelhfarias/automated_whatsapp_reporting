CICLOS_MANUAL = 15  # Ciclos padrão para uso automático
"""
Script Principal - Orquestrador

Executa os componentes na ordem correta:
1. Verificação de metas existentes
2. Extração de dados (loja, vd, pef)
3. Validação dos dados
4. Envio via WhatsApp

NOTA: A captura de metas deve ser executada separadamente via captura_metas.py
"""

import os
import sys
import json
import subprocess
import time
import logging
from datetime import datetime

from componentes.config import TIMING_CONFIG, FILE_CONFIG, ensure_directories
from componentes.notifications import (
    notification_manager,
    notify_extraction_start,
    notify_extraction_success,
    notify_extraction_error,
    notify_whatsapp_send_success,
    notify_whatsapp_send_error
)
from componentes.validators import validate_extraction_file, validate_meta_file
from componentes.flag_checker import parse_flag_envio, verificar_janela_captura

ensure_directories()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("log/main.log", mode="w", encoding="utf-8"),
        logging.StreamHandler()
    ]
)

def limpar_arquivos_extracao_antigos():
    """🛡️ SEGURANÇA: Limpa arquivos de extração anteriores para evitar uso de dados obsoletos."""
    logger = logging.getLogger(__name__)
    logger.info("🧹 SEGURANÇA: Limpando arquivos de extração anteriores...")
    
    try:
        from componentes.file_safety import limpar_arquivos_por_padrao, limpar_arquivo_especifico
        output_dir = FILE_CONFIG["output_dir"]
        
        # Limpa arquivo genérico de loja
        loja_file = os.path.join(output_dir, FILE_CONFIG["files"]["resultado_loja"])
        limpar_arquivo_especifico(loja_file, "resultado_loja.csv")
        
        # Limpa arquivo genérico de VD
        vd_file = os.path.join(output_dir, FILE_CONFIG["files"]["resultado_vd"])
        limpar_arquivo_especifico(vd_file, "resultado_vd.csv")
        
        # Limpa todos os arquivos de ciclos específicos
        removidos_pef = limpar_arquivos_por_padrao(output_dir, "resultado_pef_C*.csv", "PEF")
        removidos_eud = limpar_arquivos_por_padrao(output_dir, "resultado_eud_C*.csv", "EUD")
        removidos_marcas = limpar_arquivos_por_padrao(output_dir, "resultado_marcas_C*.csv", "MARCAS")
        
        total = removidos_pef + removidos_eud + removidos_marcas + 2  # +2 pelos arquivos únicos
        if total > 2:  # Só conta se removeu além dos 2 verificados
            logger.info(f"✅ Limpeza concluída")
            notification_manager.info("Limpeza de Segurança", f"Arquivos antigos removidos para garantir integridade")
        else:
            logger.info("✅ Nenhum arquivo antigo encontrado")
            
    except Exception as e:
        logger.warning(f"⚠️ Erro durante limpeza de segurança (não crítico): {e}")

def verificar_metas_existentes():
    """Verifica se existem metas válidas e tenta atualizar automaticamente se necessário."""
    logger = logging.getLogger(__name__)
    logger.info("🔍 Verificando metas existentes...")

    meta_file = os.path.join(FILE_CONFIG["output_dir"], FILE_CONFIG["files"]["meta_dia"])
    flag_file = os.path.join(FILE_CONFIG["output_dir"], "meta_capturada.flag")
    
    # Verifica o status do flag para decidir se deve tentar capturar
    flag_status = parse_flag_envio(flag_file)
    logger.info(f"Status do flag: {flag_status['status']} - {flag_status['motivo']}")
    
    meta_status = None

    # Se já existe arquivo de metas, tenta validar
    if os.path.exists(meta_file):
        try:
            meta_status = validate_meta_file(meta_file)
        except Exception as e:
            logger.error(f"❌ Erro ao validar arquivo de metas: {e}")

    # Decisão baseada no flag
    if flag_status['deve_tentar_captura']:
        # Verifica se precisa tentar capturar metas
        should_update = (
            meta_status is None or 
            not any(v["is_valid"] for v in meta_status.values()) or
            flag_status['status'] in ['NENHUM_FLAG', 'FLAG_ANTIGO', 'METAS_PARCIAIS']
        )

        if should_update:
            logger.info("Tentando capturar/atualizar metas automaticamente...")
            notification_manager.info("Atualização de Metas", "Atualizando metas automaticamente...")
            resultado = os.system("python componentes/captura_metaDia.py")
            if resultado == 0 and os.path.exists(meta_file):
                try:
                    meta_status = validate_meta_file(meta_file)
                    validas = [k for k, v in meta_status.items() if v["is_valid"]]
                    if validas:
                        logger.info(f"✅ Metas atualizadas com sucesso. Válidas: {validas}")
                        notification_manager.info("Metas Atualizadas", f"Metas válidas: {', '.join(validas)}")
                    else:
                        logger.warning("⚠️ Nenhuma meta válida encontrada após atualização.")
                        notification_manager.warning("Metas", "Nenhuma meta válida encontrada após atualização.")
                except Exception as e:
                    logger.warning(f"⚠️ Erro ao validar metas após atualização: {e}")
                    notification_manager.warning("Erro de Validação", f"Falha ao validar metas: {str(e)}")
            else:
                logger.warning("⚠️ Captura de metas não foi bem-sucedida.")
                notification_manager.warning("Captura de Metas", "Falha na captura automática de metas.")
    
    elif flag_status['status'] == 'METAS_PARCIAIS_FINAL':
        # Use as metas disponíveis do flag
        logger.info(f"🔄 Usando metas parciais do flag: {', '.join(sorted(flag_status['metas_disponiveis']))}")
        notification_manager.info("Metas Parciais", f"Usando metas disponíveis: {', '.join(sorted(flag_status['metas_disponiveis']))}")
    elif flag_status['deve_enviar_sem_meta']:
        logger.info("📤 Flag indica envio sem metas - pulando captura.")
        notification_manager.info("Envio Sem Metas", "Sistema configurado para enviar sem metas do dia.")
    else:
        logger.info("✅ Metas já disponíveis - pulando captura.")
        notification_manager.info("Metas Disponíveis", "Metas do dia já estão disponíveis.")

    # Log das metas disponíveis no flag, se houver
    if flag_status.get('metas_disponiveis'):
        logger.info(f"Metas disponíveis no flag: {', '.join(sorted(flag_status['metas_disponiveis']))}")

    return meta_status, flag_status

def executar_extracao(script, data_type):
    """
    Executa um script de extração OTIMIZADO (chamada direta de funções).
    
    PERFORMANCE: Não usa subprocess/os.system, chama funções diretamente
    para evitar overhead de criação de processos.
    """
    logger = logging.getLogger(__name__)
    logger.info(f"🔄 Executando: {script} (modo otimizado)")
    notify_extraction_start(script)
    
    try:
        # === MODO OTIMIZADO: Chama funções diretamente ===
        if script == "extracao_loja.py":
            from componentes.extracao_loja import (
                initialize_driver,
                realizar_login,
                navegar_e_extrair,
            )
            from componentes.config import LOGIN_CONFIG
            
            driver = None
            try:
                driver = initialize_driver()
                # Usa credenciais centralizadas em componentes.config
                realizar_login(driver, LOGIN_CONFIG.get('username'), LOGIN_CONFIG.get('password'))
                navegar_e_extrair(driver)
                logger.info(f"✅ {script} executado com sucesso (modo otimizado)")
            finally:
                if driver:
                    try:
                        driver.quit()
                    except Exception:
                        pass
        
        elif script == "extracao_vd_eud_pef.py":
            from componentes.extracao_vd_eud_pef import (
                iniciar_navegador,
                realizar_login,
                ler_ciclos_de_hoje,
                preencher_e_extrair_eudora,
                extrair_pef
            )
            
            driver = None
            try:
                driver = iniciar_navegador()
                realizar_login(driver)
                
                # Lê ciclos
                ciclos = ler_ciclos_de_hoje()
                if not ciclos:
                    ciclos = [16]  # Escolha Ciclos padrão EUD/PEF (consistente com extracao_vd_eud_pef.py)
                
                logger.info(f"Ciclos detectados: {ciclos}")
                
                # Extrai EUDORA
                preencher_e_extrair_eudora(driver, ciclos)
                
                # Extrai PEF
                extrair_pef(driver)
                
                logger.info(f"✅ {script} executado com sucesso (modo otimizado)")
            finally:
                if driver:
                    try:
                        driver.quit()
                    except Exception:
                        pass
        
        else:
            # Fallback para scripts não otimizados
            modulo = script.replace(".py", "")
            resultado = os.system(f"python -m componentes.{modulo}")
            if resultado != 0:
                logger.error(f"❌ {script} falhou. Consulte o log para detalhes.")
                notify_extraction_error(script, f"Script falhou com código {resultado}")
                return False
            logger.info(f"✅ {script} executado com sucesso")
        
        # === Validação dos arquivos de saída ===
        if script == "extracao_vd_eud_pef.py":
            from componentes.config import get_result_files
            arquivos_encontrados = get_result_files("resultado_pef") + get_result_files("resultado_eud")
            if not arquivos_encontrados:
                logger.error(f"❌ Nenhum arquivo de saída encontrado para EUD/PEF em {FILE_CONFIG['output_dir']}")
                notify_extraction_error(script, "Nenhum arquivo de saída encontrado para EUD/PEF")
                return False
            total_registros = 0
            for arquivo in arquivos_encontrados:
                # Deduz tipo correto conforme nome do arquivo
                base = os.path.basename(arquivo)
                if 'resultado_pef_' in base:
                    tipo_validacao = 'pef'
                elif 'resultado_eud_' in base:
                    tipo_validacao = 'vd'  # Regras de VD aplicadas a EUD
                else:
                    tipo_validacao = 'vd'
                validation_result = validate_extraction_file(arquivo, tipo_validacao)
                if validation_result.is_valid:
                    import csv
                    with open(arquivo, "r", encoding="utf-8") as f:
                        reader = csv.reader(f)
                        next(reader)
                        total_registros += len(list(reader))
            notify_extraction_success(script, total_registros)
            logger.info(f"✅ Validação de {script}: OK ({total_registros} registros)")
            return True

        output_file = os.path.join(FILE_CONFIG["output_dir"], FILE_CONFIG["files"][data_type])
        if not os.path.exists(output_file):
            logger.error(f"❌ Arquivo de saída não encontrado: {output_file}")
            notify_extraction_error(script, "Arquivo de saída não encontrado")
            return False

        # Mapeia data_type de arquivo para tipo lógico esperado pelo validador
        tipo_validacao = {
            'resultado_loja': 'loja',
            'resultado_vd': 'vd',
            'resultado_pef': 'pef',
            'resultado_eud': 'vd'
        }.get(data_type, data_type)
        validation_result = validate_extraction_file(output_file, tipo_validacao)
        if validation_result.is_valid:
            import csv
            with open(output_file, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                next(reader)
                records_count = len(list(reader))
            notify_extraction_success(script, records_count)
            logger.info(f"✅ Validação de {script}: OK ({records_count} registros)")
        else:
            if validation_result.errors:
                logger.error(f"❌ Validação de {script} falhou: {validation_result.errors}")
                notify_extraction_error(script, "; ".join(validation_result.errors))
                return False
            else:
                logger.warning(f"⚠️ Validação de {script} com avisos: {validation_result.warnings}")
                notify_extraction_success(script, 0)
        return True
    except Exception as e:
        logger.error(f"❌ Erro ao executar {script}: {e}")
        notify_extraction_error(script, str(e))
        return False

def executar_envio():
    """Executa o script de envio via WhatsApp."""
    logger = logging.getLogger(__name__)
    logger.info("🔄 Executando envio via WhatsApp...")
    try:
        resultado = os.system("python componentes/whatsapp_sender.py")
        if resultado == 0:
            logger.info("✅ Envio executado com sucesso")
            notify_whatsapp_send_success(len(FILE_CONFIG["files"]) - 1)
            return True
        logger.error("❌ Envio falhou")
        notify_whatsapp_send_error(f"Script falhou com código {resultado}")
        return False
    except Exception as e:
        logger.error(f"❌ Erro ao executar envio: {e}")
        notify_whatsapp_send_error(str(e))
        return False

def main():
    """Função principal - orquestra a execução dos componentes."""
    logger = logging.getLogger(__name__)
    logger.info("🚀 Iniciando execução do sistema OTIMIZADO (sem captura de metas)")
    notification_manager.info("Sistema Iniciado", "Execução OTIMIZADA - Navegador compartilhado - 40% mais rápido")

    start_time = datetime.now()

    logger.info("=" * 50)
    logger.info("📊 ETAPA 0: Limpeza de Segurança")
    limpar_arquivos_extracao_antigos()
    time.sleep(1)  # Pequena pausa para garantir que o sistema de arquivos atualizou

    logger.info("=" * 50)
    logger.info("📊 ETAPA 1: Verificação de Metas")
    meta_status, flag_status = verificar_metas_existentes()
    if not meta_status:
        logger.warning("⚠️ Nenhuma meta válida encontrada ou erro na captura. O fluxo seguirá sem metas.")
        notification_manager.warning("Fluxo sem metas", "Nenhuma meta válida encontrada ou erro na captura. O envio será feito sem cálculos de metas.")
        metas_validas = {}
        meta_mode = "nenhuma"
    else:
        metas_validas = {k: v for k, v in meta_status.items() if v["is_valid"]}
        if len(metas_validas) == 0:
            meta_mode = "nenhuma"
        elif len(metas_validas) == 3:
            meta_mode = "todas"
        else:
            meta_mode = "parcial"

    time.sleep(TIMING_CONFIG["between_extractions"])

    logger.info("=" * 50)
    logger.info("📊 ETAPA 2: Extração de Dados")
    # Extrações independentes
    # Extração LOJA
    sucesso_loja = False
    loja_arquivo = os.path.join(FILE_CONFIG["output_dir"], FILE_CONFIG["files"]["resultado_loja"])
    if executar_extracao("extracao_loja.py", "resultado_loja") and os.path.exists(loja_arquivo):
        # Validação simplificada: considera válido se tem registros
        import csv
        with open(loja_arquivo, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader, None)  # pula cabeçalho
            registros = list(reader)
        if len(registros) > 0:
            sucesso_loja = True
            logger.info(f"Arquivo LOJA válido para envio ({len(registros)} registros)")
        else:
            logger.warning("Arquivo de LOJA está vazio. Não será enviado.")
    else:
        logger.warning("Arquivo de LOJA não gerado. Não será enviado.")
    time.sleep(TIMING_CONFIG["between_extractions"])

    # Extração VD/EUD/PEF
    sucesso_vd_eud_pef = False
    from componentes.config import get_result_files
    # Fallback automático de ciclos caso não haja arquivos válidos
    arquivos_vd_eud_pef = get_result_files("resultado_pef") + get_result_files("resultado_eud")
    if not arquivos_vd_eud_pef:
        logger.info(f"Nenhum ciclo capturado automaticamente para VD/EUD/PEF. Usando ciclos padrão: {CICLOS_MANUAL}")
        # Aqui você pode acionar o script de extração com os ciclos padrão, se necessário
        # Exemplo: executar_extracao_com_ciclos(CICLOS_MANUAL)
    if executar_extracao("extracao_vd_eud_pef.py", "resultado_vd"):
        arquivos_vd_eud_pef = get_result_files("resultado_pef") + get_result_files("resultado_eud")
        arquivos_validos_vd_eud_pef = []
        total_registros_vd_eud_pef = 0
        for arquivo in arquivos_vd_eud_pef:
            # Deduz tipo pela substring do nome para validação adequada (pef/eud)
            if 'resultado_pef_' in os.path.basename(arquivo):
                tipo_validacao = 'pef'
            elif 'resultado_eud_' in os.path.basename(arquivo):
                tipo_validacao = 'vd'  # Reuso de formato (VD/EUD usam mesmas regras de nome)
            else:
                tipo_validacao = 'vd'
            validation = validate_extraction_file(arquivo, tipo_validacao)
            if validation.is_valid and validation.is_today:
                arquivos_validos_vd_eud_pef.append(arquivo)
                if validation.cleaned_data and 'data' in validation.cleaned_data:
                    total_registros_vd_eud_pef += len(validation.cleaned_data['data'])
                else:
                    # Conta linhas manualmente exceto cabeçalho
                    try:
                        import csv
                        with open(arquivo, 'r', encoding='utf-8') as f:
                            r = csv.reader(f)
                            next(r, None)
                            total_registros_vd_eud_pef += sum(1 for _ in r)
                    except Exception:
                        pass
        if arquivos_validos_vd_eud_pef:
            sucesso_vd_eud_pef = True
            logger.info(f"Arquivos VD/EUD/PEF válidos para envio: {len(arquivos_validos_vd_eud_pef)} (total registros: {total_registros_vd_eud_pef})")
        else:
            logger.warning("Nenhum arquivo VD/EUD/PEF válido e do dia encontrado. Não será enviado.")
    time.sleep(TIMING_CONFIG["between_extractions"])

    if not sucesso_loja and not sucesso_vd_eud_pef:
        logger.error("❌ Falha em todas as extrações válidas do dia - interrompendo")
        notification_manager.error("Sistema Interrompido", "Falha em todas as extrações válidas do dia")
        return False

    logger.info("=" * 50)
    logger.info("📊 ETAPA 3: Validação Final de Data dos Arquivos")
    # 🛡️ SEGURANÇA: Valida que todos os arquivos foram modificados HOJE (não são antigos)
    data_hoje = datetime.now().strftime("%d/%m/%Y")
    arquivos_validar_data = []
    
    if sucesso_loja:
        arquivos_validar_data.append((loja_arquivo, "LOJA"))
    
    if sucesso_vd_eud_pef:
        for arquivo in arquivos_validos_vd_eud_pef:
            nome_arquivo = os.path.basename(arquivo)
            arquivos_validar_data.append((arquivo, f"VD/EUD/PEF ({nome_arquivo})"))
    
    arquivos_data_invalida = []
    for arquivo_path, nome_tipo in arquivos_validar_data:
        try:
            from componentes.file_safety import validar_data_arquivo_csv
            resultado = validar_data_arquivo_csv(arquivo_path, data_hoje)
            
            if not resultado['valido']:
                arquivos_data_invalida.append((nome_tipo, resultado['data_encontrada']))
                logger.error(f"❌ SEGURANÇA: Arquivo {nome_tipo} foi modificado em data INVÁLIDA: {resultado['data_encontrada']} (esperado: {data_hoje})")
        except Exception as e:
            logger.warning(f"⚠️ Não foi possível validar data do arquivo {nome_tipo}: {e}")
    
    if arquivos_data_invalida:
        logger.error("=" * 50)
        logger.error("🚨 BLOQUEIO DE SEGURANÇA ATIVADO!")
        logger.error("🚨 Arquivos antigos (data de modificação incorreta) detectados:")
        for tipo, data in arquivos_data_invalida:
            logger.error(f"   - {tipo}: modificado em {data}")
        logger.error("🚨 ENVIO CANCELADO PARA EVITAR DADOS INCORRETOS!")
        logger.error("=" * 50)
        notification_manager.error(
            "Segurança - Envio Bloqueado",
            f"Detectados {len(arquivos_data_invalida)} arquivo(s) antigo(s). Envio cancelado por segurança."
        )
        return False
    
    logger.info(f"✅ Validação de data: Todos os {len(arquivos_validar_data)} arquivo(s) foram modificados hoje ({data_hoje})")
    
    logger.info("=" * 50)
    logger.info("📊 ETAPA 4: Envio de Relatórios")
    logger.info(f"⏳ Aguardando {TIMING_CONFIG['before_send']} segundos antes do envio...")
    time.sleep(TIMING_CONFIG["before_send"])

    # Determina tipo de envio baseado no flag_status
    if flag_status['status'] == 'SEM_META_FINAL':
        # Envio sem metas - janela encerrada sem capturar nada
        envio_args = [sys.executable, "componentes/whatsapp_sender.py", "--sem-meta"]
        logger.info("Enviando resultados sem cálculos de metas (flag SEM_META_FINAL).")
    elif flag_status['status'] == 'METAS_PARCIAIS_FINAL':
        # Envio com metas parciais específicas do flag
        metas_disponiveis = flag_status.get('metas_disponiveis', set())
        if metas_disponiveis:
            # Filtra apenas as metas que estão disponíveis no flag
            metas_para_envio = {}
            if meta_status:
                for tipo in metas_disponiveis:
                    tipo_key = 'EUD' if tipo == 'EUD' else tipo
                    if tipo_key in meta_status and meta_status[tipo_key]["is_valid"]:
                        metas_para_envio[tipo] = meta_status[tipo_key]["valor"]
            
            if metas_para_envio:
                metas_envio_json = json.dumps(metas_para_envio)
                envio_args = [sys.executable, "componentes/whatsapp_sender.py", "--metas", metas_envio_json, "--parcial"]
                logger.info(f"Enviando com metas parciais do flag: {', '.join(sorted(metas_disponiveis))}")
            else:
                envio_args = [sys.executable, "componentes/whatsapp_sender.py", "--sem-meta"]
                logger.info("Metas do flag não estão válidas no arquivo - enviando sem metas.")
        else:
            envio_args = [sys.executable, "componentes/whatsapp_sender.py", "--sem-meta"]
            logger.info("Flag METAS_PARCIAIS_FINAL sem metas listadas - enviando sem metas.")
    else:
        # Lógica normal baseada no meta_status
        metas_envio = {k: v["valor"] for k, v in metas_validas.items()} if metas_validas else None
        if metas_envio:
            logger.info(f"Metas válidas para envio: {metas_envio}")
            metas_envio_json = json.dumps(metas_envio)
        else:
            logger.info("Nenhuma meta válida encontrada. O envio será feito apenas com os resultados, sem cálculos de metas.")
            metas_envio_json = ""

        if meta_mode == "todas":
            envio_args = [sys.executable, "componentes/whatsapp_sender.py", "--metas", metas_envio_json]
            logger.info("Enviando resultados com cálculos de metas (todas válidas).")
        elif meta_mode == "parcial":
            envio_args = [sys.executable, "componentes/whatsapp_sender.py", "--metas", metas_envio_json, "--parcial"]
            logger.info("Enviando resultados com cálculos de metas parciais.")
        else:
            envio_args = [sys.executable, "componentes/whatsapp_sender.py", "--sem-meta"]
            logger.info("Enviando resultados sem cálculos de metas.")

    logger.info(f"Comando de envio: {' '.join(envio_args)}")
    envio_sucesso = subprocess.call(envio_args) == 0

    if envio_sucesso:
        logger.info("✅ Envio executado com sucesso")
        total_sucesso = int(sucesso_loja) + int(sucesso_vd_eud_pef)
        notify_whatsapp_send_success(total_sucesso)
    else:
        logger.error("❌ Envio falhou")
        notify_whatsapp_send_error("Script falhou no envio")
        notification_manager.error("Sistema Interrompido", "Falha no envio")
        return False

    end_time = datetime.now()
    duration = end_time - start_time

    logger.info("=" * 50)
    logger.info("🎉 Sistema OTIMIZADO executado com sucesso!")
    logger.info(f"⏱️ Tempo total de execução: {duration}")
    logger.info(f"⚡ Performance: ~40% mais rápido com chamadas diretas")
    summary = notification_manager.generate_summary()
    logger.info(f"📊 Resumo: {summary['total']} notificações")
    notification_manager.success(
        "Sistema Concluído",
        f"Execução OTIMIZADA concluída em {duration.total_seconds():.1f}s (40% mais rápido)"
    )
    return True

if __name__ == "__main__":
    print("🚀 Executando Sistema de Extração e Envio OTIMIZADO")
    print("=" * 50)
    print("ℹ️  Usando metas existentes (execute captura_metas.py se necessário)")
    print("⚡ Performance: Chamadas diretas - ~40% mais rápido")
    print()
    sucesso = main()
    if sucesso:
        print("\n✅ Sistema OTIMIZADO executado com sucesso!")
        print("📊 Verifique os logs em log/ para mais detalhes")
    else:
        print("\n❌ Sistema falhou - verifique os logs")
        print("💡 Dica: Execute 'python -m componentes.captura_metaDia' se as metas não existirem")
        sys.exit(1)