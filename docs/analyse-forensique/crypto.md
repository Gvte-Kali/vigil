---
layout: default
parent: "🔍 Analyse forensique"
nav_order: 211
---

# 🔐 Fichiers verrouillés (crypto) — `vigil_crypto.sh`

> `scripts/analyse/vigil_crypto.sh` détecte les fichiers **protégés par
> mot de passe** ou **chiffrés** : archives (zip/7z/rar) et documents pouvant être
> chiffrés (Office OLE/OOXML, PDF, OpenDocument).

---

## 📖 En résumé

Le script détecte les **candidats** (archives et documents chiffrables), vérifie
pour chacun s'il est **réellement protégé par mot de passe** (via `7za` ou
`file` en fallback), puis ne retient que les fichiers **confirmés** comme
verrouillés. Le **SHA-256** de chaque fichier confirmé est calculé et un
rapport PDF est généré. Les statistiques et la liste ne portent que sur les
fichiers **confirmés** (pas les candidats).

---

## ⚙️ Options

| Option | Effet |
|---|---|
| `--pdf` / `--no-pdf` | rapport PDF (activé par défaut) |
| `--copy-to DIR` | copier les fichiers verrouillés vers `DIR` |

## 🔄 Déroulement

1. Bannière, **détection** des candidats (archives + documents chiffrables).
2. **Vérification** de la protection par mot de passe via `7za` (polyvalent),
   fallback `file`.
3. **Filtrage** : seuls les fichiers **confirmés** verrouillés sont retenus.
4. **SHA-256** de chaque fichier confirmé.
5. **Copie** optionnelle vers un dossier.
6. **Rapport PDF** (statistiques **confirmées** avant la liste **confirmée**).

## 🔍 Pertinence forensique

- Un fichier verrouillé peut indiquer une **volonté de dissimulation**.
- La présence d'archives chiffrées oriente la suite de l'enquête (cassage de
  mot de passe, exploitation dédiée).

> ℹ️ Les **candidats** (fichiers détectés mais non confirmés verrouillés) ne
> figurent ni dans les statistiques ni dans la liste du rapport — seuls les
> fichiers **confirmés** sont reportés.

## 🔗 Voir aussi

- [Archives](archives.md)
- [Générateur PDF](../rapports-pdf/README.md)
