import sys
from urllib.parse import quote, urljoin

import requests
from bs4 import BeautifulSoup
from flask import Flask, redirect, render_template
from flask_frozen import Freezer

app = Flask(__name__)
app.config["FREEZER_DESTINATION"] = "docs"
freezer = Freezer(app)

SEARCH_TERMS = ["python", "javascript", "java"]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def get_soup(url, params=None):
    response = requests.get(url, params=params, headers=HEADERS, timeout=20)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def get_text(element, default="정보 없음"):
    if element is None:
        return default
    return element.get_text(" ", strip=True)


def scrape_berlin(term):
    base_url = "https://berlinstartupjobs.com"
    search_term = quote(term.lower().replace(" ", "-"), safe="")
    url = f"{base_url}/skill-areas/{search_term}/"
    soup = get_soup(url)
    jobs = []

    for item in soup.select("li.bjs-jlid"):
        title_link = item.select_one(".bjs-jlid__h a")
        if title_link is None:
            continue

        jobs.append(
            {
                "title": get_text(title_link),
                "company": get_text(item.select_one(".bjs-jlid__b")),
                "location": "Berlin",
                "link": urljoin(base_url, title_link.get("href", "")),
            }
        )

    return jobs


def scrape_weworkremotely(term):
    base_url = "https://weworkremotely.com"
    url = f"{base_url}/remote-jobs/search"
    soup = get_soup(url, {"utf8": "✓", "term": term})
    jobs = []

    # 현재 페이지와 이전 페이지 구조를 모두 처리한다.
    for item in soup.select("li.new-listing-container, section.jobs li"):
        title = item.select_one(".new-listing__header__title__text, .title")
        if title is None:
            continue

        link = item.select_one("a.listing-link--unlocked") or title.find_parent("a")
        if link is None:
            continue

        locations = item.select(".new-listing__categories__category")
        location = locations[-1] if locations else item.select_one(".region")

        jobs.append(
            {
                "title": get_text(title),
                "company": get_text(
                    item.select_one(".new-listing__company-name, .company")
                ),
                "location": get_text(location, "Remote"),
                "link": urljoin(base_url, link.get("href", "")),
            }
        )

    return jobs


def scrape_web3(term):
    base_url = "https://web3.career"
    search_term = quote(term.lower().replace(" ", "-"), safe="")
    url = f"{base_url}/{search_term}-jobs"
    soup = get_soup(url)
    jobs = []

    for item in soup.select("tr.job-row-grid, tr.table_row"):
        title = item.select_one("h2")
        link = title.find_parent("a") if title else None
        if title is None or link is None:
            continue

        location = get_text(item.select_one(".job-location-mobile"), "Remote")

        jobs.append(
            {
                "title": get_text(title),
                "company": get_text(item.select_one("h3")),
                "location": location.replace("📍", "").strip(),
                "link": urljoin(base_url, link.get("href", "")),
            }
        )

    return jobs


@app.route("/")
def home():
    return render_template(
        "index.html",
        term="",
        results={},
        errors=[],
        total=0,
    )


@app.route("/search/<term>/")
def search(term):
    term = term.lower().strip()
    if not term:
        return redirect("/")

    results = {}
    errors = []

    scrapers = [
        ("Berlin Startup Jobs", scrape_berlin),
        ("We Work Remotely", scrape_weworkremotely),
        ("Web3 Career", scrape_web3),
    ]

    for source, scraper in scrapers:
        try:
            results[source] = scraper(term)
        except requests.RequestException:
            results[source] = []
            errors.append(f"{source}의 정보를 가져오지 못했습니다.")

    total = sum(len(jobs) for jobs in results.values())

    return render_template(
        "index.html",
        term=term,
        results=results,
        errors=errors,
        total=total,
    )


@freezer.register_generator
def search_urls():
    for term in SEARCH_TERMS:
        yield "search", {"term": term}


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "build":
        freezer.freeze()
    else:
        app.run(debug=True)
