import os
import sys

# Patch anti-bug aiohttp (Python 3.14/Windows) pour la connexion WSS de edge-tts
import aiohttp.helpers
_old_get_env_proxy_for_url = aiohttp.helpers.get_env_proxy_for_url
def _patched_get_env_proxy_for_url(url):
    try:
        return _old_get_env_proxy_for_url(url)
    except Exception:
        return None, None
aiohttp.helpers.get_env_proxy_for_url = _patched_get_env_proxy_for_url

# Nettoyage supplémentaire des variables d'environnement
for var in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"]:
    os.environ.pop(var, None)

import asyncio
import json
import random
import time
import threading
import requests
import nest_asyncio
import edge_tts
import whisper
from openai import OpenAI
from moviepy import VideoFileClip, AudioFileClip, TextClip, CompositeVideoClip, concatenate_videoclips

# Application de nest_asyncio
nest_asyncio.apply()

# Module TikTok
from tiktok_uploader.upload import upload_video

# Authentification et API YouTube
import google_auth_oauthlib.flow
import googleapiclient.discovery
import googleapiclient.errors
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.http import MediaFileUpload

# =========================================================
# CONFIGURATION ET CLÉS
# =========================================================
# Les clés sont récupérées depuis les variables d'environnement (.env)
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "VOTRE_CLE_GROQ")
PIXABAY_API_KEY = os.getenv("PIXABAY_API_KEY", "VOTRE_CLE_PIXABAY")
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

HISTORY_FILE = "history.json"
TOKEN_FILE = "token.json"
COOKIES_FILE = "cookies.txt"

VOICES = ["fr-FR-HenriNeural", "fr-FR-DeniseNeural", "fr-FR-RemyMultilingualNeural"]
THEMES = [
    "une vérité psychologique captivante sur le cerveau humain et nos habitudes",
    "un principe stoïcien puissant pour garder le contrôle émotionnel au quotidien",
    "un fait scientifique méconnu et fascinant sur la perception du temps",
    "un conseil d'ultra-productivité utilisé par les plus grands leaders pour éviter la procrastination",
    "une leçon de vie profonde inspirée par les grandes figures historiques"
]
SEARCH_KEYWORDS = ["nature", "galaxy", "technology", "ocean", "city night", "abstract", "forest", "space", "architecture"]

# Chargement de l'historique anti-répétition
if os.path.exists(HISTORY_FILE):
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        history = json.load(f)
else:
    history = {"scripts": [], "video_ids": []}

def save_history():
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

# =========================================================
# AUTHENTIFICATION YOUTUBE AUTONOME
# =========================================================
def get_youtube_service():
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(
                "client_secret.json", SCOPES
            )
            creds = flow.run_local_server(port=0)

        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())

    return googleapiclient.discovery.build("youtube", "v3", credentials=creds)

# =========================================================
# PUBLICATION TIKTOK
# =========================================================
def publish_to_tiktok(video_path, description):
    print("Mise en ligne sur TikTok...")
    if not os.path.exists(COOKIES_FILE):
        print("Avertissement : Le fichier 'cookies.txt' est introuvable. Étape TikTok ignorée.")
        return

    try:
        upload_video(
            video_path,
            description=description,
            cookies=COOKIES_FILE,
            browser='chromium',
            headless=False
        )
        print("--- [SUCCÈS] Vidéo publiée sur TikTok ---")
    except Exception as e:
        print(f"Erreur lors de la publication TikTok : {e}")

# =========================================================
# GENERATION ET PUBLICATION SIMULTANÉE
# =========================================================
def generate_and_upload_short():
    print("\n--- [NOUVEAU SHORT] Début de la génération ---")

    # 1. Génération du script via Groq
    client = OpenAI(
        api_key=GROQ_API_KEY,
        base_url="https://api.groq.com/openai/v1"
    )
    theme = random.choice(THEMES)
    
    prompt = (
        f"Rédige un court texte captivant en 2 phrases (entre 35 et 50 mots au total) sur le thème suivant : {theme}. "
        "La première phrase doit accrocher l'attention et la deuxième apporter la révélation/le conseil. "
        f"Ne répète aucune de ces idées : {history['scripts'][-20:]}. "
        "Donne uniquement le texte en français, sans guillemets ni introduction."
    )

    models_to_try = ["openai/gpt-oss-20b", "llama3-70b-8192", "llama3-8b-8192"]
    texte = None

    for model_name in models_to_try:
        try:
            print(f"Essai de génération avec Groq ({model_name})...")
            res = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}]
            )
            texte = res.choices[0].message.content.strip()

            if texte:
                break
        except Exception as e:
            print(f"Modèle {model_name} indisponible : {e}")

    if not texte:
        raise Exception("Aucun modèle Groq n'a fonctionné. Vérifie ta clé API GROQ_API_KEY.")

    history["scripts"].append(texte)
    save_history()
    print(f"Script généré : {texte}")

if __name__ == "__main__":
    generate_and_upload_short()