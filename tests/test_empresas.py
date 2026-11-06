"""
Tests de los portales de empresas (Greenhouse, Lever, Ashby, Teamtailor).
Datos armados con la forma de cada API; nunca llaman a internet.
Los contract checks con respuestas REALES se saltean si falta el fixture.
"""
import json
from pathlib import Path

import pytest

from src.sources import SourceError, empresas, rss
from src.sources.empresas import Company, load_companies, parse_company_line

FIX = Path(__file__).parent / "fixtures"
CO = Company("Acme", "greenhouse", "acme")


# ------------------------------------------------------- empresas.txt

@pytest.mark.parametrize(
    "line, expected",
    [
        ("CDA | teamtailor | https://cda.teamtailor.com/", Company("CDA", "teamtailor", "https://cda.teamtailor.com")),
        ("Acme | Greenhouse | acme", Company("Acme", "greenhouse", "acme")),
        ("Beta|lever|beta-co", Company("Beta", "lever", "beta-co")),
    ],
)
def test_lineas_validas(line, expected):
    assert parse_company_line(line) == expected


@pytest.mark.parametrize(
    "line",
    [
        "Acme | greenhouse",                          # falta la dirección
        "Acme | workday | acme",                      # ATS no soportado
        "Acme | lever | acme/../../otra",             # intento de cambiar la ruta
        "Acme | ashby | acme?x=1",
        "Acme | teamtailor | http://acme.com",        # sin https
        "Acme | teamtailor | acme",                   # no es URL
        " | lever | acme",
    ],
)
def test_lineas_invalidas(line):
    with pytest.raises(ValueError):
        parse_company_line(line)


def test_load_companies_ignora_comentarios_y_junta_errores(tmp_path):
    path = tmp_path / "empresas.txt"
    path.write_text("# comentario\n\nAcme | lever | acme\nRota | nada | x\n", encoding="utf-8")
    companies, errors = load_companies(path)
    assert companies == [Company("Acme", "lever", "acme")]
    assert errors == ["empresas.txt línea 4: ats desconocido: nada (opciones: greenhouse, lever, ashby, teamtailor)"]


def test_sin_archivo_no_hay_empresas(tmp_path):
    assert load_companies(tmp_path / "no.txt") == ([], [])


# ------------------------------------------------------- cada ATS

def test_greenhouse():
    data = {"jobs": [
        {"id": 123, "title": "QA Analyst", "absolute_url": "https://boards.greenhouse.io/acme/jobs/123",
         "location": {"name": "Buenos Aires"}, "content": "&lt;p&gt;Testing &amp;amp; APIs&lt;/p&gt;",
         "first_published": "2026-11-01T10:00:00-03:00"},
        {"title": "sin id"},
    ]}
    [job] = empresas.parse_greenhouse(data, CO)
    assert (job.source, job.source_id, job.company) == ("Greenhouse", "123", "Acme")
    assert job.location == "Buenos Aires"
    assert job.description == "Testing & APIs"       # des-escapado y sin HTML
    assert job.published_at == "2026-11-01T10:00:00-03:00"


@pytest.mark.parametrize(
    "workplace, expected",
    [("remote", "Buenos Aires (Remote)"), ("hybrid", "Buenos Aires (Híbrido)"),
     ("on-site", "Buenos Aires (Presencial)"), ("unspecified", "Buenos Aires"), (None, "Buenos Aires")],
)
def test_lever_modalidad(workplace, expected):
    data = [{"id": "abc", "text": "QA", "hostedUrl": "https://jobs.lever.co/acme/abc",
             "categories": {"location": "Buenos Aires"}, "workplaceType": workplace,
             "descriptionPlain": "Intro", "lists": [{"text": "Requisitos", "content": "<li>SQL</li>"}],
             "additionalPlain": "Beneficios", "createdAt": 1730800000000}]
    [job] = empresas.parse_lever(data, CO)
    assert job.location == expected
    assert job.description == "Intro\nRequisitos\nSQL\nBeneficios"
    assert job.published_at.startswith("2024-11-05")


def test_ashby_junta_ubicaciones_y_saltea_no_publicadas():
    data = {"jobs": [
        {"id": "1", "title": "QA", "jobUrl": "https://jobs.ashbyhq.com/acme/1", "location": "Argentina",
         "secondaryLocations": [{"location": "Chile"}], "workplaceType": "Remote",
         "descriptionPlain": "Testing", "publishedAt": "2026-11-01T00:00:00Z"},
        {"id": "2", "title": "Oculta", "jobUrl": "https://jobs.ashbyhq.com/acme/2", "isListed": False},
    ]}
    [job] = empresas.parse_ashby(data, CO)
    assert job.location == "Argentina, Chile (Remote)"


def test_teamtailor_rss():
    xml = b"""<rss xmlns:tt="https://teamtailor.com/locations"><channel><item>
      <title>QA Analyst</title><link>https://cda.teamtailor.com/jobs/1-qa</link>
      <guid>tt-1</guid><pubDate>Wed, 05 Nov 2026 10:00:00 +0000</pubDate>
      <description>&lt;p&gt;Testing&lt;/p&gt;</description>
      <tt:remoteStatus>hybrid</tt:remoteStatus>
      <tt:locations><tt:location><tt:city>Buenos Aires</tt:city><tt:country>Argentina</tt:country></tt:location></tt:locations>
    </item></channel></rss>"""
    [job] = empresas.parse_teamtailor(rss.ET.fromstring(xml), Company("CDA", "teamtailor", "https://cda.teamtailor.com"))
    assert (job.source, job.source_id, job.company) == ("Teamtailor", "tt-1", "CDA")
    assert job.location == "Buenos Aires, Argentina (Híbrido)"
    assert job.description == "Testing"


def test_teamtailor_aviso_real_de_cda():
    # Estructura copiada del feed real (03/11/2026): remoteStatus SIN namespace,
    # locations con namespace tt:, y una sede con nombre, dirección y zip.
    xml = b"""<rss xmlns:tt="https://teamtailor.com/locations"><channel><item>
      <title>QA JR</title><description>&lt;p&gt;Testing funcional&lt;/p&gt;</description>
      <pubDate>Tue, 03 Nov 2026 18:04:14 -0300</pubDate>
      <link>https://cdainformatica.na.teamtailor.com/jobs/731271-qa-jr</link>
      <remoteStatus>none</remoteStatus>
      <guid>110ec2ca-b09a-4fba-bf35-9c97698cdeda</guid>
      <tt:locations><tt:location>
        <tt:name>Sede Argentina</tt:name><tt:address>Av. Caseros 3515</tt:address>
        <tt:zip>C1263</tt:zip><tt:city>Buenos Aires</tt:city><tt:country>Argentina</tt:country>
      </tt:location></tt:locations>
      <tt:department>Talento y Cultura</tt:department><tt:role/>
    </item></channel></rss>"""
    cda = Company("CDA", "teamtailor", "https://cdainformatica.na.teamtailor.com")
    [job] = empresas.parse_teamtailor(rss.ET.fromstring(xml), cda)
    assert job.location == "Buenos Aires, Argentina (Presencial)"
    assert job.published_at == "2026-11-03T18:04:14-03:00"
    assert job.source_id == "110ec2ca-b09a-4fba-bf35-9c97698cdeda"


def test_teamtailor_sin_ciudad_usa_el_nombre_de_la_sede():
    xml = b"""<rss xmlns:tt="x"><channel><item><title>QA</title><link>https://a.teamtailor.com/jobs/1</link>
      <guid>1</guid><tt:locations><tt:location><tt:name>Oficina Central</tt:name></tt:location></tt:locations>
    </item></channel></rss>"""
    [job] = empresas.parse_teamtailor(rss.ET.fromstring(xml), Company("A", "teamtailor", "https://a.teamtailor.com"))
    assert job.location == "Oficina Central"


@pytest.mark.parametrize("data", [None, {}, {"jobs": None}, [], "texto"])
def test_respuestas_raras_no_rompen(data):
    assert empresas.parse_greenhouse(data if isinstance(data, dict) or data is None else {}, CO) == []
    assert empresas.parse_lever(data, CO) == []


# ------------------------------------------------------- fetch()

def test_una_empresa_caida_no_frena_a_las_demas(monkeypatch):
    ok = Company("Ok", "lever", "ok")
    down = Company("Caida", "greenhouse", "caida")

    def fake_lever(company, session=None):
        return empresas.parse_lever([{"id": "1", "text": "QA", "hostedUrl": "https://jobs.lever.co/ok/1"}], company)

    def fake_greenhouse(company, session=None):
        raise SourceError("Greenhouse Caida: Timeout")

    monkeypatch.setitem(empresas.READERS, "lever", fake_lever)
    monkeypatch.setitem(empresas.READERS, "greenhouse", fake_greenhouse)
    assert [j.company for j in empresas.fetch(companies=[down, ok])] == ["Ok"]


def test_si_fallan_todas_es_SourceError(monkeypatch):
    def down(company, session=None):
        raise SourceError("x")

    monkeypatch.setitem(empresas.READERS, "lever", down)
    with pytest.raises(SourceError):
        empresas.fetch(companies=[Company("A", "lever", "a"), Company("B", "lever", "b")])


def test_sin_empresas_configuradas_no_falla():
    assert empresas.fetch(companies=[]) == []


# --------------------------------- contract checks con respuestas REALES

@pytest.mark.parametrize(
    "ats, filename, loader",
    [("greenhouse", "greenhouse_sample.json", json.loads),
     ("lever", "lever_sample.json", json.loads),
     ("ashby", "ashby_sample.json", json.loads),
     ("teamtailor", "teamtailor_sample.xml", rss.ET.fromstring)],
)
def test_contrato_respuesta_real(ats, filename, loader):
    path = FIX / filename
    if not path.exists():
        pytest.skip(f"falta tests/fixtures/{filename}")
    raw = path.read_bytes()
    data = loader(raw.decode("utf-8") if loader is json.loads else raw)
    jobs = getattr(empresas, f"parse_{ats}")(data, Company("Real", ats, "real"))
    assert len(jobs) >= 1
    assert all(j.url.startswith("https://") and j.title for j in jobs)
    assert all("<p>" not in j.description for j in jobs)
