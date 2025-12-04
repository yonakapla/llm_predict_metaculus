import os
import json
import pprint  # For nicer printing of the list

def scan_and_print_history(root_folder="forecasts"):
    """
    Scans JSON files for the specific path: aggregations -> unweighted -> history.
    If valid (history has items): Prints the history content.
    """
    stats = {
        "total_files": 0,
        "valid_unweighted_history": 0,
        "valid_with_news": 0,
        "missing_or_empty": []
    }

    print("\n" * 2 + f"--- Starting STRICT scan for 'unweighted' history in: {root_folder} ---")

    for subdir, dirs, files in os.walk(root_folder):
        for file in files:
            if file.endswith(".json"):
                stats["total_files"] += 1
                file_path = os.path.join(subdir, file)

                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)

                    # 1. Resolve 'aggregations' location
                    aggregations = None
                    if data.get("aggregations"):
                        aggregations = data["aggregations"]
                    elif data.get("question_details", {}).get("aggregations"):
                        aggregations = data["question_details"]["aggregations"]

                    # 2. Validate 'unweighted' -> 'history' structure
                    is_valid = False
                    history_content = []

                    if aggregations and isinstance(aggregations, dict):
                        # STRICT CHECK: Look ONLY for 'unweighted'
                        unweighted = aggregations.get("unweighted")

                        if unweighted and isinstance(unweighted, dict):
                            history = unweighted.get("history")

                            # Check if history is a list and has items
                            if isinstance(history, list) and len(history) > 0:
                                is_valid = True
                                history_content = history

                    # 3. Process results
                    if is_valid:
                        stats["valid_unweighted_history"] += 1

                        # --- PRINTING THE CONTENT AS REQUESTED ---
                        print(f"✅ Found valid history in: {file}")
                        print(f"   Path: {file_path}")
                        print(f"   History ({len(history_content)} items):")
                        pprint.pprint(history_content, indent=4, width=120)  # Pretty print the list
                        print("-" * 80)  # Separator
                        # -----------------------------------------

                        # Check for News (only for valid files)
                        news = data.get("news")
                        if news and isinstance(news, str) and news.strip():
                            stats["valid_with_news"] += 1

                    else:
                        stats["missing_or_empty"].append(file_path)

                except Exception as e:
                    print(f"[ERROR] Processing {file_path}: {e}")

    if len(stats['missing_or_empty']) > 0:
        print("\n❌ Files missing proper 'unweighted' history:")
        for p in stats['missing_or_empty']:
            print(f" - {p}")

    # Summary Report
    print("\n" + "=" * 50)
    print("📊 FINAL SUMMARY")
    print("=" * 50)
    print(f"Total JSON Files:                 {stats['total_files']}")
    print(f"Files with VALID unweighted history: {stats['valid_unweighted_history']}")
    print(f"Files with Valid History + News:     {stats['valid_with_news']}")
    print(f"Files Invalid (Missing/Empty):       {len(stats['missing_or_empty'])}")
    print("=" * 50)




if __name__ == "__main__":
    scan_and_print_history()