"""Simple macro sequence editor widget."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class MacroEditor(QWidget):
    """Edit a sequence of macro steps (button + delay)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        layout.addWidget(QLabel("Macro steps (button presses with hold time)"))

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Button", "Hold (ms)", "Delay after (ms)"])
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

        row = QHBoxLayout()
        self.button_input = QLineEdit()
        self.button_input.setPlaceholderText("e.g. A")
        row.addWidget(self.button_input, 1)
        add_btn = QPushButton("Add step")
        add_btn.setObjectName("Primary")
        add_btn.clicked.connect(self._add_step)
        row.addWidget(add_btn)
        remove_btn = QPushButton("Remove selected")
        remove_btn.clicked.connect(self._remove_step)
        row.addWidget(remove_btn)
        layout.addLayout(row)

    def _add_step(self) -> None:
        name = self.button_input.text().strip() or "A"
        r = self.table.rowCount()
        self.table.insertRow(r)
        self.table.setItem(r, 0, QTableWidgetItem(name))
        self.table.setItem(r, 1, QTableWidgetItem("50"))
        self.table.setItem(r, 2, QTableWidgetItem("30"))
        self.button_input.clear()

    def _remove_step(self) -> None:
        for idx in sorted({i.row() for i in self.table.selectedIndexes()}, reverse=True):
            self.table.removeRow(idx)

    def steps(self) -> list[dict]:
        out = []
        for r in range(self.table.rowCount()):
            try:
                hold = int(self.table.item(r, 1).text())
            except (AttributeError, ValueError):
                hold = 0
            try:
                delay = int(self.table.item(r, 2).text())
            except (AttributeError, ValueError):
                delay = 0
            out.append(
                {
                    "button": self.table.item(r, 0).text() if self.table.item(r, 0) else "",
                    "hold_ms": hold,
                    "delay_ms": delay,
                }
            )
        return out

    def set_steps(self, steps: list[dict]) -> None:
        self.table.setRowCount(0)
        for step in steps:
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(str(step.get("button", ""))))
            self.table.setItem(r, 1, QTableWidgetItem(str(step.get("hold_ms", 0))))
            self.table.setItem(r, 2, QTableWidgetItem(str(step.get("delay_ms", 0))))
