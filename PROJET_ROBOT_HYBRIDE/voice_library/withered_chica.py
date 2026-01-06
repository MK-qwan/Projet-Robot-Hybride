import subprocess
import numpy as np
import librosa
import soundfile as sf
from pydub import AudioSegment
from pydub.playback import play
import os

def say_withered_chica(text):
    raw_wav = "temp_chica.wav"
    output_wav = "withered_chica.wav"

    # 1. Synthèse eSpeak : On évite de saturer dès l'entrée (-a 100 au lieu de 220)
    try:
        subprocess.run([
            'espeak-ng',
            '-v', 'fr+f3',
            '-p', '30',       # Plus grave pour l'effet "animatronique"
            '-s', '130',      # Vitesse plus naturelle mais lente
            '-a', '100',      
            '-w', raw_wav,
            text
        ], check=True)
    except Exception as e:
        print(f"❌ Erreur : {e}")
        return

    # Charger l'audio
    y, sr = librosa.load(raw_wav, sr=44100)

    # A. Pitch Shift : -5 demi-tons pour un effet monstrueux (plus radical que -0.10)
    y_low = librosa.effects.pitch_shift(y, sr=sr, n_steps=-5)

    # B. Distorsion contrôlée (Soft Clipping)
    # On mélange l'original et le pitch shifté avant de saturer légèrement
    y_combined = (y * 0.4 + y_low * 0.6)
    y_distorted = np.clip(y_combined * 2.0, -0.8, 0.8) # Utilise clip plutôt que tanh pour garder de la clarté

    # C. MÉGA RÉVERB / ÉCHOS
    def apply_reverb(signal, sr):
        # Délais en secondes
        delays = [0.03, 0.06, 0.12]
        reverb = np.zeros(len(signal) + int(sr * 0.5))
        reverb[:len(signal)] = signal

        for d in delays:
            shift = int(sr * d)
            reverb[shift:shift+len(signal)] += signal * 0.3
        
        return reverb

    y_reverb = apply_reverb(y_distorted, sr)

    # D. Tremolo (Effet de moteur cassé)
    # On réduit l'intensité (0.2 au lieu de 0.4) pour ne pas hacher les mots
    t = np.arange(len(y_reverb)) / sr
    tremolo = 1.0 + 0.2 * np.sin(2 * np.pi * 35 * t) 
    y_unstable = y_reverb * tremolo

    # E. Normalisation finale
    # C'est l'étape cruciale pour éviter que ce ne soit qu'un "bruit"
    max_val = np.max(np.abs(y_unstable))
    if max_val > 0:
        y_final = y_unstable / max_val
    else:
        y_final = y_unstable

    # Export
    sf.write(output_wav, y_final, sr)
    print(f"Fichier généré : {output_wav}")

    # Lecture
    try:
        sound = AudioSegment.from_wav(output_wav)
        play(sound)
    except Exception as e:
        print(f"Erreur de lecture : {e}")

    if os.path.exists(raw_wav):
        os.remove(raw_wav)