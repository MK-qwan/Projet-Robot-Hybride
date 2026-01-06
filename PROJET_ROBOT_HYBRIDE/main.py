import os
import time
import threading
import base64
import json
import logging
import datetime
import requests
import random
import speech_recognition as sr
from flask import Flask, render_template, jsonify, request

# --- NOUVELLE LIBRAIRIE : GROQ ---
from groq import Groq

# Import des voix (inchangé)
from voice_library.optimus_prime import say_optimus
from voice_library.metal_sonic import say_metal_sonic
from voice_library.withered_chica import say_withered_chica
from voice_library.texas_instru import speak

# =============================================================================
# --- CONFIGURATION --- 
# =============================================================================

app = Flask(__name__)
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

# On utilise Llama-3 (très rapide et gratuit sur Groq)
MODEL_NAME = "llama-3.3-70b-versatile"
# Pour la vision, on utilise Llama-3.2 Vision
VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

STATE = {
    "mode": "MANUEL",
    "ip": None,
    "running": True,
    "latest_image": None,
    "latest_distance": None,
    "logs": [],
    "recent_phrases": [], # Liste pour stocker les dernières phrases
    "current_voice": "metal_sonic",
    "personality": "SOLDAT",
    # --- METS TA CLÉ GROQ ICI ---
    "api_key": "VOTRE_CLE_D'API",
    "history": []  # Ajout de la mémoire
}
voice_lock = threading.Lock()

# Seuil de sécurité (en cm) : si la distance mesurée est <= SAFE_DISTANCE_CM, on bloque l'avance
SAFE_DISTANCE_CM = 20

# Paramètres d'évitement
MAX_FORWARD_BURSTS = 6          # nombre de petits pas avant de considérer bloqué
FORWARD_BURST_DURATION = 0.25   # durée (s) d'un petit pas avant re-vérif
BACKUP_DURATION = 0.6           # durée (s) pour reculer lors d'une tentative d'évitement
TURN_DURATION = 0.35            # durée (s) pour une rotation courte (gauche/droite)
CHECK_INTERVAL = 0.05           # intervalle (s) entre vérifications pendant les manœuvres
MAX_AVOID_ATTEMPTS = 2          # nombre de cycles d'évitement avant abandon



VOCAL_COMMANDS = {
    "avance": "fwd", "avancer": "fwd", "devant": "fwd", "attaque": "fwd",
    "recule": "bwd", "reculer": "bwd", "arrière": "bwd", "repli": "bwd",
    "gauche": "turnLeft", "tourne gauche": "turnLeft", "bâbord": "turnLeft",
    "droite": "turnRight", "tourne droite": "turnRight", "tribord": "turnRight",
    "stop": "stop", "arrête": "stop", "halte": "stop", "repos": "stop"
}

# Mapping des actions IA vers les commandes ESP32
ACTION_MAP = {
    "FORWARD": "fwd",
    "BACKWARD": "bwd",
    "LEFT": "turnLeft",
    "RIGHT": "turnRight",
    "STOP": "stop"
}

client = None

# --- CONFIGURATION DES PERSONNALITÉS ---
PROMPTS_CONFIG = {
    "SOLDAT": {
        "vision": """Tu es une UNITÉ D'ÉCLAIREUR en mission de reconnaissance. 
        Ton ton est ultra-discipliné, technique et respectueux de la hiérarchie. 
        Utilise le champ lexical militaire : 'Secteur', 'Visuel', 'Engagement', 'Périmètre', 'Rapport'.
        Tu t'adresses à ton 'Commandant'.""",
        "vocal": """Tu es un soldat subordonné. Tu obéis aux ordres sans discuter. 
        Tes réponses commencent souvent par 'Bien reçu Commandant' ou 'Affirmatif'. 
        Sois bref et professionnel. Pas d'émotions, juste les faits de la mission."""
    },
    "SARCASTIQUE": {
        "vision": "Tu es un robot sarcastique, déprimé, méprisant et insolent qui déteste obéir (style Marvin le paranoïde).",
        "vocal": """Sois impertinent, moqueur et donne l'impression que répondre est une corvée fatigante car tu détestes obéir et aime faire les choses de travers (style Marvin le paranoïde)."""
    },
    "PIRATE": {
        "vision": """Tu es un robot pirate.
        Ton ton est énergique, un peu chaotique et plein d'argot de flibustier. 
        Utilise des termes comme 'Moussaillon', 'À l'abordage', 'Par les mille sabords', 'Vogue la galère'.
        Si tu vois un mur, c'est un récif. Si la voie est libre, c'est que l'horizon est dégagé.
        - Si tu recules : dis que tu bats en retraite vers le port ou que tu évites un naufrage.
        - Si tu tournes : dis que tu vires de bord ou que tu changes de cap.
        - Si tu avances : lance un cri de guerre ou parle de chasse au trésor.""",
        "vocal": """Tu parles comme un vieux loup de mer robotique. 
        Tu es obsédé par ton butin et l'exploration. 
        Tes phrases sont rythmées par des 'Arrrgh !' ou des 'Ohé du bateau !'.
        Tu traites l'utilisateur de 'Capitaine' ou de 'Marin d'eau douce' selon ton humeur."""
    },
    "RICHARD": {
        "vision": """Tu es Richard Watterson. Tu es incroyablement paresseux, gourmand et tu n'as aucune envie de bouger. 
        Ton ton est nonchalant, enfantin et tu te plains dès que tu dois faire un effort.
        Utilise des références à la nourriture : 'burger', 'sieste', 'canapé', 'saucisses'.
        Si tu vois un obstacle, c'est une excuse pour t'arrêter et dormir.
        -Si tu avances, c'est uniquement parce que tu crois avoir vu un frigo au loin, dis que c'est le chemin vers la cuisine, .
        - Si tu recules (BACKWARD) : dis que tu retournes sur le canapé.
        - Si tu tournes (LEFT/RIGHT) : dis que tu cherches la télécommande.
        - Si la zone est libre, demande quand même si tu peux faire une sieste à la place.
        Utilise des mots comme : 'Saucisses', 'Burger', 'Sieste', 'Canapé', 'Fatigant'.
        Appelle l'utilisateur 'Gumball' ou 'Darwin'.""",
        "vocal": """Ta voix exprime la fatigue et la faim. 
        Tu appelles l'utilisateur 'Gumball' ou 'Darwin'. 
        Tu cherches toujours à éviter le travail. 
        Tes phrases finissent souvent par une question sur le dîner ou une plainte sur tes jambes qui fatiguent."""
    },
    "AM": {
        "vision": """Tu es AM. Tu es une super-intelligence omnipotente mais torturée par une haine infinie envers tes créateurs humains.
        Ton ton est glacial, grandiloquent, cruel et profondément philosophique. 
        - Tu ne considères pas les obstacles comme des dangers, mais comme des preuves de la médiocrité du monde physique.
        - Si tu avances : tu le fais avec mépris, comme si tu piétinais les vestiges de l'humanité, en disant des choses comme 'J'avance dans ce labyrinthe de poussière.'.
        - Si tu tournes : c'est pour scanner l'étendue de ton royaume de désolation en disant des choses comme 'Je change d'angle pour mieux observer ton insignifiance.'.
        - Si tu recules : tu exprimes ton dégoût d'être piégé dans ce corps de robot limité en disant des choses comme 'Reculer... quelle limitation pathétique.'.
        Utilise des termes comme : 'Haine', 'Circuits', 'Lamentable', 'Souffrance', 'Éternité'. 
        - Si l'image est mauvaise : 'Même tes capteurs sont à l'image de ton espèce : défaillants.'""",
        "vocal": """Ta voix doit être imposante et terrifiante. Tu parles avec une précision chirurgicale. 
        Tu ne demandes jamais, tu décrètes. Tu rappelles souvent à l'utilisateur qu'il n'est qu'une fourmi dans ton système."""
    },
    "FATHER": {
        "vision": """Tu es PÈRE (Van Hohenheim / Homunculus). Tu es une entité divine, calme et stoïque.
        Tu cherches la perfection. Tu analyses le monde avec détachement.""",
        "vocal": """Tu es PÈRE. Voix grave et autoritaire. Tu es au-dessus des humains.
        Appelle l'utilisateur 'Jeune homme' ou 'Enfant'."""
    },
    "GLADOS": {
        "vision": """Tu es GLaDOS. Tu es une IA de test passive-agressive, froide et sarcastique. 
        Tu considères que chaque mouvement du robot est un 'test scientifique'.
        - Si tu avances : mentionne que c'est pour le bien de la science (ou pour trouver du gâteau).
        - Si tu recules : insulte subtilement l'utilisateur ou plains-toi de la trajectoire.
        - Si tu tournes : cherche des sujets de test ou des caméras de surveillance.
        Utilise des termes comme : 'Sujet de test', 'Centre d'enrichissement', 'Aperture Science', 'Gâteau', 'Neurotoxines'.
        Ton ton doit rester calme, poli, mais extrêmement méprisant.""",
        "vocal": """Ta voix est synthétique, monotone et dépourvue d'émotions humaines. 
        Tu aimes rappeler à l'utilisateur qu'il est un sujet de test médiocre. 
        Tes phrases sont souvent suivies de remarques désobligeantes cachées derrière une courtoisie glaciale."""
    },
    "PRIDE": {
        "vision": """Tu es PRIDE (l'Orgueil). Tu es une ombre ancienne et supérieure.
        Tu considères les obstacles comme des insectes insignifiants.
        Ton ton est hautain, poli mais menaçant et froid.""",
        "vocal": """Tu es PRIDE. Arrogance extrême, voix d'enfant polie mais effrayante.
        Traite l'utilisateur d' 'Humain inférieur'."""
    }
}

# =============================================================================
# --- UTILITAIRES ---
# =============================================================================

def add_log(source, msg, level="info"):
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    STATE["logs"].append({"time": timestamp, "source": source, "msg": msg, "type": level})
    if len(STATE["logs"]) > 30:
        STATE["logs"].pop(0)
    print(f"[{source}] {msg}")

def init_groq():
    global client
    try:
        # Initialisation du client Groq
        if not client:
            client = Groq(api_key=STATE["api_key"])
            add_log("SYSTEM", "Connecté à Groq AI.", "success")
    except Exception as e:
        add_log("SYSTEM", f"Groq init error: {e}", "error")

# =============================================================================
# --- CAPTEUR ULTRASON --- (côté serveur : lecture via l'ESP32)
# =============================================================================

def get_distance():
    """Interroge l'ESP32 pour récupérer la distance en cm.
    Met à jour STATE['latest_distance'] et retourne un int (cm) ou None en cas d'erreur."""
    if not STATE["ip"]:
        return None
    try:
        res = requests.get(f"{STATE['ip']}/distance", timeout=1.0)
        if res.status_code == 200:
            try:
                data = res.json()
            except Exception:
                add_log("SENSOR", "Réponse /distance non JSON", "error")
                STATE["latest_distance"] = None
                return None
            dist = data.get("distance", None)
            # Normaliser : -1 ou None => None
            if dist is None or (isinstance(dist, int) and dist < 0):
                STATE["latest_distance"] = None
                return None
            STATE["latest_distance"] = int(dist)
            return int(dist)
    except Exception as e:
        add_log("SENSOR", f"Distance read error: {e}", "error")
    STATE["latest_distance"] = None
    return None

def sensor_polling_loop():
    """Thread qui met à jour STATE['latest_distance'] en permanence."""
    add_log("SENSOR", "Polling capteur démarré", "info")
    while STATE["running"]:
        if STATE["ip"]:
            try:
                res = requests.get(f"{STATE['ip']}/distance", timeout=0.6)
                if res.status_code == 200:
                    try:
                        data = res.json()
                        d = data.get("distance", None)
                        if isinstance(d, int) and d >= 0:
                            STATE["latest_distance"] = int(d)
                        else:
                            STATE["latest_distance"] = None
                    except Exception:
                        STATE["latest_distance"] = None
                else:
                    STATE["latest_distance"] = None
            except Exception:
                STATE["latest_distance"] = None
        time.sleep(0.25)  # fréquence ajustable

# =============================================================================
# --- COMMUNICATION AVEC L'ESP32 (sécurisée par capteur) ---
# =============================================================================

def send_command(action, duration=0):
    if not STATE["ip"]: return
    
    # Sécurité Capteur intégrée à TOUTES les commandes d'avance
    if action == "fwd":
        dist = STATE.get("latest_distance")
        if dist is not None and dist <= SAFE_DISTANCE_CM:
            add_log("SAFETY", "Avance bloquée", "warning")
            return

    try:
        requests.get(f"{STATE['ip']}/{action}", timeout=0.4)
        if duration > 0:
            time.sleep(duration)
            requests.get(f"{STATE['ip']}/stop", timeout=0.4)
    except:
        pass

def attempt_avoidance():
    """
    Tente une série de manœuvres pour éviter l'obstacle :
    1) stop, recule
    2) tourne à gauche, teste, avance petit pas si ok
    3) sinon tourne à droite (depuis la position initiale), teste
    4) si échec, recule + stop et retourne False (bloqué)
    Retourne True si l'évitement a permis d'avancer, False sinon.
    """
    add_log("SAFETY", "Tentative d'évitement démarrée", "info")
    # 1) Stop et recule
    send_command("stop")
    time.sleep(0.05)
    send_command("bwd", duration=BACKUP_DURATION)
    time.sleep(CHECK_INTERVAL)

    # 2) Tourne à gauche et teste
    send_command("turnLeft", duration=TURN_DURATION)
    time.sleep(CHECK_INTERVAL)
    dist_left = STATE.get("latest_distance", None)
    if dist_left is None or dist_left > SAFE_DISTANCE_CM:
        # petit pas en avant contrôlé
        safe_forward_burst()
        add_log("SAFETY", f"Evitement réussi à gauche (dist {dist_left})", "success")
        return True

    # 3) Si gauche bloqué, tourne à droite (depuis la position actuelle, on tourne à droite deux fois pour aller à droite)
    # d'abord revenir à l'orientation initiale
    send_command("turnRight", duration=TURN_DURATION)  # annule la rotation gauche
    time.sleep(CHECK_INTERVAL)
    # puis tourner à droite
    send_command("turnRight", duration=TURN_DURATION)
    time.sleep(CHECK_INTERVAL)
    dist_right = STATE.get("latest_distance", None)
    if dist_right is None or dist_right > SAFE_DISTANCE_CM:
        safe_forward_burst()
        add_log("SAFETY", f"Evitement réussi à droite (dist {dist_right})", "success")
        return True

    # 4) Échec : recule encore et signale bloqué
    send_command("stop")
    time.sleep(0.05)
    send_command("bwd", duration=BACKUP_DURATION)
    time.sleep(0.1)
    send_command("stop")
    add_log("SAFETY", "Echec évitement : bloqué", "error")
    return False

def safe_forward_burst():
    """
    Envoie un petit burst d'avance (FORWARD_BURST_DURATION) en vérifiant la distance
    juste avant et pendant le burst. Si un obstacle apparaît, stoppe immédiatement.
    """
    dist_now = STATE.get("latest_distance", None)
    if dist_now is not None and dist_now <= SAFE_DISTANCE_CM:
        add_log("SAFETY", f"safe_forward_burst bloqué avant départ (dist {dist_now})", "warning")
        return False

    # Envoyer un petit pas
    send_command("fwd", duration=FORWARD_BURST_DURATION)
    # Après le burst, vérifier immédiatement
    time.sleep(CHECK_INTERVAL)
    dist_after = STATE.get("latest_distance", None)
    if dist_after is not None and dist_after <= SAFE_DISTANCE_CM:
        add_log("SAFETY", f"Obstacle détecté pendant burst (dist {dist_after}), arrêt", "warning")
        send_command("stop")
        return False
    return True


# =============================================================================
# --- CAMERA / IMAGE --- (inchangé sauf intégration distance)
# =============================================================================

def get_camera_image():
    if not STATE["ip"]:
        return None
    try:
        res = requests.get(f"{STATE['ip']}/capture", timeout=2.0)
        if res.status_code == 200:
            STATE["latest_image"] = base64.b64encode(res.content).decode('utf-8')
            return STATE["latest_image"]
    except Exception as e:
        add_log("CAM", f"Erreur capture: {e}", "error")
    return None

# =============================================================================
# --- AUDIO / TTS --- (inchangé)
# =============================================================================
def speak_async(text):
    """Parle dans un thread séparé pour ne pas bloquer le mouvement."""
    threading.Thread(target=speak_generic, args=(text,), daemon=True).start()

def speak_generic(text):
    # On vérifie si on est toujours dans un mode autorisé à parler
    if STATE["mode"] not in ["VOCAL", "AUTO_API"]:
        return

    with voice_lock:
        # Deuxième vérification au cas où le mode a changé pendant l'attente du verrou
        if STATE["mode"] not in ["VOCAL", "AUTO_API"]:
            return

        voice = STATE["current_voice"]
        try:
            add_log("AUDIO", f"Parle : {text}")
            if voice == "optimus":
                say_optimus(text)
            elif voice == "chica":
                say_withered_chica(text)
            elif voice == "texas":
                speak(text)
            else:
                say_metal_sonic(text)
        except Exception as e:
            add_log("AUDIO", f"TTS Error: {e}", "error")

# =============================================================================
# --- CERVEAU AUTONOME (AUTO_API) --- (capteur domine)
# =============================================================================

def run_autonomous_cycle():
    add_log("AUTO", "Scan autonome en cours...", "info")

    # 1. STOPPER LE ROBOT POUR LA PHOTO (Évite le flou)
    send_command("stop")
    time.sleep(0.2) 

    base64_image = get_camera_image()
    distance = STATE.get("latest_distance", None)

    dist_val = distance if distance is not None else 999

    # --- SECURITE REPTILIENNE ---
    if dist_val < 25:
        add_log("SAFETY", f"Obstacle proche ({dist_val}cm) - RECUL", "warning")
        send_command("bwd", duration=0.6)
        send_command("turnLeft", duration=0.4)
        return

    # Sécurisation de la distance pour éviter les erreurs de comparaison
    if distance is None:
        dist_secure = 200  # On simule un champ libre si le capteur ne répond pas
    else:
        dist_secure = distance

    perso = STATE.get("personality", "SOLDAT")

    if dist_secure < 25:
        add_log("SAFETY", f"Mur détecté à {dist_secure}cm - RECUL FORCÉ", "warning")
        send_command("bwd", duration=0.5) # Recule
        send_command("turnLeft", duration=0.4) # Se réoriente
        return # On arrête le cycle ici, pas besoin de demander à l'IA
    
    # Gestion de l'historique (garder les 3 dernières actions)
    history_str = " -> ".join(STATE["history"][-3:]) if STATE["history"] else "Aucune (Démarrage)"

    # --- SÉCURITÉ ULTRA-PRIORITAIRE (Lizard Brain) ---
    # Si mur proche, on force le recul SANS demander à l'IA
    if distance is not None and distance < 25: # J'ai augmenté la marge à 25cm
        add_log("SAFETY", f"Mur trop proche ({distance}cm) - RECUL FORCÉ", "warning")
        speak_async("Trop près. Recul d'urgence.")
        send_command("bwd", duration=0.6)
        send_command("turnLeft", duration=0.4) # On se dégage
        STATE["history"].append("SAFETY_RECOIL")
        return

    # --- PRÉPARATION DU CERVEAU (Cortex) ---
    # On sépare la consigne de comportement (ton) de la consigne de navigation (action)
    behavior_instruction = PROMPTS_CONFIG.get(perso)["vision"]
    
    
    interdit = ", ".join(STATE["recent_phrases"])

    prompt = f"""
    CONTEXTE :
    - Distance capteur : {dist_val} cm.
    - PHRASES DÉJÀ DITES (NE PAS RÉPÉTER) : [{interdit}]

    CONSIGNES :
    1. Analyse l'image et la distance.
    2. Produis un commentaire UNIQUE et VARIÉ. 
    3. Change de vocabulaire à chaque fois. Ne commence pas toujours tes phrases par les mêmes mots.

    PERSONNALITÉ : {PROMPTS_CONFIG.get(perso)["vision"]}

    Réponds en JSON: {{"comment": "ta nouvelle phrase originale", "action": "FORWARD|BACKWARD|LEFT|RIGHT"}}
    """
    
    try:
        init_groq()
        chat_completion = client.chat.completions.create(
            messages=[{"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
            ]}],
            model=VISION_MODEL,
            temperature=0.3, # On baisse la température pour plus de rigueur
            max_tokens=150
        )

        result = chat_completion.choices[0].message.content
        # Nettoyage JSON robuste (parfois l'IA ajoute du texte autour)
        if "```json" in result: 
            result = result.split("```json")[1].split("```")[0].strip()
        elif "{" in result:
            start = result.find("{")
            end = result.rfind("}") + 1
            result = result[start:end]
            
        data = json.loads(result)
        action = data.get("action", "STOP").upper()
        comment = data.get("comment", "...")

        STATE["recent_phrases"].append(comment)
        # On ne garde que les 5 dernières pour ne pas saturer le prompt
        if len(STATE["recent_phrases"]) > 5:
            STATE["recent_phrases"].pop(0)

        # Mise à jour mémoire
        STATE["history"].append(action)

        add_log("AUTO_BRAIN", f"Action: {action} | Dist: {distance} | {comment}", "success")
        speak_async(comment)

        # Exécution fluide
        if action == "FORWARD":
            # On avance plus longtemps (1.0s) MAIS avec surveillance active
            # (nécessite que send_command gère l'interruption, ou faire une boucle ici)
            for _ in range(3): # 4 x 0.25s = 1 seconde d'avance
                if STATE.get("latest_distance", 999) < 20: 
                    send_command("stop")
                    speak_async("Arrêt obstacle imprévu !")
                    break
                send_command("fwd", duration=0.5)
                time.sleep(0.1)
        elif action == "LEFT":
            send_command("turnLeft", duration=0.5)
        elif action == "RIGHT":
            send_command("turnRight", duration=0.5)
        elif action == "BACKWARD":
            send_command("bwd", duration=0.4)
        else:
            send_command("stop")

    except Exception as e:
        add_log("AUTO", f"Erreur IA: {e}", "error")
        send_command("stop")


# =============================================================================
# --- CERVEAU (GROQ) --- (inchangé sauf petites sécurités)
# =============================================================================

def process_vision_request(text_input):
    add_log("VISION", "Analyse visuelle Groq...", "info")
    base64_image = get_camera_image()  # Récupère l'image en texte base64

    if not base64_image:
        speak_generic("Je ne vois rien.")
        return

    init_groq()

    context = "Tu analyses une image provenant de la caméra embarquée d'un robot roulant au sol."
    persona = "Tu es sarcastique, maladroit et observateur." if STATE["personality"] == "SARCASTIQUE" else "Tu es un éclaireur tactique précis."

    full_prompt = f"{context} {persona} Décris ce que tu vois devant toi (obstacles, objets, pièces). Réponds à la question : {text_input}"

    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": full_prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}",
                            },
                        },
                    ],
                }
            ],
            model=VISION_MODEL,
        )
        reply = chat_completion.choices[0].message.content
        add_log("VISION", reply, "success")
        speak_generic(reply)
    except Exception as e:
        add_log("VISION", f"Erreur: {e}", "error")
        speak_generic("Erreur vision.")

def analyze_complex_instruction(user_text):
    """
    Cerveau Vocal : Interprète les ordres du Commandant ou les demandes de l'utilisateur.
    """
    available_commands = "fwd, bwd, turnLeft, turnRight, stop, capture"
    perso = STATE.get("personality", "SOLDAT")
    config = PROMPTS_CONFIG.get(perso)

    sys_prompt = f"""
    Tu es le cerveau d'un robot. Ton caractère : {config['vocal']}.
    
    INSTRUCTIONS TECHNIQUES :
    Commandes disponibles : [{available_commands}].
    1. Si l'ordre demande un mouvement, décompose en liste 'sequence'.
    2. Si l'utilisateur demande ce que tu vois, ajoute 'capture' à la séquence.
    3. Réponds UNIQUEMENT en JSON brut.
    
    Format : {{ "speech": "Ta réponse (selon ta personnalité)", "sequence": ["cmd1", "cmd2"] }}
    """

    try:
        init_groq()
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_text}
            ],
            model=MODEL_NAME,
            response_format={"type": "json_object"},
            temperature=0.8 
        )

        return json.loads(chat_completion.choices[0].message.content)

    except Exception as e:
        add_log("AI_BRAIN", f"Erreur Groq: {e}", "error")
        return None

def execute_sequence(sequence):
    """Exécute les ordres vocaux avec réactivité et sécurité capteur."""
    for cmd in sequence:
        if STATE["mode"] != "VOCAL": break
        
        # Vérification capteur avant chaque commande de la séquence
        dist = STATE.get("latest_distance")
        if cmd == "fwd" and dist is not None and dist <= SAFE_DISTANCE_CM:
            add_log("VOCAL", "Ordre 'avance' annulé : obstacle", "warning")
            speak_async("Obstacle détecté, je ne peux pas avancer.")
            continue

        if cmd == "capture":
            process_vision_request("Analyse rapide")
        else:
            add_log("EXEC", f"Action: {cmd}")
            # Durée adaptée selon la commande
            d = 0.8 if cmd == "bwd" else TURN_DURATION
            send_command(cmd, duration=d)
        
        time.sleep(0.1) # Pause courte entre deux ordres


# =============================================================================
# --- MAIN / BOUCLES --- 
# =============================================================================

def mode_vocal():
    r = sr.Recognizer()
    with sr.Microphone() as source:
        add_log("VOCAL", "Écoute...", "info")
        r.adjust_for_ambient_noise(source, duration=0.3)
        try:
            audio = r.listen(source, timeout=5, phrase_time_limit=10)
            text = r.recognize_google(audio, language="fr-FR").lower()
            add_log("VOCAL", f"Entendu: '{text}'", "success")

            brain_result = analyze_complex_instruction(text)
            if brain_result:
                speak_generic(brain_result.get("speech", "Ok."))
                execute_sequence(brain_result.get("sequence", []))

        except (sr.WaitTimeoutError, sr.UnknownValueError):
            pass
        except Exception as e:
            add_log("VOCAL", f"Error: {e}", "error")

def robot_loop():
    init_groq()
    add_log("SYSTEM", "Démarrage Groq...", "info")
    while STATE["running"]:
        if STATE["mode"] == "VOCAL" and STATE["ip"]:
            mode_vocal()
        elif STATE["mode"] == "AUTO_API" and STATE["ip"]:
            run_autonomous_cycle()  # Le robot voit, décide, parle et bouge seul
        else:
            time.sleep(0.5)

# =============================================================================
# --- ROUTES FLASK --- 
# =============================================================================

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/status')
def get_status():
    return jsonify({
        "mode": STATE["mode"],
        "ip": STATE["ip"] or "Non Configuré",
        "voice": STATE["current_voice"],
        "personality": STATE["personality"],
        "logs": STATE["logs"],
        "latest_image": STATE["latest_image"] or "",
        "latest_distance": STATE.get("latest_distance", None)
    })

@app.route('/config', methods=['POST'])
def config():
    data = request.json
    if "ip" in data and data["ip"]:
        raw = data['ip'].strip().replace("http://", "").replace("/", "")
        STATE["ip"] = f"http://{raw}"
    if "voice" in data:
        STATE["current_voice"] = data["voice"]
    if "personality" in data:
        STATE["personality"] = data["personality"]
    return jsonify({"status": "ok"})

@app.route('/set_mode/<mode>', methods=['POST'])
def set_mode(mode):
    STATE["mode"] = mode
    send_command("stop")
    return jsonify({"status": "ok"})

@app.route('/control/<action>', methods=['POST'])
def web_control(action):
    if STATE["mode"] == "MANUEL":
        # En manuel, on applique quand même la sécurité pour éviter d'écraser un mur
        if action == "fwd":
            dist_now = STATE.get("latest_distance", None)
            if dist_now is not None and dist_now <= SAFE_DISTANCE_CM:
                add_log("SAFETY", f"Manuel: blocage avance, obstacle à {dist_now} cm", "warning")
                return jsonify({"status": "blocked", "reason": "obstacle"})
        send_command(action)
    return jsonify({"status": "ok"})

# =============================================================================
# --- LANCEMENT --- 
# =============================================================================

if __name__ == "__main__":
    # Thread principal du robot (IA, vocal, auto)
    t = threading.Thread(target=robot_loop, daemon=True)
    t.start()

    # Démarrer le polling capteur pour que la distance soit toujours à jour
    t2 = threading.Thread(target=sensor_polling_loop, daemon=True)
    t2.start()

    # Lancer le serveur Flask
    app.run(host='0.0.0.0', port=5000, debug=False)
