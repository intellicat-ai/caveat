"""OpenAlex queries used by the authoring stages.

Every function returns plain data; callers record the query string and the
date next to any number they keep, so each count is reproducible.
"""
from net import Client

API = "https://api.openalex.org"
WORK_FIELDS = ("id,doi,title,publication_year,cited_by_count,is_retracted,primary_topic,"
               "best_oa_location,open_access,authorships,primary_location")


def _headers(client: Client) -> dict:
    key = client.config.get("api_key")
    return {"Authorization": f"Bearer {key}"} if key else {}


def short_id(oa_id: str | None) -> str | None:
    return None if oa_id is None else oa_id.rsplit("/", 1)[-1]


def work(client: Client, ref: str) -> dict | None:
    """A work by OpenAlex id (W...) or DOI (10.x/... or https://doi.org/...)."""
    ref = ref.strip()
    if ref.startswith("https://doi.org/"):
        ref = ref[len("https://doi.org/"):]
    key = ref if ref.startswith("W") else f"doi:{ref}"
    return client.json(f"{API}/works/{key}", params={"select": WORK_FIELDS}, headers=_headers(client))


def phrase_filter(phrase: str, field: str = "title_and_abstract") -> str:
    """An exact-phrase search filter. Commas would split the filter, so they
    are dropped."""
    phrase = phrase.replace(",", " ").replace('"', " ").strip()
    return f'{field}.search:"{phrase}"'


def count(client: Client, filt: str) -> int:
    d = client.json(f"{API}/works", params={"filter": filt, "per-page": 1, "select": "id"}, headers=_headers(client))
    return d["meta"]["count"]


def group_by(client: Client, filt: str | None, key: str) -> list[dict]:
    params = {"group_by": key}
    if filt:
        params["filter"] = filt
    d = client.json(f"{API}/works", params=params, headers=_headers(client))
    return d["group_by"]


def sample(client: Client, filt: str, n: int, seed: int, fields: str = WORK_FIELDS) -> list[dict]:
    """A uniform random sample of up to n works (OpenAlex sample with a seed)."""
    d = client.json(f"{API}/works", params={"filter": filt, "sample": n, "seed": seed, "per-page": min(n, 200),
                                            "select": fields}, headers=_headers(client))
    return d["results"]


def top_cited(client: Client, filt: str, n: int, fields: str = WORK_FIELDS) -> list[dict]:
    d = client.json(f"{API}/works", params={"filter": filt, "sort": "cited_by_count:desc", "per-page": min(n, 200),
                                            "select": fields}, headers=_headers(client))
    return d["results"]


def topic(client: Client, topic_id: str) -> dict | None:
    return client.json(f"{API}/topics/{short_id(topic_id)}", headers=_headers(client))


def oa_pdf_url(w: dict) -> str | None:
    loc = w.get("best_oa_location") or {}
    return loc.get("pdf_url")
