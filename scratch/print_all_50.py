import json
import os
import pandas as pd

project_dir = r"d:\VinAI\K4-Day9-2A202601224-HoangTruongGiang"
input_dir = os.path.join(project_dir, 'input')
output_dir = os.path.join(project_dir, 'output')

print(f"{'Case':<8} {'Status':<12} {'Primary Issue':<25} {'Refund':<10} {'Secondary Issues'}")
print("="*80)

for i in range(1, 51):
    case_file = f"EC_{i:03d}.json"
    with open(os.path.join(output_dir, case_file), 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    p = data['case_assessment']['primary_issue']
    s = data['case_assessment']['secondary_issues']
    st = data['case_assessment']['case_status']
    r = data['financial_resolution']['recommended_refund_brl']
    
    print(f"{case_file:<8} {st:<12} {p:<25} {r:<10.2f} {s}")
