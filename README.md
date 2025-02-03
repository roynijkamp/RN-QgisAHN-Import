# RN-QgisAHN-Import
Qgis plugin om Nederlandse AHN data te importeren en bij te snijden voor gebruik in AutoCAD Civil 3D

## Doel

Het doel van de plugin is het voor de gebruiker zo eenvoudig mogelijk te maken een stuk AHN te clippen voor gebruik in Civil 3D zonder veel kennis van Qgis.

## Werking

!! Voor een juiste werking van de plugin is de AutoCAD plugin RN CAD Tools(R) ook benodigd.

Vanuit Civil 3D wordt met de RN CAD Tools een JSON bestand geexporteerd met hierin een verwijzing naar de geselecteerde AHN kaartbladen en een verwijzing naar een GML bestand met daarin de contour waarop de AHN Geclipped moet worden.
De plugin leest deze JSON in en doorloopt de volgende stappen:

- Importeer de AHN kaartbladen (GeoTiff)
- Importeer de GML contour
- Indien meer dan 1 kaartblad: Merge de geimporteerde bladen tot 1 raster laag
- Converteer indien nodig de contour naar een juist formaat
- Clip het samengevoegd raster op de geimporteerde contour
- Exporteer het resultaat van het clippen naar GeoTiff

Vervolgens kan in Civil deze GeoTiff eenvoudig ingeladen worden met de CAD Tool. Na het inladen kunnen er hoogte labels geplaatst worden in een zelf gekozen grid, of contourlijnen van het hoogteverloop geplaatst worden.