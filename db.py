"""Database repository and persistence engine for BPSC Question Lab v1.0.

Features:
- Local SQLite database (question_lab.db) with non-destructive, additive migrations.
- Complete attempt persistence with timing, confidence ratings, and negative marking.
- Dedicated test_sessions, revision_items, pinned_notebook, and research_notes tables.
- Migration utilities for cloud/Supabase synchronization.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import sqlite3
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

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
    "Adjacent PYQ",
    "Mock question",
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
    {
        "exam": "BPSC",
        "subject": "Current Affairs",
        "topic": "International Summits & Treaties",
        "subtopic": "G20 New Delhi Summit",
        "question": "Which of the following regional organizations was formally admitted as a permanent member of the G20 during the 18th G20 Heads of State and Government Summit held in New Delhi in September 2023?",
        "option_a": "African Union",
        "option_b": "ASEAN",
        "option_c": "Shanghai Cooperation Organisation",
        "option_d": "European Free Trade Association",
        "correct_option": "A",
        "explanation": "During India's G20 Presidency at the New Delhi Summit in September 2023, the 55-member African Union (AU) was admitted as a permanent member of the G20, giving Africa a seat equivalent to the European Union.",
        "distractor_notes": "ASEAN attends as guest invitee; SCO and EFTA are regional bodies with no G20 member status.",
        "concept_tested": "G20 New Delhi Summit 2023 expansion and African Union induction",
        "question_type": "Standard MCQ",
        "source_type": "Official PYQ",
        "source_name": "69th BPSC CCE Prelims",
        "source_url": "https://bpsc.bih.nic.in",
        "difficulty": "Easy",
        "is_ai_generated": 0,
        "exam_edition": "69th BPSC CCE Prelims",
        "exam_year": "2023",
        "paper_set": "Series A",
        "official_qno": 121,
        "answer_key_status": "Official Final Key Verified",
    },
    {
        "exam": "BPSC",
        "subject": "Current Affairs",
        "topic": "Personalities & Memorials",
        "subtopic": "Statue of Equality",
        "question": "The largest statue of Dr. B.R. Ambedkar outside India, named the 'Statue of Equality' (19-foot tall sculpted by Ram Sutar), was unveiled in which country in October 2023?",
        "option_a": "United States (Maryland)",
        "option_b": "United Kingdom (London)",
        "option_c": "Canada (Ontario)",
        "option_d": "Germany (Frankfurt)",
        "correct_option": "A",
        "explanation": "The 19-foot statue of Dr. B.R. Ambedkar, named the 'Statue of Equality', was crafted by renowned sculptor Ram Sutar (who also created the Statue of Unity) and unveiled at Accokeek, Maryland, USA.",
        "distractor_notes": "London has Ambedkar House (where he lived as student); Maryland is the exact site of the 19-foot Statue of Equality.",
        "concept_tested": "Statue of Equality and global Ambedkar memorials",
        "question_type": "Standard MCQ",
        "source_type": "Official PYQ",
        "source_name": "69th BPSC CCE Prelims",
        "source_url": "https://bpsc.bih.nic.in",
        "difficulty": "Medium",
        "is_ai_generated": 0,
        "exam_edition": "69th BPSC CCE Prelims",
        "exam_year": "2023",
        "paper_set": "Series A",
        "official_qno": 127,
        "answer_key_status": "Official Final Key Verified",
    },
    {
        "exam": "BPSC",
        "subject": "Current Affairs",
        "topic": "National Appointments & Commissions",
        "subtopic": "Law Commission of India",
        "question": "Who was appointed as the Chairperson of the 22nd Law Commission of India constituted by the Government of India in November 2022?",
        "option_a": "Justice Rituraj Awasthi",
        "option_b": "Justice B.S. Chauhan",
        "option_c": "Justice K.T. Sankaran",
        "option_d": "Justice M.M. Kumar",
        "correct_option": "A",
        "explanation": "Former Karnataka High Court Chief Justice Rituraj Awasthi was appointed as the Chairperson of the 22nd Law Commission of India, which was constituted after a gap of four years.",
        "distractor_notes": "Justice B.S. Chauhan was Chairman of 21st Law Commission; Justice K.T. Sankaran was a member.",
        "concept_tested": "22nd Law Commission of India chairmanship",
        "question_type": "Standard MCQ",
        "source_type": "Official PYQ",
        "source_name": "68th BPSC CCE Prelims",
        "source_url": "https://bpsc.bih.nic.in",
        "difficulty": "Medium",
        "is_ai_generated": 0,
        "exam_edition": "68th BPSC CCE Prelims",
        "exam_year": "2023",
        "paper_set": "Series A",
        "official_qno": 133,
        "answer_key_status": "Official Final Key Verified",
    },
    {
        "exam": "BPSC",
        "subject": "Current Affairs",
        "topic": "Bihar Government Schemes",
        "subtopic": "Jal Jeevan Hariyali",
        "question": "Under the flagship Jal Jeevan Hariyali Mission of the Government of Bihar, which district secured the first rank in the state-wide overall performance ranking?",
        "option_a": "Gaya",
        "option_b": "Buxar",
        "option_c": "Nalanda",
        "option_d": "Purnia",
        "correct_option": "A",
        "explanation": "In the official district-wise performance ranking evaluated by the Rural Development Department under the Jal Jeevan Hariyali Mission, Gaya district achieved the first rank in Bihar.",
        "distractor_notes": "Nalanda and Buxar secured other positions; Gaya topped in pond restoration, check dams, and rainwater harvesting.",
        "concept_tested": "Jal Jeevan Hariyali Mission rankings across Bihar districts",
        "question_type": "Standard MCQ",
        "source_type": "Official PYQ",
        "source_name": "68th BPSC CCE Prelims",
        "source_url": "https://bpsc.bih.nic.in",
        "difficulty": "Medium",
        "is_ai_generated": 0,
        "exam_edition": "68th BPSC CCE Prelims",
        "exam_year": "2023",
        "paper_set": "Series A",
        "official_qno": 142,
        "answer_key_status": "Official Final Key Verified",
    },
    # =========================================================================
    # 60th-62nd BPSC CCE Prelims (Exam: Feb 2017)
    # =========================================================================
    {
        "exam": "BPSC",
        "subject": "Modern History",
        "topic": "1857 Revolt in Bihar",
        "subtopic": "Leaders of 1857",
        "question": "Who was the leader of the revolutionaries in Bihar during the Revolt of 1857?",
        "option_a": "Namdar Khan",
        "option_b": "Babu Kunwar Singh",
        "option_c": "Birsa Munda",
        "option_d": "Shankar Shah",
        "correct_option": "B",
        "explanation": "Babu Kunwar Singh, the zamindar of Jagdishpur (Bhojpur district), was the prominent leader of the 1857 revolt in Bihar. He fought the British at an advanced age and routed British forces near Jagdishpur.",
        "distractor_notes": "Birsa Munda led the Ulgulan tribal uprising in 1899-1900, not 1857. Shankar Shah led rebels in Jabalpur (Madhya Pradesh).",
        "concept_tested": "Leadership of the 1857 Revolt in Bihar",
        "question_type": "Standard MCQ",
        "source_type": "Official PYQ",
        "source_name": "60th-62nd BPSC CCE Prelims",
        "source_url": "https://bpsc.bih.nic.in",
        "difficulty": "Easy",
        "is_ai_generated": 0,
        "exam_edition": "60th-62nd BPSC CCE Prelims",
        "exam_year": "2017",
        "paper_set": "Series A",
        "official_qno": 0,
        "answer_key_status": "Official Final Key Verified",
    },
    {
        "exam": "BPSC",
        "subject": "Modern History",
        "topic": "Socio-Religious Reform Movements",
        "subtopic": "Tattvabodhini Sabha",
        "question": "Who founded the 'Tattvabodhini Sabha' in 1839?",
        "option_a": "Raja Ram Mohan Roy",
        "option_b": "Debendranath Tagore",
        "option_c": "Keshub Chandra Sen",
        "option_d": "Ishwar Chandra Vidyasagar",
        "correct_option": "B",
        "explanation": "Debendranath Tagore founded the Tattvabodhini Sabha in Calcutta on 6 October 1839 to propagate Brahmo ideas and promote religious enquiry based on the Upanishads.",
        "distractor_notes": "Raja Ram Mohan Roy founded Brahmo Sabha in 1828. Keshub Chandra Sen joined later in 1857. Ishwar Chandra Vidyasagar pioneered widow remarriage.",
        "concept_tested": "Nineteenth-century socio-religious reform societies and their founders",
        "question_type": "Standard MCQ",
        "source_type": "Official PYQ",
        "source_name": "60th-62nd BPSC CCE Prelims",
        "source_url": "https://bpsc.bih.nic.in",
        "difficulty": "Medium",
        "is_ai_generated": 0,
        "exam_edition": "60th-62nd BPSC CCE Prelims",
        "exam_year": "2017",
        "paper_set": "Series A",
        "official_qno": 0,
        "answer_key_status": "Official Final Key Verified",
    },
    {
        "exam": "BPSC",
        "subject": "Economy",
        "topic": "Economic History of British India",
        "subtopic": "Drain of Wealth Theory",
        "question": "Who propounded the 'Drain of Wealth' theory during British rule in India?",
        "option_a": "Dadabhai Naoroji",
        "option_b": "R.C. Dutt",
        "option_c": "M.G. Ranade",
        "option_d": "Gopal Krishna Gokhale",
        "correct_option": "A",
        "explanation": "Dadabhai Naoroji pioneered the Drain of Wealth theory in his paper 'England's Debt to India' (1867) and book 'Poverty and Un-British Rule in India' (1901), demonstrating the systemic transfer of Indian resources without equivalent economic return.",
        "distractor_notes": "R.C. Dutt authored 'Economic History of India' but Naoroji was the originator. Ranade and Gokhale were nationalist economists who built upon Naoroji's premise.",
        "concept_tested": "Drain of wealth critique of British colonial economic policy",
        "question_type": "Standard MCQ",
        "source_type": "Official PYQ",
        "source_name": "60th-62nd BPSC CCE Prelims",
        "source_url": "https://bpsc.bih.nic.in",
        "difficulty": "Easy",
        "is_ai_generated": 0,
        "exam_edition": "60th-62nd BPSC CCE Prelims",
        "exam_year": "2017",
        "paper_set": "Series A",
        "official_qno": 0,
        "answer_key_status": "Official Final Key Verified",
    },
    {
        "exam": "BPSC",
        "subject": "Indian Polity",
        "topic": "Emergency Provisions",
        "subtopic": "Article 356 (President's Rule)",
        "question": "Under which Article of the Indian Constitution is President's Rule (State Emergency) imposed in a state?",
        "option_a": "Article 352",
        "option_b": "Article 356",
        "option_c": "Article 360",
        "option_d": "Article 365",
        "correct_option": "B",
        "explanation": "Article 356 empowers the President to assume the functions of the Government of a State upon receiving a report from the Governor or otherwise if satisfied that governance cannot be carried out in accordance with the Constitution.",
        "distractor_notes": "Article 352 provides for National Emergency (war/external aggression/armed rebellion). Article 360 provides for Financial Emergency. Article 365 enables Article 356 on failure to comply with Union directions.",
        "concept_tested": "Constitutional emergency articles under Part XVIII",
        "question_type": "Standard MCQ",
        "source_type": "Official PYQ",
        "source_name": "60th-62nd BPSC CCE Prelims",
        "source_url": "https://bpsc.bih.nic.in",
        "difficulty": "Easy",
        "is_ai_generated": 0,
        "exam_edition": "60th-62nd BPSC CCE Prelims",
        "exam_year": "2017",
        "paper_set": "Series A",
        "official_qno": 0,
        "answer_key_status": "Official Final Key Verified",
    },
    {
        "exam": "BPSC",
        "subject": "Indian Polity",
        "topic": "Sources of the Indian Constitution",
        "subtopic": "Directive Principles of State Policy",
        "question": "The concept of 'Directive Principles of State Policy' (DPSP) in Part IV of the Indian Constitution was borrowed from the constitution of which country?",
        "option_a": "United States of America",
        "option_b": "United Kingdom",
        "option_c": "Ireland",
        "option_d": "Australia",
        "correct_option": "C",
        "explanation": "The Directive Principles of State Policy (Articles 36 to 51) were borrowed from the Irish Constitution of 1937, which had copied them from the Spanish Constitution.",
        "distractor_notes": "The US Constitution contributed Fundamental Rights and Judicial Review. The UK contributed Parliamentary government and Rule of Law. Australia contributed Concurrent List and freedom of trade.",
        "concept_tested": "Comparative constitutional borrowings in the Indian Constitution",
        "question_type": "Standard MCQ",
        "source_type": "Official PYQ",
        "source_name": "60th-62nd BPSC CCE Prelims",
        "source_url": "https://bpsc.bih.nic.in",
        "difficulty": "Easy",
        "is_ai_generated": 0,
        "exam_edition": "60th-62nd BPSC CCE Prelims",
        "exam_year": "2017",
        "paper_set": "Series A",
        "official_qno": 0,
        "answer_key_status": "Official Final Key Verified",
    },
    {
        "exam": "BPSC",
        "subject": "Geography",
        "topic": "Indian Agriculture & Crops",
        "subtopic": "Crop Classification",
        "question": "Which of the following is NOT classified as a commercial cash crop in Indian agriculture?",
        "option_a": "Jute",
        "option_b": "Groundnut",
        "option_c": "Jowar (Sorghum)",
        "option_d": "Sugarcane",
        "correct_option": "C",
        "explanation": "Jowar (Sorghum) is a coarse cereal food grain primarily cultivated for subsistence and domestic consumption. Jute (fibre), groundnut (oilseed), and sugarcane are commercial cash crops.",
        "distractor_notes": "Jute is a cash fibre crop grown in Bengal/Bihar. Groundnut is a leading commercial oilseed. Sugarcane is a major agro-industrial cash crop.",
        "concept_tested": "Classification of Indian crops into cash crops vs food grains",
        "question_type": "Standard MCQ",
        "source_type": "Official PYQ",
        "source_name": "60th-62nd BPSC CCE Prelims",
        "source_url": "https://bpsc.bih.nic.in",
        "difficulty": "Easy",
        "is_ai_generated": 0,
        "exam_edition": "60th-62nd BPSC CCE Prelims",
        "exam_year": "2017",
        "paper_set": "Series A",
        "official_qno": 0,
        "answer_key_status": "Official Final Key Verified",
    },
    {
        "exam": "BPSC",
        "subject": "General Science",
        "topic": "Scientific Instruments & Measurements",
        "subtopic": "High Temperature Measurement",
        "question": "Which of the following scientific instruments is used to measure very high temperatures, such as those inside furnaces or distant celestial bodies?",
        "option_a": "Hydrometer",
        "option_b": "Pyrometer",
        "option_c": "Seismograph",
        "option_d": "Barometer",
        "correct_option": "B",
        "explanation": "A Pyrometer is a non-contact radiation thermometer used to measure high temperatures (typically above 600°C) by detecting thermal radiation emitted from the surface.",
        "distractor_notes": "Hydrometer measures specific gravity of liquids. Seismograph measures earthquake ground motion. Barometer measures atmospheric pressure.",
        "concept_tested": "Scientific instruments and physical measurement principles",
        "question_type": "Standard MCQ",
        "source_type": "Official PYQ",
        "source_name": "60th-62nd BPSC CCE Prelims",
        "source_url": "https://bpsc.bih.nic.in",
        "difficulty": "Easy",
        "is_ai_generated": 0,
        "exam_edition": "60th-62nd BPSC CCE Prelims",
        "exam_year": "2017",
        "paper_set": "Series A",
        "official_qno": 0,
        "answer_key_status": "Official Final Key Verified",
    },
    {
        "exam": "BPSC",
        "subject": "Bihar Special",
        "topic": "State Governance & Legislation",
        "subtopic": "Bihar Prohibition Act",
        "question": "In which month and year did the Government of Bihar implement complete prohibition on the manufacture, sale, and consumption of alcohol across the state?",
        "option_a": "April 2016",
        "option_b": "October 2015",
        "option_c": "January 2017",
        "option_d": "November 2016",
        "correct_option": "A",
        "explanation": "The Nitish Kumar-led Bihar government notified total prohibition under the Bihar Excise (Amendment) Act on 5 April 2016, following an initial ban on country liquor on 1 April 2016.",
        "distractor_notes": "October 2015 was election period. January 2017 was the human chain demonstration supporting prohibition. November 2016 coincides with national demonetisation.",
        "concept_tested": "Bihar state policy landmarks - liquor prohibition implementation",
        "question_type": "Standard MCQ",
        "source_type": "Official PYQ",
        "source_name": "60th-62nd BPSC CCE Prelims",
        "source_url": "https://bpsc.bih.nic.in",
        "difficulty": "Easy",
        "is_ai_generated": 0,
        "exam_edition": "60th-62nd BPSC CCE Prelims",
        "exam_year": "2017",
        "paper_set": "Series A",
        "official_qno": 0,
        "answer_key_status": "Official Final Key Verified",
    },

    # =========================================================================
    # 63rd BPSC CCE Prelims (Exam: July 1, 2018)
    # =========================================================================
    {
        "exam": "BPSC",
        "subject": "Modern History",
        "topic": "Revolutionary Nationalism in Bihar",
        "subtopic": "Anushilan Samiti Patna Branch",
        "question": "Who established a branch of the revolutionary organization 'Anushilan Samiti' at Patna in the year 1913?",
        "option_a": "Sachindra Nath Sanyal",
        "option_b": "Prafulla Chaki",
        "option_c": "Bankim Chandra Mitra",
        "option_d": "Bhupendra Nath Datta",
        "correct_option": "A",
        "explanation": "Sachindra Nath Sanyal set up a branch of the Anushilan Samiti in Patna in 1913. He placed Bankim Chandra Mitra of BN College in charge of recruiting youth for the revolutionary cause.",
        "distractor_notes": "Prafulla Chaki was martyred in 1908 after the Muzaffarpur bomb incident. Bankim Chandra Mitra was recruited by Sanyal. Bhupendra Nath Datta edited Yugantar in Bengal.",
        "concept_tested": "Revolutionary underground movements in colonial Bihar",
        "question_type": "Standard MCQ",
        "source_type": "Official PYQ",
        "source_name": "63rd BPSC CCE Prelims",
        "source_url": "https://bpsc.bih.nic.in",
        "difficulty": "Hard",
        "is_ai_generated": 0,
        "exam_edition": "63rd BPSC CCE Prelims",
        "exam_year": "2018",
        "paper_set": "Series A",
        "official_qno": 0,
        "answer_key_status": "Official Final Key Verified",
    },
    {
        "exam": "BPSC",
        "subject": "Modern History",
        "topic": "Bihar Provincial Conference",
        "subtopic": "First Session 1908",
        "question": "Who presided over the first session of the Bihar Provincial Conference held at Patna in 1908?",
        "option_a": "Sir Syed Ali Imam",
        "option_b": "Dr. Rajendra Prasad",
        "option_c": "Mazharul Haque",
        "option_d": "Sachchidananda Sinha",
        "correct_option": "A",
        "explanation": "The first session of the Bihar Provincial Conference was convened at Patna in 1908 under the presidency of Sir Syed Ali Imam, where a historic resolution demanding a separate Bihar province was unanimously passed.",
        "distractor_notes": "Dr. Rajendra Prasad served as secretary of the Bihar Students Conference. Mazharul Haque and Sachchidananda Sinha were pivotal figures in the separate Bihar movement but did not preside over this first conference session.",
        "concept_tested": "Origins of modern Bihar statehood and the 1908 Patna Conference",
        "question_type": "Standard MCQ",
        "source_type": "Official PYQ",
        "source_name": "63rd BPSC CCE Prelims",
        "source_url": "https://bpsc.bih.nic.in",
        "difficulty": "Hard",
        "is_ai_generated": 0,
        "exam_edition": "63rd BPSC CCE Prelims",
        "exam_year": "2018",
        "paper_set": "Series A",
        "official_qno": 0,
        "answer_key_status": "Official Final Key Verified",
    },
    {
        "exam": "BPSC",
        "subject": "Modern History",
        "topic": "Moderate Nationalist Organizations",
        "subtopic": "Servants of India Society",
        "question": "Who among the following founded the 'Servants of India Society' in Pune in 1905?",
        "option_a": "Gopal Krishna Gokhale",
        "option_b": "Bal Gangadhar Tilak",
        "option_c": "Mahatma Gandhi",
        "option_d": "Mahadev Govind Ranade",
        "correct_option": "A",
        "explanation": "Gopal Krishna Gokhale founded the Servants of India Society on 12 June 1905 in Pune to train national missionaries for the service of India and promote education and social reform through constitutional means.",
        "distractor_notes": "Tilak founded the Deccan Education Society and Home Rule League. Gandhi acknowledged Gokhale as his political mentor. Ranade was Gokhale's mentor and founder of the Poona Sarvajanik Sabha.",
        "concept_tested": "Nationalist organizations of the Moderate era and their leaders",
        "question_type": "Standard MCQ",
        "source_type": "Official PYQ",
        "source_name": "63rd BPSC CCE Prelims",
        "source_url": "https://bpsc.bih.nic.in",
        "difficulty": "Easy",
        "is_ai_generated": 0,
        "exam_edition": "63rd BPSC CCE Prelims",
        "exam_year": "2018",
        "paper_set": "Series A",
        "official_qno": 0,
        "answer_key_status": "Official Final Key Verified",
    },
    {
        "exam": "BPSC",
        "subject": "Indian Polity",
        "topic": "All India Services",
        "subtopic": "Article 312 Rajya Sabha Powers",
        "question": "Under which Article of the Constitution of India can the Rajya Sabha initiate the creation of one or more new All-India Services?",
        "option_a": "Article 310",
        "option_b": "Article 311",
        "option_c": "Article 312",
        "option_d": "Article 315",
        "correct_option": "C",
        "explanation": "Under Article 312, if the Rajya Sabha declares by resolution supported by not less than two-thirds of the members present and voting that it is necessary in the national interest, Parliament may by law create new All-India Services common to the Union and States.",
        "distractor_notes": "Article 310 deals with doctrine of pleasure/tenure. Article 311 provides procedural safeguards against dismissal. Article 315 establishes Union and State Public Service Commissions.",
        "concept_tested": "Special constitutional powers of Rajya Sabha and All-India Services under Article 312",
        "question_type": "Standard MCQ",
        "source_type": "Official PYQ",
        "source_name": "63rd BPSC CCE Prelims",
        "source_url": "https://bpsc.bih.nic.in",
        "difficulty": "Medium",
        "is_ai_generated": 0,
        "exam_edition": "63rd BPSC CCE Prelims",
        "exam_year": "2018",
        "paper_set": "Series A",
        "official_qno": 0,
        "answer_key_status": "Official Final Key Verified",
    },
    {
        "exam": "BPSC",
        "subject": "Geography",
        "topic": "Census of India 2011",
        "subtopic": "Population Density Ranking",
        "question": "According to the Census 2011, which state in India has the highest density of population?",
        "option_a": "Kerala",
        "option_b": "Uttar Pradesh",
        "option_c": "Bihar",
        "option_d": "West Bengal",
        "correct_option": "C",
        "explanation": "As per Census 2011, Bihar ranks first among all Indian states in population density with 1,106 persons per square kilometre, surpassing West Bengal (1,028 persons per sq km).",
        "distractor_notes": "West Bengal was number one in Census 2001 but slipped to second in 2011. Uttar Pradesh has the largest total population but density is 829. Kerala's density is 860.",
        "concept_tested": "Demographic indicators of India and Bihar from Census 2011",
        "question_type": "Standard MCQ",
        "source_type": "Official PYQ",
        "source_name": "63rd BPSC CCE Prelims",
        "source_url": "https://bpsc.bih.nic.in",
        "difficulty": "Easy",
        "is_ai_generated": 0,
        "exam_edition": "63rd BPSC CCE Prelims",
        "exam_year": "2018",
        "paper_set": "Series A",
        "official_qno": 0,
        "answer_key_status": "Official Final Key Verified",
    },
    {
        "exam": "BPSC",
        "subject": "Geography",
        "topic": "Physiography of India",
        "subtopic": "Hill Ranges of Peninsular Plateau",
        "question": "The Satmala Hills are situated in which of the following states of India?",
        "option_a": "Maharashtra",
        "option_b": "Madhya Pradesh",
        "option_c": "Andhra Pradesh",
        "option_d": "Gujarat",
        "correct_option": "A",
        "explanation": "The Satmala Hills are located in Nashik district of Maharashtra, extending along the Sahyadri range and forming part of the Western Ghats plateau system.",
        "distractor_notes": "Madhya Pradesh contains the Vindhya and Satpura ranges. Andhra Pradesh contains the Nallamala and Palkonda ranges. Gujarat contains Gir and Girnar hills.",
        "concept_tested": "Regional topography and mountain systems of Peninsular India",
        "question_type": "Standard MCQ",
        "source_type": "Official PYQ",
        "source_name": "63rd BPSC CCE Prelims",
        "source_url": "https://bpsc.bih.nic.in",
        "difficulty": "Hard",
        "is_ai_generated": 0,
        "exam_edition": "63rd BPSC CCE Prelims",
        "exam_year": "2018",
        "paper_set": "Series A",
        "official_qno": 0,
        "answer_key_status": "Official Final Key Verified",
    },
    {
        "exam": "BPSC",
        "subject": "General Science",
        "topic": "Scientific Instruments",
        "subtopic": "Atmospheric Humidity",
        "question": "Which of the following instruments is used for measuring relative humidity in the atmosphere?",
        "option_a": "Hydrometer",
        "option_b": "Hygrometer",
        "option_c": "Pyrometer",
        "option_d": "Lactometer",
        "correct_option": "B",
        "explanation": "A Hygrometer measures the amount of water vapour (humidity) in the atmosphere or enclosed gas volumes.",
        "distractor_notes": "Hydrometer measures the specific gravity (relative density) of liquids. Pyrometer measures extreme temperatures. Lactometer tests milk purity and density.",
        "concept_tested": "Distinction between Hygrometer and Hydrometer",
        "question_type": "Standard MCQ",
        "source_type": "Official PYQ",
        "source_name": "63rd BPSC CCE Prelims",
        "source_url": "https://bpsc.bih.nic.in",
        "difficulty": "Easy",
        "is_ai_generated": 0,
        "exam_edition": "63rd BPSC CCE Prelims",
        "exam_year": "2018",
        "paper_set": "Series A",
        "official_qno": 0,
        "answer_key_status": "Official Final Key Verified",
    },
    {
        "exam": "BPSC",
        "subject": "General Science",
        "topic": "Human Physiology & Nutrition",
        "subtopic": "Vitamin Synthesis",
        "question": "Which vitamin is synthesized most rapidly in the human body through the direct exposure of skin to sunlight?",
        "option_a": "Vitamin A",
        "option_b": "Vitamin B",
        "option_c": "Vitamin C",
        "option_d": "Vitamin D",
        "correct_option": "D",
        "explanation": "Vitamin D3 (cholecalciferol) is synthesized in epidermal layers of human skin when 7-dehydrocholesterol absorbs ultraviolet-B (UVB) radiation from natural sunlight.",
        "distractor_notes": "Vitamin A is converted from dietary beta-carotene in the liver. Vitamin B complex and Vitamin C are water-soluble vitamins that must be ingested through food.",
        "concept_tested": "Cutaneous photochemical synthesis of Vitamin D in humans",
        "question_type": "Standard MCQ",
        "source_type": "Official PYQ",
        "source_name": "63rd BPSC CCE Prelims",
        "source_url": "https://bpsc.bih.nic.in",
        "difficulty": "Easy",
        "is_ai_generated": 0,
        "exam_edition": "63rd BPSC CCE Prelims",
        "exam_year": "2018",
        "paper_set": "Series A",
        "official_qno": 0,
        "answer_key_status": "Official Final Key Verified",
    },
    {
        "exam": "BPSC",
        "subject": "General Science",
        "topic": "Nuclear Chemistry & Physics",
        "subtopic": "Heavy Water",
        "question": "What is the chemical composition of 'Heavy Water' commonly used as a neutron moderator in nuclear reactors?",
        "option_a": "Deuterium oxide (D₂O)",
        "option_b": "Hydrogen peroxide (H₂O₂)",
        "option_c": "Distilled water with minerals",
        "option_d": "Tritium oxide (T₂O)",
        "correct_option": "A",
        "explanation": "Heavy water is Deuterium Oxide (D₂O), where ordinary hydrogen (protium) is replaced by deuterium, an isotope of hydrogen containing one proton and one neutron.",
        "distractor_notes": "Hydrogen peroxide is H₂O₂, a bleaching and antiseptic agent. Distilled water is pure H₂O. Tritium oxide (T₂O) is super-heavy water containing radioactive tritium.",
        "concept_tested": "Chemical composition and nuclear applications of heavy water",
        "question_type": "Standard MCQ",
        "source_type": "Official PYQ",
        "source_name": "63rd BPSC CCE Prelims",
        "source_url": "https://bpsc.bih.nic.in",
        "difficulty": "Easy",
        "is_ai_generated": 0,
        "exam_edition": "63rd BPSC CCE Prelims",
        "exam_year": "2018",
        "paper_set": "Series A",
        "official_qno": 0,
        "answer_key_status": "Official Final Key Verified",
    },

    # =========================================================================
    # 64th BPSC CCE Prelims (Exam: Dec 16, 2018)
    # =========================================================================
    {
        "exam": "BPSC",
        "subject": "Modern History",
        "topic": "Champaran Satyagraha 1917",
        "subtopic": "Invitation to Mahatma Gandhi",
        "question": "Who among the following persistently invited Mahatma Gandhi at the Lucknow Congress Session (1916) to visit Champaran and investigate the grievances of indigo farmers?",
        "option_a": "Dr. Rajendra Prasad",
        "option_b": "Raj Kumar Shukla",
        "option_c": "Mazharul Haque",
        "option_d": "Brajkishore Prasad",
        "correct_option": "B",
        "explanation": "Raj Kumar Shukla, a local farmer from Murali Bharhawa village in Champaran, met Gandhi at the Lucknow Session of Congress in 1916 and persistently followed him to Kanpur and Ahmedabad until Gandhi agreed to visit Champaran.",
        "distractor_notes": "Rajendra Prasad, Mazharul Haque, and Brajkishore Prasad joined Gandhi upon his arrival in Patna and Motihari, assisting with legal testimonies.",
        "concept_tested": "Key historical figures of the 1917 Champaran Satyagraha",
        "question_type": "Standard MCQ",
        "source_type": "Official PYQ",
        "source_name": "64th BPSC CCE Prelims",
        "source_url": "https://bpsc.bih.nic.in",
        "difficulty": "Easy",
        "is_ai_generated": 0,
        "exam_edition": "64th BPSC CCE Prelims",
        "exam_year": "2018",
        "paper_set": "Series A",
        "official_qno": 0,
        "answer_key_status": "Official Final Key Verified",
    },
    {
        "exam": "BPSC",
        "subject": "Ancient & Medieval History",
        "topic": "Prehistoric Archaeological Sites of Bihar",
        "subtopic": "Chirand Bone Artifacts",
        "question": "Chirand, an archaeological site famous for its extensive Neolithic bone tools and deer antler implements, is located in which district of Bihar?",
        "option_a": "Patna",
        "option_b": "Saran",
        "option_c": "Nalanda",
        "option_d": "Vaishali",
        "correct_option": "B",
        "explanation": "Chirand is situated in the Saran (Chapra) district on the north bank of the River Ganga, near the confluence of the Ghaghara and Ganga. It is renowned for bone and antler tools dating to the Neolithic period.",
        "distractor_notes": "Patna is famous for Kumhrar (Mauryan pillared hall). Nalanda for the ancient Mahavihara ruins. Vaishali for Kolhua (Ashokan pillar) and Relic Stupa.",
        "concept_tested": "Neolithic archaeology and prehistoric cultures of Bihar",
        "question_type": "Standard MCQ",
        "source_type": "Official PYQ",
        "source_name": "64th BPSC CCE Prelims",
        "source_url": "https://bpsc.bih.nic.in",
        "difficulty": "Medium",
        "is_ai_generated": 0,
        "exam_edition": "64th BPSC CCE Prelims",
        "exam_year": "2018",
        "paper_set": "Series A",
        "official_qno": 0,
        "answer_key_status": "Official Final Key Verified",
    },
    {
        "exam": "BPSC",
        "subject": "Indian Polity",
        "topic": "Directive Principles of State Policy",
        "subtopic": "Article 40 (Village Panchayats)",
        "question": "Which Article of the Constitution of India contains the Directive Principle directing the State to organize Village Panchayats as units of self-government?",
        "option_a": "Article 39",
        "option_b": "Article 40",
        "option_c": "Article 44",
        "option_d": "Article 48",
        "correct_option": "B",
        "explanation": "Article 40 in Part IV of the Indian Constitution instructs: 'The State shall take steps to organise village panchayats and endow them with such powers and authority as may be necessary to enable them to function as units of self-government.'",
        "distractor_notes": "Article 39 deals with economic justice and livelihood. Article 44 deals with Uniform Civil Code. Article 48 deals with organization of agriculture and animal husbandry.",
        "concept_tested": "Gandhian Directive Principles under Article 40",
        "question_type": "Standard MCQ",
        "source_type": "Official PYQ",
        "source_name": "64th BPSC CCE Prelims",
        "source_url": "https://bpsc.bih.nic.in",
        "difficulty": "Easy",
        "is_ai_generated": 0,
        "exam_edition": "64th BPSC CCE Prelims",
        "exam_year": "2018",
        "paper_set": "Series A",
        "official_qno": 0,
        "answer_key_status": "Official Final Key Verified",
    },
    {
        "exam": "BPSC",
        "subject": "Indian Polity",
        "topic": "Panchayati Raj Institutions",
        "subtopic": "Minimum Age Eligibility",
        "question": "What is the minimum age prescribed under the Constitution of India to contest elections to Panchayati Raj Institutions (PRIs)?",
        "option_a": "18 years",
        "option_b": "21 years",
        "option_c": "25 years",
        "option_d": "30 years",
        "correct_option": "B",
        "explanation": "Under Article 243F(1)(a), a person is qualified to be chosen as a member of a Panchayat if they have attained the age of 21 years (unlike legislative assemblies where the minimum age is 25).",
        "distractor_notes": "18 years is the universal voting age under Article 326. 25 years is required for Lok Sabha and Vidhan Sabha. 30 years is required for Rajya Sabha and Vidhan Parishad.",
        "concept_tested": "Age qualifications for constitutional bodies in India",
        "question_type": "Standard MCQ",
        "source_type": "Official PYQ",
        "source_name": "64th BPSC CCE Prelims",
        "source_url": "https://bpsc.bih.nic.in",
        "difficulty": "Easy",
        "is_ai_generated": 0,
        "exam_edition": "64th BPSC CCE Prelims",
        "exam_year": "2018",
        "paper_set": "Series A",
        "official_qno": 0,
        "answer_key_status": "Official Final Key Verified",
    },
    {
        "exam": "BPSC",
        "subject": "Geography",
        "topic": "Mineral Resources of India",
        "subtopic": "Mica Production",
        "question": "Which of the following Indian states is the leading producer of mica in the country?",
        "option_a": "Rajasthan",
        "option_b": "Andhra Pradesh",
        "option_c": "Jharkhand",
        "option_d": "Bihar",
        "correct_option": "B",
        "explanation": "Andhra Pradesh (particularly the Nellore mica belt) is the leading producer of crude and sheet mica in India, accounting for over 70% of total national output.",
        "distractor_notes": "Rajasthan (Bhilwara belt) is second. Jharkhand's Koderma-Hazaribagh belt and Bihar's Nawada-Gaya belt were historically dominant but production has declined.",
        "concept_tested": "Geographical distribution of strategic mineral reserves across Indian states",
        "question_type": "Standard MCQ",
        "source_type": "Official PYQ",
        "source_name": "64th BPSC CCE Prelims",
        "source_url": "https://bpsc.bih.nic.in",
        "difficulty": "Medium",
        "is_ai_generated": 0,
        "exam_edition": "64th BPSC CCE Prelims",
        "exam_year": "2018",
        "paper_set": "Series A",
        "official_qno": 0,
        "answer_key_status": "Official Final Key Verified",
    },

    # =========================================================================
    # 65th BPSC CCE Prelims (Exam: Oct 15, 2019)
    # =========================================================================
    {
        "exam": "BPSC",
        "subject": "Bihar Special",
        "topic": "Census 2011 Bihar",
        "subtopic": "Child Sex Ratio",
        "question": "According to the Census 2011, what was the Child Sex Ratio (0 to 6 years age group) in Bihar?",
        "option_a": "935",
        "option_b": "918",
        "option_c": "942",
        "option_d": "925",
        "correct_option": "A",
        "explanation": "As per Census 2011, the Child Sex Ratio (0-6 years) in Bihar was 935 girls per 1,000 boys (higher than the national average of 919).",
        "distractor_notes": "918 was the overall sex ratio of Bihar in 2011. 942 was the child sex ratio in 2001 census. 925 is an incorrect distractor.",
        "concept_tested": "Detailed demographic statistics of Bihar from Census 2011",
        "question_type": "Standard MCQ",
        "source_type": "Official PYQ",
        "source_name": "65th BPSC CCE Prelims",
        "source_url": "https://bpsc.bih.nic.in",
        "difficulty": "Medium",
        "is_ai_generated": 0,
        "exam_edition": "65th BPSC CCE Prelims",
        "exam_year": "2019",
        "paper_set": "Series A",
        "official_qno": 0,
        "answer_key_status": "Official Final Key Verified",
    },
    {
        "exam": "BPSC",
        "subject": "Bihar Special",
        "topic": "Print Media & Nationalist Press in Bihar",
        "subtopic": "Searchlight Newspaper",
        "question": "Who served as the long-tenured Editor of 'The Searchlight', the prominent English nationalist daily newspaper published from Patna?",
        "option_a": "Abdul Bari",
        "option_b": "Lambodar Mukherjee",
        "option_c": "Murali Mohan Prasad",
        "option_d": "Ramananda Chatterjee",
        "correct_option": "C",
        "explanation": "Murali Mohan Prasad was the editor of 'The Searchlight' from 1922 into the post-independence era, spearheading investigative reporting against British administrative excesses.",
        "distractor_notes": "Abdul Bari was a prominent trade unionist and Congress leader. Ramananda Chatterjee edited 'The Modern Review' from Calcutta. Lambodar Mukherjee was a lawyer and activist.",
        "concept_tested": "History of English press in colonial Bihar during the freedom struggle",
        "question_type": "Standard MCQ",
        "source_type": "Official PYQ",
        "source_name": "65th BPSC CCE Prelims",
        "source_url": "https://bpsc.bih.nic.in",
        "difficulty": "Hard",
        "is_ai_generated": 0,
        "exam_edition": "65th BPSC CCE Prelims",
        "exam_year": "2019",
        "paper_set": "Series A",
        "official_qno": 0,
        "answer_key_status": "Official Final Key Verified",
    },
    {
        "exam": "BPSC",
        "subject": "Bihar Special",
        "topic": "Agricultural Events of Bihar",
        "subtopic": "Krishi Kumbha Mela 2019",
        "question": "In February 2019, the mega agricultural conference 'Krishi Kumbha Mela 2019' was hosted in which town of Bihar?",
        "option_a": "Motihari",
        "option_b": "Patna",
        "option_c": "Rajgir",
        "option_d": "Muzaffarpur",
        "correct_option": "A",
        "explanation": "The Krishi Kumbha Mela 2019 was organized at Gandhi Maidan in Motihari (East Champaran district) by the Union Ministry of Agriculture and Bihar Agricultural University to demonstrate modern farm technologies.",
        "distractor_notes": "Patna frequently hosts trade expos. Rajgir hosts Malmas Mela and international cultural festivals. Muzaffarpur is the litchi hub of Bihar.",
        "concept_tested": "Major state development and agricultural conferences in Bihar",
        "question_type": "Standard MCQ",
        "source_type": "Official PYQ",
        "source_name": "65th BPSC CCE Prelims",
        "source_url": "https://bpsc.bih.nic.in",
        "difficulty": "Medium",
        "is_ai_generated": 0,
        "exam_edition": "65th BPSC CCE Prelims",
        "exam_year": "2019",
        "paper_set": "Series A",
        "official_qno": 0,
        "answer_key_status": "Official Final Key Verified",
    },
    {
        "exam": "BPSC",
        "subject": "Modern History",
        "topic": "Revolutionary Terrorism & HRA",
        "subtopic": "Kakori Conspiracy Case 1925",
        "question": "Which of the following revolutionaries was NOT hanged by the British colonial government in connection with the Kakori Train Robbery Case (1925)?",
        "option_a": "Ram Prasad Bismil",
        "option_b": "Ashfaqulla Khan",
        "option_c": "Rajendra Lahiri",
        "option_d": "Chandrashekhar Azad",
        "correct_option": "D",
        "explanation": "Chandrashekhar Azad evaded British police capture after Kakori and went on to reorganize the HRA into the Hindustan Socialist Republican Association (HSRA). Ram Prasad Bismil, Ashfaqulla Khan, Rajendra Lahiri, and Roshan Singh were executed in December 1927.",
        "distractor_notes": "Ram Prasad Bismil was hanged at Gorakhpur Jail; Ashfaqulla Khan at Faizabad; Rajendra Lahiri at Gonda; Roshan Singh at Naini (Allahabad).",
        "concept_tested": "Kakori conspiracy case trial outcomes and revolutionary leaders",
        "question_type": "Standard MCQ",
        "source_type": "Official PYQ",
        "source_name": "65th BPSC CCE Prelims",
        "source_url": "https://bpsc.bih.nic.in",
        "difficulty": "Medium",
        "is_ai_generated": 0,
        "exam_edition": "65th BPSC CCE Prelims",
        "exam_year": "2019",
        "paper_set": "Series A",
        "official_qno": 0,
        "answer_key_status": "Official Final Key Verified",
    },
    {
        "exam": "BPSC",
        "subject": "Ancient & Medieval History",
        "topic": "Medieval History of Bihar",
        "subtopic": "Mughal Conquest of Kashmir & Exile",
        "question": "Yousuf Shah Chak, the last independent Muslim Sultan of the Kashmir Valley, was exiled by Mughal Emperor Akbar to which place in Bihar where his tomb is situated?",
        "option_a": "Patna",
        "option_b": "Bihar Sharif",
        "option_c": "Gaya",
        "option_d": "Munger",
        "correct_option": "B",
        "explanation": "Yousuf Shah Chak was annexed by Akbar in 1586 and subsequently exiled to Biswak in Nalanda district (Bihar). He died in 1592 and is buried at Kashmir Chak near Bihar Sharif.",
        "distractor_notes": "Bihar Sharif in Nalanda is the historical resting place of Sufi saint Makhdum Yahya Maneri and contains Yousuf Shah Chak's cemetery. Patna, Gaya, and Munger are other historic towns in Bihar.",
        "concept_tested": "Akbar's territorial expansions and the exile of Kashmiri royalty to medieval Bihar",
        "question_type": "Standard MCQ",
        "source_type": "Official PYQ",
        "source_name": "65th BPSC CCE Prelims",
        "source_url": "https://bpsc.bih.nic.in",
        "difficulty": "Hard",
        "is_ai_generated": 0,
        "exam_edition": "65th BPSC CCE Prelims",
        "exam_year": "2019",
        "paper_set": "Series A",
        "official_qno": 0,
        "answer_key_status": "Official Final Key Verified",
    },
]

try:
    from pyqs_archive import NEW_VERIFIED_PYQS
    VERIFIED_BPSC_PYQS.extend(NEW_VERIFIED_PYQS)
except ImportError:
    pass


def connect_db() -> sqlite3.Connection:
    """Return a high-performance connection with Row factory, WAL mode, and memory caching."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30.0)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute("PRAGMA cache_size = -64000;")
        conn.execute("PRAGMA temp_store = MEMORY;")
    except Exception:
        pass
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
        if "original_language" not in q_cols:
            conn.execute("ALTER TABLE questions ADD COLUMN original_language TEXT NOT NULL DEFAULT 'English'")
        if "original_question_hindi" not in q_cols:
            conn.execute("ALTER TABLE questions ADD COLUMN original_question_hindi TEXT NOT NULL DEFAULT ''")
        if "normalized_stem" not in q_cols:
            conn.execute("ALTER TABLE questions ADD COLUMN normalized_stem TEXT NOT NULL DEFAULT ''")
            try:
                unfilled = conn.execute("SELECT id, question FROM questions WHERE normalized_stem = ''").fetchall()
                for r in unfilled:
                    n_stem = normalize_question_text(r["question"])
                    conn.execute("UPDATE questions SET normalized_stem = ? WHERE id = ?", (n_stem, r["id"]))
            except Exception:
                pass

        # High-Speed B-Tree Indexes for Instant Lookups on 7,500+ MCQs
        try:
            conn.execute("CREATE INDEX IF NOT EXISTS idx_questions_normalized_stem ON questions(normalized_stem);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_questions_source_type ON questions(source_type);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_questions_subject ON questions(subject);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_questions_topic ON questions(topic);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_questions_exam ON questions(exam);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_questions_source_name ON questions(source_name);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_questions_exam_edition ON questions(exam_edition);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_questions_difficulty ON questions(difficulty);")
        except Exception:
            pass

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

        try:
            conn.execute("CREATE INDEX IF NOT EXISTS idx_attempts_question_id ON attempts(question_id);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_attempts_session_id ON attempts(test_session_id);")
        except Exception:
            pass

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
        try:
            conn.execute("CREATE INDEX IF NOT EXISTS idx_revision_items_due ON revision_items(due_date, is_completed);")
        except Exception:
            pass

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
        try:
            conn.execute("CREATE INDEX IF NOT EXISTS idx_pinned_question_id ON pinned_notebook(question_id);")
        except Exception:
            pass

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

        # 7. Uploaded Mock Test PDF Files Registry
        conn.execute("""
            CREATE TABLE IF NOT EXISTS uploaded_mock_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL UNIQUE,
                file_hash TEXT NOT NULL DEFAULT '',
                mock_title TEXT NOT NULL DEFAULT '',
                uploaded_at TEXT NOT NULL,
                questions_count INTEGER NOT NULL DEFAULT 0,
                file_size_bytes INTEGER NOT NULL DEFAULT 0
            )
        """)

        # 8. Background Persistent OCR Jobs
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ocr_jobs (
                job_id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                mock_title TEXT NOT NULL,
                target_exam TEXT NOT NULL DEFAULT 'BPSC',
                status TEXT NOT NULL DEFAULT 'running',
                progress REAL NOT NULL DEFAULT 0.0,
                progress_msg TEXT NOT NULL DEFAULT '',
                total_pages INTEGER NOT NULL DEFAULT 0,
                processed_pages INTEGER NOT NULL DEFAULT 0,
                extracted_questions_json TEXT NOT NULL DEFAULT '[]',
                stats_json TEXT NOT NULL DEFAULT '{}',
                error_msg TEXT NOT NULL DEFAULT '',
                cancel_requested INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
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
    payload.setdefault("original_language", "English")
    payload.setdefault("original_question_hindi", "")
    if "normalized_stem" not in payload or not payload["normalized_stem"]:
        payload["normalized_stem"] = normalize_question_text(payload.get("question", ""))
    if "created_at" not in payload:
        payload["created_at"] = datetime.now().isoformat(timespec="seconds")

    # Detect columns present in the target database to ensure backward compatibility
    existing_cols = {r[1] for r in conn.execute("PRAGMA table_info(questions)").fetchall()}
    insert_keys = [k for k in payload.keys() if k in existing_cols]
    col_names = ", ".join(insert_keys)
    val_placeholders = ", ".join(f":{k}" for k in insert_keys)

    cur = conn.execute(f"INSERT INTO questions ({col_names}) VALUES ({val_placeholders})", payload)
    return int(cur.lastrowid)


def normalize_question_text(text: str) -> str:
    """Normalize question stem for high-accuracy deduplication.

    Removes:
    - Leading question numbers (e.g. '1.', '1)', 'Q.1', 'Question 25 -')
    - Formatting noise and non-word characters
    - Case differences and redundant whitespaces
    """
    if not text:
        return ""
    s = str(text).strip()
    s = re.sub(
        r"^(?:\(?\d{1,4}\)?[\.\:\-\s]+|q(?:uestion)?\s*[\.\:\-]?\s*\d{1,4}[\.\)\:\-\s]+)",
        "",
        s,
        flags=re.IGNORECASE,
    )
    s = s.rstrip("?.:;! \t\n\r")
    s = re.sub(r"\s+", " ", s.lower()).strip()
    return s


def is_question_duplicate(
    stem: str, conn: Optional[sqlite3.Connection] = None
) -> Tuple[bool, Optional[int]]:
    """Check if a question stem already exists in the database using high-speed index lookups."""
    if not stem or not str(stem).strip():
        return False, None

    raw_stem = str(stem).strip()
    norm_stem = normalize_question_text(raw_stem)

    def _check(c: sqlite3.Connection) -> Tuple[bool, Optional[int]]:
        # 1. Fast indexed B-Tree lookup via idx_questions_normalized_stem
        try:
            row = c.execute(
                "SELECT id FROM questions WHERE normalized_stem = ? LIMIT 1",
                (norm_stem,),
            ).fetchone()
            if row:
                return True, int(row[0])
        except Exception:
            pass

        # 2. Exact raw stem match
        row = c.execute(
            "SELECT id FROM questions WHERE lower(trim(question)) = lower(trim(?)) LIMIT 1",
            (raw_stem,),
        ).fetchone()
        if row:
            return True, int(row[0])

        return False, None

    if conn is not None:
        return _check(conn)
    with connect_db() as c:
        return _check(c)


def filter_duplicate_questions(
    questions: List[Dict[str, Any]],
    conn: Optional[sqlite3.Connection] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Separate a list of questions into unique new questions and duplicate questions.

    Uses high-speed B-Tree index batch lookups to handle 7,500+ question databases in milliseconds.
    """
    unique_list: List[Dict[str, Any]] = []
    duplicate_list: List[Dict[str, Any]] = []
    seen_batch_stems: set = set()

    def _process(c: sqlite3.Connection):
        # Extract all normalized stems in this incoming batch
        batch_norms = [normalize_question_text(q.get("question", "")) for q in questions]
        clean_norms = [n for n in batch_norms if n]

        # Fast indexed query for only the stems in this batch
        existing_stems: Dict[str, int] = {}
        cols = {r[1] for r in c.execute("PRAGMA table_info(questions)").fetchall()}
        has_norm = "normalized_stem" in cols

        if has_norm and clean_norms:
            # Query in chunks of 400 to stay well under SQLite parameter limits
            for i in range(0, len(clean_norms), 400):
                sub_norms = clean_norms[i : i + 400]
                placeholders = ",".join("?" for _ in sub_norms)
                try:
                    rows = c.execute(
                        f"SELECT normalized_stem, id FROM questions WHERE normalized_stem IN ({placeholders})",
                        sub_norms,
                    ).fetchall()
                    for r in rows:
                        if r[0]:
                            existing_stems[r[0]] = int(r[1])
                except Exception:
                    pass
        elif not has_norm:
            # Fallback for legacy schemas without normalized_stem column
            try:
                db_rows = c.execute("SELECT id, question FROM questions").fetchall()
                for qid, q_text in db_rows:
                    if q_text:
                        existing_stems[normalize_question_text(q_text)] = int(qid)
            except Exception:
                pass

        for q in questions:
            stem = q.get("question", "")
            norm = normalize_question_text(stem)
            if not norm:
                continue

            if norm in seen_batch_stems:
                duplicate_list.append(
                    {**q, "duplicate_reason": "Repeated within current upload batch"}
                )
                continue

            if norm in existing_stems:
                qid = existing_stems[norm]
                duplicate_list.append(
                    {
                        **q,
                        "duplicate_reason": f"Already exists in Question Bank (#Q{qid})",
                    }
                )
                continue

            seen_batch_stems.add(norm)
            unique_list.append(q)

    if conn is not None:
        _process(conn)
    else:
        with connect_db() as c:
            _process(c)

    return unique_list, duplicate_list


def _ensure_mock_files_table(conn: sqlite3.Connection) -> None:
    """Ensure uploaded_mock_files table exists in connection."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS uploaded_mock_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL UNIQUE,
            file_hash TEXT NOT NULL DEFAULT '',
            mock_title TEXT NOT NULL DEFAULT '',
            uploaded_at TEXT NOT NULL,
            questions_count INTEGER NOT NULL DEFAULT 0,
            file_size_bytes INTEGER NOT NULL DEFAULT 0
        )
    """
    )


def is_pdf_already_uploaded(
    filename: str, file_hash: str = "", conn_factory: Any = None
) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """Check if a PDF filename or hash has already been uploaded."""
    clean_name = str(filename).strip().lower()
    clean_hash = str(file_hash).strip().lower()
    connector = conn_factory or connect_db

    with connector() as conn:
        _ensure_mock_files_table(conn)
        if clean_hash:
            row = conn.execute(
                "SELECT * FROM uploaded_mock_files WHERE lower(filename) = ? OR lower(file_hash) = ? LIMIT 1",
                (clean_name, clean_hash),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM uploaded_mock_files WHERE lower(filename) = ? LIMIT 1",
                (clean_name,),
            ).fetchone()

        if row:
            return True, dict(row)

        try:
            q_row = conn.execute(
                "SELECT COUNT(*), MIN(created_at), source_name FROM questions WHERE lower(source_name) = ? OR lower(exam_edition) LIKE ? GROUP BY source_name LIMIT 1",
                (clean_name, f"%{clean_name}%"),
            ).fetchone()
            if q_row and q_row[0] > 0:
                return True, {
                    "filename": filename,
                    "file_hash": file_hash,
                    "mock_title": q_row[2] or filename,
                    "uploaded_at": q_row[1] or "Previously",
                    "questions_count": q_row[0],
                }
        except Exception:
            pass

        return False, None


def record_uploaded_pdf(
    filename: str,
    file_hash: str,
    mock_title: str,
    questions_count: int,
    file_size_bytes: int = 0,
    conn_factory: Any = None,
) -> None:
    """Record an uploaded mock PDF file in the registry."""
    connector = conn_factory or connect_db
    with connector() as conn:
        _ensure_mock_files_table(conn)
        conn.execute(
            """
            INSERT INTO uploaded_mock_files (filename, file_hash, mock_title, uploaded_at, questions_count, file_size_bytes)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(filename) DO UPDATE SET
                file_hash = excluded.file_hash,
                mock_title = excluded.mock_title,
                uploaded_at = excluded.uploaded_at,
                questions_count = excluded.questions_count,
                file_size_bytes = excluded.file_size_bytes
        """,
            (
                filename.strip(),
                file_hash.strip(),
                mock_title.strip(),
                datetime.now().isoformat(timespec="seconds"),
                questions_count,
                file_size_bytes,
            ),
        )
        conn.commit()


def get_all_uploaded_mock_files(conn_factory: Any = None) -> pd.DataFrame:
    """Return all recorded uploaded PDF files."""
    connector = conn_factory or connect_db
    with connector() as conn:
        _ensure_mock_files_table(conn)
        return pd.read_sql_query(
            "SELECT * FROM uploaded_mock_files ORDER BY id DESC", conn
        )


def find_and_remove_duplicate_questions() -> Tuple[int, List[Dict[str, Any]]]:
    """Find and remove duplicate questions from the database, preserving the oldest record.

    Returns:
        (deleted_count, list_of_cleaned_stems)
    """
    with connect_db() as conn:
        all_rows = conn.execute(
            "SELECT id, question, subject, topic FROM questions ORDER BY id ASC"
        ).fetchall()
        seen: Dict[str, int] = {}
        to_delete_ids: List[int] = []
        cleaned_info: List[Dict[str, Any]] = []

        for r in all_rows:
            qid = int(r["id"])
            norm = normalize_question_text(r["question"])
            if not norm:
                continue
            if norm in seen:
                to_delete_ids.append(qid)
                cleaned_info.append(
                    {
                        "deleted_id": qid,
                        "kept_id": seen[norm],
                        "stem": r["question"][:80]
                        + ("..." if len(r["question"]) > 80 else ""),
                        "subject": r["subject"],
                    }
                )
            else:
                seen[norm] = qid

        if to_delete_ids:
            placeholders = ",".join("?" for _ in to_delete_ids)
            conn.execute(
                f"DELETE FROM questions WHERE id IN ({placeholders})",
                to_delete_ids,
            )
            conn.commit()

        return len(to_delete_ids), cleaned_info


def add_question(item: Dict[str, Any], skip_if_duplicate: bool = False) -> int:
    """Thread-safe single question insertion with optional deduplication."""
    with connect_db() as conn:
        if skip_if_duplicate:
            stem = item.get("question", "")
            is_dup, existing_id = is_question_duplicate(stem, conn=conn)
            if is_dup and existing_id:
                return existing_id
        qid = insert_question(conn, item)
        conn.commit()
        return qid


def add_questions_batch(items: List[Dict[str, Any]], skip_if_duplicate: bool = False) -> int:
    """Fast batch insertion for hundreds or thousands of questions in a single SQLite transaction."""
    if not items:
        return 0
    with connect_db() as conn:
        to_insert = items
        if skip_if_duplicate:
            to_insert, _ = filter_duplicate_questions(items, conn=conn)
        
        inserted_cnt = 0
        for item in to_insert:
            try:
                insert_question(conn, item)
                inserted_cnt += 1
            except Exception:
                pass
        conn.commit()
        return inserted_cnt


def update_question_fields(question_id: int, fields: Dict[str, Any]) -> bool:
    """Safely update specific fields (e.g. translated question, options, explanation) for a question."""
    if not fields or question_id <= 0:
        return False
    with connect_db() as conn:
        existing_cols = {r[1] for r in conn.execute("PRAGMA table_info(questions)").fetchall()}
        valid_fields = {k: v for k, v in fields.items() if k in existing_cols}
        if not valid_fields:
            return False

        if "question" in valid_fields and ("normalized_stem" not in valid_fields or not valid_fields["normalized_stem"]):
            valid_fields["normalized_stem"] = normalize_question_text(valid_fields["question"])

        set_clauses = ", ".join(f"{k} = ?" for k in valid_fields.keys())
        params = list(valid_fields.values()) + [question_id]
        cur = conn.execute(f"UPDATE questions SET {set_clauses} WHERE id = ?", params)
        conn.commit()
        return cur.rowcount > 0


def list_questions(
    exam: str = "All",
    subject: str = "All",
    topic: str = "All",
    source_type: str = "All",
    exam_edition: str = "All",
    difficulty: str = "All",
    keyword: str = "",
    limit: Optional[int] = None,
    offset: int = 0,
) -> pd.DataFrame:
    """Retrieve filtered questions with optional LIMIT and OFFSET."""
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
    if exam_edition != "All":
        query += " AND exam_edition = ?"
        params.append(exam_edition)
    if difficulty != "All":
        query += " AND difficulty = ?"
        params.append(difficulty)
    if keyword and keyword.strip():
        kw = f"%{keyword.strip().lower()}%"
        query += " AND (LOWER(question) LIKE ? OR LOWER(topic) LIKE ? OR LOWER(explanation) LIKE ?)"
        params.extend([kw, kw, kw])
    query += " ORDER BY subject, topic, id"
    if limit is not None:
        query += f" LIMIT {int(limit)} OFFSET {int(offset)}"
    with connect_db() as conn:
        return pd.read_sql_query(query, conn, params=params)


def count_questions(
    exam: str = "All",
    subject: str = "All",
    topic: str = "All",
    source_type: str = "All",
    conn_factory: Any = None,
) -> int:
    """Return count of questions matching criteria using fast SQLite index."""
    query = "SELECT COUNT(*) FROM questions WHERE 1=1"
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
    connector = conn_factory or connect_db
    with connector() as conn:
        return int(conn.execute(query, params).fetchone()[0])


def get_question_bank_summary(conn_factory: Any = None) -> Dict[str, Any]:
    """Return fast aggregated metrics for the question bank without loading rows into Pandas."""
    connector = conn_factory or connect_db
    with connector() as conn:
        row = conn.execute(
            """
            SELECT
                COUNT(*) as total_questions,
                SUM(CASE WHEN source_type = 'Official PYQ' THEN 1 ELSE 0 END) as pyq_count,
                SUM(CASE WHEN source_type = 'Adjacent PYQ' THEN 1 ELSE 0 END) as adjacent_pyq_count,
                SUM(CASE WHEN source_type = 'Mock question' THEN 1 ELSE 0 END) as mock_count,
                SUM(CASE WHEN source_type = 'AI-generated' THEN 1 ELSE 0 END) as ai_count,
                SUM(CASE WHEN source_type = 'Built-in sample' THEN 1 ELSE 0 END) as sample_count,
                COUNT(DISTINCT subject) as distinct_subjects,
                COUNT(DISTINCT source_name) as distinct_sources
            FROM questions
            """
        ).fetchone()
        if not row:
            return {
                "total_questions": 0,
                "pyq_count": 0,
                "adjacent_pyq_count": 0,
                "mock_count": 0,
                "ai_count": 0,
                "sample_count": 0,
                "distinct_subjects": 0,
                "distinct_sources": 0,
            }
        return {
            "total_questions": int(row["total_questions"] or 0),
            "pyq_count": int(row["pyq_count"] or 0),
            "adjacent_pyq_count": int(row["adjacent_pyq_count"] or 0),
            "mock_count": int(row["mock_count"] or 0),
            "ai_count": int(row["ai_count"] or 0),
            "sample_count": int(row["sample_count"] or 0),
            "distinct_subjects": int(row["distinct_subjects"] or 0),
            "distinct_sources": int(row["distinct_sources"] or 0),
        }


def get_distinct_subjects(
    source_type: str = "All",
    exam: str = "All",
    conn_factory: Any = None,
    **kwargs: Any,
) -> List[str]:
    """Return distinct subjects using fast indexed query."""
    if "source_type" in kwargs:
        source_type = kwargs["source_type"]
    if "exam" in kwargs:
        exam = kwargs["exam"]
    connector = conn_factory or connect_db
    with connector() as conn:
        query = "SELECT DISTINCT subject FROM questions WHERE subject != ''"
        params: List[Any] = []
        if exam != "All":
            query += " AND exam IN (?, 'Both')"
            params.append(exam)
        if source_type != "All":
            query += " AND source_type = ?"
            params.append(source_type)
        query += " ORDER BY subject"
        rows = conn.execute(query, params).fetchall()
        return [r[0] for r in rows if r[0]]


def get_distinct_topics(
    subject: Optional[str] = "All",
    source_type: str = "All",
    exam: str = "All",
    conn_factory: Any = None,
    **kwargs: Any,
) -> List[str]:
    """Return distinct topics using fast indexed query."""
    if "subject" in kwargs:
        subject = kwargs["subject"]
    if "source_type" in kwargs:
        source_type = kwargs["source_type"]
    if "exam" in kwargs:
        exam = kwargs["exam"]
    connector = conn_factory or connect_db
    with connector() as conn:
        query = "SELECT DISTINCT topic FROM questions WHERE topic != ''"
        params: List[Any] = []
        if subject and subject != "All":
            query += " AND subject = ?"
            params.append(subject)
        if exam != "All":
            query += " AND exam IN (?, 'Both')"
            params.append(exam)
        if source_type != "All":
            query += " AND source_type = ?"
            params.append(source_type)
        query += " ORDER BY topic"
        rows = conn.execute(query, params).fetchall()
        return [r[0] for r in rows if r[0]]


def get_distinct_editions(
    source_type: str = "All",
    exam: str = "All",
    conn_factory: Any = None,
    **kwargs: Any,
) -> List[str]:
    """Return distinct exam editions using fast indexed query."""
    if "source_type" in kwargs:
        source_type = kwargs["source_type"]
    if "exam" in kwargs:
        exam = kwargs["exam"]
    connector = conn_factory or connect_db
    with connector() as conn:
        query = "SELECT DISTINCT exam_edition FROM questions WHERE exam_edition != ''"
        params: List[Any] = []
        if exam != "All":
            query += " AND exam IN (?, 'Both')"
            params.append(exam)
        if source_type != "All":
            query += " AND source_type = ?"
            params.append(source_type)
        query += " ORDER BY exam_edition"
        rows = conn.execute(query, params).fetchall()
        return [r[0] for r in rows if r[0]]


def get_subject_counts(
    source_type: str = "All",
    exam: str = "All",
    conn_factory: Any = None,
    **kwargs: Any,
) -> Dict[str, int]:
    """Return question distribution per subject using fast indexed group by."""
    if "source_type" in kwargs:
        source_type = kwargs["source_type"]
    if "exam" in kwargs:
        exam = kwargs["exam"]
    connector = conn_factory or connect_db
    with connector() as conn:
        query = "SELECT subject, COUNT(*) FROM questions WHERE 1=1"
        params: List[Any] = []
        if exam != "All":
            query += " AND exam IN (?, 'Both')"
            params.append(exam)
        if source_type != "All":
            query += " AND source_type = ?"
            params.append(source_type)
        query += " GROUP BY subject ORDER BY COUNT(*) DESC"
        rows = conn.execute(query, params).fetchall()
        return {r[0]: int(r[1]) for r in rows if r[0]}


def get_difficulty_counts(
    source_type: str = "All",
    exam: str = "All",
    conn_factory: Any = None,
    **kwargs: Any,
) -> Dict[str, int]:
    """Return question distribution per difficulty using fast indexed group by."""
    if "source_type" in kwargs:
        source_type = kwargs["source_type"]
    if "exam" in kwargs:
        exam = kwargs["exam"]
    connector = conn_factory or connect_db
    with connector() as conn:
        query = "SELECT difficulty, COUNT(*) FROM questions WHERE 1=1"
        params: List[Any] = []
        if exam != "All":
            query += " AND exam IN (?, 'Both')"
            params.append(exam)
        if source_type != "All":
            query += " AND source_type = ?"
            params.append(source_type)
        query += " GROUP BY difficulty"
        rows = conn.execute(query, params).fetchall()
        return {r[0]: int(r[1]) for r in rows if r[0]}


def get_pinned_questions_df(conn_factory: Any = None) -> pd.DataFrame:
    """Instant indexed retrieval of all pinned questions via single SQL join."""
    connector = conn_factory or connect_db
    with connector() as conn:
        return pd.read_sql_query(
            """
            SELECT q.*, p.pinned_at, p.note as pin_notes
            FROM questions q
            JOIN pinned_notebook p ON q.id = p.question_id
            ORDER BY p.pinned_at DESC
            """,
            conn,
        )


def list_mock_questions(
    exam: str = "All",
    subject: str = "All",
    topic: str = "All",
    mock_name: str = "All",
    difficulty: str = "All",
    keyword: str = "",
    limit: Optional[int] = None,
    offset: int = 0,
) -> pd.DataFrame:
    """Retrieve filtered mock questions with optional LIMIT and OFFSET."""
    query = "SELECT * FROM questions WHERE source_type = 'Mock question'"
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
    if mock_name != "All":
        query += " AND source_name = ?"
        params.append(mock_name)
    if difficulty != "All":
        query += " AND difficulty = ?"
        params.append(difficulty)
    if keyword and keyword.strip():
        kw = f"%{keyword.strip().lower()}%"
        query += " AND (LOWER(question) LIKE ? OR LOWER(topic) LIKE ? OR LOWER(explanation) LIKE ?)"
        params.extend([kw, kw, kw])
    query += " ORDER BY subject, topic, id"
    if limit is not None:
        query += f" LIMIT {int(limit)} OFFSET {int(offset)}"
    with connect_db() as conn:
        return pd.read_sql_query(query, conn, params=params)


def get_mock_test_names() -> List[str]:
    """Return distinct names of uploaded mock tests."""
    with connect_db() as conn:
        rows = conn.execute(
            "SELECT DISTINCT source_name FROM questions WHERE source_type = 'Mock question' AND source_name != '' ORDER BY source_name"
        ).fetchall()
        return [r[0] for r in rows if r[0]]


def delete_mock_test(source_name: str) -> int:
    """Delete all mock questions associated with a given mock test name."""
    with connect_db() as conn:
        cur = conn.execute(
            "DELETE FROM questions WHERE source_type = 'Mock question' AND (source_name = ? OR exam_edition LIKE ?)",
            (source_name, f"%{source_name}%"),
        )
        conn.execute(
            "DELETE FROM uploaded_mock_files WHERE lower(mock_title) = ? OR lower(filename) = ? OR lower(filename) LIKE ?",
            (source_name.lower(), source_name.lower(), f"%{source_name.lower()}%"),
        )
        conn.commit()
        return cur.rowcount


def get_adjacent_exam_names() -> List[str]:
    """Return distinct names or editions of uploaded BPSC-adjacent exam papers."""
    with connect_db() as conn:
        rows = conn.execute(
            "SELECT DISTINCT source_name FROM questions WHERE source_type = 'Adjacent PYQ' AND source_name != '' ORDER BY source_name"
        ).fetchall()
        return [r[0] for r in rows if r[0]]


def delete_adjacent_exam(source_name: str) -> int:
    """Delete all adjacent PYQ questions associated with a given exam paper name or edition."""
    with connect_db() as conn:
        cur = conn.execute(
            "DELETE FROM questions WHERE source_type = 'Adjacent PYQ' AND (source_name = ? OR exam_edition LIKE ?)",
            (source_name, f"%{source_name}%"),
        )
        conn.execute(
            "DELETE FROM uploaded_mock_files WHERE lower(mock_title) = ? OR lower(filename) = ? OR lower(filename) LIKE ?",
            (source_name.lower(), source_name.lower(), f"%{source_name.lower()}%"),
        )
        conn.commit()
        return cur.rowcount


def get_question_ids(
    exam: str = "All",
    subject: str = "All",
    topic: str = "All",
    source_type: str = "All",
    exam_edition: str = "All",
    source_name: str = "All",
) -> List[int]:
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
    if exam_edition != "All":
        query += " AND exam_edition = ?"
        params.append(exam_edition)
    if source_name != "All":
        query += " AND source_name = ?"
        params.append(source_name)
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
    limit: int = 5,
    exam_edition: str = "All",
    conn_factory: Any = None,
) -> List[Dict[str, Any]]:
    """Retrieve authentic official PYQs matching subject/topic to serve as stylistic few-shot exemplars.

    Selection strategy:
    1. Exact subject + topic keyword match in question, topic, subtopic, or concept_tested.
    2. Multi-keyword decomposition across significant terms.
    3. Other PYQs from the same subject.
    4. Other PYQs from the target exam edition / exam.
    5. General official PYQ fallback.
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
        edition_clause = " AND exam_edition = ?" if exam_edition != "All" else ""
        edition_param = [exam_edition] if exam_edition != "All" else []

        # Stage 1: Topic keywords match in question, topic, subtopic, or concept_tested
        if clean_topic and clean_topic != "general":
            pattern = f"%{clean_topic}%"
            if subject and subject != "All":
                stage1 = conn.execute(
                    f"""
                    SELECT * FROM questions
                    WHERE source_type = 'Official PYQ'
                      AND subject = ?{edition_clause}
                      AND (LOWER(topic) LIKE ? OR LOWER(subtopic) LIKE ? OR LOWER(concept_tested) LIKE ? OR LOWER(question) LIKE ?)
                    ORDER BY id DESC LIMIT ?
                    """,
                    [subject] + edition_param + [pattern, pattern, pattern, pattern, limit],
                ).fetchall()
            else:
                stage1 = conn.execute(
                    f"""
                    SELECT * FROM questions
                    WHERE source_type = 'Official PYQ'{edition_clause}
                      AND (LOWER(topic) LIKE ? OR LOWER(subtopic) LIKE ? OR LOWER(concept_tested) LIKE ? OR LOWER(question) LIKE ?)
                    ORDER BY id DESC LIMIT ?
                    """,
                    edition_param + [pattern, pattern, pattern, pattern, limit],
                ).fetchall()
            _add_rows(stage1)

            # Stage 1b: Tokenized keyword matching if still under limit
            if len(results) < limit:
                stop_words = {"in", "and", "the", "of", "to", "for", "a", "an", "on", "with", "or", "&", "state"}
                tokens = [w for w in re.split(r"[\s,;/-]+", clean_topic) if len(w) >= 3 and w not in stop_words]
                for tok in tokens:
                    if len(results) >= limit:
                        break
                    tok_pat = f"%{tok}%"
                    if subject and subject != "All":
                        tok_rows = conn.execute(
                            f"""
                            SELECT * FROM questions
                            WHERE source_type = 'Official PYQ'
                              AND subject = ?{edition_clause}
                              AND (LOWER(topic) LIKE ? OR LOWER(subtopic) LIKE ? OR LOWER(concept_tested) LIKE ? OR LOWER(question) LIKE ?)
                            ORDER BY id DESC LIMIT ?
                            """,
                            [subject] + edition_param + [tok_pat, tok_pat, tok_pat, tok_pat, limit - len(results)],
                        ).fetchall()
                    else:
                        tok_rows = conn.execute(
                            f"""
                            SELECT * FROM questions
                            WHERE source_type = 'Official PYQ'{edition_clause}
                              AND (LOWER(topic) LIKE ? OR LOWER(subtopic) LIKE ? OR LOWER(concept_tested) LIKE ? OR LOWER(question) LIKE ?)
                            ORDER BY id DESC LIMIT ?
                            """,
                            edition_param + [tok_pat, tok_pat, tok_pat, tok_pat, limit - len(results)],
                        ).fetchall()
                    _add_rows(tok_rows)

        # Stage 2: Same subject official PYQs
        if len(results) < limit and subject and subject != "All":
            stage2 = conn.execute(
                f"""
                SELECT * FROM questions
                WHERE source_type = 'Official PYQ'
                  AND subject = ?{edition_clause}
                ORDER BY id DESC LIMIT ?
                """,
                [subject] + edition_param + [limit - len(results)],
            ).fetchall()
            _add_rows(stage2)

        # Stage 3: Target exam official PYQs
        if len(results) < limit:
            stage3 = conn.execute(
                f"""
                SELECT * FROM questions
                WHERE source_type = 'Official PYQ'{edition_clause}
                  AND (exam = ? OR ? = 'Both' OR exam = 'Both')
                ORDER BY id DESC LIMIT ?
                """,
                edition_param + [exam, exam, limit - len(results)],
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


def get_pinned_question_ids() -> Set[int]:
    """Fetch set of all pinned question IDs for fast O(1) membership checks."""
    with connect_db() as conn:
        rows = conn.execute("SELECT question_id FROM pinned_notebook").fetchall()
        return {int(r["question_id"]) for r in rows}



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
        tables = [
            "questions",
            "attempts",
            "test_sessions",
            "revision_items",
            "pinned_notebook",
            "research_notes",
            "uploaded_mock_files",
            "ocr_jobs",
        ]
        export_data = {}
        for t in tables:
            rows = conn.execute(f"SELECT * FROM {t}").fetchall()
            export_data[t] = [dict(r) for r in rows]
        return json.dumps(export_data, indent=2)


# -----------------------------------------------------------------------------
# Background Persistent OCR Job Management
# -----------------------------------------------------------------------------

def _ensure_ocr_jobs_table(conn: sqlite3.Connection) -> None:
    """Ensure the ocr_jobs table exists idempotently."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ocr_jobs (
            job_id TEXT PRIMARY KEY,
            filename TEXT NOT NULL,
            mock_title TEXT NOT NULL,
            target_exam TEXT NOT NULL DEFAULT 'BPSC',
            job_type TEXT NOT NULL DEFAULT 'mock',
            status TEXT NOT NULL DEFAULT 'running',
            progress REAL NOT NULL DEFAULT 0.0,
            progress_msg TEXT NOT NULL DEFAULT '',
            total_pages INTEGER NOT NULL DEFAULT 0,
            processed_pages INTEGER NOT NULL DEFAULT 0,
            extracted_questions_json TEXT NOT NULL DEFAULT '[]',
            stats_json TEXT NOT NULL DEFAULT '{}',
            error_msg TEXT NOT NULL DEFAULT '',
            cancel_requested INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    try:
        conn.execute("ALTER TABLE ocr_jobs ADD COLUMN job_type TEXT DEFAULT 'mock'")
    except Exception:
        pass


def create_ocr_job(
    job_id: str,
    filename: str,
    mock_title: str,
    target_exam: str = "BPSC",
    total_pages: int = 0,
    job_type: str = "mock",
    conn_factory: Any = None,
) -> None:
    """Register a new background OCR job in SQLite."""
    now = datetime.now().isoformat(timespec="seconds")
    connector = conn_factory or connect_db
    with connector() as conn:
        _ensure_ocr_jobs_table(conn)
        conn.execute(
            """
            INSERT INTO ocr_jobs (
                job_id, filename, mock_title, target_exam, job_type, status,
                progress, progress_msg, total_pages, processed_pages,
                extracted_questions_json, stats_json, error_msg,
                cancel_requested, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, 'running', 0.0, 'Initializing background OCR...', ?, 0, '[]', '{}', '', 0, ?, ?)
            """,
            (job_id, filename, mock_title, target_exam, job_type, total_pages, now, now),
        )
        conn.commit()


def update_ocr_job_progress(
    job_id: str,
    progress: float,
    progress_msg: str,
    processed_pages: int,
    extracted_questions: Optional[List[Dict[str, Any]]] = None,
    stats: Optional[Dict[str, Any]] = None,
    conn_factory: Any = None,
) -> None:
    """Update progress and incremental extracted questions for a running OCR job."""
    now = datetime.now().isoformat(timespec="seconds")
    connector = conn_factory or connect_db
    with connector() as conn:
        _ensure_ocr_jobs_table(conn)
        if extracted_questions is not None and stats is not None:
            conn.execute(
                """
                UPDATE ocr_jobs
                SET progress = ?, progress_msg = ?, processed_pages = ?,
                    extracted_questions_json = ?, stats_json = ?, updated_at = ?
                WHERE job_id = ?
                """,
                (
                    progress,
                    progress_msg,
                    processed_pages,
                    json.dumps(extracted_questions),
                    json.dumps(stats),
                    now,
                    job_id,
                ),
            )
        else:
            conn.execute(
                """
                UPDATE ocr_jobs
                SET progress = ?, progress_msg = ?, processed_pages = ?, updated_at = ?
                WHERE job_id = ?
                """,
                (progress, progress_msg, processed_pages, now, job_id),
            )
        conn.commit()


def complete_ocr_job(
    job_id: str,
    extracted_questions: List[Dict[str, Any]],
    stats: Dict[str, Any],
    conn_factory: Any = None,
) -> None:
    """Mark an OCR job as completed and persist final parsed question payloads."""
    now = datetime.now().isoformat(timespec="seconds")
    connector = conn_factory or connect_db
    with connector() as conn:
        _ensure_ocr_jobs_table(conn)
        conn.execute(
            """
            UPDATE ocr_jobs
            SET status = 'completed', progress = 1.0,
                progress_msg = 'Extraction and categorization complete.',
                extracted_questions_json = ?, stats_json = ?, updated_at = ?
            WHERE job_id = ?
            """,
            (json.dumps(extracted_questions), json.dumps(stats), now, job_id),
        )
        conn.commit()


def fail_ocr_job(
    job_id: str,
    error_msg: str,
    conn_factory: Any = None,
) -> None:
    """Mark an OCR job as failed with error details."""
    now = datetime.now().isoformat(timespec="seconds")
    connector = conn_factory or connect_db
    with connector() as conn:
        _ensure_ocr_jobs_table(conn)
        conn.execute(
            """
            UPDATE ocr_jobs
            SET status = 'failed', error_msg = ?, updated_at = ?
            WHERE job_id = ?
            """,
            (error_msg, now, job_id),
        )
        conn.commit()


def request_cancel_ocr_job(
    job_id: str,
    conn_factory: Any = None,
) -> None:
    """Request graceful cancellation of a running background OCR job."""
    now = datetime.now().isoformat(timespec="seconds")
    connector = conn_factory or connect_db
    with connector() as conn:
        _ensure_ocr_jobs_table(conn)
        conn.execute(
            """
            UPDATE ocr_jobs
            SET cancel_requested = 1, status = 'cancelled',
                progress_msg = 'Extraction cancelled by user.', updated_at = ?
            WHERE job_id = ?
            """,
            (now, job_id),
        )
        conn.commit()


def is_ocr_job_cancel_requested(
    job_id: str,
    conn_factory: Any = None,
) -> bool:
    """Check if the user has requested cancellation for this job."""
    connector = conn_factory or connect_db
    with connector() as conn:
        _ensure_ocr_jobs_table(conn)
        row = conn.execute(
            "SELECT cancel_requested, status FROM ocr_jobs WHERE job_id = ?",
            (job_id,),
        ).fetchone()
        if not row:
            return False
        return bool(row["cancel_requested"]) or row["status"] == "cancelled"


def get_ocr_job(
    job_id: str,
    conn_factory: Any = None,
) -> Optional[Dict[str, Any]]:
    """Retrieve full details of an OCR job, parsing nested JSON structures."""
    connector = conn_factory or connect_db
    with connector() as conn:
        _ensure_ocr_jobs_table(conn)
        row = conn.execute(
            "SELECT * FROM ocr_jobs WHERE job_id = ?",
            (job_id,),
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        try:
            d["extracted_questions"] = json.loads(d.get("extracted_questions_json") or "[]")
        except Exception:
            d["extracted_questions"] = []
        try:
            d["stats"] = json.loads(d.get("stats_json") or "{}")
        except Exception:
            d["stats"] = {}
        return d


def get_active_ocr_job(job_type: Optional[str] = None, conn_factory: Any = None) -> Optional[Dict[str, Any]]:
    """Retrieve currently running background OCR job if any, optionally filtered by job_type."""
    connector = conn_factory or connect_db
    with connector() as conn:
        _ensure_ocr_jobs_table(conn)
        if job_type:
            row = conn.execute(
                "SELECT * FROM ocr_jobs WHERE status = 'running' AND job_type = ? ORDER BY created_at DESC LIMIT 1",
                (job_type,),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM ocr_jobs WHERE status = 'running' ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
        if not row:
            return None
        d = dict(row)
        try:
            d["extracted_questions"] = json.loads(d.get("extracted_questions_json") or "[]")
        except Exception:
            d["extracted_questions"] = []
        try:
            d["stats"] = json.loads(d.get("stats_json") or "{}")
        except Exception:
            d["stats"] = {}
        return d


def get_latest_completed_or_active_job(job_type: Optional[str] = None, conn_factory: Any = None) -> Optional[Dict[str, Any]]:
    """Retrieve the most recent active or completed OCR job for state restoration, optionally filtered by job_type."""
    connector = conn_factory or connect_db
    with connector() as conn:
        _ensure_ocr_jobs_table(conn)
        if job_type:
            row = conn.execute(
                "SELECT * FROM ocr_jobs WHERE status IN ('running', 'completed', 'cancelled') AND job_type = ? ORDER BY created_at DESC LIMIT 1",
                (job_type,),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM ocr_jobs WHERE status IN ('running', 'completed', 'cancelled') ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
        if not row:
            return None
        d = dict(row)
        try:
            d["extracted_questions"] = json.loads(d.get("extracted_questions_json") or "[]")
        except Exception:
            d["extracted_questions"] = []
        try:
            d["stats"] = json.loads(d.get("stats_json") or "{}")
        except Exception:
            d["stats"] = {}
        return d


def clear_ocr_job(
    job_id: str,
    conn_factory: Any = None,
) -> None:
    """Delete an OCR job record after it has been reviewed or saved."""
    connector = conn_factory or connect_db
    with connector() as conn:
        _ensure_ocr_jobs_table(conn)
        conn.execute("DELETE FROM ocr_jobs WHERE job_id = ?", (job_id,))
        conn.commit()

