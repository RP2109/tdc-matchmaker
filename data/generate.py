"""Generate mocked clients, candidate profiles and 30 days of share history. Run: python data/generate.py"""

import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from matching import check  # noqa: E402

random.seed(7)
OUT = Path(__file__).resolve().parent

CLIENTS = [
    {"id": "C1", "name": "Priya Sharma", "gender": "F", "age": 29, "city": "Delhi", "religion": "Hindu", "matchmaker": "A",
     "hard": {"age_min": 29, "age_max": 35, "religions": ["Hindu", "Jain"], "cities": ["Delhi", "Gurgaon", "Noida"],
              "no_smoking": True, "wants_children": "yes"},
     "soft": {"min_education": "Master's", "professions": ["Software Engineer", "Product Manager", "Consultant", "Doctor"],
              "drinking_ok": ["never", "occasionally"], "min_income_lpa": 25}},
    {"id": "C2", "name": "Aditya Mehra", "gender": "M", "age": 32, "city": "Mumbai", "religion": "Hindu", "matchmaker": "B",
     "hard": {"age_min": 25, "age_max": 32, "religions": ["Hindu"], "cities": ["Mumbai", "Pune"], "no_smoking": True,
              "diet": ["veg", "eggetarian"]},
     "soft": {"min_education": "Bachelor's", "drinking_ok": ["never", "occasionally"]}},
    {"id": "C3", "name": "Simran Kaur", "gender": "F", "age": 31, "city": "Gurgaon", "religion": "Sikh", "matchmaker": "A",
     "hard": {"age_min": 31, "age_max": 38, "religions": ["Sikh", "Hindu"], "cities": ["Delhi", "Gurgaon", "Chandigarh"]},
     "soft": {"min_education": "Bachelor's", "professions": ["Business Owner", "Lawyer", "Chartered Accountant", "Banker"],
              "min_income_lpa": 30}},
    {"id": "C4", "name": "Rahul Verma", "gender": "M", "age": 30, "city": "Bangalore", "religion": "Hindu", "matchmaker": "B",
     "hard": {"age_min": 25, "age_max": 31, "religions": ["Hindu", "Jain"], "cities": ["Bangalore", "Hyderabad", "Pune"],
              "no_smoking": True, "diet": ["veg", "eggetarian"], "wants_children": "yes"},
     "soft": {"min_education": "Bachelor's", "drinking_ok": ["never"]}},
    {"id": "C5", "name": "Neha Gupta", "gender": "F", "age": 27, "city": "Pune", "religion": "Hindu", "matchmaker": "B",
     "hard": {"age_min": 27, "age_max": 33, "religions": ["Hindu"], "cities": ["Pune", "Mumbai"], "no_smoking": True},
     "soft": {"min_education": "Bachelor's", "professions": ["Software Engineer", "Doctor", "Banker", "Civil Servant"],
              "drinking_ok": ["never", "occasionally"], "min_income_lpa": 20}},
]

M_NAMES = ["Arjun", "Rohan", "Karan", "Vikram", "Siddharth", "Aman", "Nikhil", "Varun", "Kunal", "Ankit", "Harsh", "Gaurav",
           "Manish", "Rajat", "Saurabh", "Abhishek", "Tarun", "Mohit", "Akash", "Dev", "Ishaan", "Kabir", "Yash", "Pranav"]
F_NAMES = ["Ananya", "Ishita", "Kavya", "Meera", "Riya", "Sanya", "Tanvi", "Pooja", "Shreya", "Aditi", "Nisha", "Divya",
           "Sneha", "Kriti", "Megha", "Aishwarya", "Ritika", "Swati"]
SURNAMES = ["Kapoor", "Malhotra", "Agarwal", "Jain", "Singh", "Bansal", "Chopra", "Iyer", "Rao", "Nair", "Khanna", "Saxena",
            "Bhatia", "Arora", "Joshi", "Kulkarni", "Reddy", "Sethi", "Gill", "Desai"]
CITIES_M = ["Delhi", "Gurgaon", "Noida", "Chandigarh", "Pune", "Mumbai", "Bangalore"]
CITIES_F = ["Mumbai", "Pune", "Bangalore", "Hyderabad", "Delhi"]
PROFESSIONS = ["Software Engineer", "Product Manager", "Consultant", "Doctor", "Chartered Accountant", "Lawyer",
               "Business Owner", "Banker", "Civil Servant", "Architect", "Designer", "Teacher"]
EDU_FOR = {"Doctor": ["MBBS"], "Chartered Accountant": ["CA"], "Lawyer": ["LLB", "Master's"], "Consultant": ["MBA"],
           "Product Manager": ["MBA", "Bachelor's"]}

_n = {"M": 0, "F": 0}


def person(gender, **fixed):
    _n[gender] += 1
    names = M_NAMES if gender == "M" else F_NAMES
    prof = fixed.get("profession") or random.choice(PROFESSIONS)
    c = {
        "id": f"{gender}{_n[gender]:03d}",
        "name": f"{random.choice(names)} {random.choice(SURNAMES)}",
        "gender": gender,
        "age": random.randint(26, 37) if gender == "M" else random.randint(24, 32),
        "city": random.choice(CITIES_M if gender == "M" else CITIES_F),
        "religion": random.choices(["Hindu", "Jain", "Sikh", "Muslim", "Christian"], [70, 10, 10, 5, 5])[0],
        "height_cm": random.randint(167, 186) if gender == "M" else random.randint(152, 170),
        "education": random.choice(EDU_FOR.get(prof, ["Bachelor's", "Master's", "Master's", "PhD"])),
        "profession": prof,
        "smoking": random.random() < 0.15,
        "drinking": random.choices(["never", "occasionally", "regularly"], [40, 45, 15])[0],
        "diet": random.choices(["veg", "eggetarian", "non-veg"], [40, 15, 45])[0],
        "wants_children": random.choices(["yes", "open", "no"], [65, 25, 10])[0],
        "income_lpa": random.choice([12, 15, 18, 22, 25, 28, 32, 36, 40, 50, 65]),
    }
    c.update(fixed)
    return c


candidates = [person("M") for _ in range(140)] + [person("F") for _ in range(90)]

# Story candidates: profiles that pass every stated preference, so the rejections reveal NEW information.
priya_ok = dict(religion="Hindu", city="Delhi", smoking=False, wants_children="yes", drinking="occasionally",
                education="Master's", profession="Software Engineer", income_lpa=32)
story = {
    # Priya keeps rejecting shorter men, yet once accepted someone at 173 cm.
    "priya_short": [person("M", age=31, height_cm=168, **priya_ok), person("M", age=33, height_cm=171, **priya_ok),
                    person("M", age=30, height_cm=174, **priya_ok)],
    "priya_accepted": person("M", age=32, height_cm=173, **{**priya_ok, "profession": "Product Manager", "education": "MBA"}),
    # Aditya keeps rejecting the youngest profiles.
    "aditya_young": [person("F", age=25, city="Mumbai", religion="Hindu", smoking=False, diet="veg", drinking="never"),
                     person("F", age=26, city="Pune", religion="Hindu", smoking=False, diet="veg", drinking="never")],
    # Neha does not want founders.
    "neha_founder": [person("M", age=30, city="Pune", religion="Hindu", smoking=False, profession="Business Owner",
                            education="MBA", income_lpa=40, drinking="never"),
                     person("M", age=29, city="Mumbai", religion="Hindu", smoking=False, profession="Business Owner",
                            education="Bachelor's", income_lpa=36, drinking="occasionally")],
    # Simran: regular drinkers.
    "simran_drink": [person("M", age=34, city="Gurgaon", religion="Sikh", smoking=False, drinking="regularly",
                            profession="Lawyer", income_lpa=40),
                     person("M", age=36, city="Delhi", religion="Hindu", smoking=False, drinking="regularly",
                            profession="Banker", income_lpa=36)],
}
for v in story.values():
    candidates += v if isinstance(v, list) else [v]

history = []


def add(client_id, cand, outcome, feedback=""):
    history.append({"client_id": client_id, "candidate_id": cand["id"], "outcome": outcome, "feedback": feedback})


add("C1", story["priya_short"][0], "rejected", "He's quite short, I'd prefer someone taller.")
add("C1", story["priya_short"][1], "rejected", "Nice profile but height is an issue for me.")
add("C1", story["priya_short"][2], "rejected", "Not sure, seems a bit short in the photos.")
add("C1", story["priya_accepted"], "accepted")
add("C2", story["aditya_young"][0], "rejected", "Too young, feels like a big age gap for me.")
add("C2", story["aditya_young"][1], "rejected", "She seems a little immature, too young honestly.")
add("C5", story["neha_founder"][0], "rejected", "Runs his own startup, I want someone with a stable job.")
add("C5", story["neha_founder"][1], "rejected", "Business family, not looking for that. Prefer a stable career.")
add("C3", story["simran_drink"][0], "rejected", "Profile says he drinks regularly, that's not for me.")
add("C3", story["simran_drink"][1], "rejected", "Too much of a party person, drinks a lot.")
add("C3", random.choice(candidates[:140]), "rejected", "Very busy at work this month, can we pause for a bit?")

# Screening misses: profiles that break a STATED preference but were still sent.
MISS_TEXT = {
    "Non-smoker (deal-breaker)": "He smokes. I clearly mentioned no smokers.",
    "Diet": "She is non-veg, I had said vegetarian only.",
    "City": "Lives in another city, I told you I won't relocate.",
    "Religion": "Different religion, I had mentioned this already.",
    "Age ≥": "Too young for me, outside the age range I gave.",
    "Age ≤": "Too old, I asked for a smaller age gap.",
    "Wants children": "Doesn't want kids. That's a deal-breaker for me.",
}
clients_by_id = {c["id"]: c for c in CLIENTS}
for cl in CLIENTS:
    pool = [c for c in candidates if c["gender"] != cl["gender"]]
    random.shuffle(pool)
    misses = 0
    for c in pool:
        fails = check(c, cl)
        if len(fails) == 1 and misses < 2:
            text = next(t for k, t in MISS_TEXT.items() if fails[0]["label"].startswith(k))
            add(cl["id"], c, "rejected", text)
            misses += 1
    # a few ordinary outcomes on profiles that pass
    passing = [c for c in pool if not check(c, cl) and c["id"] not in {h["candidate_id"] for h in history}]
    for c in passing[:2]:
        add(cl["id"], c, "accepted")
    generic = ["Not my type, didn't feel any connection from the profile.", "Looks are not what I'm looking for."]
    for c, t in zip(passing[2:4], generic):
        add(cl["id"], c, "rejected", t)

(OUT / "clients.json").write_text(json.dumps(CLIENTS, indent=2))
(OUT / "candidates.json").write_text(json.dumps(candidates, indent=2))
(OUT / "history.json").write_text(json.dumps(history, indent=2))
print(f"{len(CLIENTS)} clients, {len(candidates)} candidates, {len(history)} history rows "
      f"({sum(h['outcome'] == 'rejected' for h in history)} rejections)")
