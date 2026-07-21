#!/usr/bin/env python3
from __future__ import annotations
import argparse, datetime as dt, json, os, platform, re, socket, sqlite3, subprocess, textwrap, urllib.parse, urllib.request
from pathlib import Path

VERSION="1.0.0"
BASE=Path("/opt/general-info")
CONFIG=BASE/"config/general-info.json"
DB_DEFAULT=Path("/var/lib/baypark-decision-queue/questions.sqlite3")
LOG=BASE/"state/general-info.log"
USAJOBS="https://data.usajobs.gov/api/search"

STATES=[
"Alabama","Alaska","Arizona","Arkansas","California","Colorado","Connecticut","Delaware","Florida","Georgia",
"Hawaii","Idaho","Illinois","Indiana","Iowa","Kansas","Kentucky","Louisiana","Maine","Maryland",
"Massachusetts","Michigan","Minnesota","Mississippi","Missouri","Montana","Nebraska","Nevada","New Hampshire","New Jersey",
"New Mexico","New York","North Carolina","North Dakota","Ohio","Oklahoma","Oregon","Pennsylvania","Rhode Island","South Carolina",
"South Dakota","Tennessee","Texas","Utah","Vermont","Virginia","Washington","West Virginia","Wisconsin","Wyoming"]
ABBR=dict(zip(
["al","ak","az","ar","ca","co","ct","de","fl","ga","hi","id","il","in","ia","ks","ky","la","me","md","ma","mi","mn","ms","mo","mt","ne","nv","nh","nj","nm","ny","nc","nd","oh","ok","or","pa","ri","sc","sd","tn","tx","ut","vt","va","wa","wv","wi","wy"], STATES))
PORTALS={
"California":"https://www.calcareers.ca.gov/","Maryland":"https://www.jobapscloud.com/MD/",
"Utah":"https://www.governmentjobs.com/careers/utah","Virginia":"https://www.jobs.virginia.gov/",
"New York":"https://statejobs.ny.gov/","Texas":"https://capps.taleo.net/careersection/ex/jobsearch.ftl",
"Florida":"https://jobs.myflorida.com/","Washington":"https://careers.wa.gov/",
"Pennsylvania":"https://www.employment.pa.gov/","Wisconsin":"https://wisc.jobs/"}

HELP="""General Info email commands:
commands | help | info
pi status | pi uptime | pi reachability | fix 192.168.5.215
federal jobs | schedule a jobs | federal cybersecurity jobs
state jobs STATE | all states | least competitive states
noc roadmap | pentest roadmap | cybersecurity by 2035
salary strategy | job stability
security plus | security plus study plan | security plus quiz

The service checks the Decision Tree queue every five minutes. It writes an
answer and marks recognized new items answered so the existing dt-core sender
can send the reply.
"""

def cfg():
    d={"database":str(DB_DEFAULT),"target_ip":"192.168.5.215","minimum_salary":45000,
       "cybersecurity_deadline_year":2035,"max_answers_per_run":20}
    try:
        x=json.loads(CONFIG.read_text())
        if isinstance(x,dict): d.update(x)
    except FileNotFoundError: pass
    return d

def norm(s): return " ".join(str(s).casefold().split())
def sh(args,timeout=10):
    try:
        p=subprocess.run(args,text=True,capture_output=True,timeout=timeout)
        return p.returncode,p.stdout.strip(),p.stderr.strip()
    except Exception as e: return 1,"",f"{type(e).__name__}: {e}"

def duration(sec):
    sec=int(sec); d,sec=divmod(sec,86400); h,sec=divmod(sec,3600); m,_=divmod(sec,60)
    return ", ".join(x for x in [f"{d} days" if d else "",f"{h} hours" if h else "",f"{m} minutes" if m else ""] if x) or "under a minute"

def pi_status():
    try: up=duration(float(Path("/proc/uptime").read_text().split()[0]))
    except Exception: up="unknown"
    _,ips,_=sh(["hostname","-I"]); _,load,_=sh(["cut","-d"," ","-f1-3","/proc/loadavg"])
    _,mem,_=sh(["free","-h"]); _,disk,_=sh(["df","-h","/"])
    _,dtc,_=sh(["systemctl","is-active","dt-core.service"])
    _,bay,_=sh(["systemctl","is-active","baypark-ollama-console.service"])
    return f"""Raspberry Pi status
Hostname: {socket.gethostname()}
OS: {platform.platform()}
Uptime: {up}
IP addresses: {ips or 'unknown'}
Load averages: {load or 'unknown'}
dt-core.service: {dtc or 'unknown'}
baypark-ollama-console.service: {bay or 'unknown'}

Memory:
{mem}

Disk:
{disk}"""

def reachable(c):
    ip=str(c["target_ip"]); _,addrs,_=sh(["ip","-4","-o","addr","show"])
    pr,_,_=sh(["ping","-c","1","-W","2",ip],4)
    hr,head,_=sh(["curl","-sS","-I","--max-time","4",f"http://{ip}/"],6)
    ok=pr==0 or (hr==0 and "HTTP/" in head)
    lines=[f"Reachability for {ip}",f"Assigned locally: {'yes' if ip in addrs else 'no'}",
           f"Ping: {'reachable' if pr==0 else 'not reachable'}",f"HTTP: {'reachable' if hr==0 and 'HTTP/' in head else 'not reachable'}"]
    if not ok:
        lines += ["","Safe fix checklist:",
        "1. On the Pi: ip -4 addr ; ip route",
        "2. sudo systemctl status ensure-book-server-ip.service",
        "3. sudo systemctl status baypark-ollama-console.service",
        "4. curl -I http://127.0.0.1/",
        f"5. curl -I http://{ip}/",
        "6. sudo journalctl -u baypark-ollama-console.service -n 150 --no-pager",
        "Do not change routes or DNS blindly."]
    return "\n".join(lines)

def usajobs(c,keyword):
    email=os.getenv("USAJOBS_EMAIL"); key=os.getenv("USAJOBS_API_KEY")
    if not email or not key:
        q=urllib.parse.quote(keyword)
        return ("Live USAJOBS API search is not configured. Add USAJOBS_EMAIL and USAJOBS_API_KEY to "
                "/etc/general-info/general-info.env; never commit that file.\n"
                f"Official search: https://www.usajobs.gov/Search/Results?k={q}\n"
                "Schedule A guidance: https://help.usajobs.gov/working-in-government/unique-hiring-paths/individuals-with-disabilities\n"
                "The service can report open postings, but it cannot predict postings that do not yet exist.")
    params=urllib.parse.urlencode({"Keyword":keyword,"ResultsPerPage":"10"})
    req=urllib.request.Request(USAJOBS+"?"+params,headers={"User-Agent":email,"Authorization-Key":key,"Host":"data.usajobs.gov"})
    with urllib.request.urlopen(req,timeout=20) as r: payload=json.loads(r.read())
    items=payload.get("SearchResult",{}).get("SearchResultItems",[])
    lines=[f"Current USAJOBS results for: {keyword}"]
    for i,item in enumerate(items[:10],1):
        d=item.get("MatchedObjectDescriptor",{})
        loc=", ".join(x.get("LocationName","") for x in d.get("PositionLocation",[])[:2])
        lines.append(f"\n{i}. {d.get('PositionTitle','Untitled')}\n{d.get('OrganizationName','')}\n{loc}\n{d.get('PositionURI','')}")
    if len(lines)==1: lines.append("No matching open announcements returned.")
    lines.append(f"\nVerify pay is at least ${int(c['minimum_salary']):,}, appointment type, hiring path, and closing date.")
    return "\n".join(lines)

def canon_state(s):
    s=norm(s)
    if s in ABBR: return ABBR[s]
    for x in STATES:
        if norm(x)==s: return x
    return None

def state_answer(c,s):
    state=canon_state(s)
    if not state: return "State not recognized. Use a full state name or two-letter abbreviation."
    url=PORTALS.get(state,f"https://www.google.com/search?q={urllib.parse.quote(state+' official state jobs')}")
    return f"""{state} job-search starting point
Portal/search: {url}

Search terms: information technology, NOC, network operations, cybersecurity,
information security, systems administrator, vulnerability, penetration testing,
IAM, endpoint security.

Require at least ${int(c['minimum_salary']):,}, permanent status, benefits, and duties
that build toward NOC or cybersecurity work. Schedule A is federal; state programs
use their own rules. Verify the official current portal before applying."""

def all_states():
    return "All 50 states supported:\n" + "\n".join(STATES) + "\nUse: state jobs STATE"

def least_comp(c):
    return f"""There is no reliable public dataset identifying a least-competitive state
specifically for a person with auditory processing disorder. Schedule A is a
federal hiring authority, not a state ranking.

Compare states monthly using:
- current openings paying at least ${int(c['minimum_salary']):,}
- permanent status and benefits
- public/disability hiring paths
- NOC, 2210, systems, IAM, endpoint, vulnerability, SOC, or junior cyber duties
- housing and relocation cost
- published applicant counts, when available

Opening count is only a proxy for opportunity, not proof of low competition."""

def roadmap(kind,c):
    y=int(c["cybersecurity_deadline_year"])
    if kind=="noc":
        return f"NOC path to {y}: strengthen TCP/IP, DNS, DHCP, routing, switching, VLANs, Linux, monitoring, ticketing, logs, and packet capture; earn Security+; build a monitoring lab; target NOC/network-support roles; then move toward security monitoring or network security."
    if kind=="pentest":
        return f"Pentest path to {y}: complete Security+, strengthen Linux/networking/Python/web/Active Directory, practice only in authorized labs, write sanitized findings and remediation reports, and first target vulnerability, SOC, systems, or security-assessment work."
    return f"Cybersecurity path to {y}: pass Security+, document projects, obtain a stable IT/NOC/IAM/endpoint/vulnerability/compliance role paying at least ${int(c['minimum_salary']):,}, add measurable security duties, and review progress every six months."

def security_plus(low):
    if "quiz" in low:
        return "Security+ question: Which control makes stolen password hashes harder to crack with precomputed tables?\nA. Tokenization\nB. Salting\nC. Federation\nD. Steganography\nReply with the letter and reasoning."
    return "Security+ plan: use the current objectives, active recall, fresh practice questions, explanations of missed answers, command-line labs, and timed exams. Schedule only after consistent performance on multiple fresh sets."

def answer(q,c):
    low=norm(q)
    if low in {"help","commands","command","info","general info"} or "what commands" in low or "what can i type" in low or "what can i enter" in low: return HELP
    if "pi status" in low or "raspberry pi info" in low or "system info" in low: return pi_status()
    if "uptime" in low: 
        try: return "System uptime: "+duration(float(Path("/proc/uptime").read_text().split()[0]))
        except Exception as e: return f"Uptime unavailable: {e}"
    if "192.168.5.215" in low or "reachable" in low or "reachability" in low: return reachable(c)
    if "schedule a job" in low: return usajobs(c,'"Schedule A" information technology cybersecurity')
    if "federal" in low and ("cyber" in low or "information security" in low): return usajobs(c,"cybersecurity information security 2210")
    if low in {"federal jobs","federal job status","new federal jobs"}: return usajobs(c,"information technology 2210")
    m=re.search(r"state jobs?\s+([a-z ]+)$",low)
    if m: return state_answer(c,m.group(1))
    if low in {"all states","state list","all state jobs"}: return all_states()
    if "least competitive" in low or "easiest state" in low: return least_comp(c)
    if "noc" in low and ("roadmap" in low or "2035" in low or "career" in low): return roadmap("noc",c)
    if ("pentest" in low or "penetration test" in low) and ("roadmap" in low or "2035" in low or "career" in low): return roadmap("pentest",c)
    if "2035" in low or "get into cybersecurity" in low or "cybersecurity roadmap" in low: return roadmap("cyber",c)
    if "salary" in low: return f"Use ${int(c['minimum_salary']):,} as the minimum and compare permanent status, benefits, retirement, promotion potential, and cybersecurity relevance."
    if "stable" in low or "stability" in low: return "Favor permanent federal, state, local-government, public-university, utility, healthcare, or school-system roles. Check funding, probation, turnover, benefits, and appointment type."
    if "security+" in low or "security plus" in low: return security_plus(low)
    if low in {"general info status","general-info status"}: return f"General Info {VERSION} is available."
    return None

def columns(conn,table): return [r[1] for r in conn.execute(f'PRAGMA table_info("{table}")')]
def pick(cols,names):
    m={x.casefold():x for x in cols}
    return next((m[n.casefold()] for n in names if n.casefold() in m),None)
def qi(s): return '"'+s.replace('"','""')+'"'

def schema(conn):
    for (table,) in conn.execute("select name from sqlite_master where type='table' and name not like 'sqlite_%'"):
        cols=columns(conn,table)
        i=pick(cols,["id","question_id","queue_id"]); q=pick(cols,["question","prompt","request_text","body"]); a=pick(cols,["answer","response","reply","response_text"])
        if i and q and a:
            return {"table":table,"id":i,"q":q,"a":a,"status":pick(cols,["status","state"]),"at":pick(cols,["answered_at","response_at","updated_at"]),"rid":pick(cols,["request_id","requestid","external_id"])}
    raise RuntimeError("No compatible queue table found.")

def process():
    c=cfg(); db=Path(c["database"])
    if not db.exists(): return 0
    con=sqlite3.connect(db,timeout=20); con.row_factory=sqlite3.Row
    try:
        s=schema(con); where=f"({qi(s['a'])} is null or trim(cast({qi(s['a'])} as text))='')"
        if s["status"]: where+=f" and lower(coalesce(cast({qi(s['status'])} as text),'pending')) in ('pending','new','open','waiting','queued')"
        rows=con.execute(f"select * from {qi(s['table'])} where {where} order by {qi(s['id'])} limit ?",(int(c["max_answers_per_run"]),)).fetchall()
        count=0
        for row in rows:
            response=answer(str(row[s["q"]] or ""),c)
            if response is None: continue
            sets=[f"{qi(s['a'])}=?"]; vals=[response]
            if s["status"]: sets.append(f"{qi(s['status'])}=?"); vals.append("answered")
            if s["at"]: sets.append(f"{qi(s['at'])}=?"); vals.append(dt.datetime.now().isoformat(timespec="seconds"))
            vals.append(row[s["id"]]); con.execute(f"update {qi(s['table'])} set {','.join(sets)} where {qi(s['id'])}=?",vals); count+=1
        con.commit(); return count
    finally: con.close()

def inspect():
    c=cfg(); con=sqlite3.connect(c["database"])
    try: print(json.dumps(schema(con),indent=2))
    finally: con.close()

def main():
    p=argparse.ArgumentParser(); p.add_argument("--process",action="store_true"); p.add_argument("--inspect-queue",action="store_true"); p.add_argument("--answer")
    a=p.parse_args()
    if a.inspect_queue: inspect()
    elif a.answer is not None: print(answer(a.answer,cfg()) or "No automatic answer matched.")
    else: process()
if __name__=="__main__": main()
