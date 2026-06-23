"""
University Info Scraper
=======================
Kunai pani university ko naam diye pachi official website bata
courses, fees, scholarships, ra entry criteria nikaalcha.

Requirements install garnu:
    pip install requests beautifulsoup4 anthropic googlesearch-python

Usage:
    python university_scraper.py
"""

import os
import json
import time
import requests
from bs4 import BeautifulSoup
import anthropic

# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "YOUR_API_KEY_HERE")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


# ─────────────────────────────────────────────
# STEP 1: Find official website via Google
# ─────────────────────────────────────────────
def find_official_website(university_name: str) -> str:
    """
    Google search garera university ko official website URL khojcha.
    """
    print(f"\n🔍 Searching official website for: {university_name}")
    try:
        from googlesearch import search
        query = f"{university_name} official university website"
        results = list(search(query, num_results=5, sleep_interval=1))
        
        # Filter likely official domains (avoid Wikipedia, ranking sites, etc.)
        skip_keywords = ["wikipedia", "ranking", "collegeboard", "topuniversities",
                         "usnews", "timeshighereducation", "niche", "reddit"]
        for url in results:
            if not any(kw in url.lower() for kw in skip_keywords):
                print(f"✅ Found: {url}")
                return url
        
        # Fallback: return first result
        if results:
            print(f"✅ Using: {results[0]}")
            return results[0]
    except ImportError:
        print("⚠️  googlesearch not installed. Using fallback search via Anthropic.")
    except Exception as e:
        print(f"⚠️  Google search error: {e}")
    
    return None


# ─────────────────────────────────────────────
# STEP 2: Scrape raw text from website pages
# ─────────────────────────────────────────────
def scrape_page(url: str, timeout: int = 10) -> str:
    """
    Ek webpage ko raw text content scrape garcha.
    """
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        
        # Remove script/style tags
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        
        text = soup.get_text(separator=" ", strip=True)
        # Limit to 8000 chars to stay within token limits
        return text[:8000]
    except Exception as e:
        return f"[ERROR scraping {url}: {e}]"


def scrape_university_pages(base_url: str) -> dict:
    """
    University ko main page + common subpages scrape garcha.
    """
    print(f"\n🌐 Scraping pages from: {base_url}")
    
    # Common paths to check
    subpaths = [
        "",                      # homepage
        "/admissions",
        "/academics",
        "/programs",
        "/courses",
        "/fees",
        "/tuition",
        "/scholarships",
        "/financial-aid",
        "/international",
    ]
    
    scraped = {}
    base = base_url.rstrip("/")
    
    for path in subpaths:
        url = base + path
        print(f"  → {url}")
        content = scrape_page(url)
        if not content.startswith("[ERROR"):
            scraped[url] = content
        time.sleep(0.5)  # polite delay
    
    return scraped


# ─────────────────────────────────────────────
# STEP 3: Extract structured info using Claude
# ─────────────────────────────────────────────
def extract_with_claude(university_name: str, scraped_data: dict) -> dict:
    """
    Scraped raw text lai Claude API pathayera structured JSON nikaalcha.
    """
    print(f"\n🤖 Extracting structured info using Claude AI...")
    
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    
    # Combine scraped content (limit total size)
    combined_text = ""
    for url, content in scraped_data.items():
        combined_text += f"\n\n--- PAGE: {url} ---\n{content[:2000]}"
        if len(combined_text) > 15000:
            break
    
    prompt = f"""
You are a university data extractor. Below is scraped text from the official website of "{university_name}".

Extract ALL of the following information and return ONLY a valid JSON object (no markdown, no explanation):

{{
  "university": "Official full name",
  "website": "official website URL",
  "location": "City, Country",
  "courses": [
    {{
      "name": "Program name",
      "level": "Undergraduate / Postgraduate / PhD / Diploma",
      "duration": "X years",
      "faculty": "Department or Faculty name"
    }}
  ],
  "fees": [
    {{
      "program": "Program name or 'All Programs'",
      "amount": "Exact amount",
      "currency": "NPR / USD / GBP / etc",
      "period": "per year / per semester / total",
      "notes": "Any additional fee notes"
    }}
  ],
  "scholarships": [
    {{
      "name": "Scholarship name",
      "amount": "Amount or percentage",
      "eligibility": "Who qualifies",
      "deadline": "Application deadline",
      "coverage": "What it covers (tuition, hostel, etc)"
    }}
  ],
  "entryCriteria": {{
    "academic": ["Minimum GPA requirement", "Percentage required", etc],
    "languageRequirements": {{
      "IELTS": "minimum band score",
      "TOEFL": "minimum score",
      "other": "other accepted tests"
    }},
    "entranceExam": "Name of entrance exam if required",
    "otherRequirements": ["portfolio", "interview", "recommendation letters", etc]
  }},
  "applicationDeadlines": ["Spring intake: Month Year", "Fall intake: Month Year"],
  "contactInfo": {{
    "email": "admissions email",
    "phone": "phone number",
    "admissionsPage": "direct URL to admissions page"
  }}
}}

SCRAPED WEBSITE CONTENT:
{combined_text}

Return ONLY the JSON. If any field is not found, use null or empty array [].
"""
    
    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}]
    )
    
    response_text = message.content[0].text.strip()
    
    # Clean up if Claude added markdown fences
    if response_text.startswith("```"):
        response_text = response_text.split("```")[1]
        if response_text.startswith("json"):
            response_text = response_text[4:]
    response_text = response_text.strip()
    
    return json.loads(response_text)


# ─────────────────────────────────────────────
# STEP 4: Display results nicely
# ─────────────────────────────────────────────
def print_results(data: dict):
    """
    Extracted data lai terminal ma sundar format ma print garcha.
    """
    sep = "─" * 60
    
    print(f"\n{'═'*60}")
    print(f"  🏫  {data.get('university', 'Unknown University')}")
    print(f"  📍  {data.get('location', 'N/A')}")
    print(f"  🌐  {data.get('website', 'N/A')}")
    print(f"{'═'*60}")
    
    # COURSES
    courses = data.get("courses", [])
    print(f"\n📚  COURSES ({len(courses)} found)")
    print(sep)
    if courses:
        for c in courses:
            print(f"  • {c.get('name')}  [{c.get('level')}]  –  {c.get('duration')}")
            if c.get("faculty"):
                print(f"      Faculty: {c.get('faculty')}")
    else:
        print("  No course data found.")
    
    # FEES
    fees = data.get("fees", [])
    print(f"\n💰  TUITION FEES ({len(fees)} entries)")
    print(sep)
    if fees:
        for f in fees:
            print(f"  • {f.get('program')}")
            print(f"      Amount : {f.get('amount')} {f.get('currency')}  ({f.get('period')})")
            if f.get("notes"):
                print(f"      Notes  : {f.get('notes')}")
    else:
        print("  No fee data found.")
    
    # SCHOLARSHIPS
    scholarships = data.get("scholarships", [])
    print(f"\n🎓  SCHOLARSHIPS ({len(scholarships)} found)")
    print(sep)
    if scholarships:
        for s in scholarships:
            print(f"  🏅 {s.get('name')}  →  {s.get('amount')}")
            print(f"      Eligibility : {s.get('eligibility')}")
            print(f"      Covers      : {s.get('coverage')}")
            print(f"      Deadline    : {s.get('deadline')}")
    else:
        print("  No scholarship data found.")
    
    # ENTRY CRITERIA
    ec = data.get("entryCriteria", {})
    print(f"\n📋  ENTRY REQUIREMENTS")
    print(sep)
    
    academic = ec.get("academic", [])
    if academic:
        print("  Academic:")
        for req in academic:
            print(f"    • {req}")
    
    lang = ec.get("languageRequirements", {})
    if any(lang.values()):
        print("  Language:")
        for test, score in lang.items():
            if score:
                print(f"    • {test.upper()}: {score}")
    
    if ec.get("entranceExam"):
        print(f"  Entrance Exam: {ec.get('entranceExam')}")
    
    other = ec.get("otherRequirements", [])
    if other:
        print("  Other:")
        for req in other:
            print(f"    • {req}")
    
    # DEADLINES
    deadlines = data.get("applicationDeadlines", [])
    if deadlines:
        print(f"\n📅  APPLICATION DEADLINES")
        print(sep)
        for d in deadlines:
            print(f"  • {d}")
    
    # CONTACT
    contact = data.get("contactInfo", {})
    if any(contact.values()):
        print(f"\n📞  CONTACT")
        print(sep)
        if contact.get("email"):
            print(f"  Email      : {contact['email']}")
        if contact.get("phone"):
            print(f"  Phone      : {contact['phone']}")
        if contact.get("admissionsPage"):
            print(f"  Admissions : {contact['admissionsPage']}")
    
    print(f"\n{'═'*60}\n")


# ─────────────────────────────────────────────
# STEP 5: Save to JSON file
# ─────────────────────────────────────────────
def save_to_json(data: dict, university_name: str):
    filename = university_name.lower().replace(" ", "_") + "_info.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"💾 Data saved to: {filename}")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    print("=" * 60)
    print("       🏫  UNIVERSITY INFO SCRAPER  🏫")
    print("=" * 60)
    
    if ANTHROPIC_API_KEY == "YOUR_API_KEY_HERE":
        print("\n⚠️  ERROR: Anthropic API key set garnu parcha!")
        print("   Option 1: Environment variable set garnu:")
        print("             export ANTHROPIC_API_KEY='sk-ant-...'")
        print("   Option 2: Script ko top ma ANTHROPIC_API_KEY variable ma directly rakhnu\n")
        return
    
    university_name = input("\nUniversity ko naam type garnu: ").strip()
    if not university_name:
        print("❌ University naam empty cha!")
        return
    
    # Step 1: Find website
    website_url = find_official_website(university_name)
    
    if not website_url:
        website_url = input("Website automatically phauna sakiyena. Manually URL dinu: ").strip()
        if not website_url.startswith("http"):
            website_url = "https://" + website_url
    
    # Step 2: Scrape pages
    scraped_data = scrape_university_pages(website_url)
    
    if not scraped_data:
        print("❌ Website scrape garna sakiyena. Site blocked cha hola.")
        return
    
    print(f"✅ {len(scraped_data)} pages scraped successfully!")
    
    # Step 3: Extract with Claude
    try:
        structured_data = extract_with_claude(university_name, scraped_data)
    except json.JSONDecodeError:
        print("❌ Claude le valid JSON return garena. API key check garnu.")
        return
    except Exception as e:
        print(f"❌ Claude API error: {e}")
        return
    
    # Step 4: Print results
    print_results(structured_data)
    
    # Step 5: Save to JSON
    save_json = input("JSON file ma save garnu? (y/n): ").strip().lower()
    if save_json == "y":
        save_to_json(structured_data, university_name)


if __name__ == "__main__":
    main()
