// Script de test pour vérifier que le dashboard fonctionne

const fs = require("fs");
const path = require("path");

console.log("🧪 Test du dashboard BudgetForge...\n");

// Vérifier la structure des fichiers
const requiredFiles = [
  "package.json",
  "tsconfig.json",
  "tailwind.config.js",
  "next.config.js",
  "postcss.config.js",
  "src/app/layout.tsx",
  "src/app/page.tsx",
  "src/app/globals.css",
  "src/app/playground/page.tsx",
  "src/components/Navigation.tsx",
  "src/components/Playground.tsx",
];

let allFilesExist = true;

requiredFiles.forEach((file) => {
  const filePath = path.join(__dirname, file);
  if (fs.existsSync(filePath)) {
    console.log(`✅ ${file}`);
  } else {
    console.log(`❌ ${file} - MANQUANT`);
    allFilesExist = false;
  }
});

// Vérifier les dépendances
console.log("\n📦 Vérification des dépendances...");

const packageJsonPath = path.join(__dirname, "package.json");
if (fs.existsSync(packageJsonPath)) {
  const packageJson = JSON.parse(fs.readFileSync(packageJsonPath, "utf8"));

  const requiredDeps = ["next", "react", "react-dom", "lucide-react"];
  const requiredDevDeps = ["tailwindcss", "typescript", "@types/react"];

  console.log("Dépendances principales:");
  requiredDeps.forEach((dep) => {
    if (packageJson.dependencies && packageJson.dependencies[dep]) {
      console.log(`✅ ${dep}: ${packageJson.dependencies[dep]}`);
    } else {
      console.log(`❌ ${dep} - MANQUANTE`);
      allFilesExist = false;
    }
  });

  console.log("\nDépendances de développement:");
  requiredDevDeps.forEach((dep) => {
    if (packageJson.devDependencies && packageJson.devDependencies[dep]) {
      console.log(`✅ ${dep}: ${packageJson.devDependencies[dep]}`);
    } else {
      console.log(`❌ ${dep} - MANQUANTE`);
      allFilesExist = false;
    }
  });
}

// Vérifier la configuration TypeScript
console.log("\n⚙️ Vérification de la configuration TypeScript...");
const tsConfigPath = path.join(__dirname, "tsconfig.json");
if (fs.existsSync(tsConfigPath)) {
  const tsConfig = JSON.parse(fs.readFileSync(tsConfigPath, "utf8"));
  if (tsConfig.compilerOptions?.jsx === "preserve") {
    console.log("✅ Configuration JSX correcte");
  } else {
    console.log("❌ Configuration JSX incorrecte");
    allFilesExist = false;
  }
}

// Résumé final
console.log("\n📊 Résumé:");
if (allFilesExist) {
  console.log("✅ Tous les fichiers requis sont présents");
  console.log("✅ Configuration correcte détectée");
  console.log("\n🚀 Pour démarrer le dashboard:");
  console.log("1. npm install");
  console.log("2. npm run dev");
  console.log("3. Ouvrir http://localhost:3000");
} else {
  console.log("❌ Des fichiers ou dépendances sont manquants");
  console.log("Veuillez vérifier la structure du projet");
}

console.log("\n🎯 Prochaines étapes:");
console.log("- Configurer les variables d'environnement");
console.log("- Tester avec une API BudgetForge fonctionnelle");
console.log("- Déployer en production");
