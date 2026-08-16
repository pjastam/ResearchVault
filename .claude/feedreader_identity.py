"""
feedreader_identity.py — Stabiele identiteit voor feed-items
=============================================================
Eén functie, ``canonical_url()``, die van een feed-link een sleutel maakt die
hetzelfde artikel over meerdere fetches en meerdere feeds heen herkent.

**Waarom dit bestaat.** De feedreader gebruikte de ruwe ``entry.link`` als
identiteit op drie plekken: het dedup-filter, het logboek en de Atom-``<id>``.
Een URL is echter een *locatie*, geen *identiteit* — publishers hangen er vrij
parameters aan. PubMed plakt bij elke fetch ``ff=<timestamp>`` aan de link:

    .../42461057/?utm_source=Other&fc=None&ff=20260816030418&v=2.20.1
                                            ^^^^^^^^^^^^^^^^ verandert per fetch

Daardoor zag elke pipeline-run hetzelfde artikel als nieuw, kreeg het een nieuwe
Atom-``<id>``, en toonde NetNewsWire het opnieuw. Gemeten op 16 aug 2026:
651 overtollige regels in ``score_log.jsonl`` (4,9%), waarvan 502 uit de
PubMed-feed ``Medical Care[Journal]``.

**Beleid: denylist, niet allowlist.** Onbekende parameters blijven staan. Een
gemiste trackingparameter kost duplicaten — zichtbaar en makkelijk te
diagnosticeren. Een te agressieve strip laat artikelen stil samenklappen, en
ontbrekende items maken geen geluid.

Alleen stdlib, zodat ``test_feedreader_identity.py`` in CI draait zonder
pip-install-stap (net als ``feedreader_fetch.py``).
"""

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

# ── Globale denylist ────────────────────────────────────────────────────────
# Elke regel is gemeten in score_log.jsonl (13.267 items, 16 aug 2026). De
# beslissende toets: varieert de parameter bínnen dezelfde host+pad? Zo ja, dan
# verandert hij terwijl het artikel gelijk blijft — dus tracking.
TRACKING_PARAMS = frozenset({
    # De hoofdschuldige: PubMed's fetch-timestamp. 43 verschillende waarden
    # voor één en dezelfde pagina — precies het aantal pipeline-runs.
    "ff",
    # PubMed, altijd letterlijk "None" — nul onderscheidend vermogen.
    "fc",
    # De UTM-familie is per definitie campagne-tracking. In dit log heeft elk
    # van de vier precies één vaste waarde (519× PubMed).
    "utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term",
    # ScienceDirect, 714×, altijd "rss_sd_all".
    "dgcid",
    # Wiley (293×) + Health Affairs (106×), altijd "R".
    "af",
    # NPO-podcasts (141×). Redundant: het pad bevat het aflevering-id al
    # (/file/ovt/138648/...). Gemeten: 131 items → 131 unieke paden, nul paden
    # met meer dan één episode-id.
    "awCollectionid", "awEpisodeid",
    # Preventief — niet in dit log aangetroffen, maar universeel click-tracking.
    "fbclid", "gclid",
})

# ── Per-host uitbreidingen ──────────────────────────────────────────────────
# Bewust NIET globaal. "v" is een parameternaam met tegengestelde rollen:
#
#   www.youtube.com          1 uniek pad (/watch) · 277 unieke v-waarden
#                            → v IS de video-identiteit; strippen klapt alle
#                              277 video's op één item
#   pubmed.ncbi.nlm.nih.gov  17 unieke paden · 2 unieke v-waarden
#                            ("2.20.0.post5 40e1b98", "2.20.1") → API-versie
#
# Sleutel zonder "www."-prefix; de lookup normaliseert dat.
TRACKING_PARAMS_PER_HOST = {
    "pubmed.ncbi.nlm.nih.gov": frozenset({"v"}),
}


def _host_key(host: str) -> str:
    """Lookup-sleutel voor TRACKING_PARAMS_PER_HOST (zonder www-prefix)."""
    return host[4:] if host.startswith("www.") else host


def item_identity(link: str, guid: str | None = None) -> str:
    """Geeft de identiteitssleutel van een feed-item: guid eerst, link als terugval.

    De RSS-``<guid>`` is de sleutel die de publisher zélf als identiteit bedoelt,
    en op elke gemeten feed is hij minstens zo goed als de link (16 aug 2026):

    ==================  ==========================  ==========================
    feed                guid                        link
    ==================  ==========================  ==========================
    PubMed              ``pubmed:42461057`` stabiel churnt per fetch (``ff=``)
    PURE (EUR/VU)       = de link, schoon           schoon — beide co-auteur-
                                                    feeds geven dezelfde guid,
                                                    dus cross-feed merging blijft
    Captivate-podcast   UUID per aflevering         showpagina, voor álle
                                                    afleveringen identiek
    Tweakers            al canoniek                 met parameters
    ==================  ==========================  ==========================

    De Captivate-rij is de reden dat dit niet puur op de URL kan: die drie
    podcastfeeds (De Groene Nerds, hasspodcast.io, homeassistant.fm) geven bij
    elke aflevering dezelfde showpagina als link. Een URL-only sleutel ziet
    aflevering 2 dan als duplicaat van aflevering 1 en gooit hem weg — stil.

    Een guid die zélf een URL is wordt gecanonicaliseerd (mocht een feed ooit
    trackingparameters in de guid zetten); een opaque guid gaat ongewijzigd door.

    Bekende faalmodus: een feed die zijn guids hergenereert geeft duplicaten.
    Dat is de gekozen faalrichting — zichtbaar en te diagnosticeren, in plaats
    van items die stil verdwijnen.
    """
    g = (guid or "").strip()
    if g:
        return canonical_url(g) if "://" in g else g
    return canonical_url(link)


def item_keys(link: str, guid: str | None = None,
              link_is_shared: bool = False) -> tuple[str, ...]:
    """Alle sleutelvormen waaronder dit item bekend kan zijn.

    Een item matcht als *één* van deze sleutels al gezien is. Twee vormen zijn
    nodig omdat de identiteitsruimte heterogeen is:

    * de guid-vorm (``pubmed:42461057``, ``yt:video:iF5IWjOWcA4``, een UUID);
    * de canonieke URL, die de historie draagt — ``score_log.jsonl`` bevat van
      vóór 16 aug 2026 alleen URLs, en ``backfill-scout.py`` kan via yt-dlp
      sowieso geen guid berekenen.

    ``link_is_shared`` zet de URL-vorm uit. Zet hem als de link binnen dezelfde
    feed-fetch bij meer dan één item voorkomt: dan onderscheidt hij niets. De
    Captivate-podcasts geven bij élke aflevering de showpagina als link — met de
    URL-vorm erbij zou aflevering 2 als duplicaat van aflevering 1 gelden en stil
    verdwijnen. Alleen de guid is daar bruikbaar.

    Zonder die vlag wint de historie-compatibiliteit: doet een feed het netjes,
    dan matcht de canonieke URL de bestaande logregels en blijft de overgang naar
    guid-identiteiten onzichtbaar — geen eenmalige duplicatengolf.
    """
    keys: list[str] = []
    ident = item_identity(link, guid)
    if ident:
        keys.append(ident)
    if not link_is_shared:
        cu = canonical_url(link)
        if cu and cu not in keys:
            keys.append(cu)
    return tuple(keys)


def canonical_url(url: str) -> str:
    """Geeft een stabiele identiteitssleutel voor een feed-link.

    Verwijdert trackingparameters, normaliseert schema/host/volgorde en laat de
    fragment-identifier vallen. De ruwe URL blijft elders bewaard: dit is de
    sleutel om op te vergelijken, niet de link om te openen.

    Lege of onparsbare invoer geeft de invoer ongewijzigd terug — een item
    zonder bruikbare URL mag nooit samenvallen met een ander item, en een
    exception hier zou een hele pipeline-run laten klappen.
    """
    if not url or not url.strip():
        return ""

    try:
        parts = urlsplit(url.strip())
    except ValueError:
        return url.strip()

    # Zonder host valt er niets te normaliseren (mailto:, urn:, kale strings).
    if not parts.netloc:
        return url.strip()

    host = parts.netloc.lower()
    drop = TRACKING_PARAMS | TRACKING_PARAMS_PER_HOST.get(_host_key(host), frozenset())

    kept = sorted(
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if k not in drop
    )

    # Afsluitende slash normaliseren: PubMed levert hem wel, andere feeds naar
    # dezelfde pagina soms niet. Een kaal pad blijft "/".
    path = parts.path.rstrip("/") or "/"

    return urlunsplit((parts.scheme.lower(), host, path, urlencode(kept), ""))
