import subprocess
import numpy as np
import librosa
import soundfile as sf
from pydub import AudioSegment
from pydub.playback import play
import os

def say_optimus(text):
    raw_wav = "temp_optimus.wav"
    output_wav = "optimus_final.wav"

    # 1. Synthèse avec espeak-ng (Voix française + variante masculine m3)
    try:
        subprocess.run([
            'espeak-ng',
            '-v', 'fr+m3',    # 'fr' pour Français, '+m3' pour une voix d'homme profonde
            '-p', '30',       # Pitch très bas (grave)
            '-s', '140',      # Vitesse solennelle
            '-a', '100',      # Volume normalisé
            '-w', raw_wav,
            text
        ], check=True)
    except Exception as e:
        print(f"❌ Erreur : Assure-toi que espeak-ng est installé. {e}")
        return

    # 2. Chargement et traitement "Transformer"
    y, sr = librosa.load(raw_wav, sr=44100)

    # A. Pitch Shifting (on descend encore un peu pour l'autorité)
    y_low = librosa.effects.pitch_shift(y, sr=sr, n_steps=-3)

    # B. Effet de "Modulation en anneau" (Ring Modulation) léger
    # C'est le secret des voix robotiques des années 80
    t = np.arange(len(y_low)) / sr
    carrier = np.sin(2 * np.pi * 40 * t) # Fréquence de base robotique
    y_robotic = y_low * (0.8 + 0.2 * carrier)

    # C. Écho de blindage (Réverbération métallique courte)
    def metal_reverb(signal, sr):
        delay = int(sr * 0.03) # 30ms pour simuler une armure métallique
        padded = np.pad(signal, (0, delay))
        reverb = padded.copy()
        reverb[delay:] += 0.4 * padded[:-delay]
        return reverb

    y_final_array = metal_reverb(y_robotic, sr)

    # D. Normalisation
    y_final_array = librosa.util.normalize(y_final_array)

    # 3. Export et Lecture
    sf.write(output_wav, y_final_array, sr)
    
    try:
        play(AudioSegment.from_wav(output_wav))
    except:
        pass

    # Nettoyage
    for f in [raw_wav, output_wav]:
        if os.path.exists(f): os.remove(f)

