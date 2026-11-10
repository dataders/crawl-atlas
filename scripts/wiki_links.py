"""Verified wiki destinations; unknown titles use explicit search, never guessed slugs."""
from urllib.parse import quote
BASE = 'https://dungeon-crawler-carl.fandom.com/'
PAGES = {
    'Carl':'Carl', 'Princess Donut':'Donut',
    'Pugilism':'Pugilism_Skill', 'Powerful Strike':'Powerful_Strike_Skill',
    'Protective Shell':'Protective_Shell_Spell',
    'Enchanted BigBoi Boxers':'Enchanted_BigBoi_Boxers',
    'Scroll of Upgrade':'Scroll_of_Upgrade',
}

def wiki_link(name):
    page = PAGES.get(name)
    return BASE+'wiki/'+page if page else BASE+'wiki/Special:Search?query='+quote(name, safe='')

def wiki_label(name):
    return 'Wiki page' if name in PAGES else 'Search wiki'

