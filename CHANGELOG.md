# Changelog

Toutes les évolutions notables du projet sont consignées dans ce fichier.

## [Non publié]

- Préparation de la publication publique et du workflow de contribution.
- Clarification de l'état scaffold et de la roadmap dans la documentation.
- Correction de la compatibilité entre `groq` et `langchain-groq` dans une PR dédiée.
- Mise à jour de `pytest` vers `9.0.3` et retrait de `ragas` vulnérable du scaffold CI.
- Ajout de la lecture des secrets Streamlit et de la protection des valeurs sensibles dans les logs.

## [0.1.0] - 2026-09-25

- Scaffold initial Python 3.12.
- Configuration centralisée des variables d'environnement.
- Point d'entrée Streamlit affichant l'état des connexions.
- Contrat abstrait d'agent.
- Schéma Supabase initial.
- Tests unitaires de base et squelette d'évaluation.
