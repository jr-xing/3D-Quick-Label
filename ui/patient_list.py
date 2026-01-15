"""Patient list widget for browsing and selecting patients."""

from pathlib import Path
from typing import Dict, List, Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QListWidget,
    QListWidgetItem, QFileDialog, QMessageBox, QLabel
)
from PySide6.QtCore import Qt, Signal

import config
from core.patient import Patient


class PatientListWidget(QWidget):
    """Widget for displaying and selecting patients.

    Shows a list of loaded patients with modification indicators.
    Provides folder loading functionality.
    """

    # Signals
    patient_selected = Signal(str)  # patient_id
    folder_loaded = Signal(list)  # list of Patient objects

    def __init__(self, parent=None):
        super().__init__(parent)
        self._patients: Dict[str, Patient] = {}
        self._setup_ui()

    def _setup_ui(self):
        """Create the UI layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        # Header
        header_label = QLabel("Patients")
        header_label.setStyleSheet("font-weight: bold;")

        # Buttons
        button_layout = QHBoxLayout()
        self.load_button = QPushButton("Load Folder")
        self.load_button.clicked.connect(self._on_load_folder)
        button_layout.addWidget(self.load_button)

        # Patient list
        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QListWidget.SingleSelection)
        self.list_widget.itemClicked.connect(self._on_item_clicked)

        # Status label
        self.status_label = QLabel("No patients loaded")

        layout.addWidget(header_label)
        layout.addLayout(button_layout)
        layout.addWidget(self.list_widget)
        layout.addWidget(self.status_label)

    def _on_load_folder(self):
        """Handle load folder button click."""
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Folder with NIfTI Files",
            "",
            QFileDialog.ShowDirsOnly
        )
        if folder:
            self.load_folder(folder)

    def load_folder(self, folder_path: str):
        """Load NIfTI files from folder.

        Finds image files matching the pattern and creates Patient objects.
        """
        folder = Path(folder_path)

        # Find image files (exclude label files)
        image_files = []
        for pattern in [config.NIFTI_PATTERN]:
            for f in folder.glob(pattern):
                # Skip label files
                if not f.name.endswith(config.LABEL_SUFFIX):
                    image_files.append(f)

        if not image_files:
            QMessageBox.warning(
                self,
                "No Files Found",
                f"No NIfTI image files found in {folder_path}"
            )
            return

        # Create patient objects
        new_patients = []
        for image_path in sorted(image_files):
            patient = Patient.from_image_path(str(image_path))
            if patient.patient_id not in self._patients:
                new_patients.append(patient)
                self._patients[patient.patient_id] = patient

        self._update_list()
        self.folder_loaded.emit(new_patients)

        self.status_label.setText(f"{len(self._patients)} patient(s) loaded")

    def add_patient(self, patient: Patient):
        """Add a single patient to the list."""
        if patient.patient_id not in self._patients:
            self._patients[patient.patient_id] = patient
            self._update_list()
            self.status_label.setText(f"{len(self._patients)} patient(s) loaded")

    def _update_list(self):
        """Update the list widget display."""
        # Remember current selection
        current_item = self.list_widget.currentItem()
        current_id = current_item.data(Qt.UserRole) if current_item else None

        self.list_widget.clear()

        for patient_id, patient in sorted(self._patients.items()):
            item = QListWidgetItem(patient.get_display_name())
            item.setData(Qt.UserRole, patient_id)

            # Highlight modified patients
            if patient.has_unsaved_changes:
                item.setForeground(Qt.red)

            self.list_widget.addItem(item)

            # Restore selection
            if patient_id == current_id:
                item.setSelected(True)
                self.list_widget.setCurrentItem(item)

    def refresh_display(self):
        """Refresh the list display (update modification indicators)."""
        self._update_list()

    def _on_item_clicked(self, item: QListWidgetItem):
        """Handle patient selection."""
        patient_id = item.data(Qt.UserRole)
        self.patient_selected.emit(patient_id)

    def get_patient(self, patient_id: str) -> Optional[Patient]:
        """Get patient by ID."""
        return self._patients.get(patient_id)

    def get_all_patients(self) -> Dict[str, Patient]:
        """Get all patients."""
        return self._patients

    def get_modified_patients(self) -> List[Patient]:
        """Get list of patients with unsaved changes."""
        return [p for p in self._patients.values() if p.has_unsaved_changes]

    def select_patient(self, patient_id: str):
        """Programmatically select a patient."""
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.data(Qt.UserRole) == patient_id:
                self.list_widget.setCurrentItem(item)
                break

    def clear(self):
        """Clear all patients."""
        self._patients.clear()
        self.list_widget.clear()
        self.status_label.setText("No patients loaded")
