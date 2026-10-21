#!/usr/bin/env python3
"""Phase 6 (Reporter): build the screening deliverables from merged decisions.

Usage:
  python build_outputs.py --work W --out OUT_DIR [--stage ta|ft] [--config screening_config.json]
                          [--tag-keywords] [--attestation FILE] [--finalize]

Writes into OUT_DIR (prefix TA_ or FT_):
  <P>_screening_log.xlsx     Summary, advanced/included records, all records, conflicts, QC, pending
                             (CSV files instead when openpyxl is not installed)
  <P>_1_include.ris, <P>_2_unclear.ris, <P>_3_exclude.ris
                             for EndNote / Zotero / Mendeley: Label (LB) = decision, note (N1) = reasons;
                             --tag-keywords also adds the decision as a keyword (Zotero tag)
  <P>_prisma_counts.json / .md   PRISMA 2020 numbers (+ a Mermaid flow diagram)
  <P>_methods_selection.md       methods paragraph and AI-use statement, with [TO COMPLETE] slots
  <P>_literature_corpus.yaml     advanced (TA) or included (FT) records as literature_corpus[]
                                 entries for Academic Research Skills (academic-paper / deep-research)
Each invocation retains a new TA_PRELIMINARY_<id> or FT_PRELIMINARY_<id> directory.
Its <P>_handoff_manifest.json binds every export to its status, context and SHA-256.
Completeness is not human approval. Final handoff requires --finalize and a JSON
attestation with schema="rsk.screening-export-attestation.v1", stage, context_id,
input_snapshot_sha256 (from a preliminary manifest), attested_by, attested_at
(timezone-qualified ISO timestamp), and human_signoff=true. Optional runtime
(string) and models (role-to-exact-model strings) are declarations, not inferred
execution receipts. Unattested identities remain unknown. Corpus YAML remains
a sequence of existing-schema entries; status travels in comments/tags/notes.
"""
import argparse
import csv
import datetime
import hashlib
import json
import os
import re
import sys
import unicodedata
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import srlib  # noqa: E402

REPO_URL = "https://github.com/Imbad0202/academic-research-skills"
MANIFEST_SCHEMA = "rsk.screening-exports.v1"
ATTESTATION_SCHEMA = "rsk.screening-export-attestation.v1"


def file_sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def input_snapshot(work, cfg, stage):
    names = ["records.json", "raw_records.json", "identification.json", "review_identity.json",
             "review_state.json", "decisions.json", "decisions_meta.json", "pending.json",
             "agreement.json", "qc_reasons.json", "qc_candidates.json", "seeds.json",
             "pilot_check.json", "pilot_override.json"]
    if stage == "ft":
        names += ["ft_manifest.json", "ft_not_retrieved.json", "ft_preparation.json",
                  "ft_decisions.json", "ft_decisions_meta.json", "ft_pending.json",
                  "ft_agreement.json", "prisma_ta.json"]
    hashes = {name: file_sha256(os.path.join(work, name))
              if os.path.isfile(os.path.join(work, name)) else None for name in names}
    state = srlib.load_json(os.path.join(work, "review_state.json"), {}) or {}
    for part in (("ta", "ft") if stage == "ft" else ("ta",)):
        path = state.get(part, {}).get("protocol_path", "")
        hashes[part + "_protocol"] = file_sha256(path) if os.path.isfile(path) else None
    return {"stage": stage, "effective_config_sha256": srlib.digest(cfg), "files": hashes}


def read_attestation(path, stage, context_id, snapshot_hash):
    if not path:
        return None
    try:
        with open(path, "rb") as f:
            raw = f.read()
        value = json.loads(raw)
        required = {"schema", "stage", "context_id", "input_snapshot_sha256", "attested_by", "attested_at"}
        if not isinstance(value, dict) or not required <= value.keys() or value.keys() - (
                required | {"human_signoff", "runtime", "models"}):
            raise ValueError("unexpected or missing attestation fields")
        if (value["schema"] != ATTESTATION_SCHEMA or value["stage"] != stage or not context_id or
                value["context_id"] != context_id or value["input_snapshot_sha256"] != snapshot_hash):
            raise ValueError("attestation does not match the current stage/context/input snapshot")
        texts = [value["attested_by"], value["attested_at"]]
        if "runtime" in value:
            texts.append(value["runtime"])
        models = value.get("models", {})
        if not isinstance(models, dict) or models.keys() - {"A", "B", "ADJ", "QC", "FTA", "FTB", "FTADJ"}:
            raise ValueError("models must map known reviewer roles to exact identities")
        texts += list(models.values())
        if any(not isinstance(v, str) or not v.strip() or any(ord(c) < 32 for c in v) for v in texts):
            raise ValueError("attested identities and timestamp must be nonempty single-line strings")
        if datetime.datetime.fromisoformat(value["attested_at"].replace("Z", "+00:00")).utcoffset() is None:
            raise ValueError("attestation timestamp must include a timezone")
        if "human_signoff" in value and type(value["human_signoff"]) is not bool:
            raise ValueError("human_signoff must be a boolean declaration")
    except (OSError, ValueError, TypeError) as exc:
        raise SystemExit(f"invalid export attestation: {exc}") from exc
    return {"declaration": value, "sha256": hashlib.sha256(raw).hexdigest(),
            "verification": "input_attested_not_independently_verified"}


def corpus_problem(u):
    if not any(split_author(a) for a in u.get("authors", [])):
        return "no authors"
    year = str(u.get("year", ""))
    if not year.isascii() or not year.isdigit() or not 1000 <= int(year) <= 2100:
        return "publication year outside corpus schema (1000-2100)"
    return None


def split_author(a):
    a = a.strip().rstrip(".")
    if not a:
        return None
    if "," in a:
        fam, giv = a.split(",", 1)
        if not fam.strip():
            return {"literal": a}
        return {"family": fam.strip(), "given": giv.strip()} if giv.strip() else {"family": fam.strip()}
    parts = a.split()
    if len(parts) >= 2 and re.fullmatch(r"([A-Z]\.?-?){1,4}", parts[-1]):
        return {"family": " ".join(parts[:-1]), "given": parts[-1]}
    return {"literal": a}


def ascii_key(s):
    s = unicodedata.normalize("NFKD", s or "")
    return re.sub(r"[^a-z0-9]", "", s.encode("ascii", "ignore").decode().lower())


def write_corpus(path, rows, stage, when, status, notice):
    """ARS literature_corpus[] entries (shared/contracts/passport/literature_corpus_entry.schema.json)."""
    ok, rejected = [], []
    for r in rows:
        u = r["u"]
        authors = [x for x in (split_author(a) for a in u.get("authors", [])) if x]
        problem = corpus_problem(u)
        if problem:
            rejected.append({"id": u["id"], "reason": problem, "record": u, "decision": r["f"]})
            continue
        first = authors[0]
        fam = ascii_key(first.get("family") or first.get("literal", ""))[:20] or "rec"
        if not fam[0].isalpha():
            fam = "rec" + fam
        pointer = (f"https://doi.org/{u['doi']}" if u.get("doi") else
                   f"https://pubmed.ncbi.nlm.nih.gov/{u['pmid']}/" if u.get("pmid") else f"urn:sr-screener:{u['id']}")
        e = [("citation_key", f"{fam}{u['year']}_{u['id']}"), ("title", u["title"] or "[no title]"),
             ("authors", authors), ("year", int(u["year"])), ("source_pointer", pointer)]
        if u.get("journal"):
            e.append(("venue", u["journal"]))
        if u.get("doi") and srlib.DOI_RE.match(u["doi"]):
            e.append(("doi", u["doi"]))
        e += [("tags", [srlib.TOOL, f"{stage.upper()}-{r['f']['d'].capitalize()}", status["status"].upper()]),
              ("obtained_via", "other"), ("adapter_name", srlib.TOOL), ("adapter_version", srlib.VERSION),
              ("obtained_at", when),
              ("user_notes", f"{notice} | {stage.upper()} screening: {r['f']['d']} ({r['f']['code']}) - {r['f'].get('why', '')} "
                             f"[decided by {r['f']['by']}]")]
        ok.append(dict(e))
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(f"# {notice}\n")
        f.write("# literature_corpus[] entries for Academic Research Skills (literature_corpus_entry.schema.json).\n")
        f.write(f"# Produced by {srlib.TOOL} {srlib.VERSION}. Preserve the handoff manifest.\n")
        f.write("# Verify its status, current context, input snapshot and every export hash before handoff.\n")
        # JSON flow syntax is valid YAML; retain the sequence schema without a YAML dependency.
        json.dump(ok, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return len(ok), rejected


def lang_ok(u, allowed):
    if not allowed:
        return True
    langs = [x.strip().lower() for x in (u.get("lang") or "").split(";") if x.strip()]
    return not langs or any(x in [a.lower() for a in allowed] for x in langs)


def main():
    srlib.utf8_stdout()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--work", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--stage", choices=["ta", "ft"], default="ta")
    ap.add_argument("--config")
    ap.add_argument("--tag-keywords", action="store_true")
    ap.add_argument("--attestation", help="explicit, context/snapshot-bound human and runtime declarations")
    ap.add_argument("--finalize", action="store_true", help="require complete screening and attested human signoff")
    a = ap.parse_args()

    cfg = srlib.load_config(a.config)
    work, out = os.path.abspath(a.work), os.path.abspath(a.out)
    output_root = out
    P = a.stage.upper()
    labels = srlib.code_labels(cfg, a.stage)
    recs = srlib.load_json(os.path.join(work, "records.json"))
    if recs is None:
        raise SystemExit("records.json not found")
    U = {u["id"]: u for u in recs["unique"]}
    RAW = srlib.load_json(os.path.join(work, "raw_records.json"), [])
    ident = srlib.load_json(os.path.join(work, "identification.json"), {})
    ta_dec = srlib.load_json(os.path.join(work, "decisions.json"), {})
    ta_pending_ids, ta_qc_ids, state_problems = srlib.ta_status(work, cfg)
    ft_stale = False
    if a.stage == "ta":
        D = ta_dec
        agree = srlib.load_json(os.path.join(work, "agreement.json"), {})
        pending_ids = sorted(ta_pending_ids)
        universe = [u["id"] for u in recs["unique"]]
    else:
        D = srlib.load_json(os.path.join(work, "ft_decisions.json"), {})
        pending = srlib.load_json(os.path.join(work, "ft_pending.json"), {"items": [], "adj": []})
        agree = srlib.load_json(os.path.join(work, "ft_agreement.json"), {})
        man = srlib.load_json(os.path.join(work, "ft_manifest.json"), [])
        universe = [x["id"] for x in man]
        ta_pending_ids, ta_qc_ids, state_problems, uncovered, ft_stale = srlib.fulltext_status(work, cfg)
        missing = {rid for rid in universe if not srlib.valid_decision(D.get(rid, {}).get("final"),
                                                                       srlib.exclusion_codes(cfg, "ft"))}
        if universe and not srlib.decision_state_current(work, "ft", cfg):
            state_problems.append("full-text decisions have no current protocol/config/retrieval identity")
            missing |= set(universe)
        pending_ids = sorted({x["id"] for x in pending["items"]} | {x["id"] for x in pending["adj"]} |
                             ta_pending_ids | missing | uncovered)

    rows = []
    for rid in universe:
        r = D.get(rid)
        if not r or rid not in U or not srlib.valid_decision(r.get("final"), srlib.exclusion_codes(cfg, a.stage)):
            continue
        u = U[rid]
        rows.append(dict(u=u, f=r["final"], A=r.get("A") or {}, B=r.get("B") or {}, J=r.get("ADJ") or {},
                         Q=r.get("QC") or {}, pre_qc=r.get("pre_qc"), pre_override=r.get("pre_override"),
                         qc_flag=r.get("qc_flag", False), ok_lang=lang_ok(u, cfg.get("languages_allowed"))))
    complete = not pending_ids and not state_problems and not ft_stale
    context = srlib.current_context(work, a.stage, cfg)
    if context is None:
        complete = False
        state_problems.append("no current screening context")
    count = lambda d: sum(1 for r in rows if r["f"]["d"] == d)
    exc_codes = {}
    for r in rows:
        if r["f"]["d"] == "exclude":
            exc_codes[r["f"]["code"]] = exc_codes.get(r["f"]["code"], 0) + 1
    code_order = srlib.exclusion_codes(cfg, a.stage)
    exc_sorted = sorted(exc_codes.items(), key=lambda kv: code_order.index(kv[0]) if kv[0] in code_order else 99)
    adv_rows = [r for r in rows if r["f"]["d"] in srlib.ADVANCE] if a.stage == "ta" else \
        [r for r in rows if r["f"]["d"] == "include"]
    seeds = srlib.load_json(os.path.join(work, "seeds.json"), []) or []
    by = {}
    for r in rows:
        by[r["f"]["by"]] = by.get(r["f"]["by"], 0) + 1
    snapshot = input_snapshot(work, cfg, a.stage)
    snapshot_hash = srlib.digest(snapshot)
    context_id = context["context_id"] if context else None
    attestation = read_attestation(a.attestation, a.stage, context_id, snapshot_hash)
    declared = attestation["declaration"] if attestation else {}
    blockers = []
    if not complete:
        blockers.append("screening_incomplete_or_stale")
    if declared.get("human_signoff") is not True:
        blockers.append("human_signoff_not_attested")
    if a.stage == "ft" and count("unclear"):
        blockers.append("fulltext_awaiting_classification")
    if any(corpus_problem(r["u"]) for r in adv_rows):
        blockers.append("corpus_entries_rejected_by_schema")
    if a.finalize and blockers:
        raise SystemExit("final handoff refused: " + ", ".join(blockers))
    if not a.finalize:
        blockers.append("finalization_not_requested")
    roles = ("A", "B", "ADJ", "QC") if a.stage == "ta" else ("FTA", "FTB", "FTADJ")
    status = {"status": "final" if a.finalize else "preliminary", "stage": a.stage,
              "screening_complete": complete, "context_id": context_id,
              "input_snapshot_sha256": snapshot_hash, "final_handoff_authorized": bool(a.finalize),
              "handoff_blockers": blockers,
              "human_signoff": {"status": "input_attested" if "human_signoff" in declared else "unknown",
                                "approved": declared.get("human_signoff")},
              "runtime": {"status": "input_attested" if "runtime" in declared else "unknown",
                          "name": declared.get("runtime")},
              "models": {role: {"status": "input_attested" if role in declared.get("models", {}) else "unknown",
                                "identity": declared.get("models", {}).get(role)} for role in roles}}
    export_id = uuid.uuid4().hex
    out = os.path.join(output_root, f"{P}_{status['status'].upper()}_{export_id}")
    os.makedirs(out, exist_ok=False)
    manifest_name = f"{P}_handoff_manifest.json"
    notice = (f"{status['status'].upper()} | stage={a.stage} | screening_complete={str(complete).lower()} | "
              f"context={context_id or 'unknown'} | final_handoff_authorized={str(a.finalize).lower()} | "
              f"manifest={manifest_name}")

    # --------------------------------------------------------------- counts
    counts = {"stage": a.stage, "tool": f"{srlib.TOOL} {srlib.VERSION}", "complete": complete,
              "pending_records": len(pending_ids), "export_status": status}
    if a.stage == "ft":
        counts.update({"pending_ta_records": len(ta_pending_ids), "pending_ta_qc_records": len(ta_qc_ids),
                       "fulltext_set_out_of_date": ft_stale})
    counts["state_problems"] = state_problems
    if a.stage == "ta":
        counts.update({
            "identified_by_database": ident.get("by_database", {}),
            "identified_total": ident.get("raw_total"),
            "duplicates_removed": ident.get("duplicates_removed"),
            "records_screened": len(rows),
            "records_to_screen": len(universe),
            "records_excluded": count("exclude"),
            "excluded_by_code": dict(exc_sorted),
            "reports_sought_for_retrieval": count("include") + count("unclear"),
            "advanced_include": count("include"),
            "advanced_unclear": count("unclear"),
            "advanced_outside_allowed_languages": sum(1 for r in adv_rows if not r["ok_lang"]),
        })
    else:
        ta_counts = srlib.load_json(os.path.join(work, "prisma_ta.json"), {})
        nr = srlib.load_json(os.path.join(work, "ft_not_retrieved.json"), []) or []
        counts.update({
            "reports_sought_for_retrieval": sum(1 for r in ta_dec.values()
                                                if r.get("final", {}).get("d") in srlib.ADVANCE),
            "reports_not_retrieved": len(nr),
            "reports_assessed": len(rows),
            "reports_to_assess": len(universe),
            "reports_excluded": count("exclude"),
            "excluded_by_reason": {labels.get(k, k): v for k, v in exc_sorted},
            "reports_unclear_awaiting_classification": count("unclear"),
            "studies_included_reports": count("include"),
            "ta": ta_counts,
        })
    counts["agreement"] = agree
    counts["decided_by"] = by
    if a.stage == "ta":
        srlib.save_json(os.path.join(work, "prisma_ta.json"), counts, indent=1)
    srlib.save_json(os.path.join(out, f"{P}_prisma_counts.json"), counts, indent=1)

    # --------------------------------------------------------------- sheets
    head = ["ID", "Final decision", "Final code", "Final reason", "Decided by", "Reviewer A", "A code", "A reason",
            "Reviewer B", "B code", "B reason", "Adjudicator", "ADJ reason", "QC", "QC reason", "Before QC/override",
            "Language OK", "First author", "Year", "Title", "Journal", "Publication type", "Language", "DOI", "PMID",
            "Sources", "Batch"]
    if a.stage == "ft":
        head[3:4] = ["Final reason", "Where"]
    head.append("Abstract")
    head += ["Export status", "Stage", "Context ID", "Handoff manifest"]

    def line(r):
        u, f = r["u"], r["f"]
        before = r["pre_override"] or r["pre_qc"]
        row = [u["id"], f["d"], f["code"], f.get("why", "")]
        if a.stage == "ft":
            row.append(f.get("where", ""))
        row += [f["by"], r["A"].get("d", ""), r["A"].get("code", ""), r["A"].get("why", ""),
                r["B"].get("d", ""), r["B"].get("code", ""), r["B"].get("why", ""),
                (r["J"].get("d", "") + "/" + r["J"].get("code", "")) if r["J"] else "", r["J"].get("why", ""),
                (r["Q"].get("d", "") + "/" + r["Q"].get("code", "")) if r["Q"] else ("FLAG" if r["qc_flag"] else ""),
                r["Q"].get("why", ""), (before["d"] + "/" + before["code"]) if before else "",
                "yes" if r["ok_lang"] else "NO", (u.get("authors") or [""])[0], u["year"], u["title"], u["journal"],
                u["type"], u["lang"], u["doi"], u["pmid"], ", ".join(u["sources"]), u.get("batch", ""),
                (u["abstract"] or "")[:32000]]
        return row + [status["status"].upper(), a.stage, context_id or "unknown", manifest_name]

    summary = [("sr-screener " + srlib.VERSION + f" - {'title/abstract' if a.stage == 'ta' else 'full-text'} "
                "screening log", "")]
    summary += [(notice, ""), ("Human signoff", status["human_signoff"]["status"]),
                ("Runtime identity", status["runtime"]["name"] or "unknown (not attested)")]
    if not complete:
        summary.append((f"INCOMPLETE: {len(pending_ids)} records need decisions or required rechecks "
                        "(resume with build_workflow.py --jobs pending, then --jobs recheck for the required QC "
                        "recheck). Numbers below are provisional.", ""))
        summary += [("INCOMPLETE: " + problem, "") for problem in state_problems]
        if a.stage == "ft" and ta_pending_ids:
            summary.append((f"Title/abstract stage still pending: {len(ta_pending_ids)} records, "
                            f"including {len(ta_qc_ids)} required title/abstract QC rechecks. "
                            "Full-text counts cannot be final until these are decided.", ""))
    if a.stage == "ta":
        summary += [("IDENTIFICATION", "")]
        summary += [(f"Records from {db}", n) for db, n in counts["identified_by_database"].items()]
        summary += [("Total records identified", counts["identified_total"]),
                    ("Duplicate records removed", counts["duplicates_removed"]),
                    ("SCREENING (title/abstract)", ""),
                    ("Records screened", counts["records_screened"]),
                    ("Records with a final decision", len(rows)),
                    ("Records excluded", counts["records_excluded"])]
        summary += [("   " + labels.get(c, c), n) for c, n in exc_sorted]
        summary += [("Records advanced to full-text assessment", counts["reports_sought_for_retrieval"]),
                    ("   include (eligible on title/abstract)", counts["advanced_include"]),
                    ("   unclear (needs the full text)", counts["advanced_unclear"])]
        if cfg.get("languages_allowed"):
            summary.append((f"   of which language outside {', '.join(cfg['languages_allowed'])} (flag, not excluded)",
                            counts["advanced_outside_allowed_languages"]))
    else:
        summary += [("FULL-TEXT ASSESSMENT", ""),
                    ("Reports sought for retrieval", counts["reports_sought_for_retrieval"]),
                    ("Reports not retrieved", counts["reports_not_retrieved"]),
                    ("Reports assessed for eligibility", counts["reports_assessed"]),
                    ("Reports excluded", counts["reports_excluded"])]
        summary += [("   " + k, v) for k, v in counts["excluded_by_reason"].items()]
        summary += [("Awaiting classification (unclear)", counts["reports_unclear_awaiting_classification"]),
                    ("Reports of included studies", counts["studies_included_reports"])]
    summary += [("REVIEWER AGREEMENT", ""),
                ("Records decided by both reviewers", agree.get("n")),
                ("Observed agreement", agree.get("observed_agreement")),
                ("Cohen's kappa", agree.get("kappa")),
                ("PABAK (prevalence-adjusted)", agree.get("pabak")),
                ("Conflicts", agree.get("conflicts", agree.get("a_only_advance", 0) + agree.get("b_only_advance", 0)))]
    summary += [(f"Final decisions made by {k}", v) for k, v in sorted(by.items())]
    if seeds:
        summary.append(("SEED STUDIES (sensitivity check)", ""))
        for s in seeds:
            fd = D.get(s["id"], {}).get("final", {}) if s.get("id") else {}
            summary.append((f"{s['label']}", f"{s['id']}: {fd.get('d', 'pending')}" if s.get("id") else "NOT IN SEARCH"))
    summary += [("", ""), ("AI decisions are decision support. The review team must verify them before reporting "
                           "(see the methods file for the reporting text).", "")]

    cols = [("Advanced" if a.stage == "ta" else "Included", adv_rows),
            ("All_Records", rows),
            ("Conflicts", [r for r in rows if r["f"]["by"] in ("ADJ", "LIBERAL")]),
            ("QC_and_Overrides", [r for r in rows if r["Q"] or r["qc_flag"] or r["pre_override"]])]
    if a.stage == "ft":
        cols.insert(1, ("Excluded_with_reasons", [r for r in rows if r["f"]["d"] == "exclude"]))
    order = {"include": 0, "unclear": 1, "exclude": 2}
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Font, PatternFill
        from openpyxl.utils import get_column_letter
        wb = Workbook()
        ws = wb.active
        ws.title = "Summary"
        ws.column_dimensions["A"].width = 78
        ws.column_dimensions["B"].width = 18
        for k, v in summary:
            ws.append([srlib.spreadsheet_text(k), srlib.spreadsheet_text(v)])
            if k and k.isupper():
                ws.cell(row=ws.max_row, column=1).font = Font(bold=True)
        fills = {"include": "C6EFCE", "unclear": "FFEB9C", "exclude": "F2F2F2"}
        widths = {"ID": 9, "Title": 60, "Abstract": 80, "Final reason": 40, "A reason": 32, "B reason": 32,
                  "ADJ reason": 32, "QC reason": 32, "Journal": 28, "Publication type": 24, "Sources": 20, "DOI": 24}
        for name, rs in cols:
            sh = wb.create_sheet(name)
            sh.append(head)
            for i, h in enumerate(head, 1):
                c = sh.cell(row=1, column=i)
                c.font = Font(bold=True, color="FFFFFF")
                c.fill = PatternFill("solid", fgColor="1F4E78")
                c.alignment = Alignment(wrap_text=True, vertical="center")
                sh.column_dimensions[get_column_letter(i)].width = widths.get(h, 11)
            for r in sorted(rs, key=lambda r: (order.get(r["f"]["d"], 3), r["u"]["id"])):
                sh.append([srlib.spreadsheet_text(v) for v in line(r)])
                sh.cell(row=sh.max_row, column=2).fill = PatternFill("solid", fgColor=fills.get(r["f"]["d"], "FFFFFF"))
            sh.freeze_panes = "B2"
            sh.auto_filter.ref = sh.dimensions
        if pending_ids:
            sh = wb.create_sheet("Pending")
            sh.append(["ID", "Title", "Batch", "Export status", "Stage", "Context ID", "Handoff manifest"])
            for rid in pending_ids:
                u = U.get(rid, {})
                sh.append([srlib.spreadsheet_text(v) for v in [rid, u.get("title", "[unknown record]"), u.get("batch", ""),
                          status["status"].upper(), a.stage, context_id or "unknown", manifest_name]])
        log_path = os.path.join(out, f"{P}_screening_log.xlsx")
        wb.save(log_path)
    except ImportError:
        log_path = os.path.join(out, f"{P}_screening_log_*.csv")
        with open(os.path.join(out, f"{P}_screening_log_Summary.csv"), "w", encoding="utf-8-sig", newline="") as f:
            csv.writer(f, quoting=csv.QUOTE_ALL).writerows([srlib.spreadsheet_text(v) for v in row] for row in summary)
        for name, rs in cols:
            with open(os.path.join(out, f"{P}_screening_log_{name}.csv"), "w", encoding="utf-8-sig", newline="") as f:
                w = csv.writer(f, quoting=csv.QUOTE_ALL)
                w.writerow(head)
                w.writerows([srlib.spreadsheet_text(v) for v in line(r)] for r in
                            sorted(rs, key=lambda r: (order.get(r["f"]["d"], 3), r["u"]["id"])))
        with open(os.path.join(out, f"{P}_screening_log_Pending.csv"), "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f, quoting=csv.QUOTE_ALL)
            w.writerow(["ID", "Title", "Batch", "Export status", "Stage", "Context ID", "Handoff manifest"])
            for rid in pending_ids:
                u = U.get(rid, {})
                w.writerow([srlib.spreadsheet_text(v) for v in [rid, u.get("title", ""), u.get("batch", ""),
                           status["status"].upper(), a.stage, context_id or "unknown", manifest_name]])
        print("openpyxl not installed: wrote CSV files instead of .xlsx (pip install openpyxl for Excel)")

    # ------------------------------------------------------------------ RIS
    def raw_for(u):
        ms = sorted(u["members"], key=lambda i: srlib.db_rank((RAW[i].get("DB") or [""])[0]))
        return RAW[ms[0]]

    def extra(r):
        u, f = r["u"], r["f"]
        lab = f"{P}-{f['d'].capitalize()}" + (f"-{f['code']}" if f["d"] == "exclude" else "")
        note = (f"sr-screener {P} [{u['id']}]: {f['d'].upper()} ({labels.get(f['code'], f['code'])}) - {f.get('why', '')}"
                f" | A: {r['A'].get('d', '')}/{r['A'].get('code', '')} | B: {r['B'].get('d', '')}/{r['B'].get('code', '')}"
                f" | by {f['by']}")
        tags = [("LB", lab), ("ID", u["id"]), ("N1", notice + " | " + note)]
        if a.tag_keywords:
            tags.append(("KW", lab))
        return tags

    ris_files = []
    for n, d in ((1, "include"), (2, "unclear"), (3, "exclude")):
        rs = [r for r in rows if r["f"]["d"] == d]
        p = os.path.join(out, f"{P}_{n}_{d}.ris")
        srlib.write_ris(p, [(raw_for(r["u"]), extra(r)) for r in rs])
        ris_files.append((os.path.basename(p), len(rs)))

    # ------------------------------------------------------------- PRISMA md
    md = [f"# PRISMA 2020 counts - {'title/abstract' if a.stage == 'ta' else 'full-text'} stage", "", f"> {notice}", ""]
    if not complete:
        md += [f"> **Provisional:** {len(pending_ids)} records are still pending.", ""]
        md += ["> " + problem for problem in state_problems]
        if a.stage == "ft" and ta_pending_ids:
            md += [f"> Title/abstract decisions or rechecks remain pending, including {len(ta_qc_ids)} "
                   "required title/abstract QC rechecks. These full-text counts are not final.", ""]
    if a.stage == "ta":
        dbs = "; ".join(f"{k} n = {v}" for k, v in counts["identified_by_database"].items())
        excl = "<br/>".join(f"{labels.get(c, c)}: {n}" for c, n in exc_sorted)
        md += ["```mermaid", "flowchart TD",
               f'  I["Records identified from databases (n = {counts["identified_total"]})<br/>{dbs}"]',
               f'  R["Records removed before screening:<br/>duplicate records (n = {counts["duplicates_removed"]})"]',
               f'  S["Records screened (n = {counts["records_screened"]})"]',
               f'  X["Records excluded (n = {counts["records_excluded"]})<br/>{excl}"]',
               f'  F["Reports sought for retrieval (n = {counts["reports_sought_for_retrieval"]})"]',
               "  I --> R", "  I --> S", "  S --> X", "  S --> F", "```", ""]
    else:
        reasons = "<br/>".join(f"{k}: {v}" for k, v in counts["excluded_by_reason"].items())
        md += ["```mermaid", "flowchart TD",
               f'  F["Reports sought for retrieval (n = {counts["reports_sought_for_retrieval"]})"]',
               f'  N["Reports not retrieved (n = {counts["reports_not_retrieved"]})"]',
               f'  E["Reports assessed for eligibility (n = {counts["reports_assessed"]})"]',
               f'  X["Reports excluded (n = {counts["reports_excluded"]})<br/>{reasons}"]',
               f'  C["Reports of included studies (n = {counts["studies_included_reports"]})"]',
               f'  U["Reports awaiting classification (n = {counts["reports_unclear_awaiting_classification"]})"]',
               "  F --> N", "  F --> E", "  E --> X", "  E --> C", "  E --> U", "```", ""]
    md += ["```json", json.dumps({k: v for k, v in counts.items() if k != "ta"}, indent=1, ensure_ascii=False), "```"]
    with open(os.path.join(out, f"{P}_prisma_counts.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")

    # --------------------------------------------------------- methods text
    mpath = os.path.join(out, f"{P}_methods_selection.md")
    with open(mpath, "w", encoding="utf-8") as f:
        f.write(f"# Selection process - {a.stage} stage (methods draft)\n\n> {notice}\n\n")
        f.write(f"Exported by sr-screener {srlib.VERSION} ({REPO_URL}). "
                f"The supplied state contains {len(rows)} recorded decisions for {len(universe)} records/reports: "
                f"{count('include')} include, {count('unclear')} unclear, {count('exclude')} exclude. "
                f"{len(pending_ids)} records need decisions or required rechecks. "
                "These are state observations, not proof that independent agents or human verification ran.\n\n")
        f.write("Runtime identity: " + (declared.get("runtime") or "unknown (not attested)") + ".\n\n")
        f.write("Model identities: " + "; ".join(
            role + "=" + (status["models"][role]["identity"] or "unknown (not attested)") for role in roles) + ".\n\n")
        f.write("Human signoff: " + status["human_signoff"]["status"] +
                (f" (approved={declared['human_signoff']})" if "human_signoff" in declared else "") + ".\n\n")
        if attestation:
            f.write(f"Declarations supplied by {declared['attested_by']} at {declared['attested_at']}; "
                    "not independently verified by this exporter.\n\n")
        f.write("Recorded agreement statistics: " + json.dumps(agree, ensure_ascii=False) + ".\n\n")
        for problem in state_problems:
            f.write("State limitation: " + problem + ".\n\n")
        f.write("[TO COMPLETE: actual search sources/dates, eligibility rules, reviewer execution and isolation, "
                "pilot coverage, adjudication, QC, human checks and supporting page locators. "
                "Configured model labels and agent names are not execution evidence.]\n")

    # --------------------------------------------------------------- corpus
    when = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    n_ok, rejected = write_corpus(os.path.join(out, f"{P}_literature_corpus.yaml"), adv_rows, a.stage, when, status, notice)
    srlib.save_json(os.path.join(out, f"{P}_corpus_rejections.json"),
                    {"export_status": status, "rejected": rejected}, indent=2)

    # Publish the manifest last; interrupted exports have no handoff authority.
    if input_snapshot(work, cfg, a.stage) != snapshot:
        raise SystemExit("screening inputs changed during export; files retained without a handoff manifest")
    artifacts = []
    for name in sorted(os.listdir(out)):
        path = os.path.join(out, name)
        artifacts.append({"base": "export", "path": name, "sha256": file_sha256(path),
                          "size_bytes": os.path.getsize(path), **status})
    if a.stage == "ta":
        path = os.path.join(work, "prisma_ta.json")
        artifacts.append({"base": "work", "path": "prisma_ta.json", "sha256": file_sha256(path),
                          "size_bytes": os.path.getsize(path), **status})
    manifest = {"schema": MANIFEST_SCHEMA, "export_id": export_id, "generated_at": when, **status,
                "artifact_bases": {"export": ".", "work": work},
                "current_context": context, "input_snapshot": snapshot, "attestation": attestation,
                "configured_models_not_execution_evidence": cfg.get("models", {}),
                "configured_model_labels_not_execution_evidence": cfg.get("model_labels", {}),
                "pending_ids": pending_ids, "state_problems": state_problems,
                "corpus_entries": n_ok, "corpus_rejected_ids": [r["id"] for r in rejected],
                "artifacts": artifacts,
                "consumer_requirements": ["Absent manifest means no final handoff authority.",
                    "Require final_handoff_authorized=true and status=final for a finalized handoff.",
                    "Match stage, current context and input snapshot; verify every listed size and SHA-256.",
                    "Resolve base=export beside this manifest; base=work against the originating work directory.",
                    "Ignore unlisted files and older export directories. Attestations are declarations, not verified execution."]}
    srlib.save_json(os.path.join(out, manifest_name), manifest, indent=2)

    print(f"records with final decision: {len(rows)} / {len(universe)}" + ("" if complete else "  ** INCOMPLETE **"))
    print(f"include {count('include')}  unclear {count('unclear')}  exclude {count('exclude')}  by: {by}")
    print(f"log: {log_path}")
    for fn, n in ris_files:
        print(f"RIS: {fn} ({n})")
    print(f"PRISMA: {P}_prisma_counts.md / .json   methods: {os.path.basename(mpath)}")
    print(f"literature corpus: {n_ok} entries; {len(rejected)} retained in {P}_corpus_rejections.json")
    print(notice)
    print(f"handoff manifest: {os.path.join(out, manifest_name)}")


if __name__ == "__main__":
    main()
