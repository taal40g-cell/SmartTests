import os
import json
import zipfile
import random

# Real questions per subject (5 each, you can add more)
real_questions = {
    "English": [
        {"question": "What is the synonym of 'happy'?", "options": ["Sad", "Joyful", "Angry", "Tired"], "answer": "Joyful"},
        {"question": "Choose the correct spelling:", "options": ["Recieve", "Receive", "Recive", "Recve"], "answer": "Receive"},
        {"question": "Which is a noun?", "options": ["Run", "Beauty", "Quickly", "Blue"], "answer": "Beauty"},
        {"question": "Identify the verb in the sentence: 'She runs fast.'", "options": ["She", "Runs", "Fast", "None"], "answer": "Runs"},
        {"question": "Pick the antonym of 'Cold'", "options": ["Hot", "Cool", "Freezing", "Chilly"], "answer": "Hot"}
    ],
    "Mathematics": [
        {"question": "What is 5 + 7?", "options": ["10", "11", "12", "13"], "answer": "12"},
        {"question": "What is 9 x 3?", "options": ["27", "26", "30", "29"], "answer": "27"},
        {"question": "Simplify: 15 ÷ 3", "options": ["3", "4", "5", "6"], "answer": "5"},
        {"question": "What is 7 - 4?", "options": ["1", "2", "3", "4"], "answer": "3"},
        {"question": "Find the value of 2²", "options": ["2", "4", "6", "8"], "answer": "4"}
    ],
    "Science": [
        {"question": "Water freezes at what temperature?", "options": ["0°C", "100°C", "50°C", "10°C"], "answer": "0°C"},
        {"question": "Which gas do we breathe in?", "options": ["Oxygen", "Carbon Dioxide", "Nitrogen", "Hydrogen"], "answer": "Oxygen"},
        {"question": "The sun is a?", "options": ["Planet", "Star", "Moon", "Asteroid"], "answer": "Star"},
        {"question": "Plants make food by?", "options": ["Digestion", "Photosynthesis", "Respiration", "Transpiration"], "answer": "Photosynthesis"},
        {"question": "Which part of the plant absorbs water?", "options": ["Stem", "Leaf", "Root", "Flower"], "answer": "Root"}
    ],
    "History": [
        {"question": "Who discovered America?", "options": ["Columbus", "Newton", "Einstein", "Napoleon"], "answer": "Columbus"},
        {"question": "When did World War II end?", "options": ["1940", "1945", "1950", "1939"], "answer": "1945"},
        {"question": "The first president of USA was?", "options": ["Lincoln", "Washington", "Jefferson", "Adams"], "answer": "Washington"},
        {"question": "Ancient Egypt is known for?", "options": ["Pyramids", "Colosseum", "Great Wall", "Stonehenge"], "answer": "Pyramids"},
        {"question": "The Renaissance started in?", "options": ["France", "Italy", "Germany", "England"], "answer": "Italy"}
    ],
    "Geography": [
        {"question": "The largest ocean is?", "options": ["Atlantic", "Indian", "Pacific", "Arctic"], "answer": "Pacific"},
        {"question": "Mount Everest is in?", "options": ["Nepal", "India", "China", "Bhutan"], "answer": "Nepal"},
        {"question": "The Sahara is a?", "options": ["Mountain", "River", "Desert", "Forest"], "answer": "Desert"},
        {"question": "The capital of France?", "options": ["Paris", "London", "Rome", "Berlin"], "answer": "Paris"},
        {"question": "Which continent is Australia in?", "options": ["Europe", "Asia", "Australia", "Africa"], "answer": "Australia"}
    ],
    "Physics": [
        {"question": "Force = ?", "options": ["Mass x Acceleration", "Mass + Acceleration", "Mass - Acceleration", "Mass / Acceleration"], "answer": "Mass x Acceleration"},
        {"question": "Light travels fastest in?", "options": ["Water", "Vacuum", "Air", "Glass"], "answer": "Vacuum"},
        {"question": "Unit of Energy?", "options": ["Joule", "Newton", "Watt", "Meter"], "answer": "Joule"},
        {"question": "Acceleration due to gravity?", "options": ["9.8 m/s²", "10 m/s²", "8 m/s²", "12 m/s²"], "answer": "9.8 m/s²"},
        {"question": "What is the SI unit of force?", "options": ["Joule", "Newton", "Watt", "Pascal"], "answer": "Newton"}
    ],
    "Chemistry": [
        {"question": "Water formula?", "options": ["H2O", "CO2", "O2", "NaCl"], "answer": "H2O"},
        {"question": "NaCl is?", "options": ["Salt", "Sugar", "Acid", "Base"], "answer": "Salt"},
        {"question": "Acidic pH value?", "options": ["<7", "7", ">7", "14"], "answer": "<7"},
        {"question": "Which gas is produced by burning?", "options": ["Oxygen", "Carbon Dioxide", "Nitrogen", "Hydrogen"], "answer": "Carbon Dioxide"},
        {"question": "The atomic number of Hydrogen?", "options": ["1", "2", "3", "4"], "answer": "1"}
    ],
    "Biology": [
        {"question": "Humans have how many heart chambers?", "options": ["2", "3", "4", "5"], "answer": "4"},
        {"question": "Blood is pumped by?", "options": ["Lungs", "Heart", "Kidney", "Liver"], "answer": "Heart"},
        {"question": "Which is a mammal?", "options": ["Shark", "Dolphin", "Frog", "Crocodile"], "answer": "Dolphin"},
        {"question": "Plants produce?", "options": ["Oxygen", "Nitrogen", "Carbon Dioxide", "Hydrogen"], "answer": "Oxygen"},
        {"question": "What carries genetic info?", "options": ["DNA", "RNA", "Protein", "Enzyme"], "answer": "DNA"}
    ],
    "ICT": [
        {"question": "HTML is used for?", "options": ["Styling", "Scripting", "Structure", "Database"], "answer": "Structure"},
        {"question": "CPU stands for?", "options": ["Central Processing Unit", "Central Program Unit", "Computer Processing Unit", "Central Power Unit"], "answer": "Central Processing Unit"},
        {"question": "RAM is volatile?", "options": ["Yes", "No", "Sometimes", "Never"], "answer": "Yes"},
        {"question": "Which is an input device?", "options": ["Monitor", "Keyboard", "Speaker", "Printer"], "answer": "Keyboard"},
        {"question": "WWW stands for?", "options": ["World Wide Web", "Web Wide World", "Wide Web World", "Web World Wide"], "answer": "World Wide Web"}
    ],
    "Economics": [
        {"question": "What is demand?", "options": ["Want", "Need", "Willingness to buy", "Price"], "answer": "Willingness to buy"},
        {"question": "What is supply?", "options": ["Available quantity", "Demand", "Price", "Profit"], "answer": "Available quantity"},
        {"question": "GDP stands for?", "options": ["Gross Domestic Product", "Gross Domestic Price", "General Domestic Product", "Gross Demand Product"], "answer": "Gross Domestic Product"},
        {"question": "Inflation means?", "options": ["Price increase", "Price decrease", "Stable price", "Profit"], "answer": "Price increase"},
        {"question": "Economics studies?", "options": ["Money", "Trade", "Resources", "All of the above"], "answer": "All of the above"}
    ]
}

class_name = "JHS1"
num_questions_per_subject = 20
output_folder = "questions"
zip_filename = "questions_zip.zip"

os.makedirs(output_folder, exist_ok=True)

for subject, base_questions in real_questions.items():
    questions = []
    while len(questions) < num_questions_per_subject:
        questions.append(random.choice(base_questions))
    safe_subject = subject.lower().replace(" ", "")
    filename = f"questions_{class_name.lower()}_{safe_subject}.json"
    with open(os.path.join(output_folder, filename), "w", encoding="utf-8") as f:
        json.dump(questions, f, indent=4)

# Create ZIP folder
with zipfile.ZipFile(zip_filename, "w", zipfile.ZIP_DEFLATED) as zipf:
    for file in os.listdir(output_folder):
        zipf.write(os.path.join(output_folder, file), file)

print(f"✅ All question files generated and zipped as {zip_filename}")
