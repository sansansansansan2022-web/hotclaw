"""E2E test suite for HotClaw.

【E2E 端到端测试】
验证从前端操作到后端状态落库再到页面展示的完整闭环。

运行方式：
    # 运行所有 E2E 测试
    pytest backend/tests/e2e/ -v

    # 运行特定测试场景
    pytest backend/tests/e2e/test_draft_workflow.py::TestSemiAutoDraftWorkflow -v

    # 运行带详细输出的测试
    pytest backend/tests/e2e/ -v -s
"""
