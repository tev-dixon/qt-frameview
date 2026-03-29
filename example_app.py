"""Example app demonstrating DataFrameTable usage.

Run:  python example_app.py
"""

import sys
import numpy as np
import pandas as pd
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout,
    QWidget, QPushButton, QLabel,
)

from dataframe_table import (
    ColumnDef,
    DataFrameTable,
    TableStyle,
    TextFilter,
    NumericFilter,
    DropdownFilter,
    OptionsFilter,
    CheckBoxDelegate,
    ButtonDelegate,
    SelectionMode
)


def make_sample_data(n: int = 500) -> pd.DataFrame:
    rng = np.random.RandomState(0)
    return pd.DataFrame({
        "id": np.arange(n),
        "name": [f"Item {i}" for i in range(n)],
        "price": np.round(rng.uniform(5, 500, n), 2),
        "in_stock": rng.choice([True, False], n),
        "category": rng.choice(["Electronics", "Books", "Clothing", "Food"], n),
        # This column exists in the DF but won't be shown — demonstrating superset support
        "internal_sku": [f"SKU-{i:05d}" for i in range(n)],
    })


# Simulates a live source that changes over time
_dynamic_tags = ["Sale", "New", "Clearance"]

def get_tags() -> list[str]:
    """Called every time the Tags dropdown is opened."""
    return list(_dynamic_tags)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DataFrameTable Example")
        self.resize(1000, 600)

        self.df = make_sample_data()

        # Assign random tags for the dynamic filter demo
        rng = np.random.RandomState(1)
        self.df["tag"] = rng.choice(_dynamic_tags, len(self.df))

        # ── Define columns ──
        columns = [
            ColumnDef(
                key="id", header="ID", stretch=0.5, sortable=True,
            ),
            ColumnDef(
                key="name", header="Product Name", stretch=2,
                sortable=True,
                filter_widget=TextFilter(placeholder="Search names…"),
            ),
            ColumnDef(
                key="price", header="Price", stretch=1,
                sortable=True,
                filter_widget=NumericFilter(placeholder="e.g. 100"),
                formatter=lambda v: f"${v:,.2f}",
            ),
            ColumnDef(
                key="in_stock", header="In Stock", stretch=0.5,
                delegate=CheckBoxDelegate(),
            ),
            ColumnDef(
                key="category", header="Category", stretch=1,
                sortable=True,
                # options_fn reads from self.df so the list is always current
                filter_widget=OptionsFilter(
                    options_fn=lambda: sorted(self.df["category"].dropna().unique()),
                    multi_select=True
                ),
            ),
            ColumnDef(
                key="tag", header="Tag", stretch=0.8,
                sortable=True,
                # Dynamic source — get_tags() is called every time dropdown opens
                filter_widget=DropdownFilter(options_fn=get_tags),
            ),
            ColumnDef(
                key="_delete", header="", stretch=0.5,
                delegate=ButtonDelegate(
                    text="Delete", on_click=self._on_delete_clicked,
                ),
            ),
        ]

        # ── Create the table ──
        self.table = DataFrameTable(
            columns=columns,
            selection_mode=SelectionMode.Extended,
            table_style=TableStyle(
                alternating_rows=True,
                row_height=30,
                grid_visible=True,
            ),
        )
        self.table.set_data(self.df)

        # ── Signals ──
        self.table.selection_changed.connect(self._on_selection_changed)
        self.table.table_model.dataChanged.connect(self._on_data_changed)

        # ── Toolbar row 1 — basics ──
        btn_toggle_filters = QPushButton("Toggle Filters")
        btn_toggle_filters.clicked.connect(
            lambda: self.table.set_filter_bar_visible(
                not self.table.is_filter_bar_visible()
            )
        )

        btn_reset_filters = QPushButton("Reset Filters")
        btn_reset_filters.clicked.connect(self.table.reset_filters)

        btn_toggle_price = QPushButton("Toggle Price Column")
        btn_toggle_price.clicked.connect(
            lambda: self.table.set_column_visible(
                "price", not self.table.is_column_visible("price")
            )
        )

        btn_select_rows = QPushButton("Select rows 0, 2, 4")
        btn_select_rows.clicked.connect(
            lambda: self.table.set_selected_rows({0, 2, 4})
        )

        # ── Toolbar row 2 — new features ──
        btn_select_first = QPushButton("Select First Visible")
        btn_select_first.clicked.connect(self._select_first)

        btn_update_cell = QPushButton("Set row 0 name → 'UPDATED'")
        btn_update_cell.clicked.connect(
            lambda: self.table.update_cell(0, "name", "UPDATED")
        )

        btn_bulk_update = QPushButton("Bulk: discount prices 10%")
        btn_bulk_update.clicked.connect(self._bulk_discount)

        btn_get_filter = QPushButton("get_filter('name') → set 'Item 1'")
        btn_get_filter.clicked.connect(self._use_get_filter)

        btn_add_tag = QPushButton("Add dynamic tag 'Limited'")
        btn_add_tag.clicked.connect(self._add_dynamic_tag)

        self.status = QLabel("Selection: (none)")

        # ── Layout ──
        row1 = QHBoxLayout()
        for btn in [btn_toggle_filters, btn_reset_filters, btn_toggle_price, btn_select_rows]:
            row1.addWidget(btn)
        row1.addStretch()

        row2 = QHBoxLayout()
        for btn in [btn_select_first, btn_update_cell, btn_bulk_update, btn_get_filter, btn_add_tag]:
            row2.addWidget(btn)
        row2.addStretch()

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.addLayout(row1)
        layout.addLayout(row2)
        layout.addWidget(self.table)
        layout.addWidget(self.status)
        self.setCentralWidget(central)

    # ── Slots ──

    def _on_selection_changed(self, selected: set):
        if selected:
            self.status.setText(f"Selection: {sorted(selected)}")
        else:
            self.status.setText("Selection: (none)")

    def _on_data_changed(self, top_left, bottom_right, roles):
        row = top_left.row()
        col = top_left.column()
        print(f"dataChanged: view row={row}, col={col}")

    def _on_delete_clicked(self, source_row: int):
        name = self.df.at[source_row, "name"]
        print(f"Delete clicked for row {source_row}: {name}")

    def _select_first(self):
        src = self.table.select_first_visible_row()
        if src is not None:
            print(f"Selected first visible row: source index {src}")
        else:
            print("No visible rows to select")

    def _bulk_discount(self):
        updates = [
            (i, "price", round(self.df.at[i, "price"] * 0.9, 2))
            for i in range(len(self.df))
        ]
        self.table.update_cells_bulk(updates)
        self.df = self.table.get_data()
        print("Applied 10% discount to all prices")

    def _use_get_filter(self):
        """Demonstrate get_filter() — retrieve the name filter and set it."""
        filt = self.table.get_filter("name")
        if filt is not None:
            self.table.set_filter_bar_visible(True)
            filt._edit.setText("Item 1")
            print("Programmatically set name filter to 'Item 1'")
        else:
            print("No filter found for 'name'")

    def _add_dynamic_tag(self):
        """Add a new tag to the dynamic source — visible next time dropdown opens."""
        if "Limited" not in _dynamic_tags:
            _dynamic_tags.append("Limited")
            print("Added 'Limited' to dynamic tags — open the Tag dropdown to see it")
        else:
            print("'Limited' already in tags")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
