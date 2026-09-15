#Doerreimmilator  v1.0.0

import html
import os
import re
import sys
import time

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFrame, QGridLayout, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QPushButton,
    QScrollArea, QSizePolicy, QSplitter, QTableWidget, QTableWidgetItem,
    QTextEdit, QVBoxLayout, QWidget
)

from data import PITCHES
from datetime import datetime


DEFAULT_FILE = "melodies.txt"



def xml_value(text, tag):
    match = re.search(
        rf"\[{tag}\](.*?)\[/{tag}\]",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    return match.group(1) if match else ""



def make_song(artist, title, compact):
###    timestamp = int(time.time())
    timestamp = datetime.now().strftime("%Y %m%d %H%M")
    return (
        f"[song]"
        f"[artist]{html.escape(artist)}[/artist]"
        f"[title]{html.escape(title)}[/title]"
        f"[compact]{compact}[/compact]"
        f"[timestamp]{timestamp}[/timestamp]"
        f"[/song]"
    )


class HelpButton(QPushButton):
    def __init__(self, text, help_text, parent=None):
        super().__init__(text, parent)
        self.setToolTip(help_text)


class PitchBlock(QFrame):
    changed = Signal()

    def __init__(self, syllable, pitch=49, parent=None):
        super().__init__(parent)

        self.syllable = syllable
        self.pitch = pitch

        self.setFrameShape(QFrame.StyledPanel)
        self.setMinimumWidth(70)
        self.setMaximumWidth(100)

        self.label = QLabel()
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setWordWrap(True)

        self.combo = QComboBox()
        for number, (name, color) in PITCHES.items():
            self.combo.addItem(f"{number}: {name}", number)

        if pitch in PITCHES:
            self.combo.setCurrentIndex(list(PITCHES).index(pitch))

        self.combo.currentIndexChanged.connect(self.pitch_changed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(3, 3, 3, 3)
        layout.addWidget(self.label)
        layout.addWidget(self.combo)

        self.update_visuals()

    def pitch_changed(self):
        self.pitch = self.combo.currentData()
        self.update_visuals()
        self.changed.emit()

    def update_visuals(self):
        if self.pitch == 0:
            color = "#ffffff"
            name = "*"
        else:
            name, color = PITCHES.get(self.pitch, ("?", "#ffffff"))

        self.label.setText(f"{self.syllable}\n{self.pitch}: {name}")
        self.setStyleSheet(
            f"""
            QFrame {{
                background-color: {color};
                border: 1px solid #777;
                border-radius: 3px;
            }}
            QLabel {{
                background: transparent;
                color: black;
            }}
            """
        )

    def compact_part(self):
        if self.pitch == 0:
            return "0*" if self.syllable == "*" else f"0{self.syllable}"
        return f"{self.pitch}{self.syllable}"




class SongCanvas(QWidget):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self.blocks = []

        self.layout = QVBoxLayout(self)
        self.layout.setAlignment(Qt.AlignTop)
        self.layout.setSpacing(4)

    def clear(self):
        while self.layout.count():
            item = self.layout.takeAt(0)
            widget = item.widget()

            if widget is not None:
                widget.deleteLater()

        self.blocks.clear()

    def create_row(self):
        row = QHBoxLayout()
        row.setAlignment(Qt.AlignLeft)
        row.setSpacing(4)

        wrapper = QWidget()
        wrapper.setLayout(row)
        wrapper.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Fixed,
        )

        self.layout.addWidget(wrapper)

        return row

    def add_block_to_row(self, row, syllable, pitch):
        block = PitchBlock(syllable, pitch)
        block.changed.connect(self.changed.emit)

        self.blocks.append(block)
        row.addWidget(block)

    def add_line(self, syllables):
        row = self.create_row()

        for syllable, pitch in syllables:
            self.add_block_to_row(row, syllable, pitch)

    def set_blocks(self, blocks):
        self.clear()

        row = self.create_row()

        for syllable, pitch in blocks:
            # 0* means: add a block
            # and then start a new line.
            
            if pitch == 0 and syllable == "*":
                self.add_block_to_row(row, syllable, pitch)
                row = self.create_row()
                continue

            self.add_block_to_row(row, syllable, pitch)

        # Remove a possible empty last row.
        if row.count() == 0:
            item = self.layout.takeAt(self.layout.count() - 1)

            if item is not None and item.widget() is not None:
                item.widget().deleteLater()

        self.changed.emit()

    def blocks_as_pairs(self):
        return [
            (block.syllable, block.pitch)
            for block in self.blocks
        ]

    def compact(self):
        return "".join(
            block.compact_part()
            for block in self.blocks
        )


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        
        self.setWindowTitle("Do erre immilator")
        self.resize(1100, 760)

        self.file_name = DEFAULT_FILE
        self.records = []

        self.setStyleSheet(
            """
            QWidget {
                background-color: #e5e0d9;
                color: #222;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #aaa;
                margin-top: 8px;
                padding-top: 12px;
            }
            QTextEdit, QLineEdit, QComboBox, QTableWidget {
                background-color: #ffffff;
            }
            QPushButton {
                background-color: #e0dace;
                border: 1px solid #aaa;
                padding: 4px 8px;
            }
            QPushButton:hover {
                background-color: #f1df85;
            }
            
            QSplitter::handle {
                background-color: #aaa49b;
            }

            QSplitter::handle:hover {
                background-color: #777066;
            }

            QSplitter::handle:pressed {
                background-color: #5f5951;
            }

            QSplitter::handle:horizontal {
                width: 4px;
            }

            QSplitter::handle:vertical {
                height: 4px;
            }
            
            
            
            
            """
        )

        self.build_ui()
        self.load_file()
        
    def build_ui(self):
        main_layout = QVBoxLayout(self)

        title = QLabel("Do erre immilator")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        main_layout.addWidget(title)
       
        # Main splitter:
        # top: Lyrics, Compact code, and Song in blocks
        # bottom: Saved in text file
        
        main_splitter = QSplitter(Qt.Vertical)

        # -------------------------------------------------
        # TOP SECTION
        # -------------------------------------------------

        # Horizontal splitter:
        # left: Lyrics and Song compact code
        # right: Song in blocks
        top_splitter = QSplitter(Qt.Horizontal)

        # Left side
        left = QWidget()
        left_layout = QVBoxLayout(left)

        # Lyrics and syllables
        lyrics_group = QGroupBox(
            "Lyrics and syllables"
        )
        lyrics_layout = QVBoxLayout(lyrics_group)

        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("Title") 
        # t(self.language,"Titel","Title")

        self.artist_edit = QLineEdit()
        self.artist_edit.setPlaceholderText("Artist")

        self.lyrics_edit = QTextEdit()
        self.lyrics_edit.setPlaceholderText(
            "Enter the syllables per line. Use spaces between syllables."
        )

        convert_lyrics = HelpButton(
            "▶",
            "Convert Lyric syllables to Blocks",            
        )
        convert_lyrics.clicked.connect(self.lyrics_to_blocks)

        lyrics_layout.addWidget(QLabel("Title"))
        lyrics_layout.addWidget(self.title_edit)
        lyrics_layout.addWidget(QLabel("Artist"))
        lyrics_layout.addWidget(self.artist_edit)
        lyrics_layout.addWidget(self.lyrics_edit)
        lyrics_layout.addWidget(convert_lyrics)

        left_layout.addWidget(lyrics_group, 2)

        # Song-compactcode
        compact_group = QGroupBox("Song-compactcode")
        compact_layout = QVBoxLayout(compact_group)

        self.compact_edit = QTextEdit()
        self.compact_edit.setPlaceholderText(
            "[song][artist]...[/artist][title]...[/title]"
        )

        compact_buttons = QHBoxLayout()

        from_compact = HelpButton(
            "▶",
            "Convert Compact string to Blocks",           
        )
        from_compact.clicked.connect(self.compact_to_blocks)

        to_file = HelpButton(
            "▼",
            "Save to text file",
        )
        to_file.clicked.connect(self.save_current)

        compact_buttons.addWidget(from_compact)
        compact_buttons.addWidget(to_file)

        compact_layout.addWidget(self.compact_edit)
        compact_layout.addLayout(compact_buttons)

        left_layout.addWidget(compact_group, 2)

        top_splitter.addWidget(left)

        # Right side: Song in blocks
        song_group = QGroupBox("Song in blocks")
        song_layout = QVBoxLayout(song_group)

        self.song_title_label = QLabel("No song loaded")
    
        self.song_title_label.setStyleSheet("font-weight: bold;")

        self.song_scroll = QScrollArea()
        self.song_scroll.setWidgetResizable(True)

        self.song_canvas = SongCanvas()
        self.song_canvas.changed.connect(self.blocks_changed)
        self.song_scroll.setWidget(self.song_canvas)

        song_layout.addWidget(self.song_title_label)
        song_layout.addWidget(self.song_scroll)

        top_splitter.addWidget(song_group)

        # Initial ratio between left and right
        top_splitter.setSizes([480, 620])

        # Place the top section in the vertical splitter
        main_splitter.addWidget(top_splitter)

        # -------------------------------------------------
        # BOTTOM SECTION
        # -------------------------------------------------

        saved_group = QGroupBox("Saved in text file")      
        
        saved_layout = QVBoxLayout(saved_group)

        file_row = QHBoxLayout()

        self.file_edit = QLineEdit(DEFAULT_FILE)
        self.file_edit.setToolTip(
            "Enter the name of the text file."
            "The file is created if it does not exist."
        )

        use_file = HelpButton(
            "Use this text file",
            "Use another text file",
        )
                
        use_file.clicked.connect(self.change_file)

        file_row.addWidget(self.file_edit)
        file_row.addWidget(use_file)

        saved_layout.addLayout(file_row)

        filter_row = QHBoxLayout()

        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText(
            "Filter by artist or title"
        )
        
        self.filter_edit.textChanged.connect(self.refresh_table)

        filter_row.addWidget(QLabel("Filter"))
        filter_row.addWidget(self.filter_edit)

        saved_layout.addLayout(filter_row)

        sort_row = QHBoxLayout()

        sort_artist_asc = QPushButton("A-Z artist")
        sort_artist_desc = QPushButton("Z-A artist")
        sort_title_asc = QPushButton("A-Z title")
        sort_title_desc = QPushButton("Z-A title")
        sort_time_asc = QPushButton("▲ timestamp")
        sort_time_desc = QPushButton("▼ timestamp")

        sort_artist_asc.clicked.connect(
            lambda: self.sort_table("artist", False)
        )
        sort_artist_desc.clicked.connect(
            lambda: self.sort_table("artist", True)
        )
        sort_title_asc.clicked.connect(
            lambda: self.sort_table("title", False)
        )
        sort_title_desc.clicked.connect(
            lambda: self.sort_table("title", True)
        )
        sort_time_asc.clicked.connect(
            lambda: self.sort_table("timestamp", False)
        )
        sort_time_desc.clicked.connect(
            lambda: self.sort_table("timestamp", True)
        )

        for button in (
            sort_artist_asc,
            sort_artist_desc,
            sort_title_asc,
            sort_title_desc,
            sort_time_asc,
            sort_time_desc,
        ):
            sort_row.addWidget(button)

        saved_layout.addLayout(sort_row)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            [
                "Delete",
                "Load",
                "Title",
                "Artist",
                "Timestamp",
                "Compactcode",
            ]            
        )

        self.table.setSortingEnabled(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setAlternatingRowColors(True)

        saved_layout.addWidget(self.table)

        # Place the bottom section in the vertical splitter
        main_splitter.addWidget(saved_group)

        # Initial ratio between top and bottom
        main_splitter.setSizes([470, 260])

        # The vertical splitter now fills the main window
        main_layout.addWidget(main_splitter)
        

    def lyrics_to_blocks(self):
        self.song_canvas.clear()

        lines = self.lyrics_edit.toPlainText().splitlines()

        for line in lines:
            line = line.strip()

            if not line:
                self.song_canvas.add_line([("*", 0)])
                continue

            syllables = line.split()
            self.song_canvas.add_line(syllables)

        self.song_title_label.setText(
            f"{self.title_edit.text()} — {self.artist_edit.text()}"
        )
        self.blocks_changed()

    def blocks_changed(self):
        compact = self.song_canvas.compact()

        title = self.title_edit.text()
        artist = self.artist_edit.text()

        self.compact_edit.setPlainText(make_song(artist, title, compact))

    def compact_to_blocks(self):
        raw = self.compact_edit.toPlainText().strip()

        if "[compact]" in raw:
            artist = html.unescape(xml_value(raw, "artist"))
            title = html.unescape(xml_value(raw, "title"))
            compact = xml_value(raw, "compact")
        else:
            artist = self.artist_edit.text()
            title = self.title_edit.text()
            compact = raw

        self.artist_edit.setText(artist)
        self.title_edit.setText(title)
        self.song_title_label.setText(f"{title} — {artist}")

        blocks = self.parse_compact(compact)
        self.song_canvas.set_blocks(blocks)

    def parse_compact(self, compact):
        blocks = []
        i = 0

        while i < len(compact):
            match = re.match(r"(\d+)", compact[i:])

            if not match:
                # Unnumbered text is treated as text without a pitch.
                next_number = re.search(r"\d+", compact[i:])
                end = i + next_number.start() if next_number else len(compact)
                blocks.append((compact[i:end], 0))
                i = end
                continue

            pitch = int(match.group(1))
            i += len(match.group(1))

            next_number = re.search(r"\d+", compact[i:])
            end = i + next_number.start() if next_number else len(compact)
            text = compact[i:end]

            if pitch == 0 and text == "*":
                blocks.append(("*", 0))
            else:
                blocks.append((text, pitch if pitch in PITCHES else 49))

            i = end

        return blocks

    def save_current(self):
        compact = self.song_canvas.compact()
        record = make_song(
            self.artist_edit.text(),
            self.title_edit.text(),
            compact,
        )

        with open(self.file_name, "a", encoding="utf-8") as file:
            file.write(record + "\n")

        self.load_file()

    def change_file(self):
        self.file_name = self.file_edit.text().strip() or DEFAULT_FILE

        if not os.path.exists(self.file_name):
            open(self.file_name, "w", encoding="utf-8").close()

        self.load_file()

    def load_file(self):
        self.file_name = self.file_edit.text().strip() or DEFAULT_FILE

        if not os.path.exists(self.file_name):
            open(self.file_name, "w", encoding="utf-8").close()

        self.records.clear()

        with open(self.file_name, "r", encoding="utf-8") as file:
            for line in file:
                line = line.strip()

                if not line:
                    continue

                self.records.append(
                    {
                        "raw": line,
                        "artist": html.unescape(xml_value(line, "artist")),
                        "title": html.unescape(xml_value(line, "title")),
                        "compact": xml_value(line, "compact"),
                        "timestamp": xml_value(line, "timestamp"),
                    }
                )

        self.refresh_table()

    def refresh_table(self):
        needle = self.filter_edit.text().lower().strip()

        rows = [
            record for record in self.records
            if needle in record["artist"].lower()
            or needle in record["title"].lower()
        ]

        self.table.setRowCount(0)

        for record in rows:
            row = self.table.rowCount()
            self.table.insertRow(row)

            delete_button = QPushButton("Delete")
            load_button = QPushButton("Load")

            delete_button.clicked.connect(
                lambda checked=False, r=record: self.delete_record(r)
            )
            load_button.clicked.connect(
                lambda checked=False, r=record: self.load_record(r)
            )

            self.table.setCellWidget(row, 0, delete_button)
            self.table.setCellWidget(row, 1, load_button)
            self.table.setItem(row, 2, QTableWidgetItem(record["title"]))
            self.table.setItem(row, 3, QTableWidgetItem(record["artist"]))
            self.table.setItem(row, 4, QTableWidgetItem(record["timestamp"]))
            self.table.setItem(row, 5, QTableWidgetItem(record["compact"]))

    def delete_record(self, record):
        answer = QMessageBox.question(
            self,
            "Delete",
            f"Delete Song '{record['title']}' ?",
        )

        if answer != QMessageBox.Yes:
            return

        self.records.remove(record)
        self.write_records()
        self.refresh_table()

    def load_record(self, record):
        self.artist_edit.setText(record["artist"])
        self.title_edit.setText(record["title"])
        self.compact_edit.setPlainText(record["raw"])
        self.compact_to_blocks()

    def write_records(self):
        with open(self.file_name, "w", encoding="utf-8") as file:
            for record in self.records:
                file.write(record["raw"] + "\n")


    def sort_table(self, field, reverse=False):
        if field == "timestamp":
            def sort_key(record):
                return record.get("timestamp", "")
        else:
            def sort_key(record):
                return record.get(field, "").casefold()

        self.records.sort(
            key=sort_key,
            reverse=reverse,
        )

        self.refresh_table()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
