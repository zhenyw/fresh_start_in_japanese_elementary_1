import genanki
import random
import os
import re
import argparse
from typing import List, Dict, Set, Tuple

# --- DEFAULT STYLING ---
DEFAULT_CSS = """
.card {
  font-family: arial, sans-serif;
  font-size: 20px;
  text-align: center;
  color: black;
  background-color: white;
}
.nightMode .card { color: white; background-color: #333; }
img { max-width: 90%; }
"""

def create_anki_model(custom_css: str) -> genanki.Model:
    """Creates the Anki model with the provided CSS."""
    return genanki.Model(
        1607392319,  # Hardcoded model ID
        'Simple Model with Media (CSS)',
        fields=[{'name': 'Front'}, {'name': 'Back'}],
        templates=[{
            'name': 'Card 1',
            'qfmt': '<div class="question">{{Front}}</div>',
            'afmt': '{{FrontSide}}<hr id="answer"><div class="answer">{{Back}}</div>',
        }],
        css=custom_css)

def find_media_files(text: str) -> Set[str]:
    """Finds all media references (images and audio) in a string."""
    img_pattern = re.compile(r'<img src="([^"]+)"\s*\/?>', re.IGNORECASE)
    sound_pattern = re.compile(r'\[sound:([^\]]+)\]', re.IGNORECASE)
    found_files = set(img_pattern.findall(text))
    found_files.update(sound_pattern.findall(text))
    return found_files

def parse_input_file(filepath: str) -> Tuple[Dict[str, str], List[Dict[str, str]]]:
    """
    Parses the input file with section-based subdeck definitions.
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        print(f"❌ Error: Input file not found at '{filepath}'")
        return {}, []

    header = {}
    cards = []
    parts = content.split('---', 1)
    header_content = parts[0]
    cards_content = parts[1] if len(parts) > 1 else ''

    # Parse header
    for line in header_content.splitlines():
        if ':' in line and not line.strip().startswith('#'):
            key, value = line.split(':', 1)
            header[key.strip().upper()] = value.strip()

    # Parse cards and subdeck sections
    current_subdeck = ""  # Start with the base deck
    for block in cards_content.split('---'):
        block = block.strip()
        if not block:
            continue

        first_line = block.splitlines()[0].strip()

        # Check if the block is a subdeck declaration
        if first_line.upper().startswith('SUBDECK:'):
            current_subdeck = first_line.split(':', 1)[1].strip()
            continue

        # Otherwise, parse as a card
        card_data = {'FRONT': [], 'BACK': []}
        current_field = None
        for line in block.splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if line.upper().startswith('FRONT:'):
                current_field = 'FRONT'
                line = line[len('FRONT:'):]
            elif line.upper().startswith('BACK:'):
                current_field = 'BACK'
                line = line[len('BACK:'):]
            if current_field:
                card_data[current_field].append(line.strip())

        if card_data['FRONT'] and card_data['BACK']:
            front_text = '<br>'.join(card_data['FRONT'])
            back_text = '<br>'.join(card_data['BACK'])
            cards.append({
                'front': front_text,
                'back': back_text,
                'subdeck': current_subdeck,
                'media_files': find_media_files(front_text) | find_media_files(back_text)
            })

    return header, cards

def main():
    """Main function to generate the Anki deck."""
    parser = argparse.ArgumentParser(description="Generate Anki deck from a text file, assuming media is in a 'media/' subfolder.")
    parser.add_argument("input_file", help="Path to the input text file.")
    parser.add_argument("-o", "--output", default="output.apkg", help="Path for the output .apkg file.")
    parser.add_argument("-d", "--deck-name", help="Default deck name (overridden by DECK_NAME in file header).")
    parser.add_argument("--css", help="Path to a custom CSS file for card styling.")

    args = parser.parse_args()

    # Load CSS or use default
    css_content = DEFAULT_CSS
    if args.css:
        try:
            with open(args.css, 'r', encoding='utf-8') as f:
                css_content = f.read()
            print(f"🎨 Loaded custom style from '{args.css}'")
        except FileNotFoundError:
            print(f"⚠️ Warning: CSS file not found at '{args.css}'. Using default style.")

    anki_model = create_anki_model(css_content)
    print(f"Parsing input file: '{args.input_file}'...")
    header_info, cards_data = parse_input_file(args.input_file)

    if not cards_data:
        print("No cards found. Exiting.")
        return

    base_deck_name = header_info.get('DECK_NAME') or args.deck_name or os.path.splitext(os.path.basename(args.input_file))[0].replace('_', ' ').title()
    print(f"Building deck: '{base_deck_name}'")

    decks = {}
    media_to_package = set()
    for card in cards_data:
        full_deck_name = f"{base_deck_name}::{card['subdeck']}" if card['subdeck'] else base_deck_name
        if full_deck_name not in decks:
            decks[full_deck_name] = genanki.Deck(random.randrange(1 << 30, 1 << 31), full_deck_name)

        note = genanki.Note(model=anki_model, fields=[card['front'], card['back']])
        decks[full_deck_name].add_note(note)

        # **MODIFIED LOGIC HERE**
        # Automatically look for media files in the 'media/' subfolder.
        for basename in card['media_files']:
            path_to_check = os.path.join('media', basename)
            if os.path.exists(path_to_check):
                media_to_package.add(path_to_check)
            else:
                print(f"⚠️ Warning: Media file not found at '{path_to_check}' and will be skipped.")

    # Build and write the final .apkg file
    anki_package = genanki.Package(decks.values())
    anki_package.media_files = list(media_to_package)
    try:
        anki_package.write_to_file(args.output)
        print(f"\n✅ Success! Anki package '{args.output}' created with {len(cards_data)} cards.")
    except Exception as e:
        print(f"❌ Error writing .apkg file: {e}")

if __name__ == "__main__":
    main()
