#!/usr/bin/env python3
"""
test_zotero_utils.py — regressietests op get_library_keys_with_weights().

Aanleiding (23 aug 2026): het annotatiegewicht stond op `+=`, waardoor een
geannoteerd item gewicht 4 kreeg terwijl vier van de zes signalen in de
codebase 3 zeggen — de constante zelf ("3x weight vs. unannotated"), haar
naamgeving als tegenhanger van WEIGHT_DEFAULT, en CLAUDE.md. De tegenspraak
zat al in de commit die de constante introduceerde en heeft vijf maanden
ongezien bestaan, want er was geen enkele test op dit bestand.

Draait op kale stdlib: feedreader_core importeert numpy op modulehoogte maar
gebruikt het alleen binnen functies, dus een stub volstaat. De CI-runner heeft
geen pip-install-stap.
"""
import sqlite3
import sys
import types
import unittest
from pathlib import Path

sys.modules.setdefault("numpy", types.ModuleType("numpy"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from feedreader_core import WEIGHT_ANNOTATIONS, WEIGHT_DEFAULT  # noqa: E402
from zotero_utils import get_library_keys_with_weights  # noqa: E402

INBOX = 99

SCHEMA = """
CREATE TABLE itemTypes       (itemTypeID INTEGER, typeName TEXT);
CREATE TABLE items           (itemID INTEGER, key TEXT, itemTypeID INTEGER);
CREATE TABLE collectionItems (itemID INTEGER, collectionID INTEGER);
CREATE TABLE deletedItems    (itemID INTEGER);
CREATE TABLE itemAttachments (itemID INTEGER, parentItemID INTEGER);
CREATE TABLE itemAnnotations (itemID INTEGER, parentItemID INTEGER);
"""

TYPES = {1: "journalArticle", 2: "note", 3: "attachment", 4: "annotation"}


class Vault:
    """Minimale Zotero-database in het geheugen."""

    def __init__(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.executescript(SCHEMA)
        self.conn.executemany("INSERT INTO itemTypes VALUES (?, ?)", TYPES.items())
        self._id = 0

    def item(self, key, typenaam="journalArticle", inbox=False, verwijderd=False):
        self._id += 1
        tid = next(k for k, v in TYPES.items() if v == typenaam)
        self.conn.execute("INSERT INTO items VALUES (?, ?, ?)", (self._id, key, tid))
        if inbox:
            self.conn.execute("INSERT INTO collectionItems VALUES (?, ?)", (self._id, INBOX))
        if verwijderd:
            self.conn.execute("INSERT INTO deletedItems VALUES (?)", (self._id,))
        return self._id

    def annoteer(self, ouder_id, aantal=1):
        self._id += 1
        bijlage = self._id
        self.conn.execute("INSERT INTO items VALUES (?, ?, 3)", (bijlage, f"ATT{bijlage}"))
        self.conn.execute("INSERT INTO itemAttachments VALUES (?, ?)", (bijlage, ouder_id))
        for _ in range(aantal):
            self._id += 1
            self.conn.execute("INSERT INTO items VALUES (?, ?, 4)", (self._id, f"ANN{self._id}"))
            self.conn.execute("INSERT INTO itemAnnotations VALUES (?, ?)", (self._id, bijlage))

    def gewichten(self):
        return get_library_keys_with_weights(self.conn, INBOX)


class TestGewichten(unittest.TestCase):

    def test_kaal_item_krijgt_basisgewicht(self):
        v = Vault()
        v.item("PLAIN001")
        self.assertEqual(v.gewichten()["PLAIN001"], float(WEIGHT_DEFAULT))

    def test_geannoteerd_item_krijgt_precies_weight_annotations(self):
        """De kern: WEIGHT_ANNOTATIONS is een absoluut gewicht, geen opslag."""
        v = Vault()
        v.annoteer(v.item("ANNOT001"))
        gewicht = v.gewichten()["ANNOT001"]
        self.assertEqual(gewicht, float(WEIGHT_ANNOTATIONS))
        self.assertNotEqual(gewicht, float(WEIGHT_DEFAULT + WEIGHT_ANNOTATIONS))

    def test_meerdere_annotaties_tellen_niet_op(self):
        v = Vault()
        v.annoteer(v.item("MANY0001"), aantal=5)
        self.assertEqual(v.gewichten()["MANY0001"], float(WEIGHT_ANNOTATIONS))

    def test_inbox_item_valt_af(self):
        v = Vault()
        v.item("INBOX001", inbox=True)
        v.item("KEEP0001")
        self.assertNotIn("INBOX001", v.gewichten())
        self.assertIn("KEEP0001", v.gewichten())

    def test_verwijderd_item_valt_af(self):
        v = Vault()
        v.item("TRASH001", verwijderd=True)
        self.assertNotIn("TRASH001", v.gewichten())

    def test_note_en_attachment_vallen_af(self):
        v = Vault()
        v.item("NOTE0001", typenaam="note")
        v.item("ATTA0001", typenaam="attachment")
        self.assertEqual(v.gewichten(), {})

    def test_annotatie_blijft_bewust_in_de_sleutelverzameling(self):
        """
        Annotaties dragen een eigen itemtype en passeren het note/attachment-filter.
        Gemeten 23 aug 2026: 58% van de sleutelverzameling is een losse PDF-markering
        van mediaan 17 tekens. Ronde 1 van de embedding-bake-off toonde dat weghalen
        niets oplevert — de vier varianten overlapten volledig in hun 95%-intervallen —
        dus dit gedrag blijft staan. Deze test legt vast dat het een keuze is en geen
        vergissing; verander het niet zonder opnieuw te meten.
        """
        v = Vault()
        v.item("LOSSEANN", typenaam="annotation")
        self.assertIn("LOSSEANN", v.gewichten())


if __name__ == "__main__":
    unittest.main(verbosity=2)
