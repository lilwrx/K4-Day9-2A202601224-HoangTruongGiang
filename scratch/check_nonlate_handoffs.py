import json
import os
import pandas as pd

project_dir = r"d:\VinAI\K4-Day9-2A202601224-HoangTruongGiang"
input_dir = os.path.join(project_dir, 'input')
output_dir = os.path.join(project_dir, 'output')

for i in range(1, 51):
    case_file = f"EC_{i:03d}.json"
    with open(os.path.join(output_dir, case_file), 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    primary = data['case_assessment']['primary_issue']
    late_sellers = data['delivery_analysis']['late_handoff_seller_ids']
    actions = data['resolution_actions']
    
    if primary not in ('late_delivery_seller', 'late_delivery_logistics') and len(late_sellers) > 0:
        print(f"{case_file}: primary={primary}, late_sellers={late_sellers}, actions={actions}")
