# -*- coding: utf-8 -*-
"""
White Label Resume Builder:
1) build_white_label_prompt(...) — промпт для GPT/Gemini (строгие правила, Projects — обязательно).
2) generate_resume_payload_gemini(...) — запрос к Gemini, возврат JSON payload {config, content}.
3) render_resume_docx(payload) — рендер красивого .docx по JSON (Times New Roman, синие заголовки).
4) create_white_label_resume(...) — полный конвейер: кандидатский текст -> JSON -> DOCX.
5) parse_json_loose(...) — «живучий» парсер JSON из свободного текста модели.
"""

from datetime import datetime
from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_BREAK
import json, re

def _extract_text_from_gemini_response(resp) -> str:
    try:
        if getattr(resp, "text", None):
            return (resp.text or "").strip()
    except Exception:
        pass
    out = []
    try:
        for cand in (getattr(resp, "candidates", None) or []):
            content = getattr(cand, "content", None)
            parts = getattr(content, "parts", None) if content else None
            if not parts:
                continue
            for p in parts:
                t = getattr(p, "text", None)
                if t: out.append(t)
    except Exception:
        pass
    return "\n".join(out).strip()

def _hex_to_rgb(hex_color: str) -> RGBColor:
    h = (hex_color or "#000000").lstrip('#')
    return RGBColor(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))

def _set_core_styles(doc: Document, font_family: str, font_size_main: int):
    style = doc.styles['Normal']
    style.font.name = font_family
    style.font.size = Pt(font_size_main)
    for sec in doc.sections:
        sec.top_margin = Inches(0.8)
        sec.bottom_margin = Inches(0.8)
        sec.left_margin = Inches(0.8)
        sec.right_margin = Inches(0.8)

def _add_section_title(doc: Document, title: str, color_hex: str, font_size_headings: int):
    p = doc.add_paragraph()
    r = p.add_run(title)
    r.bold = True
    r.font.size = Pt(font_size_headings)
    r.font.color.rgb = _hex_to_rgb(color_hex)
    p.paragraph_format.line_spacing = 1.2
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(4)

def _add_text(doc: Document, text: str, bold: bool = False):
    if not text:
        return
    p = doc.add_paragraph(text)
    if p.runs:
        p.runs[0].bold = bool(bold)
    p.paragraph_format.line_spacing = 1.2
    p.paragraph_format.space_after = Pt(2)

def _render_skills(doc: Document, skills):
    if not skills:
        return
    if isinstance(skills, str):
        _add_text(doc, skills)
    elif isinstance(skills, list):
        _add_text(doc, ", ".join(map(str, skills)))
    elif isinstance(skills, dict):
        for k, v in skills.items():
            line = f"{k}: {', '.join(map(str, v)) if isinstance(v, list) else v}"
            _add_text(doc, line)

def _render_experience(doc: Document, exp_list: list):
    if not exp_list:
        return
    for it in exp_list:
        header = " — ".join([x for x in [it.get("company"), it.get("position")] if x])
        if header: _add_text(doc, header, bold=True)
        if it.get("period"): _add_text(doc, it["period"], bold=True)  # Сделать период полужирным
        for key in ("responsibilities", "achievements"):
            for ln in (it.get(key) or []):
                _add_text(doc, ln)
        techs = it.get("technologies") or []
        if techs:
            _add_text(doc, f"Технологии: {', '.join(map(str, techs))}")

def _render_education(doc: Document, education):
    if not education:
        return
    if isinstance(education, str):
        _add_text(doc, education); return
    for ed in education:
        line = " — ".join(filter(None, [ed.get("institution"), ed.get("degree")]))
        if line: _add_text(doc, line, bold=True)
        if ed.get("years"): _add_text(doc, ed["years"])
        if ed.get("details"): _add_text(doc, ed["details"])

def _render_projects(doc: Document, projects: list):
    if not projects:
        return
    for pr in projects:
        if pr.get("title"): _add_text(doc, pr["title"], bold=True)
        if pr.get("role"): _add_text(doc, f"Роль: {pr['role']}")
        if pr.get("period"): _add_text(doc, f"Период: {pr['period']}")
        if pr.get("description"): _add_text(doc, pr["description"])
        techs = pr.get("technologies") or []
        if techs: _add_text(doc, f"Технологии: {', '.join(map(str, techs))}")
        if pr.get("results"): _add_text(doc, f"Результаты: {pr['results']}")

def _post_fix_bold_skills(doc: Document):
    SECTION_HEADERS = {
        "РЕЗЮМЕ", "КРАТКОЕ ОПИСАНИЕ ПРОФИЛЯ",
        "КЛЮЧЕВЫЕ НАВЫКИ", "ОПЫТ РАБОТЫ", "ОБРАЗОВАНИЕ",
        "ДОПОЛНИТЕЛЬНАЯ ИНФОРМАЦИЯ", "ПРОЕКТЫ",
    }
    start_idx, end_idx = None, None
    for i, p in enumerate(doc.paragraphs):
        if p.text.strip().upper() == "КЛЮЧЕВЫЕ НАВЫКИ":
            start_idx = i + 1
            break
    if start_idx is None:
        return
    for j in range(start_idx, len(doc.paragraphs)):
        if doc.paragraphs[j].text.strip().upper() in SECTION_HEADERS:
            end_idx = j
            break
    if end_idx is None:
        end_idx = len(doc.paragraphs)
    for k in range(start_idx, end_idx):
        p = doc.paragraphs[k]
        txt = p.text
        if not txt or ":" not in txt:
            continue
        idx = txt.find(":")
        head = txt[: idx + 1].strip()
        tail = txt[idx + 1 :].lstrip()
        for r in p.runs: r.text = ""
        run_head = p.add_run(head + (" " if tail else "")); run_head.bold = True
        if tail:
            run_tail = p.add_run(tail); run_tail.bold = False

def _post_fix_inline_dicts(doc: Document):
    pattern = re.compile(r"^\s*\{\s*'title'\s*:\s*'([^']*)'\s*,\s*'items'\s*:\s*\[([^\]]*)\]\s*\}\s*$")
    for p in doc.paragraphs:
        m = pattern.match(p.text.strip())
        if not m:
            continue
        title = m.group(1).strip()
        items_raw = m.group(2).strip()
        parts = [x.strip().strip("'").strip('"') for x in items_raw.split(",") if x.strip()]
        for r in p.runs: r.text = ""
        if title:
            rt = p.add_run(title); rt.bold = True
        for it in parts:
            br = p.add_run(); br.add_break(WD_BREAK.LINE)
            p.add_run(it)

def render_resume_docx(payload: dict, vacancy_text: str = "") -> str:
    cfg = payload.get("config", {})
    cnt = payload.get("content", {})
    doc = Document()
    _set_core_styles(doc, cfg.get("font_family", "Times New Roman"), int(cfg.get("font_size_main", 12)))
    color = cfg.get("color_headings", "#1F4E79")
    hsize = int(cfg.get("font_size_headings", 14))
    sections = cfg.get("sections", [
        "ФИО","РЕЗЮМЕ","Краткое описание профиля",
        "Ключевые навыки","Опыт работы","Образование","Дополнительная информация","Проекты"
    ])
    fio = cnt.get("fio") or {}
    # Убираем отдельное отображение ФИО в начале - оно будет в секции РЕЗЮМЕ
    
    for sec in sections:
        su = sec.upper()
        if su == "ФИО":
            continue
        _add_section_title(doc, sec, color, hsize)
        if su == "РЕЗЮМЕ":
            if fio.get("full_name"): _add_text(doc, f"ФИО: {fio['full_name']}", bold=True)
            if cnt.get("position_grade"): _add_text(doc, f"ДОЛЖНОСТЬ: {cnt['position_grade']}", bold=True)
            if cnt.get("grade"): _add_text(doc, f"Грейд: {cnt['grade']}", bold=True)
            if fio.get("location"): _add_text(doc, f"Локация: {fio['location']}", bold=True)
            if fio.get("citizenship"): _add_text(doc, f"Гражданство: {fio['citizenship']}", bold=True)
            if fio.get("birth_date"): _add_text(doc, f"Дата рождения: {fio['birth_date']}", bold=True)
        elif su == "КРАТКОЕ ОПИСАНИЕ ПРОФИЛЯ":
            if cnt.get("summary"): _add_text(doc, cnt["summary"])
        elif su == "КЛЮЧЕВЫЕ НАВЫКИ":
            _render_skills(doc, cnt.get("skills"))
        elif su == "ОПЫТ РАБОТЫ":
            _render_experience(doc, cnt.get("experience"))
        elif su == "ОБРАЗОВАНИЕ":
            _render_education(doc, cnt.get("education"))
        elif su == "ДОПОЛНИТЕЛЬНАЯ ИНФОРМАЦИЯ":
            extra = cnt.get("extra")
            if isinstance(extra, list):
                for ln in extra: _add_text(doc, str(ln))
            elif extra: _add_text(doc, str(extra))
        elif su == "ПРОЕКТЫ":
            _render_projects(doc, cnt.get("projects"))
    _post_fix_bold_skills(doc)
    _post_fix_inline_dicts(doc)
    
    # Выделяем технологии из вакансии жирным шрифтом
    if vacancy_text:
        technologies = _extract_technologies_from_vacancy(vacancy_text)
        _highlight_technologies_in_text(doc, technologies)
    
    name_for_file = (cnt.get("fio") or {}).get("full_name") or "Name"
    date_str = datetime.now().strftime("%Y-%m-%d")
    # Use current directory instead of Linux path
    import os
    fn = os.path.join(os.getcwd(), f"WhiteLabel_Resume_{name_for_file.replace(' ', '_')}_{date_str}.docx")
    doc.save(fn)
    return fn

def parse_json_loose(raw):
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str):
        raise ValueError("Ожидалась строка с JSON.")
    
    s = raw.strip()
    print(f"DEBUG: Original response length: {len(s)}")
    
    # Check for truncated JSON (incomplete braces)
    open_braces = s.count('{')
    close_braces = s.count('}')
    if open_braces > close_braces:
        print(f"WARNING: JSON appears to be truncated. Open braces: {open_braces}, Close braces: {close_braces}")
    
    # Remove markdown code blocks
    if s.startswith("```json"):
        s = s[len("```json"):].strip()
    if s.endswith("```"):
        s = s[:-3].strip()
    
    # Try parsing as-is
    try:
        return json.loads(s)
    except json.JSONDecodeError as e:
        print(f"DEBUG: First parse attempt failed: {e}")
    
    # Try extracting JSON from braces
    try:
        start, end = s.find("{"), s.rfind("}")
        if start != -1 and end != -1 and end > start:
            json_part = s[start:end+1]
            print(f"DEBUG: Extracted JSON part length: {len(json_part)}")
            return json.loads(json_part)
    except json.JSONDecodeError as e:
        print(f"DEBUG: Second parse attempt failed: {e}")
    
    # Remove invisible characters
    s2 = re.sub(r"[\u200b-\u200f\u202a-\u202e]", "", s)
    
    # Try one more time with cleaned string
    try:
        return json.loads(s2)
    except json.JSONDecodeError as e:
        print(f"DEBUG: Final parse attempt failed: {e}")
        print(f"DEBUG: Problematic JSON around error position:")
        error_pos = getattr(e, 'pos', 0)
        start_pos = max(0, error_pos - 100)
        end_pos = min(len(s2), error_pos + 100)
        print(f"DEBUG: Context: {repr(s2[start_pos:end_pos])}")
        
        # Try to fix common JSON issues
        s3 = s2
        # Fix trailing commas
        s3 = re.sub(r',(\s*[}\]])', r'\1', s3)
        # Fix unescaped quotes in strings
        s3 = re.sub(r'(?<!\\)"(?=.*".*:)', r'\\"', s3)
        
        # Try to complete truncated JSON by adding missing closing braces
        open_braces = s3.count('{')
        close_braces = s3.count('}')
        if open_braces > close_braces:
            missing_braces = open_braces - close_braces
            print(f"DEBUG: Attempting to complete truncated JSON by adding {missing_braces} closing braces")
            s3 = s3.rstrip(',\n\r\t ') + '}' * missing_braces
        
        try:
            return json.loads(s3)
        except json.JSONDecodeError as e2:
            print(f"DEBUG: Even after fixes, parsing failed: {e2}")
            # Save the problematic JSON to a file for inspection
            with open("debug_json_error.txt", "w", encoding="utf-8") as f:
                f.write(f"Original error: {e}\n")
                f.write(f"Error position: {error_pos}\n")
                f.write(f"Problematic JSON:\n{s2}")
            raise ValueError(f"Не удалось распарсить JSON. Ошибка: {e}. Детали сохранены в debug_json_error.txt")

def _extract_technologies_from_vacancy(vacancy_text: str) -> list:
    """Извлекает технологии и ключевые слова из текста вакансии"""
    import re
    
    # Общие технологии и фреймворки
    tech_patterns = [
        r'\b(?:Python|Java|JavaScript|TypeScript|C\#|C\+\+|PHP|Ruby|Go|Rust|Kotlin|Swift)\b',
        r'\b(?:React|Angular|Vue|Django|Flask|Spring|Laravel|Express|Node\.js)\b',
        r'\b(?:PostgreSQL|MySQL|MongoDB|Redis|Elasticsearch|Oracle|SQL Server)\b',
        r'\b(?:Docker|Kubernetes|AWS|Azure|GCP|Jenkins|GitLab|GitHub)\b',
        r'\b(?:Linux|Windows|MacOS|Ubuntu|CentOS)\b',
        r'\b(?:Git|SVN|Mercurial)\b',
        r'\b(?:REST|GraphQL|API|JSON|XML|SOAP)\b',
        r'\b(?:HTML|CSS|SASS|LESS|Bootstrap|Tailwind)\b',
        r'\b(?:Webpack|Vite|Babel|ESLint|Prettier)\b',
        r'\b(?:Terraform|Ansible|Puppet|Chef)\b',
        r'\b(?:Prometheus|Grafana|ELK|Splunk)\b',
        r'\b(?:Kafka|RabbitMQ|ActiveMQ)\b',
        r'\b(?:Hadoop|Spark|Airflow|Greenplum)\b'
    ]
    
    technologies = set()
    text_upper = vacancy_text.upper()
    
    for pattern in tech_patterns:
        matches = re.findall(pattern, vacancy_text, re.IGNORECASE)
        technologies.update(matches)
    
    return list(technologies)

def _highlight_technologies_in_text(doc: Document, technologies: list):
    """Выделяет технологии жирным шрифтом в документе"""
    if not technologies:
        return
        
    import re
    
    for paragraph in doc.paragraphs:
        if not paragraph.text.strip():
            continue
            
        original_text = paragraph.text
        has_matches = False
        
        # Проверяем, есть ли технологии в этом параграфе
        for tech in technologies:
            if re.search(r'\b' + re.escape(tech) + r'\b', original_text, re.IGNORECASE):
                has_matches = True
                break
        
        if not has_matches:
            continue
            
        # Очищаем параграф и пересоздаем с выделением
        paragraph.clear()
        
        remaining_text = original_text
        while remaining_text:
            # Находим ближайшее совпадение
            earliest_match = None
            earliest_pos = len(remaining_text)
            matched_tech = None
            
            for tech in technologies:
                match = re.search(r'\b' + re.escape(tech) + r'\b', remaining_text, re.IGNORECASE)
                if match and match.start() < earliest_pos:
                    earliest_pos = match.start()
                    earliest_match = match
                    matched_tech = tech
            
            if earliest_match is None:
                # Нет больше совпадений, добавляем остальной текст
                paragraph.add_run(remaining_text)
                break
            
            # Добавляем текст до совпадения
            if earliest_pos > 0:
                paragraph.add_run(remaining_text[:earliest_pos])
            
            # Добавляем совпадение жирным
            bold_run = paragraph.add_run(earliest_match.group())
            bold_run.bold = True
            
            # Продолжаем с оставшимся текстом
            remaining_text = remaining_text[earliest_match.end():]

def build_prompt_simple(candidate_text: str, vacancy_text: str) -> str:
    return f"""
Верни ТОЛЬКО JSON {{"config":{{...}}, "content":{{...}}}} на русском, без комментариев.
White Label: не включай контакты и email. Сохрани ВСЁ содержание без сокращений.
Если нет Summary — создай 3–5 предложений. Определи должность по вакансии.
ГРЕЙД: определи только как Senior, Middle или Junior на основе опыта работы.
ГРАЖДАНСТВО: определи из локации и укажи как РФ (для России/Москвы), РБ (для Беларуси/Минска), или возьми из резюме если указано.
ПРОЕКТЫ обязательны: найди все даже если они спрятаны в обязанностях/Обо мне.
Схема:
{{
 "config": {{
   "output_format": "docx",
   "font_family": "Times New Roman",
   "font_size_main": 12,
   "font_size_headings": 14,
   "color_headings": "#1F4E79",
   "language": "ru",
   "sections": [
     "ФИО","РЕЗЮМЕ","Краткое описание профиля",
     "Ключевые навыки","Опыт работы","Образование","Дополнительная информация","Проекты"
   ],
   "white_label": true,
   "exclude_contacts": true,
   "exclude_email": true
 }},
 "content": {{
   "fio": {{"full_name":"","location":"","citizenship":"","birth_date":""}},
   "position_grade":"", "grade":"", "summary":"",
   "skills": {{}},
   "experience":[{{"company":"","position":"","period":"","responsibilities":[],"technologies":[],"achievements":[]}}],
   "education":[{{"institution":"","degree":"","years":"","details":""}}],
   "extra": [],
   "projects":[{{"title":"","role":"","period":"","description":"","technologies":[],"results":""}}]
 }}
}}

ИСХОДНОЕ РЕЗЮМЕ:
{candidate_text}

ТРЕБОВАНИЯ ВАКАНСИИ:
{vacancy_text}
""".strip()

def generate_payload_once(api_key: str,
                          candidate_text: str,
                          vacancy_text: str,
                          model_name: str = "gemini-2.5-pro") -> dict:
    import google.generativeai as genai
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)
    prompt = build_prompt_simple(candidate_text, vacancy_text)
    resp = model.generate_content(
        prompt,
        generation_config=genai.types.GenerationConfig(
            temperature=0.1,
            max_output_tokens=12288,  # Increased from 6144 to handle larger resumes
            response_mime_type="application/json",
        )
    )
    raw = _extract_text_from_gemini_response(resp)
    if not raw:
        finish = None
        safety = None
        try:
            if resp.candidates:
                finish = getattr(resp.candidates[0], "finish_reason", None)
                safety = getattr(resp.candidates[0], "safety_ratings", None)
        except Exception:
            pass
        raise ValueError(f"Пустой ответ от Gemini. finish_reason={finish}, safety={safety}")
    data = parse_json_loose(raw)
    if not isinstance(data, dict) or "config" not in data or "content" not in data:
        raise ValueError("Модель не вернула JSON с ключами {config, content}.")
    cfg = data.setdefault("config", {})
    if "sections" in cfg and "Проекты" not in cfg["sections"]:
        cfg["sections"].append("Проекты")
    return data

def create_white_label_resume_once(api_key: str,
                                   candidate_text: str,
                                   vacancy_text: str):
    payload = generate_payload_once(api_key, candidate_text, vacancy_text)
    filename = render_resume_docx(payload, vacancy_text)
    return filename

#===== Пример использования (раскомментируй, подставь API ключ и тексты) =====

import os
from dotenv import load_dotenv
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if __name__ == "__main__":
    candidate = '''
      
Contact
 Apt 321, 31, Veshnyakovskaya
 str., Moscow, 111538, Russian
 Federation.
 7-916-685-9607 (Mobile)
 sergts@mail.ru
 www.linkedin.com/in/sergts
 (LinkedIn)
 github.com/itboss2 (Portfolio)
 Top Skills
 System Architects
 Telecommunications Billing
 WebSphere ESB
 Languages
 English - C1 Certified (Full
 Professional)
 Bulgarian (Elementary)
 Russian - C2 Certifed (Native or
 Bilingual)
 Byelorussian - C2 Certified (Full
 Professional)
 Polish (Limited Working)
 German (Elementary)
 Ukrainian (Elementary)
 Certifications
 Palo Alto Networks Accredited
 Configuration Engineer (ACE) 
PAN-OS 6.1
 Cisco Network Support Engineer
 VMware Technical Sales
 Professional 5 for 6 competencies:
 Infrastructure Virtualization, Desktop
 Virtualization, Business Continuity,
 Virtualization of Business Critical
 Applications, Infrastructure as a
 Service, Management
 IBM Certified Database Associate 
DB2 10.1 Fundamentals
 Honors-Awards
 3rd prize winner of Russia Huawei
 2017 Channel Partner Skill
 Competition
 Sergey Tsuprikov, Tech
 Advisor, IBM DS, LSSBB,
 MCP,Mentor
 IT architect and project manager with 10+ years of experience in
 Big Data, Data Science, enterprise software design area | Banking
 | Telecom | FinTech | Data Lake | DWH | BI | Data Driven | Data
 Management | Data Quality
 Moscow, Moscow City, Russia
 Summary
 12+ years of experience as an IT architect for enterprise software
 (like OEBSl) design, complicated cross-platform data migration and
 integration, distributed data centers turn-key design.
 7+ years of experience as a project manager for projects up to 15M
 USD. 
7+ years of experience as a business and/or system analyst, mostly
 in the banking area. 
5+ years of experience as an out-staff instructor (PMI PMBOK,
 PRINCE2, ITIL, IBM solutions).
 10+ years of experience as a subject matter expert (SME) in banking
 and finance, sales and marketing, logistics, manufacturing, retail,
 FMCG. 
5+ years of successful daily work face-to-face and remote with
 Indian banking analysts from Oracle Corp. 
My mobile phone: 7-916-685-9607 (9:00-22:00 GMT+3, Moscow),
 Telegram: @sergts1 .
 My private email - sergts@mail.ru (please, use bossit@gmail.com
 only in case of troubles with sending to sergts@mail.ru).
 I have 30+ years of experience in IT. Have received 120+ worldwide
 IT certificates after exams (i.e. 70+ technical from IBM): Program
 & Portfolio Management Expert (#35), Project Management
 Expert (PME) #000412, IBM Data Science Professional, VMware
 Certified Professional 4 (#63533), EMCTAe, Six Sigma Black Belt
 Professional, MCP, etc. 
 Page 1 of 9
  
3rd prize winner of 1st Innotech All
Russia hackathon for VTB banking
 group (Top2 in Russia)
 Honorable Mention of O'Reilly
 worldwide IT architecture contest
 (Architectural Katas 2021)
 3rd prize winner of annual student
 judo championship of Belarusian
 State University
 Top 25 influencer of Russian IT
 market
 Publications
 Fluctuational transitions in an
 optically bistable element
 30+ my (w/o coauthor) articles
 Set of 570+ my own (w/o co-authors)
 publications in printed magazines
 Fluctuational transitions and related
 phenomena in a passive all-optical
 bistable system
 Stochastic resonance in an all
optical passive bistable system
 Hardware: PC, Mac, HP/IBM/Dell servers, HP/IBM/EMC/NetApp/Dell
 NAS/SAN, LAN/WAN. 
OS: IBM AIX, Linux CentOS, MS Windows 10, Windows Server
 2016, MacOS.
 Programming languages: Python, VBA, DHTML, PGSQL, PL/SQL.
 Methodologies: ASAP, AIM, PJM, PMBOK, BABOK, PRINCE2,
 RUP, BPMN, MSF, MOF, SADT (IDEF), Agile SCRUM, ITIL, ITSM,
 TQM, COBIT, Lean, Six Sigma, TDD, TOGAF, QFD, COSO, ISO.
 DBMS: MS SQL Server, Oracle Database, PostgreSQL, MS Access.
 Application software: MS Project Server, Jira, SAP BO, MS Office,
 MS Visio, ARIS ToolSet, Atlassian Jira, Confluence, SPSS, Matlab,
 VMware, Citrix, HP Service Manager, SVN, Orbus iServer.
 Core banking systems: Misys MIDAS, Misys Equation, Oracle
 FLEXCUBE, FIS Sanchez Profile, DiasoftBank.
 I have visited 400+ IT events worldwide (in 10+ countries) and
 was a speaker at various events. 5+years was a staff writer of
 Computerworld-Russia, after was a frequent contributor to several
 IT major magazines, included PCWEEK, BYTE, Macworld, Network
 World. Was included in the records book of Russia due to the
 number of printed publications (570+) in mass media without co
authors.
 Countries I visited during a business trips (times in bracket): USA
 (2), Germany (5), France (2), Switzerland (1), UK (2), Ireland (2),
 Singapore (1), South Korea (1), Cyprus (2), Poland (1), Czech (1).
 And 10+ (mostly, Europe) in vacations.
 Experience
 Nexign
 Solutions Architect
 March 2025 - May 2025 (3 months)
 Moscow, Moscow City, Russia
 Design of the billing systems (OSS/BSS) integration with banking and payment
 solutions for Megafon (#2 telco operator in RF and CIS: 78M customers, 36K
 staff).
 Stack: Sparx EA, Oracle database, PostgreSQL, RabbitMQ, Linux, K8s.
 Innotech
 Page 2 of 9
  
2 years 7 months
 Platform Solutions Architect
 June 2023 - March 2025 (1 year 10 months)
 Moscow, Moscow City, Russia
 The largest IT company (www.inno.tech) in Russia with 16K+ staff focused
 to custom software development for banks. All my projects below dedicated
 to VTB banking group, one of the largest financial institutions in Europe (20M
 retail clients, 1М corporate clients). All solutions below based on MSA and with
 streaming data to Hadoop:- Designed from scratch a payments engine for partners.- Designed a corporate loans solution for migration from old CFT core banking
 systems to new.- Upgraded a corporate pledges module with integration for external
 organizations (Pricestat, M2, Federal Notarial Chamber, etc).
 Lead Architect
 September 2022 - May 2023 (9 months)
 Moscow, Moscow City, Russia
 Designed a Risk Management solution (RWA calculation) based on Hadoop
 Data Lake with Spark engine and DWH based on GreenPlum MPP for VTB
 bank. 
Stack: Oracle database, PostgreSQL, Apache Airflow, Apache Spark,
 Greenplum, Linux, K8s, Hadoop, OpenShift.
 Promsvyazbank
 System Architect
 May 2021 - September 2022 (1 year 5 months)
 Moscow, Moscow City, Russia
 Universal bank (www.psbank.ru) in Top5 Russia, with offices also in China,
 Kazakhstan, Cyprus.- Designed of 20+ production & testing environments, mostly for CBS, ERP,
 card processing. - Reviewed and tested of 10+ tools for Architecture as a Code.- Performed an IT architecture audit for several large banks during M&A
 processes.
 Stack:: Oracle database, PostgreSQL, Kafka, SAP PI, SAP PO, Informatica
 PWC, IBM WAS, K8s, ELK, Hadoop, VMware, Linux, RabbitMQ.
 MTS Group
 Senior Solutions Architect
 Page 3 of 9
  
December 2020 - May 2021 (6 months)
 Moscow, Moscow City, Russia
 #1 telco operator (www.mts.ru) in Russia with offices also in Belarus, Armenia:
 88M+ customers, 15K+ staff. Designed a KION - the top high-load on-line
 cinema. Stack: Java (+Spring Boot), PostgreSQL, Python, Apache Kafka,
 Redis, Memcached, Kubernetes (K8s), Docker, ELK, Hadoop, Prometheus,
 GitLab.
 Federal Treasury of Russian Federation  
Deputy Head of system architecture department
 December 2018 - November 2020 (2 years)
 Moscow,  Russian Federation
 www.roskazna.gov.ru - the one of the largest daughter at Ministry of Finance.
 130M+ customers.- Designed a huge Data Centers and distributed DR high load IT solutions for
 24x7x365, including Big Data: 85 regions of RF in 11 time zones, 2M+ users. - Transformed Oracle e-Business Suite (OEBS) to custom-developed SW with
 the same features  (10M+ USD budget). - Designed a draft of a large Data Lake based on Hadoop with several ETL/
 ELT tools. 
Stack: 20+ Oracle SW solutions (DB, RAC, OEBS, GG, etc), Java (+Spring
 Boot), Python, Hadoop, PostgreSQL, Docker, Kubernetes (K8s), Apache
 Kafka, Cassandra, Ignite, Camel, ActiveMQ, ELK.
 NTR Lab (Software Development)
 Analyst Team Lead
 July 2018 - October 2018 (4 months)
 Moscow, Russian Federation
 Completed 10+ presale projects for IT solutions: AI (artificial neural networks,
 Machine Learning, Computer Vision), Big Data, IoT, blockchain. Developed a
 data model and other elements for an innovative blockchain solution based on
 the directed acyclic graph (DAG). Managed a team of 6 analysts.
 Premium IT Solution
 Lead Analyst
 February 2018 - April 2018 (3 months)
 Moscow, Russian Federation
 Renovated features of cash centers chain for Sberbank of Russia (Top1).
 SCANEX R&D Center
 Lead Engineer
 Page 4 of 9
  
July 2014 - December 2017 (3 years 6 months)
 Moscow, Russian Federation
 Only one manufacturer (www.scanex.ru) in Russia of own designed space
 stations for Earth remote censoring.
 Designed: cloud portal (SaaS) based on OpenStack & OpenShift for maritime
 navigation (1M+ USD budget), Earth remote censoring center for Emergency
 Ministry of Kazakhstan, Defense Ministry of RF; optimized satellites data
 receiving business processes. Trained 20+ persons (PMI PMBOK, PRINCE2,
 ITIL, IBM). Stack: Centos Linux, Python, VMware vSphere, Oracle MySQL, MS
 SQL Server, PostgreSQL, Docker, K8s, AWS, MS Azure.
 ANT-Inform
 Project manager
 November 2013 - February 2014 (4 months)
 Moscow, Russian Federation
 Implemented of own designed ERP/MES system for several Gazprom
 branches.
 Compulink Group
 IT Architect
 October 2012 - October 2013 (1 year 1 month)
 Moscow, Russian Federation
 System integrator (www.compulink.ru) in Top10 of Russia. 200+ staff.
 Designed a DC for the largest Moscow Energy company (VMware SRM,
 Linux HA Cluster for SAP R/3); DC for the largest oil transport company
 (EMC VMAX, IBM Power); DC for a large oil company (NetApp FAS3220
 MetroCluster).
 KPBS (Krikunov & Partners Business Systems)
 Senior Expert
 July 2011 - June 2012 (1 year)
 Moscow, Russian Federation
 Completed cross-platform data migration for Societe Generale Bank from Delta
 Informatic core banking systems (CBS) based on Oracle to Misys Equation
 CBS based on IBM DB2, developed a logistic module (based on OpenBravo
 source code) for Leroy Merlin hypermarkets chain. 
Written recommendations: Petr Chekunaev, Head of the development
 department at Krikunov & Partners Business Systems
 Page 5 of 9
  
Quorum Ltd.
 Key accounts manager
 October 2010 - February 2011 (5 months)
 Moscow, Russian Federation
 The member of Compulink Group dedicated to CBS and other software
 package development for banks. Completed 10+ bids (CBS, electronic
 documents archive solutions). Conducted presentation&demo of electronic
 documents archive solution of Quorum Ltd. for 20+ banks on-site.
 CPS (Center of Professional Software).
 Division head/Project manager
 November 2009 - September 2010 (11 months)
 Managed several sales and sales support projects of IT solutions: VMware,
 Veeam, Citrix, Symantec, IBM, HP. Have signed partner contracts with ~10
 new IT vendors, mostly Western.
 Written recommendations: Sergey Kondrashov, Head of marketing and
 development department at CPS
 Jet Infosystems
 Information Technology Analyst
 November 2006 - April 2009 (2 years 6 months)
 Moscow
 Implemented Oracle FLEXCUBE (#1 CBS) at Unicreditbank. Completed data
 cleansing and migration from MIDAS CBS to FLEXCUBE: developed strategy
 and project plan, mapped data, created reports, PL/SQL scripts, carried out
 UAT, another testing. 
Written recommendations: Dmitry Chernov, Head of FLEXCUBE department at
 Jet Infosystems
 Bank Renaissance Credit
 Project manager
 June 2006 - October 2006 (5 months)
 Implemented of FIS Sanchez Profile (Western CBS), integrated FIS Sanchez
 Profile, DiasoftBank, other systems (OpenWay W4, Capstone, etc) by using
 IBM WebSphere ESB.
 CSBI Group
 Principal consultant
 Page 6 of 9
  
September 2004 - May 2006 (1 year 9 months)
 Moscow, Russian Federation
 Completed 10+ bids for complex IT solutions: CBS, Enterprise documents
 management solutions (EDMS), credit scoring solutions, card management
 systems, ERP, CRM, etc. 
Written recommendations: Dmitry Chernov, General manager deputy at
 ComputerLand CIS
 US Russia Marketing Group
 Project manager
 August 2002 - May 2004 (1 year 10 months)
 Completed 10+ market researches in the area of high-end electronics and
 industrial equipment, carried out business development, sales & marketing.
 Written recommendations: Iliya Gorbatov, head at URMG representation office
 in Moscow, RF
 Interface Ltd.
 CEO deputy of international operations
 March 2002 - August 2002 (6 months)
 Moscow, Russian Federation
 Sales and marketing business software solutions (ERP, CRM, EDMS, etc) for
 foreign clients. Created several business plans and offers for investors.
 NBZ Computers
 Head Of Marketing Department
 January 2001 - March 2002 (1 year 3 months)
 Moscow, Russian Federation
 Carried out of the promotion campaigns for IT solutions: Apple, Tally, OKI,
 Minolta-QMS.
 Diamond Communications
 Head Of Marketing Department
 March 2000 - December 2000 (10 months)
 Moscow, Russian Federation
 Carried out of the promotion campaigns for IT solutions: Cisco, Lucent, RAD,
 Digi, etc. Managed 5 subordinates.
 Cabletron Systems
 Marketing manager
 Page 7 of 9
  
September 1999 - March 2000 (7 months)
 Moscow, Russian Federation
 Managed of the promotion campaigns for Cabletron network products. Created
 a Russian version of a corporate website (cabletron.ru).
 Written recommendations: Denis Symington, Country manager at Cabletron
 CIS
 Sybase Software
 Marketing Manager
 August 1998 - May 1999 (10 months)
 Moscow, Russian Federation
 Carried out of the promotion campaigns of Sybase Software products: DBMS,
 DWH, SW dev tools.
 LANIT
 Sales and Marketing Manager
 May 1997 - June 1998 (1 year 2 months)
 Moscow, Russian Federation
 Carried out of the promotion campaigns of major LANIT software products:
 LanHello, LanVisit, LanDocs, etc.
 Written recommendations: Leonid Manihas, General manager deputy at
 LANIT.
 Infoart Ltd.
 Senior Staff Writer
 October 1996 - May 1997 (8 months)
 Published more than 50 own (i.e. w/o co-authors) articles in IT and business
 area at the ComputerWeek-Moscow weekly.
 Compulink Group
 Marketing Manager
 October 1995 - October 1996 (1 year 1 month)
 Moscow, Russian Federation
 Increased sales revenue of Unisys PCs and servers in 3+ times.
 Infoart Ltd.
 Senior Sraff Writer
 October 1992 - October 1995 (3 years 1 month)
 Moscow, Moscow City, Russia
 Page 8 of 9
  
Printed 500+ own articles about IT business w/o co-authors, mostly in
 ComputerWorld-Russia weekly. Visited 10+ countries (mostly Western Europe
 as well as US and Singapore) during business trips.
 Education
 Corporate Finance Institute® (CFI)
 Some finance analysis courses, close to Business Intelligence & Data Analyst
 (BIDA) certification · (February 2023 - December 2024)
 IBM Big Data University
 Some university courses, Big Data · (January 2019 - September 2022)
 Deep Learning School at Moscow Institute of Physics and
 Technology
 Some university courses, Advanced stream: Python, NumPy, Deep Learning,
 Neural Networks, Neural Machine Translation.  · (2019 - 2020)
 Charles Sturt University
 Some university courses, Computer Science · (2017 - 2020)
 IBM Partners Academy
 Diploma, IT: software & hardware, services, tech support, ITSM · (2012 - 2018)
 Page 9 of 9'''
    vacancy = '''
    BD-10128 (https://t.me/omega_vacancy_bot?start=3093_BD-10128)
📅 Дата публикации: 08.10.2025 12:13

🥇 Разработчик EDW (Middle / Middle+)

🇧🇾💰 Месячная ставка для юр лица РБ:
Вариант 1. Ежемесячная выплата Штат/Контракт (на руки) до: 141 000 RUB (с выплатой зарплаты 11 числа месяца следующего за отчетным)

Вариант 2. Выплата ИП/Самозанятый
С отсрочкой платежа 50 рабочих дней после подписания акта:
(Актирование: ежемесячное):
1346 RUB/час (Gross)
Справочно в месяц (при 165 раб. часов): 222 000 RUB(Gross)

🇷🇺💰 Месячная ставка для юр лица РФ:
Вариант 1. Ежемесячная выплата Штат/Контракт (на руки) до: 135 000 RUB (с выплатой зарплаты 11 числа месяца следующего за отчетным)

Вариант 2. Выплата ИП/Самозанятый
С отсрочкой платежа 50 рабочих дней после подписания акта:
(Актирование: ежемесячное):
1403 RUB/час (Gross)
Справочно в месяц (при 165 раб. часов): 231 000 RUB(Gross)

📍 Локация/Гражданство: Любая / Любое
🏠 Формат работы: Удалённо (фулл-тайм, тайм-зона МСК)
🎓 Грейд: Middle / Middle+

📎 Задачи:
— Разработка программного кода новых и доработка существующих компонентов аналитического хранилища данных;
— Разработка правил и практик работы с кодом, описание их в базе знаний;
— Разработка и описание механизмов публикации кода и релизов;
— Оптимизация запросов и структур баз данных;
— Оперативное реагирование на информацию о проблемах в зоне ответственности, выполнение задач в установленный срок;
— Проведение код-ревью.

💻 Требования:
— Общий опыт работы не менее 3 лет;
— Опыт работы с ELT-процессами;
— Опыт работы с системами контроля версий (git, Gitlab, Bitbucket);
— Опыт работы с распределёнными базами данных - Hadoop, Greenplum;
— Знание SQL (ANSI, PL/SQL), опыт оптимизации запросов;
— Опыт использования системами ведения документации.

⚠️ Особые условия:
— Резюме должно содержать: образование, город, ключевые компетенции, название проектов, роль в проекте, описание самих проектов, обязанности специалиста, достижения (если есть), основные используемые технологии специалистом на проекте, состав команды.
— Все требования из запроса должны быть отражены в проектах в резюме.

❗️ Обязательные данные по кандидату при подаче:
● ФИО
● Страна + Город
● Дата рождения (не возраст, а дата)
● Электронная почта
● Образование (ВУЗ, год окончания, специальность)
● Грейд
● Ставка
● Чек-лист соответствия требованиям (ДА/НЕТ)

Контакт для вопросов: @sazanovich_ma (не забудьте указать 🆔 запроса)'''
    fn, payload = create_white_label_resume_once(GEMINI_API_KEY, candidate, vacancy)
    print("Готово:", fn)
