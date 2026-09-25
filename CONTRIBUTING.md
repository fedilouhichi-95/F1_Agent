# Contributing

Merci de participer à PitStop Assistant. Le projet suit un développement orienté vers la reproductibilité, la sécurité et la continuité de la roadmap.

## Avant de commencer

1. Lire [`AGENTS.md`](AGENTS.md), [`SPEC.md`](SPEC.md) et [`PROGRESS.md`](PROGRESS.md).
2. Vérifier que la proposition n'est pas déjà couverte par une issue ou une PR.
3. Préférer une issue pour discuter d'une fonctionnalité ou d'un changement d'architecture.

## Workflow

- Créer une branche dédiée à partir de `main`.
- Garder une PR atomique et facile à relire.
- Utiliser les commits conventional commits : `type(scope): résumé`.
- Ne jamais ajouter de secrets, de données cloud privées ou de fichiers générés.
- Mettre à jour la documentation et les tests concernés.

## Vérifications attendues

```bash
pip install -r requirements.txt -r requirements-dev.txt
ruff check .
ruff format --check .
python -m pytest -m "not eval"
```

Le marqueur `eval` correspond actuellement à une vérification structurelle. Il ne constitue pas encore un quality gate RAGAS.

## Checklist de PR

- [ ] La modification est décrite et Bornée.
- [ ] Les tests pertinents sont ajoutés ou mis à jour.
- [ ] La CI passe.
- [ ] La documentation affectée est à jour.
- [ ] Aucun secret n'est présent dans le diff.
- [ ] Les changements de dépendances sont justifiés.
- [ ] Les migrations ou changements de schéma passent par le code prévu.

## Communication

Les discussions techniques peuvent être menées dans les Issues ou Discussions GitHub. Les rapports de vulnérabilité doivent suivre [`SECURITY.md`](SECURITY.md) et ne doivent pas être publiés dans une issue publique.
