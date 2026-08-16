"""
test_feedreader_identity.py — Unittests voor de identiteitssleutel

Draait op kale stdlib (CI heeft geen pip-install-stap):
    python3 -m unittest test_feedreader_identity -v
"""

import unittest

from feedreader_identity import (
    TRACKING_PARAMS_PER_HOST,
    canonical_url,
    item_identity,
    item_keys,
)


class TestGerapporteerdeBug(unittest.TestCase):
    """De concrete regressie: PubMed's ff= liet items dagelijks terugkeren.

    Beide URLs komen letterlijk uit score_log.jsonl — hetzelfde erratum, twee
    opeenvolgende pipeline-runs (03:04 en 07:06 op 16 aug 2026).
    """

    BASE = ("https://pubmed.ncbi.nlm.nih.gov/42461057/"
            "?utm_source=Other&utm_medium=rss&utm_campaign=None"
            "&utm_content=1VCF4_1oOVazbJoli5IZNQujrUQMxHsnQskPIE_UxXHtfOUEAc&fc=None")

    def test_zelfde_artikel_over_twee_runs(self):
        run1 = f"{self.BASE}&ff=20260816030418&v=2.20.1"
        run2 = f"{self.BASE}&ff=20260816070654&v=2.20.1"
        self.assertEqual(canonical_url(run1), canonical_url(run2))

    def test_overleeft_api_versiebump(self):
        """Op 5 aug 2026 sprong v= van 2.20.0.post5 naar 2.20.1."""
        oud = f"{self.BASE}&ff=20260805011630&v=2.20.0.post5+40e1b98"
        nieuw = f"{self.BASE}&ff=20260816030418&v=2.20.1"
        self.assertEqual(canonical_url(oud), canonical_url(nieuw))

    def test_sleutel_bevat_geen_ruis_meer(self):
        self.assertEqual(
            canonical_url(f"{self.BASE}&ff=20260816030418&v=2.20.1"),
            "https://pubmed.ncbi.nlm.nih.gov/42461057",
        )

    def test_verschillende_artikelen_blijven_verschillend(self):
        a = f"{self.BASE}&ff=20260816030418&v=2.20.1"
        b = a.replace("42461057", "42497003")
        self.assertNotEqual(canonical_url(a), canonical_url(b))


class TestYouTubeIdentiteit(unittest.TestCase):
    """De gevaarlijkste faalmodus: 277 video's die samenklappen tot één item."""

    def test_v_blijft_behouden_op_youtube(self):
        self.assertIn("v=dQw4w9WgXcQ", canonical_url(
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ"))

    def test_twee_videos_blijven_gescheiden(self):
        self.assertNotEqual(
            canonical_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ"),
            canonical_url("https://www.youtube.com/watch?v=-0kJLh9du4c"),
        )

    def test_zelfde_video_met_campagneruis(self):
        self.assertEqual(
            canonical_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ"),
            canonical_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ"
                          "&utm_source=rss&fbclid=xyz"),
        )


class TestDenylistBeleid(unittest.TestCase):
    """Onbekende parameters blijven staan — falen richting duplicaten."""

    def test_onbekende_parameter_blijft(self):
        self.assertIn("artikelid=1234", canonical_url(
            "https://voorbeeld.nl/nieuws?artikelid=1234"))

    def test_v_blijft_op_onbekende_host(self):
        """'v' staat NIET globaal op de denylist — alleen per host."""
        self.assertIn("v=abc", canonical_url("https://voorbeeld.nl/x?v=abc"))

    def test_alleen_pubmed_heeft_een_per_host_regel(self):
        self.assertEqual(set(TRACKING_PARAMS_PER_HOST), {"pubmed.ncbi.nlm.nih.gov"})


class TestNormalisatie(unittest.TestCase):

    def test_parametervolgorde_maakt_niet_uit(self):
        self.assertEqual(
            canonical_url("https://voorbeeld.nl/a?x=1&y=2"),
            canonical_url("https://voorbeeld.nl/a?y=2&x=1"),
        )

    def test_afsluitende_slash(self):
        self.assertEqual(
            canonical_url("https://pure.eur.nl/en/publications/framework/"),
            canonical_url("https://pure.eur.nl/en/publications/framework"),
        )

    def test_fragment_valt_weg(self):
        self.assertEqual(
            canonical_url("https://voorbeeld.nl/a#sectie-3"),
            canonical_url("https://voorbeeld.nl/a"),
        )

    def test_hoofdletters_in_host_en_schema(self):
        self.assertEqual(
            canonical_url("HTTPS://Voorbeeld.NL/a"),
            canonical_url("https://voorbeeld.nl/a"),
        )

    def test_pad_blijft_hoofdlettergevoelig(self):
        """Paden zijn dat op de meeste servers wél."""
        self.assertNotEqual(
            canonical_url("https://voorbeeld.nl/Artikel"),
            canonical_url("https://voorbeeld.nl/artikel"),
        )

    def test_www_wordt_niet_gestript(self):
        """Conservatief: www en bare host kunnen verschillende sites zijn."""
        self.assertNotEqual(
            canonical_url("https://www.voorbeeld.nl/a"),
            canonical_url("https://voorbeeld.nl/a"),
        )

    def test_www_prefix_vindt_wel_de_per_host_regel(self):
        self.assertEqual(
            canonical_url("https://www.pubmed.ncbi.nlm.nih.gov/1/?v=2.20.1"),
            "https://www.pubmed.ncbi.nlm.nih.gov/1",
        )


class TestRobuustheid(unittest.TestCase):
    """Een kapotte URL mag nooit een hele pipeline-run laten klappen."""

    def test_lege_invoer(self):
        self.assertEqual(canonical_url(""), "")
        self.assertEqual(canonical_url("   "), "")

    def test_geen_host(self):
        self.assertEqual(canonical_url("mailto:iemand@voorbeeld.nl"),
                         "mailto:iemand@voorbeeld.nl")
        self.assertEqual(canonical_url("gewoon-tekst"), "gewoon-tekst")

    def test_lege_urls_vallen_niet_samen(self):
        """Twee items zonder URL mogen elkaar niet wegdedupen."""
        self.assertEqual(canonical_url(""), canonical_url(""))  # documenteert
        # ...daarom moet de aanroeper items zonder URL overslaan, niet dedupen.

    def test_parameter_zonder_waarde_blijft(self):
        self.assertIn("vlag=", canonical_url("https://voorbeeld.nl/a?vlag="))

    def test_idempotent(self):
        u = "https://pubmed.ncbi.nlm.nih.gov/42461057/?ff=123&v=2.20.1"
        self.assertEqual(canonical_url(canonical_url(u)), canonical_url(u))


class TestItemIdentity(unittest.TestCase):
    """Guid eerst, canonieke URL als terugval. Alle guids hieronder zijn
    letterlijk opgehaald uit de betreffende live feeds op 16 aug 2026."""

    def test_pubmed_guid_overleeft_link_churn(self):
        link = ("https://pubmed.ncbi.nlm.nih.gov/42461057/?utm_source=Other"
                "&fc=None&ff={}&v=2.20.1")
        self.assertEqual(
            item_identity(link.format("20260816030418"), "pubmed:42461057"),
            item_identity(link.format("20260816070654"), "pubmed:42461057"),
        )

    def test_captivate_afleveringen_blijven_gescheiden(self):
        """DE regressie voor het stille verlies: identieke link, andere guid."""
        showpagina = "https://doe-duurzaam.nl/de-groene-nerds-podcast/"
        self.assertNotEqual(
            item_identity(showpagina, "9499d371-5688-4f21-a45d-558fd0e82723"),
            item_identity(showpagina, "9e2b8630-6ffd-4702-b549-6980ee6ca643"),
        )

    def test_pure_co_auteurs_blijven_samenvallen(self):
        """Zelfde paper via de feeds van Cattel én Van Kleef."""
        guid = ("https://pure.eur.nl/en/publications/"
                "a-framework-for-the-design-of-risk-adjustment-models-in-health-ca/")
        self.assertEqual(item_identity(guid, guid), item_identity(guid, guid))
        self.assertEqual(item_identity(guid, guid), canonical_url(guid))

    def test_zonder_guid_terugval_op_link(self):
        link = "https://voorbeeld.nl/artikel?utm_source=rss"
        self.assertEqual(item_identity(link), canonical_url(link))
        self.assertEqual(item_identity(link, None), canonical_url(link))
        self.assertEqual(item_identity(link, "   "), canonical_url(link))

    def test_guid_in_url_vorm_wordt_gecanonicaliseerd(self):
        """Mocht een feed ooit tracking in de guid zetten."""
        self.assertEqual(
            item_identity("x", "https://tweakers.net/nieuws/234180?utm_source=rss"),
            "https://tweakers.net/nieuws/234180",
        )

    def test_opaque_guid_gaat_ongewijzigd_door(self):
        self.assertEqual(item_identity("x", "pubmed:42461057"), "pubmed:42461057")
        self.assertEqual(item_identity("x", "yt:video:dQw4w9WgXcQ"),
                         "yt:video:dQw4w9WgXcQ")

    def test_guid_wint_van_link(self):
        """Anders zou de link-churn alsnog doorwerken."""
        self.assertEqual(
            item_identity("https://a.nl/1?ff=1", "vast-id"),
            item_identity("https://b.nl/2?ff=2", "vast-id"),
        )


class TestItemKeys(unittest.TestCase):
    """De sleutelverzameling die de overgang naar guid-identiteiten draagt."""

    PUBMED_LINK = ("https://pubmed.ncbi.nlm.nih.gov/42461057/?utm_source=Other"
                   "&fc=None&ff=20260816030418&v=2.20.1")

    def test_bevat_beide_vormen(self):
        keys = item_keys(self.PUBMED_LINK, "pubmed:42461057")
        self.assertIn("pubmed:42461057", keys)
        self.assertIn("https://pubmed.ncbi.nlm.nih.gov/42461057", keys)

    def test_matcht_historische_logregel(self):
        """Regels van vóór 16 aug 2026 dragen alleen de canonieke URL.

        Zonder deze match zou de eerste run na de fix élk item als nieuw zien —
        nog één volledige duplicatengolf in NetNewsWire.
        """
        historie = {"https://pubmed.ncbi.nlm.nih.gov/42461057"}
        keys = item_keys(self.PUBMED_LINK, "pubmed:42461057")
        self.assertTrue(any(k in historie for k in keys))

    def test_youtube_matcht_zowel_guid_als_url(self):
        """backfill-scout.py kent via yt-dlp alleen de URL-vorm."""
        keys = item_keys("https://www.youtube.com/watch?v=iF5IWjOWcA4",
                         "yt:video:iF5IWjOWcA4")
        self.assertIn("yt:video:iF5IWjOWcA4", keys)
        self.assertIn("https://www.youtube.com/watch?v=iF5IWjOWcA4", keys)

    def test_gedeelde_link_valt_terug_op_alleen_guid(self):
        """Captivate: showpagina bij élke aflevering, dus URL-vorm uitschakelen."""
        showpagina = "https://doe-duurzaam.nl/de-groene-nerds-podcast/"
        a = item_keys(showpagina, "9499d371-5688-4f21-a45d-558fd0e82723",
                      link_is_shared=True)
        b = item_keys(showpagina, "9e2b8630-6ffd-4702-b549-6980ee6ca643",
                      link_is_shared=True)
        self.assertEqual(a, ("9499d371-5688-4f21-a45d-558fd0e82723",))
        self.assertFalse(set(a) & set(b), "afleveringen mogen niet overlappen")

    def test_zonder_de_vlag_zouden_afleveringen_botsen(self):
        """Documenteert waaróm link_is_shared bestaat."""
        showpagina = "https://doe-duurzaam.nl/de-groene-nerds-podcast/"
        a = item_keys(showpagina, "uuid-1")
        b = item_keys(showpagina, "uuid-2")
        self.assertTrue(set(a) & set(b))

    def test_pure_co_auteurs_delen_een_sleutel(self):
        link = ("https://pure.eur.nl/en/publications/"
                "a-framework-for-the-design-of-risk-adjustment-models-in-health-ca/")
        cattel = item_keys(link, link)
        kleef = item_keys(link, link)
        self.assertTrue(set(cattel) & set(kleef))

    def test_zonder_guid_alleen_de_url(self):
        self.assertEqual(item_keys("https://voorbeeld.nl/a?utm_source=x"),
                         ("https://voorbeeld.nl/a",))

    def test_leeg_item_levert_geen_sleutels(self):
        """Anders zouden alle URL-loze items elkaar wegdedupen."""
        self.assertEqual(item_keys("", None), ())
        self.assertEqual(item_keys("", "", link_is_shared=True), ())


if __name__ == "__main__":
    unittest.main()
