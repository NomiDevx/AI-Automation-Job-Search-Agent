"""
=================================================================
  AI Automation Job Search Agent
  Opens Chrome -> Searches Latest AI Automation Jobs
  -> Saves results to separate CSV files per source
=================================================================

Sources:
  1. LinkedIn Jobs   (public, no login)
  2. Indeed Jobs
  3. Google Jobs Widget
 
Output folder: job_results/
  jobs_linkedin.csv
  jobs_indeed.csv
  jobs_google.csv
  jobs_all_combined_<timestamp>.csv
"""

import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import csv
import os
import random
import time
import re
from datetime import datetime
from dataclasses import dataclass, fields, asdict

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    StaleElementReferenceException,
    WebDriverException,
)

# ─── Config ───────────────────────────────────────────────────────────────────
SEARCH_QUERY    = "AI Automation"   # job search query
OUTPUT_DIR      = os.path.join(os.path.dirname(os.path.abspath(__file__)), "job_results")
MAX_JOBS        = 25          # per source
PAGE_TIMEOUT    = 20
HEADLESS        = False       # set True to hide Chrome window

# ─── Data Model ───────────────────────────────────────────────────────────────
@dataclass
class Job:
    title:       str = ""
    company:     str = ""
    location:    str = ""
    date_posted: str = ""
    job_type:    str = ""
    salary:      str = ""
    description: str = ""
    url:         str = ""
    source:      str = ""
    scraped_at:  str = ""

# ─── Utilities ────────────────────────────────────────────────────────────────
def log(msg: str, tag: str = "INFO") -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] [{tag}] {msg}", flush=True)

def sleep(a=1.0, b=3.0): time.sleep(random.uniform(a, b))

def first_text(driver_or_el, *selectors, default="N/A") -> str:
    for sel in selectors:
        try:
            el = driver_or_el.find_element(By.CSS_SELECTOR, sel)
            t = el.text.strip()
            if t:
                return t
        except Exception:
            pass
    return default

def first_attr(driver_or_el, attr, *selectors, default="N/A") -> str:
    for sel in selectors:
        try:
            el = driver_or_el.find_element(By.CSS_SELECTOR, sel)
            v = el.get_attribute(attr)
            if v:
                return v.strip()
        except Exception:
            pass
    return default

def save_csv(jobs: list, filename: str) -> str:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    path = os.path.join(OUTPUT_DIR, filename)
    cols = [f.name for f in fields(Job)]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for j in jobs:
            w.writerow(asdict(j))
    return path

def scroll_down(driver, times=3, pause=1.2):
    for _ in range(times):
        driver.execute_script("window.scrollBy(0, 800);")
        time.sleep(pause)

# ─── Driver Setup ─────────────────────────────────────────────────────────────
def make_driver() -> webdriver.Chrome:
    opts = Options()
    if HEADLESS:
        opts.add_argument("--headless=new")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1440,900")
    opts.add_argument("--disable-infobars")
    opts.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)

    driver = webdriver.Chrome(options=opts)
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
    })
    driver.set_page_load_timeout(PAGE_TIMEOUT)
    return driver

# ─────────────────────────────────────────────────────────────────────────────
#  SOURCE 1: LinkedIn Jobs (public search, no login)
# ─────────────────────────────────────────────────────────────────────────────
def scrape_linkedin(driver) -> list:
    jobs = []
    log("Opening LinkedIn Jobs …", "LI")

    # LinkedIn public job search URL with sorting by date, last 7 days
    q = SEARCH_QUERY.replace(" ", "%20")
    url = (
        f"https://www.linkedin.com/jobs/search/"
        f"?keywords={q}&location=Worldwide&f_TPR=r604800&sortBy=DD&position=1&pageNum=0"
    )
    try:
        driver.get(url)
    except TimeoutException:
        pass
    sleep(3, 5)

    # Dismiss any modal / sign-in popup
    for _ in range(3):
        try:
            driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
            sleep(0.5, 1)
        except Exception:
            break

    wait = WebDriverWait(driver, 12)
    collected = 0
    scroll_round = 0

    while collected < MAX_JOBS and scroll_round < 10:
        # Possible card selectors (LinkedIn changes them frequently)
        CARD_SELS = [
            "div.job-search-card",
            "li.jobs-search-results__list-item",
            "div.base-card",
            "[data-entity-urn]",
            ".job-card-container",
        ]
        cards = []
        for sel in CARD_SELS:
            cards = driver.find_elements(By.CSS_SELECTOR, sel)
            if cards:
                break

        log(f"  Found {len(cards)} cards (collected {collected})", "LI")

        for card in cards:
            if collected >= MAX_JOBS:
                break
            try:
                driver.execute_script("arguments[0].scrollIntoView({block:'center'});", card)
                sleep(0.4, 0.8)

                title = first_text(card,
                    "h3.base-search-card__title",
                    "h3.job-search-card__title",
                    "span.sr-only",
                    "h3",
                )
                company = first_text(card,
                    "h4.base-search-card__subtitle",
                    "h4.job-search-card__company-name",
                    "a.job-search-card__company-name",
                    "h4",
                )
                location = first_text(card,
                    "span.job-search-card__location",
                    "[class*='location']",
                )
                # posted date from <time> tag
                try:
                    t_el = card.find_element(By.TAG_NAME, "time")
                    date_posted = t_el.get_attribute("datetime") or t_el.text.strip()
                except Exception:
                    date_posted = "N/A"

                # job URL
                job_url = first_attr(card, "href",
                    "a.base-card__full-link",
                    "a[href*='/jobs/view/']",
                    "a",
                )

                if title == "N/A":
                    continue

                job = Job(
                    title       = title,
                    company     = company,
                    location    = location,
                    date_posted = date_posted,
                    url         = job_url,
                    source      = "LinkedIn",
                    scraped_at  = datetime.now().isoformat(),
                )
                jobs.append(job)
                collected += 1
                log(f"  [{collected}] {title} @ {company}", "LI")

            except StaleElementReferenceException:
                pass
            except Exception as e:
                log(f"  Card error: {str(e)[:80]}", "WARN")

        # Scroll to load more cards
        scroll_down(driver, times=2, pause=1.2)
        sleep(1.5, 2.5)
        scroll_round += 1

    log(f"LinkedIn: {len(jobs)} jobs collected.", "LI")
    return jobs


# ─────────────────────────────────────────────────────────────────────────────
#  SOURCE 2: Indeed Jobs
# ─────────────────────────────────────────────────────────────────────────────
def scrape_indeed(driver) -> list:
    jobs = []
    log("Opening Indeed Jobs …", "IN")

    q = SEARCH_QUERY.replace(" ", "+")
    url = f"https://www.indeed.com/jobs?q={q}&sort=date&fromage=14&start=0"
    try:
        driver.get(url)
    except TimeoutException:
        pass
    sleep(3, 5)

    wait  = WebDriverWait(driver, 12)
    page  = 0
    collected = 0

    while collected < MAX_JOBS and page < 4:
        log(f"  Indeed page {page+1} …", "IN")
        sleep(2, 3)
        scroll_down(driver, times=3, pause=0.8)

        CARD_SELS = [
            ".job_seen_beacon",
            "div.cardOutline",
            "div[class*='jobCard']",
            "li[class*='job']",
        ]
        cards = []
        for sel in CARD_SELS:
            cards = driver.find_elements(By.CSS_SELECTOR, sel)
            if cards:
                break

        log(f"  Found {len(cards)} cards on page {page+1}", "IN")

        for card in cards:
            if collected >= MAX_JOBS:
                break
            try:
                driver.execute_script("arguments[0].scrollIntoView({block:'center'});", card)
                sleep(0.3, 0.7)

                title = first_text(card,
                    "h2.jobTitle span[title]",
                    "h2.jobTitle span",
                    "h2.jobTitle",
                    "[data-testid='jobTitle']",
                )
                company = first_text(card,
                    "[data-testid='company-name']",
                    "span.companyName",
                    ".companyName",
                )
                location = first_text(card,
                    "[data-testid='text-location']",
                    ".companyLocation",
                    "div[class*='location']",
                )
                salary = first_text(card,
                    ".salary-snippet-container",
                    "[data-testid='attribute_snippet_testid']",
                    default="",
                )
                date_posted = first_text(card,
                    "span.date",
                    "[data-testid='myJobsStateDate']",
                    default="N/A",
                )
                # URL
                job_url = first_attr(card, "href",
                    "h2.jobTitle a",
                    "a[id^='job_']",
                    "a[href*='/rc/clk']",
                    "a",
                )
                if job_url and not job_url.startswith("http"):
                    job_url = "https://www.indeed.com" + job_url

                if title == "N/A":
                    continue

                job = Job(
                    title       = title,
                    company     = company,
                    location    = location,
                    date_posted = date_posted,
                    salary      = salary,
                    url         = job_url,
                    source      = "Indeed",
                    scraped_at  = datetime.now().isoformat(),
                )
                jobs.append(job)
                collected += 1
                log(f"  [{collected}] {title} @ {company}", "IN")

            except StaleElementReferenceException:
                pass
            except Exception as e:
                log(f"  Card error: {str(e)[:80]}", "WARN")

        # Next page
        try:
            next_btn = driver.find_element(
                By.CSS_SELECTOR,
                'a[data-testid="pagination-page-next"], a[aria-label="Next Page"]',
            )
            driver.execute_script("arguments[0].click();", next_btn)
            sleep(3, 5)
            page += 1
        except NoSuchElementException:
            log("  No more pages on Indeed.", "IN")
            break

    log(f"Indeed: {len(jobs)} jobs collected.", "IN")
    return jobs


# ─────────────────────────────────────────────────────────────────────────────
#  SOURCE 3: Google Jobs (htl search widget)
# ─────────────────────────────────────────────────────────────────────────────
def scrape_google_jobs(driver) -> list:
    jobs = []
    log("Opening Google Jobs …", "GJ")

    q = SEARCH_QUERY.replace(" ", "+")
    url = f"https://www.google.com/search?q={q}+jobs&ibp=htl;jobs&hl=en"
    try:
        driver.get(url)
    except TimeoutException:
        pass
    sleep(3, 5)

    # Accept consent if shown
    for btn_text in ["Accept all", "I agree", "Accept"]:
        try:
            btn = driver.find_element(
                By.XPATH, f"//button[contains(normalize-space(),'{btn_text}')]"
            )
            btn.click()
            sleep(1, 2)
            break
        except NoSuchElementException:
            pass

    wait = WebDriverWait(driver, 12)
    collected = 0
    scroll_round = 0

    CARD_SELS_GOOGLE = [
        "li.iFjolb",
        "li.PwjeAc",
        "div.EimVGf",
        "[jsname='n6D0wb'] li",
        "ul.EIkAsc li",
    ]

    PANEL_TITLE   = ["h2.KLsYvd", ".tJ9zfc", "[class*='job-title']", "h2"]
    PANEL_COMPANY = [".nJlQNd", ".vNEEBe", "[class*='company']"]
    PANEL_LOC     = [".Qk80Jf", ".rSa5xb", "[class*='location']"]
    PANEL_DATE    = [".SuWscb", ".LL4CDc", "[class*='date']"]
    PANEL_SALARY  = [".I2Cbhb", "[class*='salary']"]
    PANEL_DESC    = [".HBvzbc", ".oqSTJd", "[class*='description']"]

    while collected < MAX_JOBS and scroll_round < 8:
        cards = []
        for sel in CARD_SELS_GOOGLE:
            cards = driver.find_elements(By.CSS_SELECTOR, sel)
            if cards:
                break

        log(f"  Found {len(cards)} Google job cards", "GJ")

        for card in cards[collected:]:
            if collected >= MAX_JOBS:
                break
            try:
                driver.execute_script("arguments[0].scrollIntoView({block:'center'});", card)
                sleep(0.4, 0.8)
                card.click()
                sleep(1.5, 2.5)

                title    = first_text(driver, *PANEL_TITLE)
                company  = first_text(driver, *PANEL_COMPANY)
                location = first_text(driver, *PANEL_LOC)
                date_p   = first_text(driver, *PANEL_DATE)
                salary   = first_text(driver, *PANEL_SALARY, default="")
                desc     = first_text(driver, *PANEL_DESC, default="")[:400]

                if title == "N/A":
                    continue

                job = Job(
                    title       = title,
                    company     = company,
                    location    = location,
                    date_posted = date_p,
                    salary      = salary,
                    description = desc,
                    url         = driver.current_url,
                    source      = "Google Jobs",
                    scraped_at  = datetime.now().isoformat(),
                )
                jobs.append(job)
                collected += 1
                log(f"  [{collected}] {title} @ {company}", "GJ")

            except StaleElementReferenceException:
                pass
            except Exception as e:
                log(f"  Card error: {str(e)[:80]}", "WARN")

        # Scroll the left job list panel
        try:
            panel = driver.find_element(By.CSS_SELECTOR,
                "div.nBDE1b, div.MZqk1, div[jsname='Tpe7nc']")
            driver.execute_script("arguments[0].scrollTop += 800;", panel)
        except Exception:
            scroll_down(driver, times=1, pause=0.8)

        sleep(1.5, 2.5)
        scroll_round += 1

        if len(cards) == collected:   # no new cards after scrolling → stop
            break

    log(f"Google Jobs: {len(jobs)} jobs collected.", "GJ")
    return jobs


# ─────────────────────────────────────────────────────────────────────────────
#  Main
# ─────────────────────────────────────────────────────────────────────────────
def main():
    print()
    print("=" * 62)
    print("  AI Automation Job Search Agent")
    print(f"  Query  : {SEARCH_QUERY}")
    print(f"  Output : {OUTPUT_DIR}")
    print("=" * 62)
    print()

    driver = make_driver()

    google_jobs: list   = []
    linkedin_jobs: list = []
    indeed_jobs: list   = []
    all_jobs: list      = []

    try:
        # ── LinkedIn ───────────────────────────────────────────
        print("\n" + "-" * 62)
        print("  SOURCE 1/3  ->  LinkedIn Jobs")
        print("-" * 62)
        linkedin_jobs = scrape_linkedin(driver)
        all_jobs.extend(linkedin_jobs)
        if linkedin_jobs:
            p = save_csv(linkedin_jobs, "jobs_linkedin.csv")
            log(f"Saved {len(linkedin_jobs)} jobs -> {p}", "SAVE")
        sleep(2, 4)

        # ── Indeed ─────────────────────────────────────────────
        print("\n" + "-" * 62)
        print("  SOURCE 2/3  ->  Indeed Jobs")
        print("-" * 62)
        indeed_jobs = scrape_indeed(driver)
        all_jobs.extend(indeed_jobs)
        if indeed_jobs:
            p = save_csv(indeed_jobs, "jobs_indeed.csv")
            log(f"Saved {len(indeed_jobs)} jobs -> {p}", "SAVE")
        sleep(2, 4)

        # ── Google Jobs ────────────────────────────────────────
        print("\n" + "-" * 62)
        print("  SOURCE 3/3  ->  Google Jobs")
        print("-" * 62)
        google_jobs = scrape_google_jobs(driver)
        all_jobs.extend(google_jobs)
        if google_jobs:
            p = save_csv(google_jobs, "jobs_google.csv")
            log(f"Saved {len(google_jobs)} jobs -> {p}", "SAVE")

    finally:
        driver.quit()
        log("Browser closed.", "DONE")

    # ── Combined ───────────────────────────────────────────────
    if all_jobs:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        p  = save_csv(all_jobs, f"jobs_all_combined_{ts}.csv")
        log(f"Combined CSV ({len(all_jobs)} jobs) -> {p}", "SAVE")

    # ── Summary ────────────────────────────────────────────────
    print()
    print("=" * 62)
    print("  SUMMARY")
    print("=" * 62)
    print(f"  LinkedIn     : {len(linkedin_jobs)} jobs")
    print(f"  Indeed       : {len(indeed_jobs)} jobs")
    print(f"  Google Jobs  : {len(google_jobs)} jobs")
    print(f"  TOTAL        : {len(all_jobs)} jobs")
    print(f"  Output dir   : {OUTPUT_DIR}")
    print("=" * 62)
    print()


if __name__ == "__main__":
    main()
