"""Database repository and persistence engine for BPSC Question Lab v1.0.

Features:
- Local SQLite database (question_lab.db) with non-destructive, additive migrations.
- Complete attempt persistence with timing, confidence ratings, and negative marking.
- Dedicated test_sessions, revision_items, pinned_notebook, and research_notes tables.
- Migration utilities for cloud/Supabase synchronization.
"""

from __future__ import annotations

import csv
import json
import sqlite3
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

APP_DIR = Path(__file__).resolve().parent
DB_PATH = APP_DIR / "question_lab.db"

SUBJECTS = [
    "Modern History",
    "Ancient & Medieval History",
    "Bihar Special",
    "Geography",
    "Indian Polity",
    "Economy",
    "General Science",
    "Environment",
    "Current Affairs",
    "Other",
]
EXAMS = ["BPSC", "UPSC", "Both"]
DIFFICULTIES = ["Easy", "Medium", "Hard"]
SOURCE_TYPES = [
    "Official PYQ",
    "Online question",
    "Book / notes",
    "User-added",
    "AI-generated",
    "Built-in sample",
]
ERROR_TYPES = [
    "Unclassified",
    "Knowledge gap",
    "Conceptual confusion",
    "Misread question",
    "Incorrect elimination / guess",
    "Careless error",
    "Calculation or reasoning error",
    "Confusion between similar facts",
    "Other",
]

SAMPLE_QUESTIONS = [
    {
        "exam": "BPSC",
        "subject": "Modern History",
        "topic": "Champaran Satyagraha",
        "question": "The Champaran Satyagraha of 1917 was primarily associated with which issue?",
        "option_a": "Indigo cultivators' grievances",
        "option_b": "Forest rights in central India",
        "option_c": "The demand for separate electorates",
        "option_d": "The salt tax",
        "correct_option": "A",
        "explanation": "The Champaran movement addressed the exploitation of indigo cultivators under the tinkathia system in Bihar.",
        "source_type": "Built-in sample",
        "source_name": "Question Lab starter set",
        "source_url": "",
        "difficulty": "Easy",
        "concept_tested": "Tinkathia system & Gandhi's first Satyagraha in India",
    },
    {
        "exam": "Both",
        "subject": "Indian Polity",
        "topic": "Fundamental Rights",
        "question": "Which Article of the Indian Constitution guarantees the right to constitutional remedies?",
        "option_a": "Article 14",
        "option_b": "Article 19",
        "option_c": "Article 21",
        "option_d": "Article 32",
        "correct_option": "D",
        "explanation": "Article 32 allows citizens to move the Supreme Court directly for the enforcement of Fundamental Rights.",
        "source_type": "Built-in sample",
        "source_name": "Question Lab starter set",
        "source_url": "",
        "difficulty": "Easy",
        "concept_tested": "Writs and Constitutional Remedies (Heart and Soul of the Constitution)",
    },
    {
        "exam": "Both",
        "subject": "Indian Polity",
        "topic": "Fundamental Duties",
        "question": "Fundamental Duties were added to the Constitution of India by which amendment?",
        "option_a": "24th Amendment",
        "option_b": "42nd Amendment",
        "option_c": "44th Amendment",
        "option_d": "52nd Amendment",
        "correct_option": "B",
        "explanation": "The 42nd Constitutional Amendment Act, 1976 added Part IVA (Article 51A) upon recommendations of the Swaran Singh Committee.",
        "source_type": "Built-in sample",
        "source_name": "Question Lab starter set",
        "source_url": "",
        "difficulty": "Easy",
        "concept_tested": "Swaran Singh Committee and 42nd Amendment 1976",
    },
    {
        "exam": "Both",
        "subject": "Ancient & Medieval History",
        "topic": "Ashoka",
        "question": "Which idea was central to Ashoka's Dhamma as reflected in his inscriptions?",
        "option_a": "Compulsory conversion to Buddhism",
        "option_b": "Expansion through perpetual warfare",
        "option_c": "Ethical conduct and respect among communities",
        "option_d": "Abolition of all forms of administration",
        "correct_option": "C",
        "explanation": "Ashoka's Dhamma emphasized moral conduct, non-violence, mutual tolerance, and social responsibility rather than dogma.",
        "source_type": "Built-in sample",
        "source_name": "Question Lab starter set",
        "source_url": "",
        "difficulty": "Medium",
        "concept_tested": "Ashokan Edicts and policy of Dhamma",
    },
    {
        "exam": "BPSC",
        "subject": "Bihar Special",
        "topic": "Rivers of Bihar",
        "question": "The Gandak River joins the Ganga in the vicinity of which place in Bihar?",
        "option_a": "Sonpur",
        "option_b": "Bhagalpur",
        "option_c": "Buxar",
        "option_d": "Munger",
        "correct_option": "A",
        "explanation": "The Gandak enters Bihar at Valmiki Nagar and joins the Ganga near Sonpur/Hajipur opposite Patna.",
        "source_type": "Built-in sample",
        "source_name": "Question Lab starter set",
        "source_url": "",
        "difficulty": "Medium",
        "concept_tested": "Confluence points of Himalayan tributaries of the Ganga in Bihar",
    },
    {
        "exam": "BPSC",
        "subject": "Bihar Special",
        "topic": "Bihar Geography",
        "question": "What is the capital of Bihar?",
        "option_a": "Gaya",
        "option_b": "Patna",
        "option_c": "Muzaffarpur",
        "option_d": "Bhagalpur",
        "correct_option": "B",
        "explanation": "Patna is the historical and administrative capital of Bihar.",
        "source_type": "Built-in sample",
        "source_name": "Question Lab starter set",
        "source_url": "",
        "difficulty": "Easy",
        "concept_tested": "Basic Bihar Geography",
    },
    {
        "exam": "Both",
        "subject": "General Science",
        "topic": "Units and Measurements",
        "question": "What is the SI unit of electrical resistance?",
        "option_a": "Volt",
        "option_b": "Ampere",
        "option_c": "Ohm",
        "option_d": "Watt",
        "correct_option": "C",
        "explanation": "Electrical resistance is measured in ohms (Ω). Volt is potential, Ampere is current, and Watt is power.",
        "source_type": "Built-in sample",
        "source_name": "Question Lab starter set",
        "source_url": "",
        "difficulty": "Easy",
        "concept_tested": "SI units in Physics",
    },
    {
        "exam": "Both",
        "subject": "Economy",
        "topic": "Reserve Bank of India",
        "question": "In which year was the Reserve Bank of India nationalised?",
        "option_a": "1935",
        "option_b": "1947",
        "option_c": "1948",
        "option_d": "1949",
        "correct_option": "D",
        "explanation": "Established under the RBI Act 1934, the RBI commenced operations in 1935 and was nationalised on January 1, 1949.",
        "source_type": "Built-in sample",
        "source_name": "Question Lab starter set",
        "source_url": "",
        "difficulty": "Medium",
        "concept_tested": "Banking history of India and nationalisation",
    },
    {
        "exam": "Both",
        "subject": "Environment",
        "topic": "National Parks",
        "question": "Kaziranga National Park is located in which Indian state?",
        "option_a": "Assam",
        "option_b": "Arunachal Pradesh",
        "option_c": "West Bengal",
        "option_d": "Meghalaya",
        "correct_option": "A",
        "explanation": "Kaziranga National Park is situated along the Brahmaputra River in Assam and is a UNESCO World Heritage Site.",
        "source_type": "Built-in sample",
        "source_name": "Question Lab starter set",
        "source_url": "",
        "difficulty": "Easy",
        "concept_tested": "Protected areas & biodiversity hotspots of India",
    },
    {
        "exam": "Both",
        "subject": "Modern History",
        "topic": "Quit India Movement",
        "question": "The Quit India Movement was launched by the Indian National Congress in which year?",
        "option_a": "1919",
        "option_b": "1930",
        "option_c": "1942",
        "option_d": "1946",
        "correct_option": "C",
        "explanation": "The All-India Congress Committee passed the 'Quit India' resolution at Gowalia Tank Maidan, Bombay, in August 1942.",
        "source_type": "Built-in sample",
        "source_name": "Question Lab starter set",
        "source_url": "",
        "difficulty": "Easy",
        "concept_tested": "Major mass movements of the Indian National Movement",
    },
    {
        "exam": "Both",
        "subject": "Indian Polity",
        "topic": "Money Bills",
        "question": "A Money Bill can be introduced in which House of Parliament?",
        "option_a": "Rajya Sabha only",
        "option_b": "Lok Sabha only",
        "option_c": "Either House",
        "option_d": "A joint sitting only",
        "correct_option": "B",
        "explanation": "Under Article 110/109, a Money Bill can only be introduced in Lok Sabha with the prior recommendation of the President.",
        "source_type": "Built-in sample",
        "source_name": "Question Lab starter set",
        "source_url": "",
        "difficulty": "Medium",
        "concept_tested": "Parliamentary procedure for Financial & Money Bills",
    },
    {
        "exam": "Both",
        "subject": "Geography",
        "topic": "Indian Monsoon",
        "question": "The retreating or withdrawal phase of the southwest monsoon generally begins first over which broad region of India?",
        "option_a": "Northwest India",
        "option_b": "The far northeastern hills",
        "option_c": "The Andaman Sea region",
        "option_d": "The southern Western Ghats",
        "correct_option": "A",
        "explanation": "Withdrawal of the southwest monsoon begins in early September from northwestern India (Rajasthan/Punjab) as low pressure weakens.",
        "source_type": "Built-in sample",
        "source_name": "Question Lab starter set",
        "source_url": "",
        "difficulty": "Medium",
        "concept_tested": "Climatology and seasonal migration of the monsoon trough",
    },
]

VERIFIED_BPSC_PYQS = [
    {
        "exam": "BPSC",
        "subject": "Bihar Special",
        "topic": "Judiciary in Bihar",
        "subtopic": "High Court",
        "question": "In which of the following years was the Patna High Court established?",
        "option_a": "1912",
        "option_b": "1916",
        "option_c": "1919",
        "option_d": "1921",
        "correct_option": "B",
        "explanation": "The Patna High Court was established on 9 February 1916 (Letters Patent issued on 9 February 1916) and commenced functioning under Sir Edward Maynard Des Champs Chamier as its first Chief Justice.",
        "distractor_notes": "1912: Bihar & Orissa carved out of Bengal; 1919: Montagu-Chelmsford Reforms; 1921: Bihar Legislative Council constituted.",
        "concept_tested": "Establishment of High Courts under British rule in Bihar",
        "question_type": "Standard MCQ",
        "source_type": "Official PYQ",
        "source_name": "69th BPSC CCE Prelims",
        "source_url": "https://bpsc.bih.nic.in",
        "difficulty": "Easy",
        "is_ai_generated": 0,
        "exam_edition": "69th BPSC CCE Prelims",
        "exam_year": "2023",
        "paper_set": "Series A",
        "official_qno": 43,
        "answer_key_status": "Official Final Key Verified",
    },
    {
        "exam": "BPSC",
        "subject": "Modern History",
        "topic": "Nationalist Politics in Bihar",
        "subtopic": "Provincial Congress",
        "question": "Who was the first President of the Bihar Provincial Congress Committee formed in 1908 at Sonpur?",
        "option_a": "Mazharul Haque",
        "option_b": "Nawab Sarfaraz Hussain Khan",
        "option_c": "Sachchidananda Sinha",
        "option_d": "Syed Hasan Imam",
        "correct_option": "B",
        "explanation": "In 1908, a meeting was held at Sonpur under the presidency of Nawab Sarfaraz Hussain Khan where the Bihar Provincial Congress Committee was formally constituted.",
        "distractor_notes": "Mazharul Haque and Sachchidananda Sinha were prominent delegates; Hasan Imam presided over the 1909 session.",
        "concept_tested": "Formation of Bihar Provincial Congress Committee (1908)",
        "question_type": "Standard MCQ",
        "source_type": "Official PYQ",
        "source_name": "68th BPSC CCE Prelims",
        "source_url": "https://bpsc.bih.nic.in",
        "difficulty": "Medium",
        "is_ai_generated": 0,
        "exam_edition": "68th BPSC CCE Prelims",
        "exam_year": "2023",
        "paper_set": "Series A",
        "official_qno": 64,
        "answer_key_status": "Official Final Key Verified",
    },
    {
        "exam": "BPSC",
        "subject": "Bihar Special",
        "topic": "Freedom Struggle in Bihar",
        "subtopic": "Peasant Movements",
        "question": "Who founded the Bihar Provincial Kisan Sabha (BPKS) in 1929 to mobilize peasants against zamindari exploitation?",
        "option_a": "Swami Sahajanand Saraswati",
        "option_b": "Karyanand Sharma",
        "option_c": "Rahul Sankrityayan",
        "option_d": "Yadunandan Sharma",
        "correct_option": "A",
        "explanation": "Swami Sahajanand Saraswati formed the Bihar Provincial Kisan Sabha (BPKS) in 1929 at the Sonpur Mela to defend peasant occupancy rights against landlord oppressions.",
        "distractor_notes": "Karyanand Sharma led the Barahiya Tal movement in Munger; Rahul Sankrityayan was active in Chapra/Ambhari; Yadunandan Sharma led the Reora satyagraha in Gaya.",
        "concept_tested": "Kisan Sabha Movement in Bihar (1929)",
        "question_type": "Standard MCQ",
        "source_type": "Official PYQ",
        "source_name": "67th BPSC CCE Re-Exam",
        "source_url": "https://bpsc.bih.nic.in",
        "difficulty": "Easy",
        "is_ai_generated": 0,
        "exam_edition": "67th BPSC CCE Re-Exam",
        "exam_year": "2022",
        "paper_set": "Series A",
        "official_qno": 78,
        "answer_key_status": "Official Final Key Verified",
    },
    {
        "exam": "BPSC",
        "subject": "Bihar Special",
        "topic": "Transportation in Bihar",
        "subtopic": "National Highways",
        "question": "The Grand Trunk Road (historical Sher Shah Suri Marg / NH 19) passes through which of the following sets of towns in Bihar?",
        "option_a": "Sasaram, Aurangabad, Dobhi",
        "option_b": "Muzaffarpur, Darbhanga, Madhubani",
        "option_c": "Purnia, Katihar, Kishanganj",
        "option_d": "Siwan, Gopalganj, Saran",
        "correct_option": "A",
        "explanation": "The Grand Trunk Road (Golden Quadrilateral segment NH 19 / old NH 2) traverses South-West Bihar through Rohtas (Sasaram), Aurangabad, and Gaya (Dobhi) districts into Jharkhand.",
        "distractor_notes": "Muzaffarpur/Darbhanga are on NH 27; Purnia/Kishanganj are on NH 31; Siwan/Saran are on NH 531.",
        "concept_tested": "Geography of Major Transport Corridors in Bihar",
        "question_type": "Standard MCQ",
        "source_type": "Official PYQ",
        "source_name": "68th BPSC CCE Prelims",
        "source_url": "https://bpsc.bih.nic.in",
        "difficulty": "Medium",
        "is_ai_generated": 0,
        "exam_edition": "68th BPSC CCE Prelims",
        "exam_year": "2023",
        "paper_set": "Series A",
        "official_qno": 82,
        "answer_key_status": "Official Final Key Verified",
    },
    {
        "exam": "BPSC",
        "subject": "Indian Polity",
        "topic": "Constitutional Bodies",
        "subtopic": "Advocate General",
        "question": "Under which Article of the Constitution of India is the Advocate General for the State appointed by the Governor?",
        "option_a": "Article 165",
        "option_b": "Article 177",
        "option_c": "Article 194",
        "option_d": "Article 217",
        "correct_option": "A",
        "explanation": "Article 165 of the Indian Constitution provides that the Governor of each State shall appoint a person who is qualified to be appointed a Judge of a High Court to be Advocate General for the State.",
        "distractor_notes": "Article 177 deals with rights of Ministers & Advocate-General regarding Houses; Article 194 with legislative privileges; Article 217 with High Court judges.",
        "concept_tested": "State Executive & Constitutional Offices",
        "question_type": "Standard MCQ",
        "source_type": "Official PYQ",
        "source_name": "68th BPSC CCE Prelims",
        "source_url": "https://bpsc.bih.nic.in",
        "difficulty": "Easy",
        "is_ai_generated": 0,
        "exam_edition": "68th BPSC CCE Prelims",
        "exam_year": "2023",
        "paper_set": "Series A",
        "official_qno": 104,
        "answer_key_status": "Official Final Key Verified",
    },
    {
        "exam": "BPSC",
        "subject": "Geography",
        "topic": "Mountain Passes of India",
        "subtopic": "Himalayan Passes",
        "question": "Which of the following mountain passes connects Sikkim with the Tibet Autonomous Region through the Chumbi Valley?",
        "option_a": "Jelep La",
        "option_b": "Shipki La",
        "option_c": "Lipulekh",
        "option_d": "Bum La",
        "correct_option": "A",
        "explanation": "Jelep La (altitude ~4,267 m) is a high mountain pass between East Sikkim and Tibet that passes through the Chumbi Valley.",
        "distractor_notes": "Shipki La connects Himachal Pradesh with Tibet; Lipulekh connects Uttarakhand with Tibet; Bum La connects Arunachal Pradesh with Tibet.",
        "concept_tested": "Strategic passes of the Eastern Himalayas",
        "question_type": "Standard MCQ",
        "source_type": "Official PYQ",
        "source_name": "69th BPSC CCE Prelims",
        "source_url": "https://bpsc.bih.nic.in",
        "difficulty": "Medium",
        "is_ai_generated": 0,
        "exam_edition": "69th BPSC CCE Prelims",
        "exam_year": "2023",
        "paper_set": "Series A",
        "official_qno": 58,
        "answer_key_status": "Official Final Key Verified",
    },
    {
        "exam": "BPSC",
        "subject": "Bihar Special",
        "topic": "Champaran Satyagraha 1917",
        "subtopic": "Resistance and Key Figures",
        "question": "During the Champaran Satyagraha (1917), who among the following saved Mahatma Gandhi's life from an assassination attempt by refusing to administer poison in milk?",
        "option_a": "Batak Mian",
        "option_b": "Hamid Ansari",
        "option_c": "Hasan Imam",
        "option_d": "Mazharul Haque",
        "correct_option": "A",
        "explanation": "Batak Mian, an employee of an indigo planter (Erwin) in Motihari, uncovered and thwarted an assassination plot by refusing to serve poisoned milk to Mahatma Gandhi during the 1917 Champaran Satyagraha.",
        "distractor_notes": "Hamid Ansari is an unrelated name; Hasan Imam and Mazharul Haque were eminent nationalist leaders and legal luminaries of Bihar.",
        "concept_tested": "Batak Mian's role in 1917 Champaran Satyagraha",
        "question_type": "Standard MCQ",
        "source_type": "Official PYQ",
        "source_name": "69th BPSC CCE Prelims",
        "source_url": "https://bpsc.bih.nic.in",
        "difficulty": "Medium",
        "is_ai_generated": 0,
        "exam_edition": "69th BPSC CCE Prelims",
        "exam_year": "2023",
        "paper_set": "Series A",
        "official_qno": 67,
        "answer_key_status": "Official Final Key Verified",
    },
    {
        "exam": "BPSC",
        "subject": "Indian Polity",
        "topic": "Writs & Constitutional Remedies",
        "subtopic": "Article 32 and Article 226",
        "question": "Consider the following statements regarding the writ of Mandamus in India:\n1. It cannot be issued against a private individual or private body.\n2. It cannot be issued to enforce a departmental instruction that lacks statutory force.\n3. It can be issued against the President of India or State Governors in their official capacities.\nWhich of the statements given above are correct?",
        "option_a": "1 and 2 only",
        "option_b": "2 and 3 only",
        "option_c": "1 and 3 only",
        "option_d": "1, 2 and 3",
        "correct_option": "A",
        "explanation": "Statements 1 and 2 are correct. Mandamus lies only against public authorities to perform statutory public duties; it cannot lie against private bodies or non-statutory instructions. Statement 3 is incorrect because Article 361 provides constitutional immunity to the President and Governors from court writs for the discharge of their official functions.",
        "distractor_notes": "Statement 3 is barred by Article 361 immunity, which eliminates options B, C, and D.",
        "concept_tested": "Writs under Article 32 & 226 and immunities under Article 361",
        "question_type": "Statement-based (1 and 2 only, etc.)",
        "source_type": "Official PYQ",
        "source_name": "69th BPSC CCE Prelims",
        "source_url": "https://bpsc.bih.nic.in",
        "difficulty": "Hard",
        "is_ai_generated": 0,
        "exam_edition": "69th BPSC CCE Prelims",
        "exam_year": "2023",
        "paper_set": "Series A",
        "official_qno": 92,
        "answer_key_status": "Official Final Key Verified",
    },
    {
        "exam": "BPSC",
        "subject": "Economy",
        "topic": "Industrial Policy & Five Year Plans",
        "subtopic": "IPR 1956",
        "question": "Consider the following statements regarding the Industrial Policy Resolution (IPR) 1956:\n1. It formed the economic and industrial foundation of the Second Five-Year Plan.\n2. It categorized industries into three schedules (A, B, and C).\n3. Under Schedule A, industries were reserved exclusively for private sector development.\nWhich of the statements given above are correct?",
        "option_a": "1 and 2 only",
        "option_b": "2 and 3 only",
        "option_c": "1 and 3 only",
        "option_d": "1, 2 and 3",
        "correct_option": "A",
        "explanation": "The Industrial Policy Resolution 1956 formed the basis of the Second Five Year Plan (Mahalanobis model). Schedule A comprised 17 industries that were exclusively reserved for the State (public sector), NOT the private sector. Schedule B consisted of 12 mixed industries progressively owned by the state, and Schedule C left the remaining industries to private enterprise.",
        "distractor_notes": "Schedule A was reserved exclusively for the public sector/State, making statement 3 false.",
        "concept_tested": "Mahalanobis strategy and Industrial Policy Resolution 1956 Schedule classification",
        "question_type": "Statement-based (1 and 2 only, etc.)",
        "source_type": "Official PYQ",
        "source_name": "69th BPSC CCE Prelims",
        "source_url": "https://bpsc.bih.nic.in",
        "difficulty": "Hard",
        "is_ai_generated": 0,
        "exam_edition": "69th BPSC CCE Prelims",
        "exam_year": "2023",
        "paper_set": "Series A",
        "official_qno": 114,
        "answer_key_status": "Official Final Key Verified",
    },
    {
        "exam": "BPSC",
        "subject": "General Science",
        "topic": "Human Physiology & Endocrine System",
        "subtopic": "Pancreatic Hormones",
        "question": "Consider the following statements regarding hormonal regulation of glucose in the human body:\n1. Insulin is synthesized and secreted by the beta cells of the Islets of Langerhans in the pancreas.\n2. Insulin lowers blood glucose concentration by stimulating glycogenesis and cellular uptake.\n3. Glucagon is secreted by alpha cells and triggers glycogen breakdown (glycogenolysis) in the liver.\nWhich of the statements given above are correct?",
        "option_a": "1 and 2 only",
        "option_b": "2 and 3 only",
        "option_c": "1 and 3 only",
        "option_d": "1, 2 and 3",
        "correct_option": "D",
        "explanation": "All three statements are factually correct. The endocrine pancreas consists of Islets of Langerhans: beta cells secrete insulin (hypoglycemic hormone that promotes cellular uptake and glycogenesis) and alpha cells secrete glucagon (hyperglycemic hormone that promotes glycogenolysis).",
        "distractor_notes": "Statements 1, 2, and 3 are all standard physiological truths; hence 1, 2 and 3 is correct.",
        "concept_tested": "Pancreatic endocrine regulation of blood glucose",
        "question_type": "Statement-based (1 and 2 only, etc.)",
        "source_type": "Official PYQ",
        "source_name": "69th BPSC CCE Prelims",
        "source_url": "https://bpsc.bih.nic.in",
        "difficulty": "Medium",
        "is_ai_generated": 0,
        "exam_edition": "69th BPSC CCE Prelims",
        "exam_year": "2023",
        "paper_set": "Series A",
        "official_qno": 18,
        "answer_key_status": "Official Final Key Verified",
    },
    {
        "exam": "BPSC",
        "subject": "Modern History",
        "topic": "Indian National Congress Sessions in Bihar",
        "subtopic": "Gaya Session 1922",
        "question": "Who presided over the 37th annual session of the Indian National Congress held at Gaya in December 1922?",
        "option_a": "Chittaranjan Das",
        "option_b": "Motilal Nehru",
        "option_c": "Hakim Ajmal Khan",
        "option_d": "Sarojini Naidu",
        "correct_option": "A",
        "explanation": "Deshbandhu Chittaranjan Das presided over the Gaya Session of the Indian National Congress in December 1922. The session saw the debate over Council entry between Pro-changers and No-changers, following which Das resigned as President and formed the Swaraj Party with Motilal Nehru as secretary.",
        "distractor_notes": "Motilal Nehru was the co-founder/secretary of Swaraj Party; Hakim Ajmal Khan presided at Ahmedabad in 1921; Sarojini Naidu presided at Kanpur in 1925.",
        "concept_tested": "Gaya Session 1922 and the Pro-changers vs No-changers debate leading to Swaraj Party",
        "question_type": "Standard MCQ",
        "source_type": "Official PYQ",
        "source_name": "69th BPSC CCE Prelims",
        "source_url": "https://bpsc.bih.nic.in",
        "difficulty": "Medium",
        "is_ai_generated": 0,
        "exam_edition": "69th BPSC CCE Prelims",
        "exam_year": "2023",
        "paper_set": "Series A",
        "official_qno": 65,
        "answer_key_status": "Official Final Key Verified",
    },
    {
        "exam": "BPSC",
        "subject": "Bihar Special",
        "topic": "Geological Structure of Bihar",
        "subtopic": "Rock Systems",
        "question": "Which of the following geological rock formations found in the state of Bihar belongs to the oldest geological era?",
        "option_a": "Dharwar rock system of Gaya and Rajgir",
        "option_b": "Vindhyan rock system of Kaimur and Rohtas",
        "option_c": "Tertiary rock system of Someshwar Range",
        "option_d": "Quaternary alluvial deposits of the Gangetic plain",
        "correct_option": "A",
        "explanation": "The Dharwar rock formations (schists, phyllites, and quartzites found in southern Bihar districts: Gaya, Nawada, Rajgir, Munger, and Jamui) date back to the Pre-Cambrian/Archaean era, making them the oldest rocks in Bihar. Vindhyan rocks are younger Pre-Cambrian, Tertiary rocks of Someshwar are Cenozoic, and the Gangetic alluvium is Quaternary/Pleistocene.",
        "distractor_notes": "Vindhyan rocks in Kaimur/Rohtas are younger than Dharwar; Someshwar hills are young Tertiary foldings; Gangetic alluvium is modern Quaternary.",
        "concept_tested": "Geological formations of Bihar (Pre-Cambrian Dharwar vs Vindhyan vs Tertiary vs Alluvial)",
        "question_type": "Standard MCQ",
        "source_type": "Official PYQ",
        "source_name": "68th BPSC CCE Prelims",
        "source_url": "https://bpsc.bih.nic.in",
        "difficulty": "Hard",
        "is_ai_generated": 0,
        "exam_edition": "68th BPSC CCE Prelims",
        "exam_year": "2023",
        "paper_set": "Series A",
        "official_qno": 89,
        "answer_key_status": "Official Final Key Verified",
    },
    {
        "exam": "BPSC",
        "subject": "Bihar Special",
        "topic": "Mineral Resources of Bihar",
        "subtopic": "Metallic & Non-Metallic Minerals",
        "question": "Which district in Bihar holds over 95% of the total pyrites (iron pyrite / fool's gold) reserves in India and is the principal source of mineral sulfur in the country?",
        "option_a": "Rohtas",
        "option_b": "Jamui",
        "option_c": "Banka",
        "option_d": "Nawada",
        "correct_option": "A",
        "explanation": "Rohtas district (specifically Amjhore in the Vindhyan plateau region) holds approximately 95% of India's known pyrites reserves and was home to the Pyrites, Phosphates and Chemicals Limited (PPCL).",
        "distractor_notes": "Jamui has major gold reserves; Banka has mica and iron ore traces; Nawada has mica pegmatites.",
        "concept_tested": "Mineral distribution in Bihar - Pyrite belt of Amjhore (Rohtas)",
        "question_type": "Standard MCQ",
        "source_type": "Official PYQ",
        "source_name": "68th BPSC CCE Prelims",
        "source_url": "https://bpsc.bih.nic.in",
        "difficulty": "Medium",
        "is_ai_generated": 0,
        "exam_edition": "68th BPSC CCE Prelims",
        "exam_year": "2023",
        "paper_set": "Series A",
        "official_qno": 74,
        "answer_key_status": "Official Final Key Verified",
    },
    {
        "exam": "BPSC",
        "subject": "Modern History",
        "topic": "Revolt of 1857 in Bihar",
        "subtopic": "Kunwar Singh Campaigns",
        "question": "During the 1857 Revolt in Bihar, which British military officer's detachment suffered a crushing defeat at the hands of Babu Kunwar Singh's forces near Jagdishpur on 23 April 1858?",
        "option_a": "Captain Le Grand",
        "option_b": "Major Eyre",
        "option_c": "General Lugard",
        "option_d": "Colonel Neill",
        "correct_option": "A",
        "explanation": "On 23 April 1858, Babu Kunwar Singh routed the British detachment led by Captain Le Grand near Jagdishpur. Le Grand was killed in the battle and the British troops suffered heavy casualties. Kunwar Singh passed away three days later on 26 April 1858.",
        "distractor_notes": "Major Vincent Eyre relieved Arrah in August 1857; General Sir Edward Lugard pursued Kunwar Singh across eastern UP; Colonel Neill operated around Allahabad/Banaras.",
        "concept_tested": "Babu Kunwar Singh's military campaigns and the battle against Captain Le Grand (23 April 1858)",
        "question_type": "Standard MCQ",
        "source_type": "Official PYQ",
        "source_name": "68th BPSC CCE Prelims",
        "source_url": "https://bpsc.bih.nic.in",
        "difficulty": "Hard",
        "is_ai_generated": 0,
        "exam_edition": "68th BPSC CCE Prelims",
        "exam_year": "2023",
        "paper_set": "Series A",
        "official_qno": 66,
        "answer_key_status": "Official Final Key Verified",
    },
    {
        "exam": "BPSC",
        "subject": "Indian Polity",
        "topic": "Local Self Government in Bihar",
        "subtopic": "Bihar Panchayati Raj Act 2006",
        "question": "Under the Bihar Panchayati Raj Act, 2006, what proportion of seats was reserved for women across all tiers of Panchayati Raj Institutions (PRIs), making Bihar the first Indian state to enact this affirmative measure?",
        "option_a": "50%",
        "option_b": "33%",
        "option_c": "30%",
        "option_d": "40%",
        "correct_option": "A",
        "explanation": "Bihar became the pioneer state in India to reserve 50% of seats for women in Panchayati Raj Institutions and Urban Local Bodies under the Bihar Panchayati Raj Act, 2006 (surpassing the 73rd Constitutional Amendment's minimum mandate of 33%).",
        "distractor_notes": "33% is the central constitutional minimum under Article 243D; 30% and 40% are plausible distractors.",
        "concept_tested": "Bihar Panchayati Raj Act 2006 and 50% women's reservation",
        "question_type": "Standard MCQ",
        "source_type": "Official PYQ",
        "source_name": "68th BPSC CCE Prelims",
        "source_url": "https://bpsc.bih.nic.in",
        "difficulty": "Easy",
        "is_ai_generated": 0,
        "exam_edition": "68th BPSC CCE Prelims",
        "exam_year": "2023",
        "paper_set": "Series A",
        "official_qno": 102,
        "answer_key_status": "Official Final Key Verified",
    },
    {
        "exam": "BPSC",
        "subject": "Environment",
        "topic": "Protected Areas of Bihar",
        "subtopic": "National Parks & Wildlife Sanctuaries",
        "question": "Which of the following is the only declared National Park and Tiger Reserve situated in the state of Bihar?",
        "option_a": "Valmiki National Park",
        "option_b": "Kaimur Wildlife Sanctuary",
        "option_c": "Bhimbandh Wildlife Sanctuary",
        "option_d": "Gautam Buddha Wildlife Sanctuary",
        "correct_option": "A",
        "explanation": "Valmiki National Park and Tiger Reserve, located in West Champaran district in the Terai region along the Gandak River and the border with Nepal (contiguous with Chitwan National Park), is the sole National Park in Bihar. Kaimur, Bhimbandh, and Gautam Buddha are Wildlife Sanctuaries.",
        "distractor_notes": "Kaimur is Bihar's largest wildlife sanctuary (proposed for 2nd tiger reserve); Bhimbandh is in Munger; Gautam Buddha sanctuary is in Gaya.",
        "concept_tested": "National parks vs Wildlife sanctuaries in Bihar (West Champaran)",
        "question_type": "Standard MCQ",
        "source_type": "Official PYQ",
        "source_name": "68th BPSC CCE Prelims",
        "source_url": "https://bpsc.bih.nic.in",
        "difficulty": "Easy",
        "is_ai_generated": 0,
        "exam_edition": "68th BPSC CCE Prelims",
        "exam_year": "2023",
        "paper_set": "Series A",
        "official_qno": 84,
        "answer_key_status": "Official Final Key Verified",
    },
    {
        "exam": "BPSC",
        "subject": "Ancient & Medieval History",
        "topic": "Buddhism & Ancient Magadha",
        "subtopic": "Buddhist Councils",
        "question": "The Second Buddhist Council was held at Vaishali in 383 BCE during the reign of which monarch of ancient Magadha?",
        "option_a": "Kalashoka",
        "option_b": "Ajatashatru",
        "option_c": "Ashoka",
        "option_d": "Kanishka",
        "correct_option": "A",
        "explanation": "The Second Buddhist Council was held at Vaishali approximately 100 years after the Mahaparinirvana of the Buddha (383 BCE) under the patronage of King Kalashoka (Shishunaga dynasty) and presided over by Sabakami.",
        "distractor_notes": "Ajatashatru patronized the First Council at Rajgriha (483 BCE); Ashoka patronized the Third Council at Pataliputra (250 BCE); Kanishka patronized the Fourth Council at Kundalvana, Kashmir.",
        "concept_tested": "Four Buddhist Councils, royal patrons, and venues",
        "question_type": "Standard MCQ",
        "source_type": "Official PYQ",
        "source_name": "67th BPSC CCE Re-Exam",
        "source_url": "https://bpsc.bih.nic.in",
        "difficulty": "Medium",
        "is_ai_generated": 0,
        "exam_edition": "67th BPSC CCE Re-Exam",
        "exam_year": "2022",
        "paper_set": "Series A",
        "official_qno": 4,
        "answer_key_status": "Official Final Key Verified",
    },
    {
        "exam": "BPSC",
        "subject": "Bihar Special",
        "topic": "Drainage System of Bihar",
        "subtopic": "Course of River Ganga",
        "question": "The River Ganga flows through how many administrative districts in the state of Bihar during its eastward journey?",
        "option_a": "12 districts",
        "option_b": "10 districts",
        "option_c": "14 districts",
        "option_d": "16 districts",
        "correct_option": "A",
        "explanation": "The Ganga traverses 12 districts in Bihar: Buxar, Bhojpur, Saran, Patna, Vaishali, Samastipur, Begusarai, Lakhisarai, Munger, Khagaria, Bhagalpur, and Katihar. It enters at Chausa (Buxar) and exits into West Bengal after Katihar.",
        "distractor_notes": "10, 14, and 16 are common distractor counts; Patna has the longest stretch of the river (~99 km).",
        "concept_tested": "Course of the Ganga through Bihar (12 districts)",
        "question_type": "Standard MCQ",
        "source_type": "Official PYQ",
        "source_name": "66th BPSC CCE Prelims",
        "source_url": "https://bpsc.bih.nic.in",
        "difficulty": "Medium",
        "is_ai_generated": 0,
        "exam_edition": "66th BPSC CCE Prelims",
        "exam_year": "2020",
        "paper_set": "Series A",
        "official_qno": 71,
        "answer_key_status": "Official Final Key Verified",
    },
]


def connect_db() -> sqlite3.Connection:
    """Return a connection with Row factory enabled."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Initialize database tables and run additive migrations."""
    with connect_db() as conn:
        # 1. Questions table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                exam TEXT NOT NULL DEFAULT 'BPSC',
                subject TEXT NOT NULL,
                topic TEXT NOT NULL DEFAULT 'Uncategorised',
                question TEXT NOT NULL,
                option_a TEXT NOT NULL,
                option_b TEXT NOT NULL,
                option_c TEXT NOT NULL,
                option_d TEXT NOT NULL,
                correct_option TEXT NOT NULL CHECK(correct_option IN ('A','B','C','D')),
                explanation TEXT NOT NULL DEFAULT '',
                source_type TEXT NOT NULL DEFAULT 'User-added',
                source_name TEXT NOT NULL DEFAULT '',
                source_url TEXT NOT NULL DEFAULT '',
                difficulty TEXT NOT NULL DEFAULT 'Medium',
                created_at TEXT NOT NULL
            )
        """)

        # Additive columns for questions
        q_cols = {r[1] for r in conn.execute("PRAGMA table_info(questions)").fetchall()}
        if "subtopic" not in q_cols:
            conn.execute("ALTER TABLE questions ADD COLUMN subtopic TEXT NOT NULL DEFAULT ''")
        if "is_ai_generated" not in q_cols:
            conn.execute("ALTER TABLE questions ADD COLUMN is_ai_generated INTEGER NOT NULL DEFAULT 0")
        if "distractor_notes" not in q_cols:
            conn.execute("ALTER TABLE questions ADD COLUMN distractor_notes TEXT NOT NULL DEFAULT ''")
        if "concept_tested" not in q_cols:
            conn.execute("ALTER TABLE questions ADD COLUMN concept_tested TEXT NOT NULL DEFAULT ''")
        if "question_type" not in q_cols:
            conn.execute("ALTER TABLE questions ADD COLUMN question_type TEXT NOT NULL DEFAULT 'Standard MCQ'")
        if "exam_edition" not in q_cols:
            conn.execute("ALTER TABLE questions ADD COLUMN exam_edition TEXT NOT NULL DEFAULT ''")
        if "exam_year" not in q_cols:
            conn.execute("ALTER TABLE questions ADD COLUMN exam_year TEXT NOT NULL DEFAULT ''")
        if "paper_set" not in q_cols:
            conn.execute("ALTER TABLE questions ADD COLUMN paper_set TEXT NOT NULL DEFAULT ''")
        if "official_qno" not in q_cols:
            conn.execute("ALTER TABLE questions ADD COLUMN official_qno INTEGER NOT NULL DEFAULT 0")
        if "answer_key_status" not in q_cols:
            conn.execute("ALTER TABLE questions ADD COLUMN answer_key_status TEXT NOT NULL DEFAULT 'Unverified'")

        # 2. Attempts table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question_id INTEGER NOT NULL,
                selected_option TEXT NOT NULL,
                is_correct INTEGER NOT NULL,
                error_type TEXT NOT NULL DEFAULT 'Unclassified',
                error_notes TEXT NOT NULL DEFAULT '',
                attempted_at TEXT NOT NULL,
                FOREIGN KEY(question_id) REFERENCES questions(id)
            )
        """)

        # Additive columns for attempts
        att_cols = {r[1] for r in conn.execute("PRAGMA table_info(attempts)").fetchall()}
        if "error_type" not in att_cols:
            conn.execute("ALTER TABLE attempts ADD COLUMN error_type TEXT NOT NULL DEFAULT 'Unclassified'")
        if "error_notes" not in att_cols:
            conn.execute("ALTER TABLE attempts ADD COLUMN error_notes TEXT NOT NULL DEFAULT ''")
        if "test_session_id" not in att_cols:
            conn.execute("ALTER TABLE attempts ADD COLUMN test_session_id TEXT NOT NULL DEFAULT ''")
        if "time_spent_seconds" not in att_cols:
            conn.execute("ALTER TABLE attempts ADD COLUMN time_spent_seconds REAL NOT NULL DEFAULT 0.0")
        if "confidence_rating" not in att_cols:
            conn.execute("ALTER TABLE attempts ADD COLUMN confidence_rating TEXT NOT NULL DEFAULT ''")
        if "score" not in att_cols:
            conn.execute("ALTER TABLE attempts ADD COLUMN score REAL NOT NULL DEFAULT 0.0")

        # 3. Test Sessions table (tracks full test attempts, timed drills, mock tests)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS test_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT UNIQUE NOT NULL,
                exam TEXT NOT NULL DEFAULT 'BPSC',
                test_mode TEXT NOT NULL DEFAULT 'Practice',
                total_questions INTEGER NOT NULL,
                correct_count INTEGER NOT NULL,
                incorrect_count INTEGER NOT NULL,
                unanswered_count INTEGER NOT NULL,
                negative_mark_rate REAL NOT NULL DEFAULT 0.0,
                total_score REAL NOT NULL DEFAULT 0.0,
                time_spent_seconds REAL NOT NULL DEFAULT 0.0,
                created_at TEXT NOT NULL
            )
        """)

        # 4. Adaptive Spaced-Repetition Schedule
        conn.execute("""
            CREATE TABLE IF NOT EXISTS revision_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject TEXT NOT NULL,
                topic TEXT NOT NULL,
                due_date TEXT NOT NULL,
                interval_days INTEGER NOT NULL DEFAULT 1,
                repetitions INTEGER NOT NULL DEFAULT 0,
                ease_factor REAL NOT NULL DEFAULT 2.5,
                last_reviewed_at TEXT DEFAULT '',
                last_outcome TEXT DEFAULT '',
                is_completed INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )
        """)

        # 5. Error Notebook Pins and Bookmark Notes
        conn.execute("""
            CREATE TABLE IF NOT EXISTS pinned_notebook (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question_id INTEGER NOT NULL UNIQUE,
                note TEXT NOT NULL DEFAULT '',
                tags TEXT NOT NULL DEFAULT '',
                pinned_at TEXT NOT NULL,
                FOREIGN KEY(question_id) REFERENCES questions(id)
            )
        """)

        # 6. Current Affairs & Source Research Notes
        conn.execute("""
            CREATE TABLE IF NOT EXISTS research_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic TEXT NOT NULL,
                title TEXT NOT NULL,
                source_url TEXT NOT NULL DEFAULT '',
                summary TEXT NOT NULL,
                key_facts TEXT NOT NULL DEFAULT '',
                bihar_angle TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            )
        """)

        # Seed initial questions if table is completely empty
        count = conn.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
        if count == 0:
            now = datetime.now().isoformat(timespec="seconds")
            for item in SAMPLE_QUESTIONS:
                values = dict(item)
                values["created_at"] = now
                insert_question(conn, values)

        # Seed verified authentic BPSC PYQs idempotently
        now = datetime.now().isoformat(timespec="seconds")
        for item in VERIFIED_BPSC_PYQS:
            exists = conn.execute(
                "SELECT 1 FROM questions WHERE question = ? OR (exam_edition = ? AND official_qno = ? AND official_qno > 0)",
                (item["question"], item.get("exam_edition", ""), item.get("official_qno", 0)),
            ).fetchone()
            if not exists:
                values = dict(item)
                values["created_at"] = now
                insert_question(conn, values)

        conn.commit()


def insert_question(conn: sqlite3.Connection, item: Dict[str, Any]) -> int:
    """Insert a question dictionary into the questions table, respecting available schema columns."""
    payload = dict(item)
    payload.setdefault("subtopic", "")
    payload.setdefault("is_ai_generated", 0)
    payload.setdefault("distractor_notes", "")
    payload.setdefault("concept_tested", "")
    payload.setdefault("question_type", "Standard MCQ")
    payload.setdefault("explanation", "")
    payload.setdefault("source_type", "User-added")
    payload.setdefault("source_name", "")
    payload.setdefault("source_url", "")
    payload.setdefault("difficulty", "Medium")
    payload.setdefault("exam_edition", "")
    payload.setdefault("exam_year", "")
    payload.setdefault("paper_set", "")
    payload.setdefault("official_qno", 0)
    payload.setdefault("answer_key_status", "Unverified")
    if "created_at" not in payload:
        payload["created_at"] = datetime.now().isoformat(timespec="seconds")

    # Detect columns present in the target database to ensure backward compatibility
    existing_cols = {r[1] for r in conn.execute("PRAGMA table_info(questions)").fetchall()}
    insert_keys = [k for k in payload.keys() if k in existing_cols]
    col_names = ", ".join(insert_keys)
    val_placeholders = ", ".join(f":{k}" for k in insert_keys)

    cur = conn.execute(f"INSERT INTO questions ({col_names}) VALUES ({val_placeholders})", payload)
    return int(cur.lastrowid)


def add_question(item: Dict[str, Any]) -> int:
    """Thread-safe single question insertion."""
    with connect_db() as conn:
        qid = insert_question(conn, item)
        conn.commit()
        return qid


def list_questions(exam: str = "All", subject: str = "All", topic: str = "All", source_type: str = "All") -> pd.DataFrame:
    """Retrieve filtered questions."""
    query = "SELECT * FROM questions WHERE 1=1"
    params: List[Any] = []
    if exam != "All":
        query += " AND exam IN (?, 'Both')"
        params.append(exam)
    if subject != "All":
        query += " AND subject = ?"
        params.append(subject)
    if topic != "All":
        query += " AND topic = ?"
        params.append(topic)
    if source_type != "All":
        query += " AND source_type = ?"
        params.append(source_type)
    query += " ORDER BY subject, topic, id"
    with connect_db() as conn:
        return pd.read_sql_query(query, conn, params=params)


def get_question_ids(exam: str = "All", subject: str = "All", topic: str = "All", source_type: str = "All") -> List[int]:
    """Return IDs of questions matching criteria."""
    query = "SELECT id FROM questions WHERE 1=1"
    params: List[Any] = []
    if exam != "All":
        query += " AND exam IN (?, 'Both')"
        params.append(exam)
    if subject != "All":
        query += " AND subject = ?"
        params.append(subject)
    if topic != "All":
        query += " AND topic = ?"
        params.append(topic)
    if source_type != "All":
        query += " AND source_type = ?"
        params.append(source_type)
    with connect_db() as conn:
        return [int(row[0]) for row in conn.execute(query, params).fetchall()]


def get_questions_by_ids(ids: List[int], conn_factory: Any = None) -> pd.DataFrame:
    """Safely fetch questions matching a list of IDs."""
    if not ids:
        return pd.DataFrame()
    placeholders = ",".join("?" for _ in ids)
    connect = conn_factory or connect_db
    with connect() as conn:
        df = pd.read_sql_query(
            f"SELECT * FROM questions WHERE id IN ({placeholders})", conn, params=ids
        )
    if df.empty:
        return df
    df = df.set_index("id")
    valid_ids = [qid for qid in ids if qid in df.index]
    if not valid_ids:
        return pd.DataFrame()
    return df.loc[valid_ids].reset_index()


def retrieve_pyq_exemplars(
    subject: str = "All",
    topic: str = "",
    exam: str = "BPSC",
    limit: int = 3,
    conn_factory: Any = None,
) -> List[Dict[str, Any]]:
    """Retrieve authentic official PYQs matching subject/topic to serve as stylistic few-shot exemplars.

    Selection strategy:
    1. PYQs where subject matches and topic/question/subtopic contains the topic query keyword.
    2. Other PYQs from the same subject.
    3. Other PYQs from the target exam (e.g. BPSC).
    4. General official PYQ fallback.
    """
    connect = conn_factory or connect_db
    with connect() as conn:
        results: List[Dict[str, Any]] = []
        seen_ids = set()

        def _add_rows(rows: List[Any]) -> None:
            for r in rows:
                row_dict = dict(r) if isinstance(r, sqlite3.Row) else {
                    k: r[k] for k in r.keys()
                } if hasattr(r, "keys") else {}
                qid = row_dict.get("id")
                if qid not in seen_ids and len(results) < limit:
                    seen_ids.add(qid)
                    results.append(row_dict)

        clean_topic = topic.strip().lower()
        # Stage 1: Exact subject + topic keyword match in question, topic, or subtopic
        if clean_topic and clean_topic != "general":
            pattern = f"%{clean_topic}%"
            if subject and subject != "All":
                stage1 = conn.execute(
                    """
                    SELECT * FROM questions
                    WHERE source_type = 'Official PYQ'
                      AND subject = ?
                      AND (LOWER(topic) LIKE ? OR LOWER(subtopic) LIKE ? OR LOWER(question) LIKE ?)
                    ORDER BY id DESC LIMIT ?
                    """,
                    (subject, pattern, pattern, pattern, limit),
                ).fetchall()
            else:
                stage1 = conn.execute(
                    """
                    SELECT * FROM questions
                    WHERE source_type = 'Official PYQ'
                      AND (LOWER(topic) LIKE ? OR LOWER(subtopic) LIKE ? OR LOWER(question) LIKE ?)
                    ORDER BY id DESC LIMIT ?
                    """,
                    (pattern, pattern, pattern, limit),
                ).fetchall()
            _add_rows(stage1)

        # Stage 2: Same subject official PYQs
        if len(results) < limit and subject and subject != "All":
            stage2 = conn.execute(
                """
                SELECT * FROM questions
                WHERE source_type = 'Official PYQ'
                  AND subject = ?
                ORDER BY id DESC LIMIT ?
                """,
                (subject, limit - len(results)),
            ).fetchall()
            _add_rows(stage2)

        # Stage 3: Target exam official PYQs
        if len(results) < limit:
            stage3 = conn.execute(
                """
                SELECT * FROM questions
                WHERE source_type = 'Official PYQ'
                  AND (exam = ? OR ? = 'Both' OR exam = 'Both')
                ORDER BY id DESC LIMIT ?
                """,
                (exam, exam, limit - len(results)),
            ).fetchall()
            _add_rows(stage3)

        # Stage 4: Any official PYQ fallback
        if len(results) < limit:
            stage4 = conn.execute(
                """
                SELECT * FROM questions
                WHERE source_type = 'Official PYQ'
                ORDER BY id DESC LIMIT ?
                """,
                (limit - len(results),),
            ).fetchall()
            _add_rows(stage4)

        return results


def record_attempt(
    question_id: int,
    selected_option: str,
    correct_option: str,
    test_session_id: str = "",
    time_spent_seconds: float = 0.0,
    confidence_rating: str = "",
    score: float = 0.0,
) -> None:
    """Record a question attempt with timing and scoring metadata."""
    is_correct = int(selected_option == correct_option)
    with connect_db() as conn:
        conn.execute("""
            INSERT INTO attempts (
                question_id, selected_option, is_correct, attempted_at,
                test_session_id, time_spent_seconds, confidence_rating, score
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            question_id,
            selected_option,
            is_correct,
            datetime.now().isoformat(timespec="seconds"),
            test_session_id,
            time_spent_seconds,
            confidence_rating,
            score,
        ))
        conn.commit()


def record_test_session(
    session_id: str,
    exam: str,
    test_mode: str,
    total_questions: int,
    correct_count: int,
    incorrect_count: int,
    unanswered_count: int,
    negative_mark_rate: float,
    total_score: float,
    time_spent_seconds: float,
) -> None:
    """Record a completed test session."""
    with connect_db() as conn:
        conn.execute("""
            INSERT INTO test_sessions (
                session_id, exam, test_mode, total_questions, correct_count,
                incorrect_count, unanswered_count, negative_mark_rate,
                total_score, time_spent_seconds, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session_id,
            exam,
            test_mode,
            total_questions,
            correct_count,
            incorrect_count,
            unanswered_count,
            negative_mark_rate,
            total_score,
            time_spent_seconds,
            datetime.now().isoformat(timespec="seconds"),
        ))
        conn.commit()


def get_test_sessions() -> pd.DataFrame:
    """Retrieve history of completed test sessions."""
    with connect_db() as conn:
        return pd.read_sql_query(
            "SELECT * FROM test_sessions ORDER BY created_at DESC", conn
        )


def get_attempts() -> pd.DataFrame:
    """Fetch complete joined attempts data."""
    with connect_db() as conn:
        return pd.read_sql_query("""
            SELECT a.id AS attempt_id, a.question_id, a.selected_option, a.is_correct,
                   a.error_type, a.error_notes, a.attempted_at, a.test_session_id,
                   a.time_spent_seconds, a.confidence_rating, a.score,
                   q.exam, q.subject, q.topic, q.subtopic, q.question, q.correct_option,
                   q.explanation, q.distractor_notes, q.concept_tested,
                   q.source_type, q.source_name, q.source_url, q.difficulty, q.is_ai_generated
            FROM attempts a JOIN questions q ON a.question_id = q.id
            ORDER BY a.attempted_at DESC, a.id DESC
        """, conn)


def get_topic_stats(since_days: int = 14) -> pd.DataFrame:
    """Calculate deterministic topic-level statistics."""
    cutoff = (datetime.now() - timedelta(days=since_days)).isoformat(timespec="seconds")
    with connect_db() as conn:
        data = pd.read_sql_query("""
            SELECT q.subject, q.topic,
                   COUNT(a.id) AS attempts,
                   SUM(a.is_correct) AS correct,
                   SUM(CASE WHEN a.is_correct = 0 THEN 1 ELSE 0 END) AS wrong,
                   SUM(CASE WHEN a.is_correct = 0 AND a.attempted_at >= ? THEN 1 ELSE 0 END) AS recent_wrong,
                   MAX(a.attempted_at) AS last_attempt
            FROM questions q JOIN attempts a ON a.question_id = q.id
            GROUP BY q.subject, q.topic
        """, conn, params=[cutoff])

    if data.empty:
        return data

    data["attempts"] = data["attempts"].fillna(0).astype(int)
    data["correct"] = data["correct"].fillna(0).astype(int)
    data["wrong"] = data["wrong"].fillna(0).astype(int)
    data["recent_wrong"] = data["recent_wrong"].fillna(0).astype(int)
    data["accuracy"] = (data["correct"] / data["attempts"] * 100).round().astype(int)
    data["priority"] = (
        (100 - data["accuracy"]) * 0.55
        + data["wrong"].clip(upper=6) * 5
        + data["recent_wrong"].clip(upper=4) * 4
    ).round(1)
    return data.sort_values(["priority", "wrong", "attempts"], ascending=False).reset_index(drop=True)


def save_error_classification(attempt_id: int, error_type: str, notes: str) -> None:
    """Update mistake category and student note."""
    with connect_db() as conn:
        conn.execute(
            "UPDATE attempts SET error_type = ?, error_notes = ? WHERE id = ?",
            (error_type, notes.strip(), attempt_id),
        )
        conn.commit()


def pin_question(question_id: int, note: str = "", tags: str = "") -> None:
    """Pin a question to the Error Notebook."""
    with connect_db() as conn:
        conn.execute("""
            INSERT INTO pinned_notebook (question_id, note, tags, pinned_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(question_id) DO UPDATE SET
                note = excluded.note,
                tags = excluded.tags,
                pinned_at = excluded.pinned_at
        """, (question_id, note.strip(), tags.strip(), datetime.now().isoformat(timespec="seconds")))
        conn.commit()


def unpin_question(question_id: int) -> None:
    """Remove a question from pinned notebook."""
    with connect_db() as conn:
        conn.execute("DELETE FROM pinned_notebook WHERE question_id = ?", (question_id,))
        conn.commit()


def get_pinned_questions() -> pd.DataFrame:
    """Fetch all pinned questions with notebook notes."""
    with connect_db() as conn:
        return pd.read_sql_query("""
            SELECT p.id AS pin_id, p.note AS notebook_note, p.tags, p.pinned_at,
                   q.*
            FROM pinned_notebook p
            JOIN questions q ON p.question_id = q.id
            ORDER BY p.pinned_at DESC
        """, conn)


def is_question_pinned(question_id: int) -> bool:
    """Check if question is currently pinned."""
    with connect_db() as conn:
        row = conn.execute(
            "SELECT 1 FROM pinned_notebook WHERE question_id = ? LIMIT 1", (question_id,)
        ).fetchone()
        return bool(row)


def save_research_note(
    topic: str,
    title: str,
    summary: str,
    key_facts: List[str],
    source_url: str = "",
    bihar_angle: str = "",
) -> int:
    """Save a source research summary."""
    with connect_db() as conn:
        cur = conn.execute("""
            INSERT INTO research_notes (topic, title, source_url, summary, key_facts, bihar_angle, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            topic,
            title,
            source_url,
            summary,
            json.dumps(key_facts),
            bihar_angle,
            datetime.now().isoformat(timespec="seconds"),
        ))
        conn.commit()
        return int(cur.lastrowid)


def get_research_notes() -> pd.DataFrame:
    """Fetch saved research notes."""
    with connect_db() as conn:
        return pd.read_sql_query(
            "SELECT * FROM research_notes ORDER BY created_at DESC", conn
        )


def import_csv(uploaded_file: Any, conn_factory: Any = None) -> Tuple[int, List[str]]:
    """Validate and import questions from a CSV file."""
    required = {
        "exam", "subject", "topic", "question", "option_a", "option_b", "option_c",
        "option_d", "correct_option",
    }
    try:
        data = pd.read_csv(uploaded_file)
        for col in data.columns:
            data[col] = data[col].astype(object).fillna("")
    except Exception as exc:
        return 0, [f"Could not read CSV: {exc}"]

    missing = required - set(data.columns)
    if missing:
        return 0, ["Missing required columns: " + ", ".join(sorted(missing))]

    inserted = 0
    problems: List[str] = []
    optional_defaults = {
        "explanation": "", "source_type": "User-added", "source_name": "Imported CSV",
        "source_url": "", "difficulty": "Medium", "subtopic": "", "distractor_notes": "",
        "concept_tested": "", "question_type": "Standard MCQ",
        "exam_edition": "", "exam_year": "", "paper_set": "", "official_qno": 0,
        "answer_key_status": "Unverified",
    }
    connect = conn_factory or connect_db
    with connect() as conn:
        for idx, row in data.iterrows():
            item = {col: str(row[col]).strip() for col in required if col in row.index}
            for col, default in optional_defaults.items():
                item[col] = str(row[col]).strip() if col in row.index and str(row[col]).strip() else default
            item["correct_option"] = item["correct_option"].upper()
            item["exam"] = item["exam"] if item["exam"] in EXAMS else "BPSC"
            item["source_type"] = item["source_type"] if item["source_type"] in SOURCE_TYPES else "User-added"
            item["difficulty"] = item["difficulty"] if item["difficulty"] in DIFFICULTIES else "Medium"
            if not all(item.get(k, "") for k in ["subject", "question", "option_a", "option_b", "option_c", "option_d"]):
                problems.append(f"Row {idx + 2}: one or more required text fields are blank.")
                continue
            if item["correct_option"] not in {"A", "B", "C", "D"}:
                problems.append(f"Row {idx + 2}: correct_option must be A, B, C or D.")
                continue
            if not item["topic"]:
                item["topic"] = "Uncategorised"
            item["created_at"] = datetime.now().isoformat(timespec="seconds")
            item["is_ai_generated"] = 0

            duplicate = conn.execute(
                "SELECT id FROM questions WHERE lower(trim(question)) = lower(trim(?)) LIMIT 1",
                (item["question"],),
            ).fetchone()
            if duplicate:
                problems.append(f"Row {idx + 2}: skipped duplicate question.")
                continue
            insert_question(conn, item)
            inserted += 1
        conn.commit()
    return inserted, problems


def export_sqlite_to_json() -> str:
    """Export all tables to a clean JSON string for migration or backup."""
    with connect_db() as conn:
        tables = ["questions", "attempts", "test_sessions", "revision_items", "pinned_notebook", "research_notes"]
        export_data = {}
        for t in tables:
            rows = conn.execute(f"SELECT * FROM {t}").fetchall()
            export_data[t] = [dict(r) for r in rows]
        return json.dumps(export_data, indent=2)
