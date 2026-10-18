import csv
import os
import sys
import time
from pathlib import Path

def main():
    # Reliably get the repo root regardless of where script is invoked
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(script_dir, '..'))
    sys.path.insert(0, repo_root)
    
    from code.router import route_ticket
    from code.retriever import build_index

    input_path = os.path.join(repo_root, "support_tickets", "support_tickets.csv")
    output_path = os.path.join(repo_root, "support_tickets", "output.csv")
    data_dir = Path(repo_root) / "data"
    
    print(f"[DEBUG] Reading from: {input_path}")

    with open(input_path, mode='r', encoding='utf-8') as f:
        reader = list(csv.DictReader(f))
        total = len(reader)
        
    print(f"[INFO] Found {total} logical tickets.")
    
    index = build_index(data_dir)
    results = []
    OUTPUT_FIELDNAMES = ["issue", "subject", "company", "response", "product_area", "status", "request_type", "justification"]

    for i, row in enumerate(reader):
        print(f"--- Processing row {i+1} of {total} ---")
        try:
            row_data = {k.capitalize() if k else "": v for k, v in row.items()}
            ticket_data = {
                "Issue": row_data.get("Issue", ""),
                "Subject": row_data.get("Subject", ""),
                "Company": row_data.get("Company", "")
            }
            result = route_ticket(ticket_row=ticket_data, index=index)
            results.append({
                "issue": ticket_data["Issue"],
                "subject": ticket_data["Subject"],
                "company": ticket_data["Company"],
                "response": result.response,
                "product_area": result.product_area,
                "status": result.status,
                "request_type": result.request_type,
                "justification": result.justification
            })
            time.sleep(1) 
        except Exception as e:
            print(f"Error on Row {i+1}: {e}")
            results.append({
                "issue": ticket_data.get("Issue", ""),
                "subject": ticket_data.get("Subject", ""),
                "company": ticket_data.get("Company", ""),
                "status": "escalated",
                "product_area": "unknown",
                "response": "This requires specialist attention. Our team will follow up with you shortly.",
                "justification": "Processing error encountered during automated triage. Escalated for safety.",
                "request_type": "product_issue"
            })

    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_FIELDNAMES, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(results)
    
    print(f"[SUCCESS] Final output saved to {output_path}")

if __name__ == "__main__":
    main()
