# BudgetForge Dashboard

Interface utilisateur moderne pour BudgetForge - Gestionnaire de budget LLM.

## Fonctionnalités

- ✅ **Playground intégré** - Testez vos prompts en temps réel
- ✅ **Monitoring du budget** - Suivi en temps réel des dépenses
- ✅ **Analytics détaillées** - Breakdown par provider et modèle
- ✅ **Gestion des clés API** - Création et rotation des clés
- ✅ **Interface responsive** - Compatible mobile et desktop

## Installation

```bash
# Installer les dépendances
npm install

# Lancer en mode développement
npm run dev

# Build pour la production
npm run build

# Démarrer en production
npm start
```

## Structure du projet

```
src/
├── app/                    # Pages Next.js 13+ (App Router)
│   ├── globals.css         # Styles globaux
│   ├── layout.tsx          # Layout principal
│   ├── page.tsx            # Page d'accueil
│   └── playground/         # Page playground
│       ├── page.tsx        # Page playground
│       └── playground.css  # Styles spécifiques
├── components/             # Composants réutilisables
│   ├── Navigation.tsx      # Navigation latérale
│   └── Playground.tsx      # Composant playground
└── docs/                   # Documentation
```

## Configuration

### Variables d'environnement

Créez un fichier `.env.local` :

```env
NEXT_PUBLIC_BUDGETFORGE_API_URL=https://budget.maxiaworld.app
NEXT_PUBLIC_BUDGETFORGE_API_KEY=votre-cle-api
```

### Personnalisation

Modifiez `tailwind.config.js` pour personnaliser les couleurs et le thème.

## Développement

### Ajouter une nouvelle page

1. Créez un dossier dans `src/app/nouvelle-page/`
2. Ajoutez un fichier `page.tsx`
3. Exportez un composant React par défaut

### Ajouter un nouveau composant

1. Créez un fichier dans `src/components/NouveauComposant.tsx`
2. Importez et utilisez dans vos pages

### Styles

- Utilisez Tailwind CSS pour le styling
- Ajoutez des styles personnalisés dans les fichiers CSS correspondants
- Respectez le système de design existant

## Déploiement

### Vercel (recommandé)

1. Poussez votre code sur GitHub
2. Connectez Vercel à votre repository
3. Configurez les variables d'environnement
4. Déployez

### Autres plateformes

Le dashboard est compatible avec toutes les plateformes supportant Next.js :
- Netlify
- Railway
- DigitalOcean App Platform
- AWS Amplify

## Technologies utilisées

- **Next.js 14** - Framework React full-stack
- **TypeScript** - Typage statique
- **Tailwind CSS** - Styling utilitaire
- **Lucide React** - Icônes
- **React Hooks** - Gestion d'état

## Support

- 📚 [Documentation API](../docs/api-reference.md)
- 💬 [Support technique](mailto:hello@maxiaworld.app)
- 🐛 [Signaler un bug](https://github.com/maxia-lab/budgetforge/issues)