import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.config import JOB_FEED_URLS
from app.jobs.parser import parse_source
from app.services.generic_board_discovery import discover_generic_sources


MAX_SOURCE_WORKERS = 4


def fetch_feed_jobs():
    jobs = []

    generic_sources = discover_generic_sources()
    generic_urls = [source.url for source in generic_sources]

    # Merge configured ATS feeds with discovered generic-board URLs.
    sources = list(dict.fromkeys(list(JOB_FEED_URLS) + generic_urls))

    if not sources:
        print("[DISCOVERY] No job feed sources configured")
        return jobs

    with ThreadPoolExecutor(max_workers=min(MAX_SOURCE_WORKERS, max(1, len(sources)))) as executor:
        future_to_url = {
            executor.submit(_fetch_one_source, source_url): source_url
            for source_url in sources
        }

        for future in as_completed(future_to_url):
            source_url = future_to_url[future]
            try:
                source_jobs, elapsed = future.result()
                print(f"[DISCOVERY] {source_url} -> {len(source_jobs)} jobs in {elapsed:.2f}s")
                jobs.extend(source_jobs)
            except Exception as e:
                print(f"[DISCOVERY] Failed to parse source {source_url!r}: {e}")

    print(f"[DISCOVERY] Total jobs fetched: {len(jobs)}")
    return jobs



def _fetch_one_source(source_url):
    start = time.perf_counter()
    source_jobs = parse_source(source_url)
    elapsed = time.perf_counter() - start
    return source_jobs, elapsed