# Fichier: voix.py
import subprocess
import os
from pydub import AudioSegment
from pydub.playback import play
from pydub.effects import normalize

def speak(texte):
    """
    Génère une voix style Dictée Magique et la joue immédiatement.
    """
    nom_fichier_temp = "temp_parole.wav"
    
    # 1. Génération de la voix brute avec espeak-ng
    try:
        subprocess.run([
            'espeak-ng', 
            '-v', 'fr', 
            '-p', '45',     # Pitch
            '-s', '140',    # Vitesse
            '-a', '200',    # Volume
            '-w', 'temp_raw.wav', 
            texte
        ], check=True, stderr=subprocess.DEVNULL) # stderr=... cache les messages techniques
    except FileNotFoundError:
        print("Erreur : Installez espeak-ng (sudo apt install espeak-ng)")
        return

    # 2. Traitement Audio (Effet Dictée Magique)
    try:
        audio = AudioSegment.from_wav("temp_raw.wav")
        audio = audio.set_frame_rate(8000)      # Basse qualité
        audio = audio.high_pass_filter(300)     # Coupe les graves
        audio = audio.low_pass_filter(3000)     # Coupe les aigus
        audio = audio + 10                      # Saturation (Gain)
        audio = normalize(audio)                # Normalisation

        # 3. Lecture directe
        play(audio)
    except Exception as e:
        print(f"Erreur audio : {e}")
    finally:
        # 4. Nettoyage silencieux des fichiers temporaires
        if os.path.exists("temp_raw.wav"):
            os.remove("temp_raw.wav")