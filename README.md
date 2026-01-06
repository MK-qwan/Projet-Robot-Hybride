# Robot IA Multi-Modal (Groq + ESP32-CAM)

Ce projet est un système de robotique avancée combinant une interface de contrôle **Flask**, une intelligence artificielle basée sur **Groq (Llama 3)** pour la vision et le dialogue, et un micrologiciel **ESP32** pour la partie motrice et capture vidéo.



## Fonctionnalités

-   **Pilotage en temps réel** : Interface web fluide avec commandes de mouvement (touches directionnelles ou pad virtuel).
-   **Vision par IA** : Utilisation de `Llama-3.2-Vision` pour analyser l'environnement via l'ESP32-CAM.
-   **Synthèse Vocale (TTS) Multiforme** : Quatre personnalités distinctes avec effets DSP :
    * **Optimus Prime** (Grave, héroïque)
    * **Metal Sonic** (Métallique, rapide)
    * **Withered Chica** (Dérangée, robotique cassée)
    * **Texas Instruments** (Style "Dictée Magique" vintage)
-   **Modes de fonctionnement** :
    * `MANUEL` : Contrôle total par l'utilisateur.
    * `AUTO_API` : Le robot prend des décisions basées sur l'analyse visuelle de l'IA.
    * `VOCAL` : Echanges avec le robot.
-   **Sécurité** : Capteur ultrasonique intégré pour éviter les collisions (arrêt automatique).

## Architecture du Projet

### 1. Backend (Python)
Le fichier `main.py` gère :
* Le serveur Flask et l'interface `index.html`.
* La communication avec l'API Groq.
* Le traitement audio (librosa, pydub, espeak-ng).
* La boucle de décision autonome.

### 2. Firmware (Arduino/C++)
Le dossier contient `esp32_car_firmware.ino` qui :
* Gère le flux vidéo de l'ESP32-CAM.
* Exécute les commandes moteurs via un pont en H.
* Renvoie les données de distance du capteur HC-SR04.

## Installation

### Prérequis
* **Système** : Kit ESP32 Cam 2WD Camera Robot Card, présent sur ce lien https://docs.keyestudio.com/projects/KS5023/en/latest/docs/2WD%20Camera%20Robot%20Car.html#car-assembly , à NOTER que le capteur Ultrason n'y est pas intégré!.
* **Dépendances système** : `espeak-ng`, `ffmpeg`.
* **Python** : 3.10+

### Étapes
1.  **Cloner le dépôt** :
    ```bash
    git clone <votre-url-repo>
    cd robot-ia
    ```

2.  **Installer les bibliothèques Python** :
    ```bash
    pip install flask requests groq numpy librosa soundfile pydub SpeechRecognition
    ```

3.  **Configurer l'ESP32** :
    * Ouvrez `esp32_car_firmware.ino` dans l'IDE Arduino.
    * Renseignez vos identifiants Wi-Fi (`ssid`, `password`).
    * Téléversez sur votre carte ESP32-CAM.

4.  **Lancer le serveur** :
    ```bash
    python main.py
    ```
    Puis accédez à `http://localhost:5000`.

##  Configuration de l'IA
Le robot utilise les modèles suivants via Groq :
* **Texte/Logique** : `llama-3.3-70b-versatile`
* **Vision** : `meta-llama/llama-4-scout-17b-16e-instruct` (sauf si changement, voir la console de groq pour les update éventuels.)

##  Sécurité
Le robot est programmé avec une `SAFE_DISTANCE_CM`. Si un obstacle est détecté à moins de cette distance, les commandes de marche avant sont bloquées, même en mode manuel.

---
*Projet développé pour l'expérimentation de l'IA embarquée.*
