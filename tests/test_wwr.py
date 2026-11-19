"""Tests de We Work Remotely (RSS). Nunca llaman al feed real."""
from pathlib import Path

import pytest
import requests

from src.sources import SourceError, rss, weworkremotely as wwr

FIXTURE = Path(__file__).parent / "fixtures" / "wwr_sample.xml"

FEED = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>WWR</title>
<item>
  <title>Acme: QA Engineer</title>
  <region>Anywhere in the World</region>
  <category>All Other Remote</category>
  <type>Full-Time</type>
  <description>&lt;p&gt;Testing de &lt;b&gt;APIs&lt;/b&gt;&lt;/p&gt;</description>
  <pubDate>Wed, 05 Nov 2026 10:00:00 +0000</pubDate>
  <guid>https://weworkremotely.com/remote-jobs/acme-qa-engineer</guid>
  <link>https://weworkremotely.com/remote-jobs/acme-qa-engineer</link>
</item>
<item><title>Sin link</title></item>
</channel></rss>"""


class FakeResp:
    def __init__(self, content=b"", status=200):
        self.content, self.status_code = content, status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))


class FakeSession:
    def __init__(self, resp=None, error=None):
        self.resp, self.error, self.urls = resp, error, []

    def get(self, url, **kwargs):
        assert kwargs.get("timeout"), "siempre hay que pasar timeout"
        self.urls.append(url)
        if self.error:
            raise self.error
        return self.resp


def parse(xml: bytes):
    return wwr.parse(rss.ET.fromstring(xml))


def test_mapea_los_campos_y_separa_empresa_del_titulo():
    job = parse(FEED)[0]
    assert (job.company, job.title) == ("Acme", "QA Engineer")
    assert job.url == "https://weworkremotely.com/remote-jobs/acme-qa-engineer"
    assert job.location == "Anywhere in the World"
    assert job.description == "Testing de APIs"
    assert job.published_at == "2026-11-05T10:00:00+00:00"
    assert job.tags == ("All Other Remote", "Full-Time")


def test_item_incompleto_se_saltea():
    assert len(parse(FEED)) == 1


@pytest.mark.parametrize(
    "raw, expected",
    [("Acme: QA: Senior", ("Acme", "QA: Senior")),   # solo corta en el primer ":"
     ("QA Engineer", ("", "QA Engineer")),
     ("Acme:", ("", "Acme:"))],
)
def test_split_title(raw, expected):
    assert wwr._split_title(raw) == expected


def test_fecha_invalida_queda_vacia():
    assert wwr._iso_date("no es fecha") == ""


@pytest.mark.parametrize(
    "session",
    [FakeSession(error=requests.Timeout()), FakeSession(FakeResp(status=503)),
     FakeSession(FakeResp(b"<rss><no cierra")), FakeSession(FakeResp(b"x" * (rss.MAX_BYTES + 1)))],
)
def test_errores_son_SourceError(session):
    with pytest.raises(SourceError):
        wwr.fetch(session=session)


def test_xml_con_entidad_externa_no_lee_archivos():
    # XXE: un feed malicioso intenta leer /etc/passwd. ElementTree no lo resuelve.
    evil = b"""<?xml version="1.0"?><!DOCTYPE r [<!ENTITY x SYSTEM "file:///etc/passwd">]>
    <rss><channel><item><title>A: &x;</title><link>https://weworkremotely.com/1</link></item></channel></rss>"""
    with pytest.raises(SourceError):
        wwr.fetch(session=FakeSession(FakeResp(evil)))


# --------------------------------------------- contract check (feed real)

@pytest.mark.skipif(not FIXTURE.exists(), reason="falta tests/fixtures/wwr_sample.xml")
def test_contrato_feed_real():
    jobs = parse(FIXTURE.read_bytes())
    assert len(jobs) >= 3
    assert all(j.url.startswith("https://weworkremotely.com/") for j in jobs)
    assert all(j.title and "<p>" not in j.description for j in jobs)
