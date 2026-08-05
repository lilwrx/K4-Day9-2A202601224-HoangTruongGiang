import json
import os
import pandas as pd

project_dir = r"d:\VinAI\K4-Day9-2A202601224-HoangTruongGiang"
data_dir = os.path.join(project_dir, 'data')
input_dir = os.path.join(project_dir, 'input')
output_dir = os.path.join(project_dir, 'output')

# Let's write a comprehensive checker to print details of all 50 output files
for i in range(1, 51):
    case_file = f"EC_{i:03d}.json"
    with open(os.path.join(output_dir, case_file), 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    p_issue = data['case_assessment']['primary_issue']
    s_issues = data['case_assessment']['secondary_issues']
    status = data['case_assessment']['case_status']
    refund = data['financial_resolution']['recommended_refund_brl']
    actions = data['resolution_actions']
    evid = data['evidence_ids']
    
    # Check for any potential anomaly
    anomalies = []
    
    # Check refund consistency
    if status == 'action_required' and refund <= 0:
        anomalies.append("action_required with refund <= 0")
    if status == 'no_action' and refund > 0:
        anomalies.append("no_action with refund > 0")
        
    # Check evidence consistency
    if p_issue == 'late_delivery_seller':
        has_seller_evid = any(e.startswith('seller:') for e in evid)
        if not has_seller_evid:
            anomalies.append("late_delivery_seller missing seller: evidence")
            
    # Check actions consistency
    if p_issue == 'valid_split_payment' and 'verify_payment_allocation' in actions:
        anomalies.append("valid_split_payment should NOT have verify_payment_allocation")
        
    if anomalies:
        print(f"ANOMALY in {case_file}: {anomalies}")

print("Anomaly check complete.")
