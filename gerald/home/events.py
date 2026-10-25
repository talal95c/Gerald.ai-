from PyQt6.QtCore import QObject, pyqtSignal


class DocumentEvents(QObject):
    document_updated = pyqtSignal(object)

    def on_done(self, document) -> None:
        self.document_updated.emit(document)


events = DocumentEvents()
