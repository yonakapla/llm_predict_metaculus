import os
import json
import html

# --- הגדרות סף ---
THRESHOLD_HIGH = 0.8
THRESHOLD_MID = 0.65
THRESHOLD_LOW = 0.5


def get_nested_2(data, keys, default=None):
    """
    מבצעת חיפוש עומק (Deep Search) עבור רשימת מפתחות.
    עבור כל מפתח ברשימה, הפונקציה מחפשת אותו בכל תתי-העץ של האובייקט הנוכחי.
    """
    # תמיכה במקרה שהועבר מפתח יחיד כמחרוזת ולא כרשימה
    if isinstance(keys, str):
        keys = [keys]

    current_data = data

    for target_key in keys:
        found = False
        # שימוש ב-Queue לחיפוש לרוחב (BFS) כדי למצוא את המופע הקרוב ביותר
        queue = [current_data]

        while queue:
            current_node = queue.pop(0)

            if isinstance(current_node, dict):
                # אם המפתח נמצא ברמה הזו - מצאנו והולכים אליו
                if target_key in current_node:
                    current_data = current_node[target_key]
                    found = True
                    break

                # אם לא, מוסיפים את הילדים לתור לחיפוש המשך
                for value in current_node.values():
                    if isinstance(value, (dict, list)):
                        queue.append(value)

            elif isinstance(current_node, list):
                # אם זו רשימה, מוסיפים את האיברים שלה לחיפוש
                for item in current_node:
                    if isinstance(item, (dict, list)):
                        queue.append(item)

        # אם עברנו על כל העץ ולא מצאנו את המפתח הנוכחי בשרשרת
        if not found:
            return default

    return current_data

def get_nested(data, keys, default=None):
    current = data
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return default
    return current


def generate_ultimate_dashboard(root_folder="forecasts", output_filename="investigation_ultimate_dashboard.html"):
    print(f"--- Generating Ultimate Dashboard (Treemap + Card Modal) from '{root_folder}' ---")

    questions_data = []

    # 1. סריקה ועיבוד נתונים
    for subdir, dirs, files in os.walk(root_folder):
        for file in files:
            if file.endswith(".json"):
                file_path = os.path.join(subdir, file)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)

                    q_details = data.get("question_details", {})
                    q_id = q_details.get("post_id", data.get("post_id"))
                    title = q_details.get("title", data.get("question", "Unknown Title"))
                    url = f"https://www.metaculus.com/questions/{q_id}/" if q_id else "#"
                    reasoning = get_nested_2(data, ["results", "forecasters"]) or "No reasoning found."
                    description = get_nested_2(data, ["description"])

                    # רזולוציה
                    resolution_raw = q_details.get("resolution", data.get("resolution"))
                    resolution_val = None

                    if isinstance(resolution_raw, str):
                        clean = resolution_raw.strip().lower()
                        if clean == "yes":
                            resolution_val = 1.0
                        elif clean == "no":
                            resolution_val = 0.0
                        else:
                            try:
                                resolution_val = float(clean)
                            except ValueError:
                                continue
                    elif isinstance(resolution_raw, (int, float)):
                        resolution_val = float(resolution_raw)

                    if resolution_val is None: continue

                    # תחזית
                    prediction = get_nested(data, ["statistics", "final_result"])
                    if prediction is None:
                        prediction = get_nested(data, ["summary", "probability"])

                    if prediction is None: continue
                    if prediction > 1.0: prediction = prediction / 100.0

                    error = abs(prediction - resolution_val)

                    # --- נתונים נוספים עבור ה-Card (נלקח מהקוד השני) ---
                    # Community Prediction
                    aggregations = q_details.get("aggregations", data.get("aggregations", {}))
                    community_prediction = "N/A"
                    if aggregations and "recency_weighted" in aggregations:
                        try:
                            cp_history = aggregations["recency_weighted"]["history"]
                            if cp_history:
                                community_prediction = f"{cp_history[-1]['centers'][0]:.2%}"
                        except:
                            pass

                    # Tournament
                    tournament = "Unknown"
                    if "projects" in q_details:
                        tournament = str(q_details["projects"])

                    # --- סיווג קטגוריות ---
                    if error > THRESHOLD_LOW:
                        main_category = "error"
                        if error > THRESHOLD_HIGH:
                            sub_category = "high"
                        elif error > THRESHOLD_MID:
                            sub_category = "mid"
                        else:
                            sub_category = "low"
                    else:
                        main_category = "safe"
                        sub_category = "safe"

                    questions_data.append({
                        "id": len(questions_data),
                        "title": title,
                        "url": url,
                        "file": file,
                        "pred": prediction,
                        "res": resolution_val,
                        "res_text": str(resolution_raw),
                        "cp": community_prediction,
                        "tournament": tournament,
                        "error": error,
                        "main_cat": main_category,
                        "sub_cat": sub_category,
                        "reasoning": reasoning,
                        "news": data.get("news", "No news available."),
                        "description": description
                    })

                except Exception as e:
                    print(f"Error reading {file}: {e}")

    # מיון
    questions_data.sort(key=lambda x: x["error"], reverse=True)

    # 2. HTML Template
    html_template = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Metaculus Ultimate Dashboard</title>
            <link rel="icon" href="wisdom_in_silico_favicon.png" type="image/png">
            <style>
                :root {{
                    --bg-main: #121212;
                    --bg-card: #1e1e1e;
                    --text-main: #e0e0e0;
                    --text-muted: #a0a0a0;
                    --col-red: #d32f2f;
                    --col-orange: #f57c00;
                    --col-green: #388e3c;
                    --col-border: #444;
                }}
                body {{ font-family: 'Segoe UI', Tahoma, sans-serif; background-color: var(--bg-main); color: var(--text-main); margin: 0; display: flex; flex-direction: column; height: 100vh; overflow: hidden; }}

                /* HEADER & FILTERS */
                header {{ background-color: #212121; padding: 10px 20px; border-bottom: 1px solid #333; display: flex; flex-direction: column; gap: 10px; box-shadow: 0 2px 5px rgba(0,0,0,0.5); z-index: 10; }}
                .header-top {{ display: flex; justify-content: space-between; align-items: center; width: 100%; }}
                h1 {{ margin: 0; font-size: 1.2rem; font-weight: 400; letter-spacing: 1px; }}

                .controls-container {{ display: flex; flex-direction: column; align-items: flex-end; gap: 8px; }}
                .controls {{ display: flex; gap: 10px; }}
                .sub-controls {{ display: none; gap: 8px; background: rgba(255,255,255,0.05); padding: 4px 10px; border-radius: 4px; animation: fadeIn 0.3s ease; }}
                @keyframes fadeIn {{ from {{ opacity: 0; transform: translateY(-5px); }} to {{ opacity: 1; transform: translateY(0); }} }}

                .btn {{ background: #333; color: white; border: 1px solid #444; padding: 6px 12px; border-radius: 4px; cursor: pointer; font-size: 0.9rem; transition: all 0.2s; }}
                .btn:hover {{ background: #444; }}
                .btn.active {{ background: #eee; color: #111; font-weight: bold; border-color: #fff; }}
                .btn-error.active {{ background: var(--col-red); color: white; border-color: var(--col-red); }}
                .btn-safe.active {{ background: var(--col-green); color: white; border-color: var(--col-green); }}
                .btn-sub {{ font-size: 0.85rem; padding: 4px 10px; }}
                .btn-sub.active {{ box-shadow: 0 0 5px rgba(255,255,255,0.5); }}

                /* GRID LAYOUT */
                #grid-container {{ flex-grow: 1; overflow-y: auto; padding: 20px; display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); grid-auto-rows: 100px; gap: 4px; }}
                .cube {{ background-color: #333; border: 1px solid #000; border-radius: 2px; padding: 8px; cursor: pointer; display: flex; flex-direction: column; justify-content: center; align-items: center; text-align: center; transition: transform 0.1s, filter 0.1s; position: relative; overflow: hidden; }}
                .cube:hover {{ transform: scale(1.05); z-index: 5; box-shadow: 0 5px 15px rgba(0,0,0,0.5); filter: brightness(1.2); border-color: #fff; }}
                .cube-err {{ font-size: 1.4rem; font-weight: bold; text-shadow: 0 1px 3px rgba(0,0,0,0.8); }}
                .cube-title {{ font-size: 0.7rem; color: rgba(255,255,255,0.8); margin-top: 5px; line-height: 1.2; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }}

                /* MODAL STYLES */
                .modal {{ display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.85); z-index: 100; backdrop-filter: blur(3px); }}
                .modal-content {{ 
                    background: #1e1e1e; margin: 2.5vh auto; width: 75%; max-width: none; height: 95vh; 
                    border-radius: 8px; border: 1px solid #444; display: flex; flex-direction: column; 
                    box-shadow: 0 10px 30px rgba(0,0,0,0.5);
                }}

                /* UPDATED: Card Header (Right Aligned Title) */
                .card-header {{ 
                    padding: 15px 20px; 
                    background: #252525; 
                    border-bottom: 1px solid var(--col-border); 
                    display: flex; 
                    flex-direction: row; /* כותרת מימין, כפתורים משמאל */
                    justify-content: space-between; 
                    align-items: center; 
                }}

                /* UPDATED: Title Styling (Full Text, RTL) */
                .card-header h2 {{ 
                    margin: 0; 
                    font-size: 1.1em; 
                    color: var(--text-main); 
                    width: 60%;             /* רוחב נדיב יותר */
                    text-align: left;      /* יישור לימין */
                    direction: ltr;         /* כיוון טקסט עברי */
                    white-space: normal;    /* שבירת שורות מותרת */
                    overflow: visible;      /* ביטול הסתרה */
                    line-height: 1.3;
                }}

                .card-header-controls {{
                    display: flex;
                    align-items: center;
                    gap: 15px;
                }}

                .card-header a {{ text-decoration: none; color: #64b5f6; font-weight: bold; font-size: 0.9em; }}
                .close-btn {{ font-size: 24px; cursor: pointer; color: #aaa; margin-left: 10px; }}
                .close-btn:hover {{ color: #fff; }}

                /* PAGER STYLES */
                .nav-controls {{ display: flex; align-items: center; gap: 10px; }}
                .nav-btn {{ background: none; border: 1px solid #555; color: #ccc; cursor: pointer; padding: 4px 10px; border-radius: 4px; font-size: 1.1rem; transition: 0.2s; user-select: none; }}
                .nav-btn:hover {{ background: #333; color: white; border-color: #888; }}
                .nav-counter {{ font-size: 0.85em; color: #888; min-width: 50px; text-align: center; }}

                /* Stats Row */
                .stats-row {{ display: flex; justify-content: space-around; padding: 15px; background: #222; border-bottom: 1px solid var(--col-border); }}
                .stat-box {{ text-align: center; flex: 1; border-right: 1px solid #333; }}
                .stat-box:last-child {{ border-right: none; }}
                .stat-value {{ font-size: 1.4em; font-weight: bold; display: block; color: var(--text-main); }}
                .stat-label {{ font-size: 0.85em; color: var(--text-muted); text-transform: uppercase; letter-spacing: 1px; }}

                /* Body Layout */
                .modal-flex-body {{ flex: 1; display: flex; overflow: hidden; border-bottom: 1px solid var(--col-border); }}
                .split-column {{ flex: 1; display: flex; flex-direction: column; padding: 15px; border-right: 1px solid var(--col-border); min-width: 0; }}
                .split-column:last-child {{ border-right: none; }}
                .section-title {{ font-size: 1em; color: var(--text-muted); border-bottom: 2px solid var(--col-border); padding-bottom: 5px; margin-bottom: 10px; margin-top: 0; }}
                .expand-scroll-box {{ flex: 1; overflow-y: auto; background: #181818; border: 1px solid #333; padding: 10px; font-size: 0.95em; line-height: 1.6; white-space: pre-wrap; color: #ccc; border-radius: 4px; }}

                /* Bottom Pane */
                .modal-bottom-pane {{ height: 25%; min-height: 150px; padding: 15px 20px; background: #222; display: flex; flex-direction: column; }}
                .footer-text {{ font-size: 0.8em; color: #666; text-align: right; margin-top: 5px; }}

            </style>
        </head>
        <body>

            <header>
                <div class="header-top">
                    <h1>Ultimate Dashboard</h1>
                    <div class="controls-container">
                        <div class="controls" id="main-controls">
                            <button class="btn active" onclick="setMainFilter('all', this)">All</button>
                            <button class="btn btn-error" onclick="setMainFilter('error', this)">Errors (>0.5)</button>
                            <button class="btn btn-safe" onclick="setMainFilter('safe', this)">Safe</button>
                        </div>
                        <div class="controls sub-controls" id="sub-controls">
                            <span style="font-size: 0.8rem; color: #aaa; align-self: center;">Filter Errors:</span>
                            <button class="btn btn-sub active" onclick="setSubFilter('all', this)">All Errors</button>
                            <button class="btn btn-sub" onclick="setSubFilter('high', this)">High (>0.8)</button>
                            <button class="btn btn-sub" onclick="setSubFilter('mid', this)">Mid</button>
                            <button class="btn btn-sub" onclick="setSubFilter('low', this)">Low</button>
                        </div>
                    </div>
                </div>
            </header>

            <div id="grid-container"></div>

            <div id="modal" class="modal" onclick="if(event.target === this) closeModal()">
                <div class="modal-content">

                    <div class="card-header">
                        <h2 id="mTitle">Title</h2>

                        <div class="card-header-controls">
                            <div class="nav-controls">
                                <button class="nav-btn" onclick="navigate(-1)" title="Previous">&#10094;</button>
                                <span class="nav-counter" id="mCounter"></span>
                                <button class="nav-btn" onclick="navigate(1)" title="Next">&#10095;</button>
                            </div>
                            <div style="border-left: 1px solid #555; height: 20px; margin: 0 10px;"></div>
                            <a id="mLink" href="#" target="_blank">Open Link ↗</a>
                            <span class="close-btn" onclick="closeModal()">&times;</span>
                        </div>
                    </div>

                    <div class="stats-row">
                        <div class="stat-box">
                            <span class="stat-value" id="mError"></span>
                            <span class="stat-label">Abs Error</span>
                        </div>
                        <div class="stat-box">
                            <span class="stat-value" id="mPred"></span>
                            <span class="stat-label">Our Prediction</span>
                        </div>
                        <div class="stat-box">
                            <span class="stat-value" id="mCp"></span>
                            <span class="stat-label">Community</span>
                        </div>
                        <div class="stat-box">
                            <span class="stat-value" id="mRes"></span>
                            <span class="stat-label">Result</span>
                        </div>
                    </div>

                    <div class="modal-flex-body">
                        <div class="split-column">
                            <h3 class="section-title">📰 News Found</h3>
                            <div class="expand-scroll-box" id="mNews"></div>
                        </div>
                        <div class="split-column">
                            <h3 class="section-title">🧠 Model Reasoning</h3>
                            <div class="expand-scroll-box" id="mReasoning"></div>
                        </div>
                    </div>

                    <div class="modal-bottom-pane">
                        <h3 class="section-title">ℹ️ Description</h3>
                        <div class="expand-scroll-box" id="mDesc" style="border: 1px solid #444;"></div>
                        <div class="footer-text" id="mFooter"></div>
                    </div>

                </div>
            </div>

            <script>
                const rawData = {json.dumps(questions_data)};
                let currentMainFilter = 'all';
                let currentSubFilter = 'all';

                // For Pagination
                let filteredQuestions = []; 
                let currentIndex = -1;

                function getColor(error) {{
                    if (error <= 0.2) return `rgba(56, 142, 60, ${{0.5 + error*2}})`; 
                    if (error <= 0.5) return `rgba(245, 124, 0, ${{0.4 + error}})`;   
                    return `rgba(211, 47, 47, ${{0.3 + error}})`;                     
                }}

                const grid = document.getElementById('grid-container');

                function render() {{
                    grid.innerHTML = '';
                    filteredQuestions = []; // Reset filtered list

                    rawData.forEach(q => {{
                        let visible = false;
                        if (currentMainFilter === 'all') {{
                            visible = true;
                        }} else if (currentMainFilter === 'safe') {{
                            if (q.main_cat === 'safe') visible = true;
                        }} else if (currentMainFilter === 'error') {{
                            if (q.main_cat === 'error') {{
                                if (currentSubFilter === 'all') visible = true;
                                else if (q.sub_cat === currentSubFilter) visible = true;
                            }}
                        }}

                        if (!visible) return;

                        // Add to pagination list
                        filteredQuestions.push(q);

                        const div = document.createElement('div');
                        div.className = 'cube';
                        div.style.backgroundColor = getColor(q.error);
                        div.title = q.title + " (Error: " + q.error.toFixed(2) + ")";
                        div.onclick = () => openModal(q);
                        div.innerHTML = `<span class="cube-err">${{q.error.toFixed(2)}}</span><span class="cube-title">${{q.title}}</span>`;
                        grid.appendChild(div);
                    }});
                }}

                function setMainFilter(type, btn) {{
                    currentMainFilter = type;
                    document.querySelectorAll('#main-controls .btn').forEach(b => b.classList.remove('active'));
                    btn.classList.add('active');
                    const subControls = document.getElementById('sub-controls');
                    if (type === 'error') {{
                        subControls.style.display = 'flex';
                        setSubFilter('all', subControls.querySelector('.btn-sub')); 
                    }} else {{
                        subControls.style.display = 'none';
                        currentSubFilter = 'all';
                    }}
                    render();
                }}

                function setSubFilter(type, btn) {{
                    currentSubFilter = type;
                    document.querySelectorAll('#sub-controls .btn').forEach(b => b.classList.remove('active'));
                    if(btn) btn.classList.add('active');
                    render();
                }}

                // --- NAVIGATION LOGIC ---
                function navigate(direction) {{
                    if (filteredQuestions.length === 0) return;

                    currentIndex += direction;

                    // Wrap around
                    if (currentIndex < 0) currentIndex = filteredQuestions.length - 1;
                    if (currentIndex >= filteredQuestions.length) currentIndex = 0;

                    openModal(filteredQuestions[currentIndex], true); 
                }}

                // Keyboard support
                document.addEventListener('keydown', function(e) {{
                    if (document.getElementById('modal').style.display === 'block') {{
                        if (e.key === 'ArrowLeft') navigate(-1);
                        if (e.key === 'ArrowRight') navigate(1);
                        if (e.key === 'Escape') closeModal();
                    }}
                }});

                const modal = document.getElementById('modal');

                function openModal(q, isNavigation = false) {{
                
                    console.log(q);
                    // Determine Index
                    if (!isNavigation) {{
                        currentIndex = filteredQuestions.findIndex(item => item.id === q.id);
                    }}

                    // Update Counter
                    if (currentIndex !== -1) {{
                        document.getElementById('mCounter').innerText = `${{currentIndex + 1}} / ${{filteredQuestions.length}}`;
                    }}

                    // Populate Header
                    document.getElementById('mTitle').innerText = q.title;
                    document.getElementById('mLink').href = q.url;

                    // Populate Stats
                    const errEl = document.getElementById('mError');
                    errEl.innerText = q.error.toFixed(3);
                    errEl.style.color = q.error > 0.5 ? '#e74c3c' : '#2ecc71';

                    document.getElementById('mPred').innerText = (q.pred * 100).toFixed(1) + "%";
                    document.getElementById('mRes').innerText = q.res + (q.res_text !== String(q.res) ? ` (${{q.res_text}})` : '');
                    document.getElementById('mCp').innerText = q.cp;

                    // Populate Content
                    document.getElementById('mNews').innerText = q.news;
                    document.getElementById('mReasoning').innerText = q.reasoning;
                    document.getElementById('mDesc').innerText = q.description;
                    document.getElementById('mFooter').innerText = `File: ${{q.file}} | Tournament: ${{q.tournament}}`;

                    modal.style.display = 'block';
                }}

                function closeModal() {{
                    modal.style.display = 'none';
                }}

                render();
            </script>
        </body>
        </html>
        """
    with open(output_filename, "w", encoding="utf-8") as f:
        f.write(html_template)

    print(f"\n✅ Ultimate Dashboard Generated: {output_filename}")

if __name__ == "__main__":
    generate_ultimate_dashboard()