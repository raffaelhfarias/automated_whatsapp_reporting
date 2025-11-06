<h1 align="center">
  <br>
  <a href="https://raw.githubusercontent.com/raffaelhfarias/automated_whatsapp_reporting/refs/heads/main/imagens/"><img src="https://raw.githubusercontent.com/raffaelhfarias/automated_whatsapp_reporting/refs/heads/main/imagens/1f916.png" alt="Markdownify" width="200"></a>
  <br>
  Whatsapp Sender Report
  <br>
</h1>

<h4 align="center">Sistema robusto e inteligente para automação de captura de metas, extração de dados de vendas e envio automatizado de relatórios via WhatsApp.</h4>

<div align="center">
  <img src="https://img.shields.io/badge/Python-3.x-blue?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/Selenium-Web_Automation-red?logo=selenium&logoColor=white" alt="Selenium">
  <img src="https://img.shields.io/badge/PyAutoGUI-GUI_Automation-yellow?logo=python&logoColor=white" alt="PyAutoGUI">
  <img src="https://img.shields.io/badge/lxml-XML_&_HTML_Parser-green?logo=python&logoColor=white" alt="lxml">
  <img src="https://img.shields.io/badge/undetected--chromedriver-Chrome_Automation-orange?logo=google-chrome&logoColor=white" alt="undetected-chromedriver">
  <img src="https://img.shields.io/badge/python--dotenv-Environment_Vars-blue?logo=python&logoColor=white" alt="python-dotenv">
  <img src="https://img.shields.io/badge/pywhatkit-WhatsApp_Automation-lightgreen?logo=whatsapp&logoColor=white" alt="pywhatkit">
</div>


<p align="center">
  <a href="#key-features">Key Features</a> •
  <a href="#how-to-use">How To Use</a> •
  <a href="#download">Download</a> •
  <a href="#credits">Credits</a> •
  <a href="#license">License</a>
</p>

<p align="center">
  <img src="https://github.com/raffaelhfarias/automated_whatsapp_reporting/blob/main/videos/envioWhatsapp.gif?raw=true" alt="screenshot" width="600">
</p>

## Key Features

* Captura automática de metas em grupos WhatsApp
  - Extração inteligente de valores de metas diárias
* Extração de dados de vendas
  - Integração com sistemas Loja, PEF e EUDORA
  - Validação automática de dados
* Envio automático de relatórios
  - Formatação inteligente de mensagens
  - Agendamento configurável
* Sistema de flags inteligente
  - Evita tentativas desnecessárias
  - Recuperação automática de falhas
* Logs detalhados
  - Monitoramento completo de operações
  - Diagnóstico rápido de problemas
* Suporte a múltiplos ciclos
  - Detecção automática de ciclos (C12, C13, etc.)
* Cross-platform
  - Windows, macOS e Linux compatível

## How To Use

Para clonar e executar este projeto, você precisará do [Git](https://git-scm.com) e [Python](https://python.org) (versão 3.8+) instalados no seu computador. No terminal:

```bash
# Clone este repositório
$ git clone https://github.com/seu-usuario/roboWhatsapp

# Entre no diretório
$ cd roboWhatsapp

# Crie um ambiente virtual
$ python -m venv .venv

# Ative o ambiente virtual
# Windows:
$ .\.venv\Scripts\activate
# Linux/macOS:
$ source .venv/bin/activate

# Instale as dependências
$ pip install -r requirements.txt

# Configure as variáveis de ambiente (copie .env.example para .env)
$ cp .env.example .env
# Edite .env com suas credenciais

# Execute o sistema
$ python main.py
```

> **Nota**
> Certifique-se de ter o Google Chrome instalado e configurado para automação.

## Download

Você pode [baixar](https://github.com/raffaelhfarias/raffaelhfarias/automated_whatsapp_reporting) a versão mais recente do RoboWhatsApp para Windows, macOS e Linux.

## Credits

Este software utiliza os seguintes pacotes open source:

- [Selenium](https://www.selenium.dev/) - Automação web
- [undetected-chromedriver](https://github.com/ultrafunkamsterdam/undetected-chromedriver) - ChromeDriver não detectável
- [Python](https://python.org/) - Linguagem de programação
- [schedule](https://github.com/dbader/schedule) - Agendamento de tarefas
- [python-dotenv](https://github.com/theskumar/python-dotenv) - Carregamento de variáveis de ambiente
- [lxml](https://lxml.de/) - Processamento XML/HTML
- [PyAutoGUI](https://pyautogui.readthedocs.io/) - Automação GUI

## License

MIT

---

> [portfólio](https://raffaelhfarias.github.io/) &nbsp;&middot;&nbsp;
> GitHub [@raffaelhfarias](https://github.com/raffaelhfarias) &nbsp;&middot;&nbsp;

