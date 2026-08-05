# Member Role Report — Day 9: Multi Agent A2A

## 1. Thông tin cá nhân

| Thông tin         | Nội dung                                      |
| ------------------ | ---------------------------------------------- |
| Họ và tên       | Nguyễn Khánh Toàn                           |
| MSSV               | 2A202601738                                    |
| Khóa/Lớp         | K4                                             |
| Vai trò chính    | Agent Architecture & LLM Orchestrator Engineer |
| Ngày hoàn thành | 2026-08-05                                     |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable                     | File/hàm phụ trách                                                                                                                                                    | Input nhận vào             | Output bàn giao                                                 | Trạng thái |
| :------------------------------------- | :----------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :--------------------------- | :--------------------------------------------------------------- | :----------- |
| **LLM Orchestrator Coordinator** | `ecom-multi-agent/orchestrator/agent.py`, `pipeline.py`, `system_prompt.md`                                                                                        | `input/EC_*.json`          | Tool calling agent routing, execution trace,`output/EC_*.json` | Hoàn thành |
| **Modular Policy Sub-Agents**    | `ecom-multi-agent/policy_agent/sub_agents/` (`full_refund_agent.py`, `freight_refund_agent.py`, `split_payment_agent.py`, `late_claim_agent.py`), `rules.py` | Data bundle từ`DataAgent` | Standardized`EC_POLICY_V2` case assessment                     | Hoàn thành |
| **Architecture & Verifier Gate** | `architecture.md`, `metadata.json`, `orchestrator/verifier.py`                                                                                                     | Final case assessment        | Clean architectural diagram,`trace.jsonl`, `metadata.json`   | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động                        | Thành viên/module được hỗ trợ | Kết quả                                                                                    |
| :---------------------------------- | :----------------------------------- | :------------------------------------------------------------------------------------------- |
| **Integrate Verifier Gate**   | `orchestrator/verifier.py`         | Hard-gate validation trước khi ghi output file để tránh false-positive hoặc sai schema |
| **Trace Logging Integration** | `logging/trace.jsonl`              | Ghi log đầy đủ latency, input/output summary và agent steps cho 50 case                 |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện                                          | File/hàm/artifact liên quan                 | Kết quả bàn giao                                                              | Cách xác minh                                              |
| :------------------------------------------------------------------- | :-------------------------------------------- | :------------------------------------------------------------------------------- | :----------------------------------------------------------- |
| **Chuyển đổi Orchestrator sang LLM Routing**                | `ecom-multi-agent/orchestrator/agent.py`    | System prompt + Tool-calling Orchestrator dùng`AgentExecutor`                 | Runs via`python ecom-multi-agent/orchestrator/pipeline.py` |
| **Chia nhỏ Policy Agent thành các sub-agent chuyên biệt** | `ecom-multi-agent/policy_agent/sub_agents/` | 4 sub-agent (`FullRefund`, `FreightRefund`, `SplitPayment`, `LateClaim`) | Integrated into`PolicyAgent` & `rules.py`                |
| **Kiểm tra Verifier Gate & Schema Compliance**                | `orchestrator/verifier.py`, `output/`     | 50/50 JSON outputs match schema with 0 verifier errors                           | `validate()` check passed across 50 cases                  |

Output bàn giao:

- 50 file JSON hợp lệ trong thư mục `output/` (`EC_001.json` - `EC_050.json`)
- File trace log `logging/trace.jsonl`
- File kiến trúc `architecture.md` và thông tin runtime `metadata.json`

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Trước đây pipeline chạy chuỗi Python cố định (`data_agent` -> `policy_agent` -> `execution_router`), chưa có routing động bằng LLM. Đồng thời `policy_agent` là 1 monolith duy nhất. Hệ thống cần được refactor sang:

1. Orchestrator dùng LLM tool-calling routing để gọi các worker.
2. `policy_agent` chia thành các sub-agent chuyên biệt theo từng miền chính sách.
3. Toàn bộ thông tin truy xuất từ database CSV qua `data_agent`, không tự bịa thông tin bên ngoài schema.

### Cách triển khai

- **`LLMOrchestrator`**: Sử dụng `AgentExecutor` + `create_tool_calling_agent` trong LangChain với system prompt Coordinator (`system_prompt.md`). Cung cấp 3 tools được đóng gói state (`fetch_order_data`, `run_policy_assessment`, `dispatch_resolution_actions`) giúp LLM nhận summary gọn thay vì truyền cả dữ liệu thô vào LLM context.
- **`Policy Sub-Agents`**: Tạo 4 sub-agent trong `policy_agent/sub_agents/`:
  - `FullRefundPolicyAgent`: Đánh giá đơn hủy (`canceled_order_paid`) / hết hàng (`unavailable_order_paid`).
  - `FreightRefundPolicyAgent`: Đánh giá giao trễ do seller (`late_delivery_seller`) hoặc vận chuyển (`late_delivery_logistics`).
  - `SplitPaymentPolicyAgent`: Đánh giá thanh toán chia làm nhiều đợt hợp lệ (`valid_split_payment`).
  - `LateClaimPolicyAgent`: Đánh giá khiếu nại giao trễ không có căn cứ (`unsupported_late_claim`).
- **Verifier Hard Gate**: Hàm `validate()` chạy trực tiếp bằng Python ngay sau tool loop để đảm bảo kết quả luôn khớp 100% schema trước khi ghi file `output/`.

### Input, output và contract

| Thành phần                   | Mô tả                                                                    |
| :----------------------------- | :------------------------------------------------------------------------- |
| Input                          | Input JSON case trong`input/EC_*.json`                                   |
| Output                         | Assessment JSON case trong`output/EC_*.json`                             |
| Module phụ thuộc             | `data_agent.agent.DataAgent`, `execution_agent.router.ExecutionRouter` |
| Module sử dụng output        | Chấm điểm tự động và audit log                                      |
| Điều kiện lỗi cần xử lý | Order không tồn tại (`found=False`), verifier schema mismatch         |

### Cách xác minh

```bash
python ecom-multi-agent/orchestrator/pipeline.py
```

- **Kết quả mong đợi:** Xử lý thành công 50/50 cases, 0 data error, 0 verifier-flagged error.
- **Kết quả thực tế:** Processed 50 cases -> `output/`, data errors: 0, verifier-flagged: 0.
- **Artifact/log:** `logging/trace.jsonl`, `output/EC_001.json` - `output/EC_050.json`.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** LLM khi gọi tool có thể nhận quá nhiều dữ liệu nếu trả về toàn bộ order bundle thô, gây trễ và dễ vượt token limit.
- **Các phương án đã cân nhắc:**
  1. Cho LLM nhận toàn bộ bundle thô (JSON lớn).
  2. Tạo `_CaseState` đóng gói cho từng case, tools chỉ trả về bản tóm tắt ngắn (status, primary issue, action count).
- **Phương án đã chọn:** Phương án 2.
- **Lý do:** Giúp LLM routing nhanh, chính xác, không bị lẫn thông tin và giữ nguyên tính đúng đắn dữ liệu trong Python.
- **Bằng chứng quyết định phù hợp:** 50/50 cases hoàn thành với thời gian tối ưu và không gặp lỗi rò rỉ context.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** Cần đảm bảo nếu LLM không thể gọi đủ tool hoặc gặp sự cố API key, pipeline vẫn đảm bảo tính sẵn sàng (fail-safe).
- **Lệnh hoặc bước tái hiện:** Chạy test suite với API key trống hoặc mạng chậm.
- **Nguyên nhân gốc:** LLM routing hoàn toàn phụ thuộc vào API response.
- **Cách xử lý:** Bổ sung fallback execution sequence trong `LLMOrchestrator` để tự động kích hoạt đủ các bước (`fetch_order_data` -> `run_policy_assessment` -> `dispatch_resolution_actions`) nếu LLM bỏ sót tool call.
- **Cách xác minh sau khi sửa:** Chạy lại 50 cases và kiểm tra 100% case đều sinh đúng output JSON.

## 7. Hiểu biết về luồng end-to-end

1. Dữ liệu từ khách hàng khiếu nại (`input/EC_*.json`) chứa `claimed_order_id`.
2. `DataAgent` kiểm tra CSVs trong `data/` và trả về bundle dữ liệu đã đối soát.
3. `PolicyAgent` thông qua các Policy Sub-Agents (`FullRefund`, `FreightRefund`, `SplitPayment`, `LateClaim`) áp dụng quy tắc `EC_POLICY_V2` một cách xác định (deterministic, không dùng LLM để quyết định) để đưa ra đánh giá, hoàn tiền và bằng chứng; hai sub-agent (`FullRefund`, `FreightRefund`) có gọi thêm một lệnh LLM xác nhận khi có API key nhưng kết quả gọi này chưa được sử dụng vào quyết định trả về.
4. `ExecutionRouter` điều phối hành động xử lý cho `RefundAgent`, `PaymentAgent`, `LogisticsAgent`.
5. `Verifier` thực thi hard gate để kiểm tra định dạng evidence, hạn mức mảng và tính nhất quán trước khi ghi file `output/EC_*.json` và ghi trace vào `logging/trace.jsonl`.

## 8. Cam kết của thành viên

Đánh dấu sau khi tự kiểm tra:

- [X] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [X] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [X] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [X] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [X] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Nguyễn Khánh Toàn
**Ngày xác nhận:** 2026-08-05
