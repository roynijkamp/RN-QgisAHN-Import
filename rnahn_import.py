# -*- coding: utf-8 -*-
"""
/***************************************************************************
 RNahnImport
                                 A QGIS plugin
 Plugin voor het importeren en bijsijnden van AHN Geotif bestanden
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                              -------------------
        begin                : 2025-01-29
        git sha              : $Format:%H$
        copyright            : (C) 2025 by Roy Nijkamp
        email                : roynijkamp@roynijkamp.nl
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication, QThread, pyqtSignal
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QFileDialog, QMessageBox, QProgressDialog
from qgis.core import QgsRasterLayer, QgsVectorLayer, QgsProject, QgsRasterLayer, QgsMapLayer, QgsProcessingFeedback, QgsProcessingAlgorithm
from osgeo import gdal
import json
import os
import requests
import processing

# Initialize Qt resources from file resources.py
from .resources import *
# Import the code for the dialog
from .rnahn_import_dialog import RNahnImportDialog
import os.path


class RNahnImport:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'RNahnImport_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&RN AHN Importeren')

        

        # Check if plugin was started the first time in current QGIS session
        # Must be set in initGui() to survive plugin reloads
        self.first_start = None

    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('RNahnImport', message)


    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None):
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered.
        :type callback: function

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str

        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            # Adds plugin icon to Plugins toolbar
            self.iface.addToolBarIcon(action)

        if add_to_menu:
            self.iface.addPluginToMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        icon_path = ':/plugins/rnahn_import/icon.png'
        self.add_action(
            icon_path,
            text=self.tr(u'RN AHN Import'),
            callback=self.run,
            parent=self.iface.mainWindow())

        # will be set False in run()
        self.first_start = True


    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginMenu(
                self.tr(u'&RN AHN Importeren'),
                action)
            self.iface.removeToolBarIcon(action)

    def import_json(self):
        # Laat de gebruiker een JSON-bestand kiezen
        json_path, _ = QFileDialog.getOpenFileName(
            None, "Selecteer een JSON-bestand", "", "JSON-bestanden (*.json)"
        )
        if not json_path:
            return

        # Bewaar het pad voor later gebruik
        self.last_directory = json_path.rsplit("/", 1)[0]  # Alleen de map opslaan (zonder bestandsnaam)

        print(f"📂 Laatst gebruikte map opgeslagen: {self.last_directory}")

        # Probeer het JSON-bestand te laden
        try:
            with open(json_path, 'r') as file:
                data = json.load(file)
        except Exception as e:
            QMessageBox.critical(None, "Fout", f"Kan JSON-bestand niet lezen: {e}")
            return

        # Verwerk de data
        for item in data:
            if item["soort"] == "kaartbladen":
                for blad in item["bladen"]:
                    naam = blad["naam"]
                    soort = blad["soort"]
                    pad = blad["pad"]

                    if soort == "lokaal":
                        # Voeg lokale bestanden toe
                        if os.path.exists(pad):
                            raster_layer = QgsRasterLayer(pad, naam)
                            if raster_layer.isValid():
                                QgsProject.instance().addMapLayer(raster_layer)
                            else:
                                QMessageBox.warning(None, "Fout", f"Rasterlaag {naam} is niet geldig.")
                        else:
                            QMessageBox.warning(None, "Fout", f"Bestand {pad} bestaat niet.")
                    elif soort == "download":
                        # Download bestand en voeg toe
                        temp_path = os.path.join(os.path.expanduser("~"), naam)
                        if self.download_file(pad, temp_path):
                            raster_layer = QgsRasterLayer(temp_path, naam)
                            if raster_layer.isValid():
                                QgsProject.instance().addMapLayer(raster_layer)
                            else:
                                QMessageBox.warning(None, "Fout", f"Rasterlaag {naam} is niet geldig.")
            elif item["soort"] == "contour":
                pad = item["pad"]
                if os.path.exists(pad):
                    vector_layer = QgsVectorLayer(pad, "Contour", "ogr")
                    if vector_layer.isValid():
                        QgsProject.instance().addMapLayer(vector_layer)
                    else:
                        QMessageBox.warning(None, "Fout", "Vectorlaag is niet geldig.")
                else:
                    QMessageBox.warning(None, "Fout", f"Bestand {pad} bestaat niet.")

    def download_file(url, save_path):
        """Download een bestand met voortgangsindicator."""
        try:
            response = requests.get(url, stream=True)
            if response.status_code != 200:
                QMessageBox.critical(None, "Fout", f"Kan bestand niet downloaden: {url}")
                return False

            # Totale bestandsgrootte ophalen
            total_size = int(response.headers.get('content-length', 0))
            downloaded_size = 0

            # Voortgangsindicator
            progress = QProgressDialog("Downloaden...", "Annuleren", 0, 100)
            progress.setWindowTitle("Download voortgang")
            progress.setMinimumWidth(300)
            progress.show()

            with open(save_path, 'wb') as file:
                for chunk in response.iter_content(chunk_size=8192):
                    if progress.wasCanceled():
                        QMessageBox.warning(None, "Geannuleerd", "Download geannuleerd door gebruiker.")
                        return False

                    file.write(chunk)
                    downloaded_size += len(chunk)
                    progress.setValue(int((downloaded_size / total_size) * 100))

            progress.close()
            return True
        except Exception as e:
            QMessageBox.critical(None, "Fout", f"Fout bij downloaden: {e}")
            return False


    def merge_rasters(self):
        """ Merge meerdere rasterlagen tot één, of retourneer de enige laag als er maar één is. """
        
        # Haal alle rasterlagen op uit het QGIS-project
        raster_layers = [layer for layer in QgsProject.instance().mapLayers().values() if isinstance(layer, QgsRasterLayer)]

        # Als er geen rasterlagen zijn, return None
        if not raster_layers:
            print("Geen rasterlagen gevonden!")
            return None

        # Als er maar 1 rasterlaag is, return die laag direct
        if len(raster_layers) == 1:
            print("🔹 Slechts 1 rasterlaag gevonden, geen merge nodig.")
            return raster_layers[0]

        # Meerdere rasterlagen: uitvoeren van de merge
        print(f"🔄 {len(raster_layers)} rasterlagen gevonden, starten met merge...")

        # Paden van rasterlagen ophalen
        input_layers = [layer.source() for layer in raster_layers]

        # Instellingen voor de processing tool 'gdal:merge'
        merge_params = {
            "INPUT": input_layers,
            "PCT": False,
            "SEPARATE": False,
            "NODATA_INPUT": None,
            "NODATA_OUTPUT": None,
            "OPTIONS": "",
            "EXTRA": "",
            "DATA_TYPE": 5,  # Zelfde datatype als invoer (0)
            "OUTPUT": "TEMPORARY_OUTPUT"
        }

        # Processing uitvoeren
        feedback = QgsProcessingFeedback()
        result = processing.run("gdal:merge", merge_params, feedback=feedback)

        # Controleren of het gelukt is
        merged_path = result["OUTPUT"]
        if not merged_path:
            print("Merge is mislukt!")
            return None

        # Toevoegen aan QGIS-project
        merged_layer = QgsRasterLayer(merged_path, "Merged Raster", "gdal")
        QgsProject.instance().addMapLayer(merged_layer)

        print("Merge voltooid!")
        return merged_layer

    def ensure_polygon_layer(self, vector_layer):
        """Controleert of de vectorlaag een polygonlaag is en converteert deze indien nodig."""
        from qgis.core import QgsVectorLayer, QgsWkbTypes, QgsProcessingFeedback
        import processing
        import os

        if not vector_layer:
            print("Geen vectorlaag gevonden.")
            return None

        # Check of de laag een polygon is
        if vector_layer.wkbType() in [QgsWkbTypes.Polygon, QgsWkbTypes.MultiPolygon]:
            return vector_layer  # Laag is al correct

        print("Vectorlaag is geen polygon. Probeer te converteren...")

        # Output pad voor geconverteerde laag
        output_path = os.path.join(os.path.expanduser("~"), "converted_polygon.gpkg")

        # Conversie uitvoeren naar polygon
        result = processing.run("native:convexhull", {
            "INPUT": vector_layer.source(),
            "OUTPUT": output_path
        }, feedback=QgsProcessingFeedback())

        if not result or "OUTPUT" not in result:
            print("Fout bij het converteren van de vectorlaag.")
            return None

        # Nieuwe geconverteerde laag laden
        converted_layer = QgsVectorLayer(output_path, "Geconverteerde Polygon", "ogr")
        if converted_layer.isValid():
            QgsProject.instance().addMapLayer(converted_layer)
            print("Vectorlaag succesvol geconverteerd naar polygon.")
            return converted_layer
        else:
            print("Geconverteerde laag is ongeldig.")
            return None

    def clip_raster(self, raster_layer, vector_layer):
        """Clip het raster met de contourlaag."""
        from qgis.core import QgsProject, QgsRasterLayer
        import processing
        import os

        if not raster_layer or not vector_layer:
            print("Raster- of vectorlaag ontbreekt.")
            return

        # Zorg ervoor dat de vectorlaag een polygon is
        polygon_layer = self.ensure_polygon_layer(vector_layer)
        if not polygon_layer:
            print("Clippen geannuleerd: Geen geldige polygonlaag gevonden.")
            return

        output_path = os.path.join(os.path.expanduser("~"), "clipped.tif")

        # Voer het clip-proces uit met de juiste polygonlaag
        processing.run("gdal:cliprasterbymasklayer", {
            "INPUT": raster_layer.source(),
            "MASK": polygon_layer.source(),
            "OUTPUT": output_path
        })

        # Voeg de nieuwe laag toe aan QGIS
        clipped_layer = QgsRasterLayer(output_path, "Geclipt Raster")
        if clipped_layer.isValid():
            QgsProject.instance().addMapLayer(clipped_layer)
            print("Raster succesvol geclipt.")
            return clipped_layer
        else:
            print("Fout bij het clippen van de rasterlaag.")
            return None

    def hide_original_layers(self):
        """Zet de originele rasterlagen uit na het mergen en clippen."""
        project_instance = QgsProject.instance()
        layer_tree = project_instance.layerTreeRoot()

        for layer in project_instance.mapLayers().values():
            if isinstance(layer, QgsRasterLayer):  # Controleer of het een rasterlaag is
                tree_layer = layer_tree.findLayer(layer.id())
                if tree_layer:
                    tree_layer.setItemVisibilityChecked(False)  # Zet de laag uit

    def export_raster(self, raster_layer):
        """ Laat de gebruiker een opslaglocatie kiezen en exporteert de rasterlaag als GeoTIFF met GDAL. """
        if not raster_layer:
            print("Geen rasterlaag om te exporteren!")
            return

         # Gebruik de laatst gekozen directory, of standaard de home directory
        start_dir = self.last_directory if hasattr(self, 'last_directory') else ""
    
        # Open bestandskiezer in de laatst gebruikte map
        file_path, _ = QFileDialog.getSaveFileName(None, "Opslaan als", start_dir, "GeoTIFF (*.tif)")


        # Als de gebruiker annuleert, stoppen
        if not file_path:
            print("Export geannuleerd door gebruiker.")
            return

        # Huidige rasterbron ophalen als GDAL Dataset
        raster_path = raster_layer.source()
        gdal_dataset = gdal.Open(raster_path)

        if not gdal_dataset:
            print("Kan rasterbron niet openen met GDAL!")
            return

        # Gebruik GDAL om het raster naar de gekozen locatie te exporteren
        gdal.Translate(file_path, gdal_dataset, format="GTiff")

        print(f"Rasterlaag succesvol opgeslagen als: {file_path}")

    def run(self):
        """Run method that performs all the real work"""

        # Create the dialog with elements (after translation) and keep reference
        # Only create GUI ONCE in callback, so that it will only load when the plugin is started
        if self.first_start == True:
            self.first_start = False
            self.dlg = RNahnImportDialog()
        self.dlg.cmdSelectFile.clicked.connect(self.start_processing)
        # show the dialog
        self.dlg.show()
        # Run the dialog event loop
        result = self.dlg.exec_()


    def start_processing(self):
        """Start de worker-thread en update de UI tijdens het proces."""
        
        self.worker = ProcessingWorker(self)  # Worker instantie maken
        self.worker.progress_updated.connect(self.update_progress)
        self.worker.task_updated.connect(self.update_task)
        self.worker.finished.connect(self.processing_complete)

        self.worker.start()  # Start de thread

    def update_progress(self, value):
        """Update de voortgangsbalk."""
        self.dlg.pgbVoortgang.setValue(value)

    def update_task(self, task_name):
        """Update het label met de huidige taak."""
        self.dlg.lblTaak.setText(task_name)

    def processing_complete(self):
        """Acties uitvoeren als alles klaar is."""
        self.dlg.lblTaak.setText("Klaar!")  

class ProcessingWorker(QThread):
    progress_updated = pyqtSignal(int)  # Signaal voor progressbar
    task_updated = pyqtSignal(str)      # Signaal voor lblTaak update
    finished = pyqtSignal()             # Signaal voor afronding

    def __init__(self, parent):
        super().__init__()
        self.parent = parent

    def run(self):
        """Voert alle stappen uit en update de UI met voortgang."""
        
        # Stap 1: JSON Importeren
        self.task_updated.emit("Importeren JSON...")
        self.parent.import_json()
        self.progress_updated.emit(20)

        # Stap 2: Samenvoegen rasters
        self.task_updated.emit("Samenvoegen rasters...")
        merged_layer = self.parent.merge_rasters()
        self.progress_updated.emit(40)

        # Stap 3: Contourlaag zoeken
        self.task_updated.emit("Contourlaag zoeken...")
        vector_layer = next(
            (layer for layer in QgsProject.instance().mapLayers().values()
            if layer.type() == QgsMapLayer.VectorLayer), 
            None
        )
        self.progress_updated.emit(60)

        # Stap 4: Originele lagen verbergen
        self.task_updated.emit("Originele lagen verbergen...")
        self.parent.hide_original_layers()
        self.progress_updated.emit(80)

        # Stap 5: Clippen op contour
        clipped_layer = None
        if merged_layer and vector_layer:
            self.task_updated.emit("Clippen op contour...")
            clipped_layer = self.parent.clip_raster(merged_layer, vector_layer)
            self.progress_updated.emit(90)
        else:
            self.task_updated.emit("Clippen overgeslagen (geen contourlaag gevonden)")

        # Stap 6: Exporteren naar GeoTIFF
        if clipped_layer:
            self.task_updated.emit("Exporteren als GeoTIFF...")
            self.parent.export_raster(clipped_layer)
            self.progress_updated.emit(100)
            self.task_updated.emit(f"Klaar! Export voltooid")
        else:
            self.task_updated.emit("Klaar! Export overgeslagen (geen geclipte laag)")


        # Verwerking voltooid
        self.finished.emit()       
