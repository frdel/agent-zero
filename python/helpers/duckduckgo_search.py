from duckduckgo_search import DDGS

def search(query: str, results = 5, region = "wt-wt", time="y") -> list[str]:

    ddgs = DDGS()
    src = ddgs.text(
        query,
        region=region,  # Specify region 
        safesearch="off",  # SafeSearch setting
        timelimit=time,  # Time limit (y = past year)
        max_results=results  # Number of results to return
    )
    results = []
    for s in src:
        results.append(str(s))
    return results