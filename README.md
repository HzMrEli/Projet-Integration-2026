# Projet-Integration-2026

Idée: Assistant de cuisine
Chabot recette oral (sans toucher le téléphone car mains sales), l'utilisateur donne les ingrédients qu'il a et le chat bot propose des recettes. 
Il demande si il veut la recette en entier, ou suivre étape par étape avec l'utilisateur.
Si étape par étape : le chatbot donne chaque étapes avec validation de l'utilisateur entre chaque étapes, pour continuer.


**Tâche 1 – Collecte de la demande**
Objectif : comprendre ce que l’utilisateur veut cuisiner, sans qu’il touche l’écran.

Mode “AlimentsFrigo” :

L’assistant demande de lister les ingrédients à l’oral, un par un ou par lot : “dis-moi ce qu’il y a dans ton frigo / placard”.​
Option de préciser contraintes : temps max, niveau de difficulté, régime, végé.
​

Mode “Nom de recette” :

L’utilisateur donne un plat (“pâtes carbonara pour 2 personnes”) et éventuellement le temps disponible et le niveau de cuisine.
L’assistant reformule pour confirmation : “Ok, carbonara pour 2 personnes, en moins de 30 minutes, c’est bien ça ?”.
​

**Tâche 2 – Proposition de recettes et options**
Objectif : transformer les ingrédients ou la recette cible en proposition concrète.

Si entrée par ingrédients :

Générer une liste de recettes possibles avec score de “compatibilité ingrédients” (recette faisable tout de suite, ou avec quelques ingrédients manquants).
Pour chaque recette, annoncer : nom, temps, difficulté, nombre de personnes, et éventuellement “tu n’as pas : oignon, crème”.
​

Si entrée par nom de recette :

Vérifier les ingrédients nécessaires et annoncer ce qui manque.​
Proposer éventuellement des substitutions simples (ex : crème → lait + beurre).


Si manque d’ingrédients critique, possibilité d’énoncer une liste de courses vocale.​

**Tâche 3 – Guidage pas-à-pas de la recette**
Objectif : accompagner l’utilisateur pendant la cuisson sans le presser.

Phase de départ de recette :

Lire tous les ingrédients et quantités, laisser le temps de tout sortir, avec commandes “répète”, “plus lentement”.
Option d’ajuster les quantités en fonction du nombre de personnes avant de commencer vraiment.
Demander quand l'utilisateur est prêt à commencer la recette (tout les ingrédients sont sorti etc)
​
Phase recette étape par étape :

Chaque étape doit être courte et lue séparément, l’assistant attend un signal (“étape suivante”, “j’ai fini”, “répète”, "ensuite") avant de continuer ou de reprendre.

BONUS: si une étape contient “cuire 10 minutes”, l’assistant propose automatiquement un minuteur intégré (“je lance un minuteur de 10 minutes ?”).
Possibilité de poser des questions contextuelles : “c’est quoi dorer ?”, “comment savoir si c’est cuit ?”.



Intentions:
- Intent “AlimentsFrigo” :
    Slots : liste_ingredients, temps_max, difficulté (débutant / intermédiaire / avancé), type_plat (rapide, équilibré, dessert…), contraintes (végé, sans gluten…).
​
- Intent “NomRecette” :
    Slots : nom_recette, nb_personnes, temps_max, difficulté_souhaitée, niveau_cuistot (débutant, confirmé).
​
- Intent “GuidageRecette” :
    Slots : id_recette, étape_courante, minuteurs_actifs.
