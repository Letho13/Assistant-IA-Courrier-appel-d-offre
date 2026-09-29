# Assistant ADV

Prototype Streamlit qui analyse un courrier client et rédige un brouillon de réponse avec un modèle servi localement par Ollama. Les prix, délais, remises et engagements ne doivent pas être inventés ; le brouillon doit être relu et validé avant envoi.

## Démonstration d'entretien

Le courrier client n'est pas prérempli : saisis ou colle manuellement la demande à analyser. Le bouton **Générer l'analyse avec l'IA locale** lance l'analyse réelle avec le modèle Ollama sélectionné ; aucun résultat fictif n'est affiché.

Sur un PC Windows avec Python 3 et un accès Internet pour installer les dépendances :

1. Copie le dossier du projet sur le PC (ou une clé USB), sans copier le dossier `.venv`.
2. Double-clique sur `Lancer la démo.bat`.
3. Dans le navigateur, ouvre `http://localhost:8501`, colle un courrier dans le champ prévu, puis lance l'analyse.

Le premier démarrage crée un environnement Python local et installe Streamlit et Requests. Ollama et un modèle compatible doivent aussi être installés sur le PC pour générer l'analyse ; sans eux, le bouton reste désactivé. L'application et le modèle s'exécutent localement. Ce projet n'est pas un site public hébergé et le dossier ne contient pas un runtime Python autonome.

### Présentation en entretien

Pitch possible : « J'ai prototypé un assistant ADV pour qualifier des demandes de cotation de transport alimentaire. Il repère les contraintes d'expédition, signale les vérifications manquantes, distingue les faits des calculs et prépare un brouillon sans inventer de prix ni de délai garanti. L'ADV garde la validation finale. »

Déroulé court : présente le workflow complet, en précisant que seule la réception des éléments est traitée dans ce prototype ; les étapes juridiques, exploitation, tarification, validation et suivi client sont affichées comme étapes à venir. Colle un courrier de démonstration, puis génère l'analyse avec Ollama. Les e-mails et pièces jointes ne sont pas importés automatiquement, et l'intégration aux tarifs réels reste à faire.

## Contrôles des demandes de transport

L'analyse porte notamment sur le transport alimentaire sous température dirigée : marchandise et température, conditionnement et dimensions des palettes, gerbabilité, poids total et moyen (calculé si le poids total et le nombre de palettes sont connus), lieux de chargement et de livraison, fréquence et date de démarrage, contraintes de hayon et de rendez-vous, délai garanti demandé, champs entre crochets à compléter et date limite de l'offre. Le brouillon répond du point de vue du transporteur et ne doit pas transformer une demande de cotation en offre validée.

Elle conserve également les contrôles tarifaires ADV : tarif au voyage, à la tonne ou à la palette ; forfaitaire ou unitaire (sans déduire cette nature de l'unité) ; grille tarifaire jointe ; indexation CNR et parts gazole/GNR ; massification, ouverture de portes ; traction, distribution ou bout en bout ; hauteur et poids moyen des palettes. Les repérages par mots-clés servent d'indices à l'analyse ; ils ne sont pas affichés séparément et une absence de détection ne prouve pas que l'information est absente.

Quand le texte fourni contient des repères de pagination explicites, les consignes de génération demandent d'ajouter le numéro de page à chaque citation à laquelle il peut être associé sans ambiguïté. Aucun numéro de page ne doit être inventé ; conserve les repères de page lors du copier-coller d'un document paginé.

L'application n'est pas connectée à une messagerie et ne lit pas les fichiers joints. La zone « Pièces jointes repérées » permet de communiquer manuellement un nom ou une description ; elle ne permet pas d'analyser le contenu d'une grille tarifaire. Le modèle ne doit donc pas prétendre avoir ouvert ou vérifié un fichier.

## Démarrage

1. Installe Ollama depuis [ollama.com](https://ollama.com/) et démarre-le.
2. Télécharge un modèle, par exemple :

   ```powershell
   ollama pull llama3.2
   ```

3. Installe les dépendances Python et lance l'application :

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   streamlit run app.py
   ```

L'application utilise par défaut l'API Ollama à `http://localhost:11434` et affiche les modèles installés dans le panneau latéral. Elle n'active pas la génération tant qu'aucun modèle local n'est disponible. Si Ollama ne répond pas, l'application affiche une erreur au lieu de produire une réponse fictive.
