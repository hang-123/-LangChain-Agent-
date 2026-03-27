from langchain_core.tools import tool
from InsightEngine.utils.config import LOCAL_DOCS_DIR

# Simple debug toggle: set False to silence console logs
DEBUG = True


@tool
def search_local_docs_by_keyword(query: str) -> str:
    """
    Keyword-based search across local txt files.

    Used as a fallback when PG vector search is unavailable.
    """
    import glob
    import os

    pattern = str(LOCAL_DOCS_DIR / "*.txt")
    paths = glob.glob(pattern)

    if DEBUG:
        print(f"[DEBUG] search_local_docs called, query={query}")
        print(f"[DEBUG] Found {len(paths)} txt files in {LOCAL_DOCS_DIR}")

    if not paths:
        return "当前没有本地舆情文档，请先在 data/docs 下放一些 txt 文件。"

    results = []
    for path in paths:
        if DEBUG:
            print(f"[DEBUG] Reading {os.path.basename(path)}")

        try:
            with open(path, "r", encoding="utf-8") as f:
                text = f.read()
        except UnicodeDecodeError:
            with open(path, "r", encoding="gbk", errors="ignore") as f:
                text = f.read()

        if query in text:
            snippet = text[:200].replace("\n", " ")
            results.append(f"[{os.path.basename(path)}]\n{snippet}...")
            if DEBUG:
                print(f"[DEBUG] ✓ hit {os.path.basename(path)}")

    if not results:
        if DEBUG:
            print(f"[DEBUG] ✗ no documents contain keyword: {query}")
        return f"在本地文档中没有找到关于「{query}」的内容。"

    if DEBUG:
        print(f"[DEBUG] 命中 {len(results)} 个文档。")

    return "\n\n".join(results)
