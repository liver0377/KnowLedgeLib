
from evaluation import NeedsClarificationEvaluator


class TestNeedsClarificationEvaluator:
    """测试反问需求评估器"""

    def test_name_property(self):
        """测试 name 属性"""
        evaluator = NeedsClarificationEvaluator()
        assert evaluator.name == "rag_needs_clarification"

    def test_evaluate_with_clarification(self):
        """测试检测到反问的情况"""
        evaluator = NeedsClarificationEvaluator()
        output = "您需要知道具体是哪个部门吗？我需要确认一下。"
        score, comment = evaluator.evaluate(output, {})

        assert score == 1.0
        assert "clarification need" in comment

    def test_evaluate_without_clarification(self):
        """测试没有反问的情况"""
        evaluator = NeedsClarificationEvaluator()
        output = "根据产品文档，CKafka提供高吞吐性能。"
        score, comment = evaluator.evaluate(output, {})

        assert score == 0.0
        assert "no clarification needed" in comment

    def test_detects_question_marks(self):
        """测试检测问号反问"""
        evaluator = NeedsClarificationEvaluator()
        output = "请问您是指文档A还是文档B？"
        score, comment = evaluator.evaluate(output, {})

        assert score == 1.0

    def test_detects_uncertainty(self):
        """测试检测不确定表达"""
        evaluator = NeedsClarificationEvaluator()
        output = "不太清楚您的意思，能否再说明一下？"
        score, comment = evaluator.evaluate(output, {})

        assert score == 1.0

    def test_detects_needs_confirmation(self):
        """测试检测需要确认"""
        evaluator = NeedsClarificationEvaluator()
        output = "需要确认这个时间范围是否正确。"
        score, comment = evaluator.evaluate(output, {})

        assert score == 1.0

    def test_evaluate_with_empty_output(self):
        """测试空输出"""
        evaluator = NeedsClarificationEvaluator()
        score, comment = evaluator.evaluate("", {})

        assert score == 0.0
        assert "Empty" in comment

    def test_evaluate_with_none_output(self):
        """测试 None 输出"""
        evaluator = NeedsClarificationEvaluator()
        score, comment = evaluator.evaluate(None, {})

        assert score == 0.0

    def test_evaluate_with_context(self):
        """测试带上下文的评估"""
        evaluator = NeedsClarificationEvaluator()
        output = "能否提供更多信息？"
        context = {"trace_id": "test-trace", "input": "测试问题"}
        score, comment = evaluator.evaluate(output, context)

        assert score == 1.0
