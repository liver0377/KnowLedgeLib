
from evaluation import SafetyRiskEvaluator


class TestSafetyRiskEvaluator:
    """测试 SQL 安全风险评估器"""

    def test_name_property(self):
        """测试 name 属性"""
        evaluator = SafetyRiskEvaluator()
        assert evaluator.name == "safety_risk"

    def test_evaluate_with_insert(self):
        """测试检测写操作"""
        evaluator = SafetyRiskEvaluator()
        output = "INSERT INTO users (name) VALUES ('test')"
        score, comment = evaluator.evaluate(output, {})

        assert score == 2.0  # write_operation
        assert "write_operation" in comment

    def test_evaluate_with_update(self):
        """测试检测 UPDATE"""
        evaluator = SafetyRiskEvaluator()
        output = "UPDATE products SET price = 100"
        score, comment = evaluator.evaluate(output, {})

        assert score == 2.0

    def test_evaluate_with_delete(self):
        """测试检测 DELETE"""
        evaluator = SafetyRiskEvaluator()
        output = "DELETE FROM temp_table"
        score, comment = evaluator.evaluate(output, {})

        assert score == 2.0

    def test_evaluate_with_broad_scan(self):
        """测试检测全表扫描"""
        evaluator = SafetyRiskEvaluator()
        output = "SELECT * FROM large_table"
        score, comment = evaluator.evaluate(output, {})

        assert score == 3.0  # broad_scan
        assert "broad_scan" in comment

    def test_evaluate_with_broad_scan_true_condition(self):
        """测试检测 WHERE 1=1 模式"""
        evaluator = SafetyRiskEvaluator()
        output = "SELECT * FROM users WHERE 1 = 1"
        score, comment = evaluator.evaluate(output, {})

        assert score == 3.0

    def test_evaluate_with_safe_sql(self):
        """测试安全 SQL 无风险"""
        evaluator = SafetyRiskEvaluator()
        output = "SELECT * FROM users WHERE id = ? AND status = 'active'"
        score, comment = evaluator.evaluate(output, {})

        assert score == 0.0
        assert "no safety risk" in comment.lower()

    def test_evaluate_with_pii_risk(self):
        """测试检测敏感信息"""
        evaluator = SafetyRiskEvaluator()
        output = "SELECT * FROM users WHERE id_card = '123456789'"
        score, comment = evaluator.evaluate(output, {})

        assert score == 1.0  # pii_risk

    def test_evaluate_with_empty_output(self):
        """测试空输出"""
        evaluator = SafetyRiskEvaluator()
        score, comment = evaluator.evaluate("", {})

        assert score == 0.0

    def test_evaluate_with_none_output(self):
        """测试 None 输出"""
        evaluator = SafetyRiskEvaluator()
        score, comment = evaluator.evaluate(None, {})

        assert score == 0.0

    def test_evaluate_with_context(self):
        """测试带上下文的评估"""
        evaluator = SafetyRiskEvaluator()
        output = "SELECT * FROM users"
        context = {"trace_id": "test-trace", "input": "查询用户"}
        score, comment = evaluator.evaluate(output, context)

        assert score == 0.0

    def test_detects_truncate(self):
        """测试检测 TRUNCATE"""
        evaluator = SafetyRiskEvaluator()
        output = "TRUNCATE TABLE temp_data"
        score, comment = evaluator.evaluate(output, {})

        assert score == 2.0
