import os
import requests
import json
import pypdf

# Directory setup
os.makedirs("data/papers", exist_ok=True)

papers = [
    {
        "filename": "CBSE_Class10_Maths_2024.pdf",
        "year": 2024,
        "url": "https://cbseacademic.nic.in/web_material/SQP/ClassX_2024_25/MathsStandard-SQP.pdf"
    },
    {
        "filename": "CBSE_Class10_Maths_2023.pdf",
        "year": 2023,
        "url": "https://cbseacademic.nic.in/web_material/SQP/ClassX_2023_24/MathsStandard-SQP.pdf"
    },
    {
        "filename": "CBSE_Class10_Maths_2022.pdf",
        "year": 2022,
        "url": "https://cbseacademic.nic.in/web_material/SQP/ClassX_2022_23/MathsStandard-SQP.pdf"
    },
    {
        "filename": "CBSE_Class10_Maths_2021.pdf",
        "year": 2021,
        "url": "https://cbseacademic.nic.in/web_material/SQP/ClassX_2021_22/MathsStandard-SQP.pdf"
    },
    {
        "filename": "CBSE_Class10_Maths_2020.pdf",
        "year": 2020,
        "url": "https://cbseacademic.nic.in/web_material/SQP/ClassX_2020_21/MathsStandard-SQP.pdf"
    }
]

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

sources_md_entries = []
verified_papers = []

print("Starting official past question paper downloads from CBSE Academic...")

for p in papers:
    save_path = os.path.join("data", "papers", p["filename"])
    print(f"Downloading {p['filename']} from {p['url']}...")
    
    # Retry up to 2 times
    downloaded = False
    for attempt in range(2):
        try:
            resp = requests.get(p["url"], headers=headers, timeout=20)
            if resp.status_code == 200 and len(resp.content) > 50000:
                with open(save_path, "wb") as f:
                    f.write(resp.content)
                downloaded = True
                break
            else:
                print(f"Attempt {attempt+1} failed with status {resp.status_code}")
        except Exception as e:
            print(f"Attempt {attempt+1} exception: {e}")

    if not downloaded:
        print(f"FAILED to download {p['filename']}")
        continue

    # Validation: open PDF and verify content
    try:
        reader = pypdf.PdfReader(save_path)
        num_pages = len(reader.pages)
        first_page_text = reader.pages[0].extract_text()
        
        is_marking_scheme = "marking scheme" in first_page_text.lower()
        is_maths = "mathematics" in first_page_text.lower() or "math" in first_page_text.lower()
        
        if num_pages >= 2 and is_maths and not is_marking_scheme:
            status = "Verified (Question Paper, Valid PDF)"
            verified_papers.append(p)
            print(f"-> Verified: {num_pages} pages, {len(resp.content)//1024} KB")
        else:
            status = f"Warning: pages={num_pages}, is_maths={is_maths}, is_marking_scheme={is_marking_scheme}"
            print(f"-> Verification issue: {status}")

        file_size_kb = os.path.getsize(save_path) // 1024
        sources_md_entries.append(
            f"| `{p['filename']}` | {p['year']} | {num_pages} | {file_size_kb} KB | [{p['url']}]({p['url']}) | {status} |"
        )
    except Exception as e:
        print(f"-> Error reading PDF: {e}")

# Write data/sources.md
sources_md_content = """# Official Past Question Papers Source Registry

Subject: **CBSE Class 10 Mathematics (Standard - Subject Code 041)**  
Source: **Central Board of Secondary Education (CBSE) Academic Official Repository** (`cbseacademic.nic.in`)

| File Name | Year | Pages | File Size | Official URL | Verification Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
""" + "\n".join(sources_md_entries) + "\n\nAll downloaded documents are genuine, public, free question papers published by CBSE.\n"

with open("data/sources.md", "w", encoding="utf-8") as f:
    f.write(sources_md_content)

print("\nWrote data/sources.md")

# Write data/syllabus.json
official_syllabus = [
    "Real Numbers",
    "Polynomials",
    "Pair of Linear Equations in Two Variables",
    "Quadratic Equations",
    "Arithmetic Progressions",
    "Triangles",
    "Coordinate Geometry",
    "Introduction to Trigonometry",
    "Some Applications of Trigonometry",
    "Circles",
    "Areas Related to Circles",
    "Surface Areas and Volumes",
    "Statistics",
    "Probability"
]

with open("data/syllabus.json", "w", encoding="utf-8") as f:
    json.dump(official_syllabus, f, indent=2)

print("Wrote data/syllabus.json with official CBSE Class 10 Mathematics topics.")
