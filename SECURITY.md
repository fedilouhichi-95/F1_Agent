# Security

## Versions prises en charge

La maintenance de sécurité est prévue pour la branche `main` et la version `0.1.0`. Les versions anciennes ne sont pas garanties.

## Signalement

Ne publiez pas une vulnérabilité dans une Issue ou une Discussion publique.

Utilisez de préférence le formulaire privé **Report a vulnerability** de GitHub Security Advisories pour ce dépôt. Si cette fonctionnalité n'est pas disponible, contactez le mainteneur via son profil GitHub en demandant un canal privé.

Pour tout signalement, indiquez :

- la version ou le commit concerné ;
- les étapes de reproduction ;
- l'impact attendu ;
- les éléments nécessaires pour vérifier le problème.

## Secrets

Ne placez jamais de clé Groq, Qdrant, Supabase, MLflow ou mot de passe dans un commit, un notebook, une documentation, un prompt ou un log. Les secrets locaux sont gérés dans `.env` et les secrets de production dans l'environnement de déploiement prévu.

## Réponse

Le projet confirme la réception, vérifie le rapport et prépare une correction ou une mitigation. Aucun délai de réponse n'est garanti pour un projet de fin d'études.
