from unittest.mock import Mock, patch

from evaluation.citation_evaluator import (
    CITATION_PATTERN,
    CitationEvaluator,
    evaluate_citation_present,
    evaluate_citation_present_with_details,
    record_citation_score,
)


class TestCitationEvaluator:
    """测试 CitationEvaluator 类"""

    def test_name_property(self):
        """测试 name 属性"""
        evaluator = CitationEvaluator()
        assert evaluator.name == "rag_citation_present"

    def test_evaluate_with_citation(self):
        """测试评估包含引用的情况"""
        evaluator = CitationEvaluator()
        output = "参见 [文档](/kb/files/550e8400-e29b-41d4-a716-446655440000/download)"
        score, comment = evaluator.evaluate(output, {})

        assert score == 1.0
        assert "Found 1 citation" in comment

    def test_evaluate_without_citation(self):
        """测试评估不包含引用的情况"""
        evaluator = CitationEvaluator()
        output = "没有引用的文本"
        score, comment = evaluator.evaluate(output, {})

        assert score == 0.0
        assert "No citations" in comment

    def test_evaluate_with_empty_output(self):
        """测试空输出"""
        evaluator = CitationEvaluator()
        score, comment = evaluator.evaluate("", {})

        assert score == 0.0
        assert "Empty" in comment

    def test_evaluate_with_context(self):
        """测试带上下文的评估"""
        evaluator = CitationEvaluator()
        output = "参见 [文档](/kb/files/123/download)"
        context = {"trace_id": "test-trace", "input": "测试问题"}
        score, comment = evaluator.evaluate(output, context)

        assert score == 1.0

    def test_evaluate_with_multiple_citations(self):
        """测试多个引用的评估"""
        evaluator = CitationEvaluator()
        output = """
        参考 [文档A](/kb/files/123/download)
        和 [文档B](/kb/files/456/download)
        """
        score, comment = evaluator.evaluate(output, {})

        assert score == 1.0
        assert "2 citations" in comment

    def test_is_enabled_default(self):
        """测试默认启用状态"""
        evaluator = CitationEvaluator()
        assert evaluator.is_enabled(None) is True


class TestEvaluateCitationPresent:
    """测试引用存在性评估函数"""

    def test_citation_present_with_valid_link(self):
        """测试包含有效引用链接的情况"""
        output = "根据产品文档 [CKafka产品白皮书 - 第4页](/kb/files/550e8400-e29b-41d4-a716-446655440000/download)，CKafka提供高吞吐性能。"
        assert evaluate_citation_present(output) is True

    def test_citation_present_with_multiple_links(self):
        """测试包含多个引用链接的情况"""
        output = """
        参考 [文档A - 第1页](/kb/files/550e8400-e29b-41d4-a716-446655440000/download)
        和 [文档B - 第2页](/kb/files/660e8400-e29b-41d4-a716-446655440001/download)
        """
        assert evaluate_citation_present(output) is True

    def test_citation_present_without_link(self):
        """测试不包含引用链接的情况"""
        output = "CKafka提供高吞吐性能，但是没有引用来源。"
        assert evaluate_citation_present(output) is False

    def test_citation_present_with_empty_string(self):
        """测试空字符串"""
        assert evaluate_citation_present("") is False

    def test_citation_present_with_none(self):
        """测试 None 输入"""
        assert evaluate_citation_present(None) is False

    def test_citation_present_with_invalid_link_format(self):
        """测试无效的链接格式"""
        output = "参见 [文档](https://example.com/doc)"
        assert evaluate_citation_present(output) is False

    def test_citation_present_with_partial_pattern(self):
        """测试部分匹配（只有链接没有文字）"""
        output = "请查看文档: [](/kb/files/550e8400-e29b-41d4-a716-446655440000/download)"
        assert evaluate_citation_present(output) is True

    def test_citation_present_with_special_chars_in_link_text(self):
        """测试链接文本中包含特殊字符"""
        output = "根据 [文档名称_测试!@#$% - 第1页](/kb/files/550e8400-e29b-41d4-a716-446655440000/download)"
        assert evaluate_citation_present(output) is True


class TestEvaluateCitationPresentWithDetails:
    """测试带详细信息的引用存在性评估函数"""

    def test_with_details_single_link(self):
        """测试单个链接的详细信息"""
        output = "参考 [文档](/kb/files/550e8400-e29b-41d4-a716-446655440000/download)"
        result = evaluate_citation_present_with_details(output)

        assert result["has_citation"] is True
        assert result["count"] == 1
        assert len(result["citations"]) == 1
        assert (
            "[文档](/kb/files/550e8400-e29b-41d4-a716-446655440000/download)" in result["citations"]
        )

    def test_with_details_multiple_links(self):
        """测试多个链接的详细信息"""
        output = """
        参考 [文档A](/kb/files/550e8400-e29b-41d4-a716-446655440000/download)
        和 [文档B](/kb/files/660e8400-e29b-41d4-a716-446655440001/download)
        """
        result = evaluate_citation_present_with_details(output)

        assert result["has_citation"] is True
        assert result["count"] == 2
        assert len(result["citations"]) == 2

    def test_with_details_no_links(self):
        """测试没有链接的详细信息"""
        output = "没有引用的文本"
        result = evaluate_citation_present_with_details(output)

        assert result["has_citation"] is False
        assert result["count"] == 0
        assert len(result["citations"]) == 0

    def test_with_details_empty_string(self):
        """测试空字符串的详细信息"""
        result = evaluate_citation_present_with_details("")

        assert result["has_citation"] is False
        assert result["count"] == 0
        assert result["citations"] == []


class TestCitationPattern:
    """测试正则表达式模式"""

    def test_pattern_matches_valid_kb_link(self):
        """测试模式匹配有效的 KB 链接"""
        import re

        link = "[文档名称 - 第1页](/kb/files/550e8400-e29b-41d4-a716-446655440000/download)"
        assert re.search(CITATION_PATTERN, link) is not None

    def test_pattern_does_not_match_regular_link(self):
        """测试模式不匹配普通 HTTP 链接"""
        import re

        link = "[文档](https://example.com/download)"
        assert re.search(CITATION_PATTERN, link) is None

    def test_pattern_does_not_match_relative_link(self):
        """测试模式不匹配相对路径链接"""
        import re

        link = "[文档](/docs/file.pdf)"
        assert re.search(CITATION_PATTERN, link) is None


@patch("evaluation.citation_evaluator.Langfuse")
@patch("evaluation.citation_evaluator.settings")
class TestRecordCitationScore:
    """测试记录分数到 Langfuse 的函数"""

    def test_record_score_when_enabled(self, mock_settings, mock_langfuse_class):
        """测试启用评估时记录分数"""
        mock_settings.LANGFUSE_TRACING = True
        mock_settings.LANGFUSE_AUTO_EVAL = True
        mock_langfuse = Mock()
        mock_langfuse_class.return_value = mock_langfuse

        output = "参见 [文档](/kb/files/550e8400-e29b-41d4-a716-446655440000/download)"
        trace_id = "test-trace-id"

        record_citation_score(trace_id, output)

        mock_langfuse.score.assert_called_once()
        call_args = mock_langfuse.score.call_args
        assert call_args[1]["name"] == "rag_citation_present"
        assert call_args[1]["value"] == 1.0
        assert call_args[1]["trace_id"] == trace_id
        assert "Found 1 citation(s)" in call_args[1]["comment"]

    def test_record_score_without_citation(self, mock_settings, mock_langfuse_class):
        """测试没有引用时记录分数"""
        mock_settings.LANGFUSE_TRACING = True
        mock_settings.LANGFUSE_AUTO_EVAL = True
        mock_langfuse = Mock()
        mock_langfuse_class.return_value = mock_langfuse

        output = "没有引用的文本"
        trace_id = "test-trace-id"

        record_citation_score(trace_id, output)

        mock_langfuse.score.assert_called_once()
        call_args = mock_langfuse.score.call_args
        assert call_args[1]["value"] == 0.0
        assert "No citations found" in call_args[1]["comment"]

    def test_skip_when_tracing_disabled(self, mock_settings, mock_langfuse_class):
        """测试 Langfuse 追踪禁用时不记录"""
        mock_settings.LANGFUSE_TRACING = False
        mock_settings.LANGFUSE_AUTO_EVAL = True

        record_citation_score("trace-id", "some output")

        mock_langfuse_class.assert_not_called()

    def test_skip_when_auto_eval_disabled(self, mock_settings, mock_langfuse_class):
        """测试自动评估禁用时不记录"""
        mock_settings.LANGFUSE_TRACING = True
        mock_settings.LANGFUSE_AUTO_EVAL = False

        record_citation_score("trace-id", "some output")

        mock_langfuse_class.assert_not_called()

    def test_skip_when_enabled_param_is_false(self, mock_settings, mock_langfuse_class):
        """测试通过参数控制不记录"""
        mock_settings.LANGFUSE_TRACING = True
        mock_settings.LANGFUSE_AUTO_EVAL = True

        record_citation_score("trace-id", "some output", enabled=False)

        mock_langfuse_class.assert_not_called()

    @patch("evaluation.citation_evaluator.logger")
    def test_handle_langfuse_exception(self, mock_logger, mock_settings, mock_langfuse_class):
        """测试处理 Langfuse 异常"""
        mock_settings.LANGFUSE_TRACING = True
        mock_settings.LANGFUSE_AUTO_EVAL = True
        mock_langfuse_class.side_effect = Exception("Langfuse connection error")

        record_citation_score("trace-id", "some output")

        mock_logger.warning.assert_called()
        assert "Failed to record citation score" in mock_logger.warning.call_args[0][0]
