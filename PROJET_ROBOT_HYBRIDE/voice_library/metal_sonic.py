import subprocess
import numpy as np
import librosa
import soundfile as sf
from pydub import AudioSegment
from pydub.playback import play
import os

def say_metal_sonic(text):
    """
    Reçoit du texte -> Joue l'audio Metal Sonic.
    """
    if not text: return
    
    raw_wav = "temp_espeak_metal.wav"
    output_wav = "metal_sonic_output.wav"

    # 1. Synthèse eSpeak
    try:
        subprocess.run([
            'espeak-ng', 
            '-v', 'fr',  # Force US accent pour Metal Sonic
            '-p', '67',     # Grave
            '-s', '140',    # Lent
            '-k', '60', 
            '-g', '2',
            #'-a', '100',
            '-w', raw_wav, 
            text
        ], check=True)
    except FileNotFoundError:
        print("❌ Erreur: espeak-ng n'est pas installé.")
        return
    except Exception as e:
        print(f"❌ Erreur eSpeak : {e}")
        return

    # 2. Traitement DSP (Aliasing + Metallic)
    try:
        y, sr = librosa.load(raw_wav, sr=44100)
        
        # Pitch Shift
        y = librosa.effects.pitch_shift(y, sr=sr, n_steps=-4.5)

        # Délai métallique court
        delay_samples = int(sr * 0.0012)
        y_metal = y + 0.75 * np.roll(y, delay_samples)

        # Decimation (Aliasing effect)
        step = 5
        y_dirty = y_metal[::step]
        y_final = np.repeat(y_dirty, step)
        
        # Resize pour matcher
        target_len = len(y_metal)
        if len(y_final) > target_len:
            y_final = y_final[:target_len]
        else:
            y_final = np.pad(y_final, (0, target_len - len(y_final)))

        # Clip
        y_final = np.clip(y_final * 2.5, -0.95, 0.95)

        sf.write(output_wav, y_final, sr)
        
        # Lecture
        play(AudioSegment.from_wav(output_wav))

    except Exception as e:
        print(f"Erreur DSP Metal Sonic: {e}")
    finally:
        if os.path.exists(raw_wav): os.remove(raw_wav)
        if os.path.exists(output_wav): os.remove(output_wav)