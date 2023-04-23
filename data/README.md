# Données

| Fichier | Contenu | Lignes et période | Source | Licence |
|---|---|---|---|---|
| `raw/Data_Train.xlsx` | Vols intérieurs indiens proposés à la vente, avec leur prix | 10 683 vols ; voyages du 1er mars au 27 juin 2019 | Concours MachineHack « Predict The Flight Ticket Price Hackathon » (2019). Copie publique : [Flight Fare Prediction MH (Kaggle)](https://www.kaggle.com/datasets/nikhilmittal/flight-fare-prediction-mh) | Non précisée (données de concours), conservées ici à des fins pédagogiques |
| `raw/india_outline_simplified.geojson` | Contour de l'Inde (frontières officielles), simplifié pour la carte du site | 1 multipolygone, ≈ 19 Ko | [India composite](https://github.com/datameet/maps/blob/master/Country/india-composite.geojson) de la communauté DataMeet, simplifié par `scripts/simplify_outline.py` (Douglas-Peucker 0,04°, îles de moins de 0,05 deg² omises) | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), « India boundaries » par DataMeet |

Le fichier d'origine de DataMeet (≈ 10 Mo) n'est pas versionné : `scripts/simplify_outline.py` le
télécharge dans `data/cache/` puis régénère la version simplifiée.

Conversion en euros : 1 € = 78,8361 ₹, taux de référence moyen de la BCE en 2019
([série EXR.A.INR.EUR.SP00.A](https://data.ecb.europa.eu/data/datasets/EXR/EXR.A.INR.EUR.SP00.A)).
La constante se trouve dans `src/flight_prices/config.py`.

## Dictionnaire des colonnes de `Data_Train.xlsx`

| Colonne | Description | Exemple |
|---|---|---|
| `Airline` | Compagnie ; le suffixe « Business » ou « Premium economy » indique la cabine | IndiGo |
| `Date_of_Journey` | Date du vol (JJ/MM/AAAA) | 24/03/2019 |
| `Source` | Ville de départ (orthographiée « Banglore » dans le fichier) | Banglore |
| `Destination` | Ville d'arrivée ; « New Delhi » et « Delhi » désignent le même aéroport (DEL) | New Delhi |
| `Route` | Itinéraire en codes d'aéroport IATA | BLR → DEL |
| `Dep_Time` | Heure de départ (HH:MM) | 22:20 |
| `Arrival_Time` | Heure d'arrivée (HH:MM), suivie d'une date quand elle diffère du jour du vol | 01:10 22 Mar |
| `Duration` | Durée totale du trajet, escales comprises | 2h 50m |
| `Total_Stops` | Nombre d'escales | non-stop |
| `Additional_Info` | Information complémentaire sur le billet | No info |
| `Price` | Prix du billet en roupies indiennes (₹) | 3897 |

## Particularités traitées dans `src/flight_prices/data.py`

- 1 ligne sans itinéraire ni nombre d'escales, et 220 doublons exacts : supprimés.
- 1 durée impossible (« 5m » pour un trajet à trois vols) : supprimée.
- La date affichée dans `Arrival_Time` est parfois incohérente (« 01:10 22 Mar » pour un vol du
  24 mars) : l'arrivée est recalculée à partir de l'heure de départ et de la durée.
- « New Delhi » n'apparaît que pour les vols de mars : fusionné avec « Delhi ».
- 7 billets en classe affaires (de 28 097 à 79 512 ₹) : décrits, mais exclus du modèle.
