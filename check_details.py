import json, glob
from src.dispute_system import CoordinatorAgent

coordinator = CoordinatorAgent('data')

for fpath in sorted(glob.glob('input/EC_*.json')):
    out, trace = coordinator.process_case(fpath)
    case_id = out['case_id']
    p_issue = out['case_assessment']['primary_issue']
    s_issues = out['case_assessment']['secondary_issues']
    actions = out['resolution_actions']
    refund = out['financial_resolution']['recommended_refund_brl']
    evidence = out['evidence_ids']
    
    print(f"{case_id}: P={p_issue} | Refund={refund} | Sec={s_issues} | Act={actions}")
