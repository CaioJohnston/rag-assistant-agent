from tools.web_search import SerpAPIETool

if __name__ == "__main__":
    tool = SerpAPIETool(k=3)
    results = tool.search_web("LangChain agents")

    print(f"Resultados: {len(results)}")
    for r in results:
        print(r["title"], "-="*4, r["link"], "-="*4, r["snippet"])