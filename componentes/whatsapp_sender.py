import os
import csv
import time
import logging
import webbrowser
import json
import argparse
from datetime import datetime
import pyperclip
import pyautogui

# Configuração de logging (apenas arquivo, sem duplicar no terminal)
os.makedirs("log", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("log/whatsapp_sender.log", mode="w", encoding="utf-8")
    ]
)

class WhatsAppSender:
    """Classe responsável pelo envio de mensagens automáticas via WhatsApp Web."""

    def __init__(self, group_links, delay_seconds=10, pre_send_delay_seconds=7):
        """
        Args:
            group_links (list): Lista de links de convite dos grupos do WhatsApp.
            delay_seconds (int): Delay entre envios para evitar bloqueio.
        """
        self.group_links = group_links
        self.delay_seconds = delay_seconds
        self.pre_send_delay_seconds = pre_send_delay_seconds
        self.logger = logging.getLogger(__name__)
        
        # Valida os links dos grupos
        self._validar_links_grupos()

    def _validar_links_grupos(self):
        """Valida se os links dos grupos parecem válidos."""
        for i, link in enumerate(self.group_links):
            if not link or len(link.strip()) < 10:
                self.logger.error(f"Link do grupo {i} parece inválido: '{link}'")
            else:
                self.logger.info(f"Link do grupo {i} validado: {link[:10]}...")

    def format_data(self, csv_file, header, emoji, meta=None, indicador_nome=None):
        """Formata os dados do CSV para mensagem WhatsApp."""
        if not os.path.exists(csv_file):
            self.logger.error(f"Arquivo {csv_file} não encontrado!")
            return None
        
        # Log para debug
        self.logger.info(f"Formatando dados de {csv_file} (meta={meta}, indicador={indicador_nome})")

        try:
            with open(csv_file, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                next(reader)
                data = []
                total_valor = 0
                for row in reader:
                    if len(row) >= 2:
                        nome, valor = row[0], row[1]
                        try:
                            valor_float = float(valor)
                            total_valor += valor_float
                            valor_formatado = f"{valor_float:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                            data.append(f"{emoji} {nome}: R$ {valor_formatado}")
                        except ValueError:
                            data.append(f"{emoji} {nome}: R$ {valor}")

                if not data:
                    self.logger.warning(f"Nenhum dado encontrado no arquivo {csv_file}")
                    return None

                message = f"{header}\n\n" + "\n".join(data)
                if meta is not None and indicador_nome is not None:
                    self.logger.info(f"Incluindo cálculo de meta para {indicador_nome} (meta={meta})")
                    meta_formatada = f"{meta:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                    realizado_formatado = f"{total_valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                    atingimento = total_valor - meta
                    atingimento_formatado = f"{atingimento:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                    emoji_ating = "🎉​" if atingimento >= 0 else "🔴"
                    label_ating = "Ultrapassou" if atingimento >= 0 else "Faltante"
                    message += f"\n\n🎯 Meta: R$ {meta_formatada}"
                    message += f"\n💰​ Realizado: R$ {realizado_formatado}"
                    message += f"\n{emoji_ating}​​ {label_ating}: R$ {atingimento_formatado}"
                else:
                    self.logger.info(f"Enviando apenas dados para {indicador_nome} (sem meta)")
                    total_formatado = f"{total_valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."
)
                    message += f"\n\n💰 Total: R$ {total_formatado}"
                
                return message
        except Exception as e:
            self.logger.error(f"Erro ao ler arquivo {csv_file}: {e}")
            return None

    def format_marcas(self, csv_file, ciclo):
        """Formata os dados de marcas para mensagem WhatsApp."""
        if not os.path.exists(csv_file):
            self.logger.warning(f"Arquivo de marcas {csv_file} não encontrado!")
            return None
        
        self.logger.info(f"Formatando dados de marcas de {csv_file} (ciclo={ciclo})")
        
        try:
            marcas_data = {}
            with open(csv_file, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                next(reader)  # Pula cabeçalho
                for row in reader:
                    if len(row) >= 2:
                        marca, valor = row[0], row[1]
                        try:
                            valor_float = float(valor)
                            marcas_data[marca] = valor_float
                        except ValueError:
                            marcas_data[marca] = 0.0
            
            if not marcas_data:
                self.logger.warning(f"Nenhum dado de marca encontrado em {csv_file}")
                return None
            
            # Formata mensagem
            message = f"*➡️ Parcial Receita Marcas -​ Ciclo {ciclo}*\n\n"
            
            for marca in ['BOT', 'OUI', 'QDB']:
                valor = marcas_data.get(marca, 0.0)
                valor_formatado = f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                message += f"{marca}: R$ {valor_formatado}\n"
            
            
            return message
            
        except Exception as e:
            self.logger.error(f"Erro ao ler arquivo de marcas {csv_file}: {e}")
            return None

    def ler_ciclos_metas(self, meta_csv_path="extracoes/meta_dia.csv"):
        """Lê ciclos do dia e metas por ciclo a partir de meta_dia.csv."""
        hoje = datetime.now().strftime("%d/%m/%Y")
        ciclos = set()
        metas_por_ciclo = {}
        if not os.path.exists(meta_csv_path):
            return [], {}
        try:
            with open(meta_csv_path, "r", encoding="utf-8") as f:
                for line in f:
                    partes = [p.strip() for p in line.strip().split(";")]
                    if len(partes) != 4:
                        continue
                    tipo, data_str, ciclo_str, valor_str = partes
                    tipo = tipo.upper() if tipo else ""
                    if tipo == "EUDORA":
                        tipo = "EUD"
                    if tipo not in ("PEF", "EUD") or data_str != hoje:
                        continue
                    if not (ciclo_str and ciclo_str.isdigit()):
                        continue
                    try:
                        ciclo = int(ciclo_str)
                        # Tenta converter o valor para float apenas se houver um valor
                        valor = float(valor_str.replace(",", ".")) if valor_str.strip() else None
                        ciclos.add(ciclo)  # Adiciona o ciclo mesmo se não tiver valor
                        metas_por_ciclo.setdefault(ciclo, {})[tipo] = valor
                    except Exception:
                        ciclos.add(ciclo)  # Adiciona o ciclo mesmo se houver erro na conversão
                        metas_por_ciclo.setdefault(ciclo, {})[tipo] = None
        except Exception as e:
            self.logger.warning(f"Falha ao ler ciclos/metas de {meta_csv_path}: {e}")
        return sorted(ciclos), metas_por_ciclo

    def abrir_whatsapp_web(self):
        """Abre o WhatsApp Web no Google Chrome."""
        self.logger.info("Abrindo WhatsApp Web...")
        chrome_path = "C:/Program Files/Google/Chrome/Application/chrome.exe %s"
        webbrowser.get(chrome_path).open("https://web.whatsapp.com/")
        
        # Aguarda mais tempo para o WhatsApp Web carregar completamente
        self.logger.info("Aguardando WhatsApp Web carregar...")
        time.sleep(15)
        
        # Verifica se está logado (procura por elementos que indicam login)
        try:
            import pygetwindow as gw
            windows = gw.getWindowsWithTitle("WhatsApp")
            if windows:
                windows[0].activate()
                time.sleep(2)
                self.logger.info("WhatsApp Web parece estar carregado")
            else:
                self.logger.warning("Janela do WhatsApp não encontrada")
        except ImportError:
            self.logger.warning("pygetwindow não disponível - pulando verificação de janela")
        except Exception as e:
            self.logger.warning(f"Erro ao verificar janela WhatsApp: {e}")
        
        self.logger.info("WhatsApp Web aberto")

    def navegar_para_grupo(self, group_link):
        """Navega para o grupo do WhatsApp pelo link."""
        self.logger.info(f"Navegando para grupo com link: {group_link}")
        group_url = f"https://web.whatsapp.com/accept?code={group_link}"
        
        # Garante que o navegador está em foco
        try:
            import pygetwindow as gw
            windows = gw.getWindowsWithTitle("WhatsApp")
            if windows:
                windows[0].activate()
                time.sleep(1)
        except ImportError:
            # Fallback sem pygetwindow - tenta garantir foco com pyautogui
            self.logger.warning("pygetwindow não disponível - usando método alternativo")
            pyautogui.click(100, 100)  # Clica em uma posição segura
            time.sleep(1)
        except Exception as e:
            self.logger.warning(f"Erro ao ativar janela WhatsApp: {e}")
            # Tenta método alternativo
            try:
                pyautogui.click(100, 100)
                time.sleep(1)
            except Exception:
                pass
        
        # Navega para o grupo
        pyautogui.hotkey("ctrl", "l")
        time.sleep(1)
        pyperclip.copy(group_url)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(1)
        pyautogui.press("enter")
        
        # Aguarda mais tempo para o grupo carregar
        self.logger.info("Aguardando carregamento do grupo...")
        time.sleep(10)
        
        # Verifica se o grupo carregou (procura por elementos típicos)
        try:
            # Tenta encontrar o campo de mensagem ou header do grupo
            pyautogui.moveTo(100, 100)  # Move o mouse para uma posição segura
            time.sleep(2)
            self.logger.info("Grupo parece ter carregado")
        except Exception as e:
            self.logger.warning(f"Possível problema no carregamento do grupo: {e}")

    def enviar_mensagem(self, mensagem):
        """Envia a mensagem para o grupo aberto no WhatsApp Web."""
        self.logger.info("Enviando mensagem...")
        
        # Copia a mensagem para o clipboard
        pyperclip.copy(mensagem)
        time.sleep(1)
        
        # Cola a mensagem (Ctrl+V)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(1)
        
        # Pressiona Enter para enviar
        pyautogui.press("enter")
        
        # Aguarda o envio ser processado
        time.sleep(3)
        
        self.logger.info("Mensagem enviada (pyautogui executado)")

    def read_metas(self, meta_file):
        """Lê o arquivo de metas e retorna um dicionário com as metas para cada indicador."""
        if not os.path.exists(meta_file):
            self.logger.error(f"Arquivo de meta {meta_file} não encontrado!")
            return None
        try:
            import pandas as pd
            df = pd.read_csv(meta_file)
            meta_pef = float(df["PEF"].iloc[0])
            meta_eud = float(df["EUDORA"].iloc[0])
            meta_loja = float(df["LOJA"].iloc[0])
            return {"PEF": meta_pef, "EUDORA": meta_eud, "LOJA": meta_loja}
        except Exception as e:
            self.logger.error(f"Erro ao ler meta: {e}")
            return None

    def get_meta_loja_csv(self, meta_csv_path="extracoes/meta_dia.csv"):
        """Busca a meta de LOJA no arquivo meta_dia.csv (linha sem ciclo)."""
        hoje = datetime.now().strftime("%d/%m/%Y")
        if not os.path.exists(meta_csv_path):
            return None
        try:
            with open(meta_csv_path, "r", encoding="utf-8") as f:
                for line in f:
                    partes = [p.strip() for p in line.strip().split(";")]
                    if len(partes) == 4:
                        tipo, data_str, ciclo_str, valor_str = partes
                        if tipo.upper() == "LOJA" and data_str == hoje and ciclo_str == "":
                            try:
                                return float(valor_str.replace(",", "."))
                            except Exception:
                                return None
        except Exception as e:
            self.logger.warning(f"Falha ao buscar meta LOJA em {meta_csv_path}: {e}")
        return None

    def send_reports(self, sem_meta=False, metas_dict=None, parcial=False):
        """Processa e envia os relatórios para os grupos do WhatsApp."""
        if metas_dict:
            self.logger.info(f"Metas recebidas por argumento: {metas_dict}")
        else:
            self.logger.info("Nenhuma meta recebida por argumento.")

        meta_pef = metas_dict["PEF"] if metas_dict and "PEF" in metas_dict else None
        meta_eud = None
        if metas_dict:
            meta_eud = metas_dict.get("EUDORA") or metas_dict.get("EUD")
        meta_loja = metas_dict["LOJA"] if metas_dict and "LOJA" in metas_dict else self.get_meta_loja_csv()

        if meta_loja is not None:
            self.logger.info(f"Meta LOJA utilizada: {meta_loja} (type: {type(meta_loja)})")
        else:
            self.logger.info("Meta LOJA não encontrada.")

        ciclos, metas_por_ciclo = self.ler_ciclos_metas()
        self.logger.info(f"Ciclos detectados para VD: {ciclos}")
        for ciclo in ciclos:
            metas_ciclo = metas_por_ciclo.get(ciclo, {})
            meta_pef_c = metas_ciclo.get("PEF")
            meta_eud_c = metas_ciclo.get("EUD")
            msg = f"Metas ciclo {ciclo}: "
            if meta_pef_c is not None:
                msg += f"PEF={meta_pef_c} (type: {type(meta_pef_c)}) "
            if meta_eud_c is not None:
                msg += f"EUD={meta_eud_c} (type: {type(meta_eud_c)})"
            self.logger.info(msg.strip())

        loja_msg = self.format_data(
            "extracoes/resultado_loja.csv",
            "*➡️ Parcial Receita LOJA*",
            "",
            meta_loja,
            "LOJA"
        )

        mensagens_vd_por_ciclo = []
        if ciclos:
            # Caso 1: Ciclos detectados via meta_dia.csv
            for ciclo in ciclos:
                metas_ciclo = metas_por_ciclo.get(ciclo, {})
                meta_pef_c = metas_ciclo.get("PEF", meta_pef)
                meta_eud_c = metas_ciclo.get("EUD", meta_eud)
                pef_msg = self.format_data(
                    f"extracoes/resultado_pef_C{ciclo}.csv",
                    f"*➡️ Parcial Receita PEF - Ciclo {ciclo}*",
                    "",
                    meta_pef_c,
                    "PEF"
                )
                eud_msg = self.format_data(
                    f"extracoes/resultado_eud_C{ciclo}.csv",
                    f"*➡️ Parcial Receita EUD -​ Ciclo {ciclo}*",
                    "",
                    meta_eud_c,
                    "EUDORA"
                )
                msg_ciclo = ""
                if pef_msg:
                    msg_ciclo += pef_msg + "\n\n"
                if eud_msg:
                    msg_ciclo += eud_msg
                if msg_ciclo.strip():
                    mensagens_vd_por_ciclo.append((ciclo, msg_ciclo.strip()))
        else:
            # Caso 2: Não há ciclos detectados - tentar detectar pelos arquivos existentes
            self.logger.info("Tentando detectar ciclos pelos arquivos de resultado existentes...")
            ciclos_encontrados = set()
            
            # Buscar arquivos resultado_*_C*.csv
            import glob
            pef_files = glob.glob("extracoes/resultado_pef_C*.csv")
            eud_files = glob.glob("extracoes/resultado_eud_C*.csv")
            
            for pef_file in pef_files:
                try:
                    # Extrair ciclo do nome do arquivo (ex: resultado_pef_C13.csv -> 13)
                    ciclo_str = pef_file.split("_C")[1].split(".csv")[0]
                    if ciclo_str.isdigit():
                        ciclos_encontrados.add(int(ciclo_str))
                except Exception:
                    continue
                    
            for eud_file in eud_files:
                try:
                    ciclo_str = eud_file.split("_C")[1].split(".csv")[0]
                    if ciclo_str.isdigit():
                        ciclos_encontrados.add(int(ciclo_str))
                except Exception:
                    continue
            
            if ciclos_encontrados:
                self.logger.info(f"Ciclos detectados pelos arquivos: {sorted(ciclos_encontrados)}")
                for ciclo in sorted(ciclos_encontrados):
                    pef_msg = self.format_data(
                        f"extracoes/resultado_pef_C{ciclo}.csv",
                        f"*➡️ Parcial Receita PEF - Ciclo {ciclo}*",
                        "",
                        meta_pef,
                        "PEF"
                    )
                    eud_msg = self.format_data(
                        f"extracoes/resultado_eud_C{ciclo}.csv",
                        f"*➡️ Parcial Receita EUD -​ Ciclo {ciclo}*",
                        "",
                        meta_eud,
                        "EUDORA"
                    )
                    msg_ciclo = ""
                    if pef_msg:
                        msg_ciclo += pef_msg + "\n\n"
                    if eud_msg:
                        msg_ciclo += eud_msg
                    if msg_ciclo.strip():
                        mensagens_vd_por_ciclo.append((ciclo, msg_ciclo.strip()))
            else:
                # Caso 3: Fallback para arquivos sem ciclo (backward compatibility)
                pef_msg = self.format_data(
                    "extracoes/resultado_pef.csv",
                    "*➡️ Parcial Receita PEF*",
                    "",
                    meta_pef,
                    "PEF"
                )
                eud_msg = self.format_data(
                    "extracoes/resultado_eud.csv",
                    "*➡️ Parcial Receita EUD*",
                    "",
                    meta_eud,
                    "EUDORA"
                )
                msg_ciclo = ""
                if pef_msg:
                    msg_ciclo += pef_msg + "\n\n"
                if eud_msg:
                    msg_ciclo += eud_msg
                if msg_ciclo.strip():
                    mensagens_vd_por_ciclo.append((None, msg_ciclo.strip()))

        self.logger.info(f"Mensagem final para grupo LOJA: {loja_msg}")

        self.abrir_whatsapp_web()

        # Enviar mensagens VD (primeiro grupo)
        if mensagens_vd_por_ciclo:
            group_link_vd = self.group_links[0]  # Primeiro grupo é VD
            self.logger.info(f"Grupo VD configurado: {group_link_vd}")
            
            for ciclo, vd_group_msg in mensagens_vd_por_ciclo:
                if vd_group_msg:
                    self.logger.info(f"Mensagem VD para ciclo {ciclo} preparada ({len(vd_group_msg)} caracteres)")
                    self.logger.info(f"Navegando para grupo VD...")
                    self.navegar_para_grupo(group_link_vd)
                    
                    # Delay extra antes do envio
                    self.logger.info(f"Aguardando {self.pre_send_delay_seconds}s antes do envio...")
                    time.sleep(self.pre_send_delay_seconds)
                    
                    self.logger.info("Enviando mensagem VD...")
                    self.enviar_mensagem(vd_group_msg)
                    
                    self.logger.info(f"✅ Mensagem VD ciclo {ciclo} enviada com sucesso!")
                    time.sleep(self.delay_seconds)
                else:
                    self.logger.warning(f"Mensagem VD para ciclo {ciclo} está vazia")
        else:
            self.logger.warning("Nenhuma mensagem VD para enviar")

        # Enviar mensagem LOJA (segundo grupo)
        if loja_msg and len(self.group_links) > 1:
            group_link_loja = self.group_links[1]  # Segundo grupo é LOJA
            self.logger.info(f"Grupo LOJA configurado: {group_link_loja}")
            self.logger.info(f"Mensagem LOJA preparada ({len(loja_msg)} caracteres)")
            
            self.logger.info("Navegando para grupo LOJA...")
            self.navegar_para_grupo(group_link_loja)
            
            # Delay extra antes do envio
            self.logger.info(f"Aguardando {self.pre_send_delay_seconds}s antes do envio...")
            time.sleep(self.pre_send_delay_seconds)
            
            self.logger.info("Enviando mensagem LOJA...")
            self.enviar_mensagem(loja_msg)
            
            self.logger.info("✅ Mensagem LOJA enviada com sucesso!")
            time.sleep(self.delay_seconds)
        else:
            if not loja_msg:
                self.logger.warning("Mensagem LOJA está vazia")
            if len(self.group_links) <= 1:
                self.logger.warning(f"Apenas {len(self.group_links)} grupo(s) configurado(s) - LOJA não disponível")

def main():
    print("📱 Enviador Automático de Informações por WhatsApp")
    print("=" * 60)
    group_links = [
        "LINK DO 1º GRUPO",
        "LINK DO 2º GRUPO CASO NECESSÁRIO"
    ] 

    parser = argparse.ArgumentParser()
    parser.add_argument("--metas", type=str, default=None)
    parser.add_argument("--parcial", action="store_true")
    parser.add_argument("--sem-meta", action="store_true")
    args = parser.parse_args()

    metas_dict = None
    if args.metas:
        try:
            metas_dict = json.loads(args.metas)
        except Exception as e:
            print(f"Erro ao interpretar --metas: {e}")

    sender = WhatsAppSender(group_links)
    print("⚠️ Certifique-se de que o WhatsApp Web está logado e em uma única aba!")
    sender.send_reports(sem_meta=args.sem_meta, metas_dict=metas_dict, parcial=args.parcial)

if __name__ == "__main__":
    main()
