from unittest.mock import Mock, patch

from evaluation import CitationEvaluator, EvaluationManager
from evaluation.base import BaseEvaluator


class TestEvaluationManager:
    """测试评估管理器"""

    def test_register_evaluator(self):
        """测试注册评估器"""
        manager = EvaluationManager()
        evaluator = CitationEvaluator()

        manager.register(evaluator)

        assert len(manager._evaluators) == 1
        assert manager._evaluators[0] is evaluator

    def test_register_multiple_evaluators(self):
        """测试注册多个评估器"""
        manager = EvaluationManager()
        evaluator1 = CitationEvaluator()

        class DummyEvaluator(BaseEvaluator):
            @property
            def name(self) -> str:
                return "dummy"

            def evaluate(self, output: str, context: dict) -> tuple[float, str]:
                return 1.0, "ok"

        evaluator2 = DummyEvaluator()

        manager.register(evaluator1)
        manager.register(evaluator2)

        assert len(manager._evaluators) == 2

    @patch("evaluation.manager.settings")
    @patch("evaluation.manager.Langfuse")
    def test_evaluate_all_when_enabled(self, mock_langfuse_class, mock_settings):
        """测试启用时执行所有评估"""
        mock_settings.LANGFUSE_TRACING = True
        mock_settings.LANGFUSE_AUTO_EVAL = True
        mock_langfuse = Mock()
        mock_langfuse_class.return_value = mock_langfuse

        manager = EvaluationManager()
        manager.register(CitationEvaluator())

        manager.evaluate_all("参见 [文档](/kb/files/123/download)", {"trace_id": "test"})

        mock_langfuse.score.assert_called_once()

    @patch("evaluation.manager.settings")
    def test_skip_when_tracing_disabled(self, mock_settings):
        """测试 tracing 禁用时不评估"""
        mock_settings.LANGFUSE_TRACING = False

        manager = EvaluationManager()
        manager.register(CitationEvaluator())

        with patch.object(manager, "_record_score") as mock_record:
            manager.evaluate_all("any output", {"trace_id": "test"})
            mock_record.assert_not_called()

    @patch("evaluation.manager.settings")
    def test_skip_when_auto_eval_disabled(self, mock_settings):
        """测试 auto_eval 禁用时不评估"""
        mock_settings.LANGFUSE_TRACING = True
        mock_settings.LANGFUSE_AUTO_EVAL = False

        manager = EvaluationManager()
        manager.register(CitationEvaluator())

        with patch.object(manager, "_record_score") as mock_record:
            manager.evaluate_all("any output", {"trace_id": "test"})
            mock_record.assert_not_called()

    @patch("evaluation.manager.settings")
    @patch("evaluation.manager.Langfuse")
    def test_continue_on_evaluator_error(self, mock_langfuse_class, mock_settings):
        """测试评估器失败时继续执行其他评估器"""
        mock_settings.LANGFUSE_TRACING = True
        mock_settings.LANGFUSE_AUTO_EVAL = True
        mock_langfuse = Mock()
        mock_langfuse_class.return_value = mock_langfuse

        manager = EvaluationManager()

        class FailingEvaluator(BaseEvaluator):
            @property
            def name(self) -> str:
                return "failing"

            def evaluate(self, output: str, context: dict) -> tuple[float, str]:
                raise Exception("Evaluator failed")

        manager.register(FailingEvaluator())
        manager.register(CitationEvaluator())

        # 不应该抛出异常
        manager.evaluate_all("any output", {"trace_id": "test"})

        # CitationEvaluator 应该被成功调用
        assert mock_langfuse.score.call_count == 1

    @patch("evaluation.manager.settings")
    def test_record_score_with_boolean_type(self, mock_settings):
        """测试 BOOLEAN 类型分数记录"""
        mock_settings.LANGFUSE_TRACING = True
        mock_settings.LANGFUSE_AUTO_EVAL = True

        manager = EvaluationManager()
        manager.register(CitationEvaluator())

        with patch("evaluation.manager.Langfuse") as mock_langfuse_class:
            mock_langfuse = Mock()
            mock_langfuse_class.return_value = mock_langfuse

            manager.evaluate_all("参见 [文档](/kb/files/123/download)", {"trace_id": "test"})

            call_args = mock_langfuse.score.call_args
            assert call_args[1]["data_type"] == "BOOLEAN"

    @patch("evaluation.manager.settings")
    def test_record_score_with_numeric_type(self, mock_settings):
        """测试 NUMERIC 类型分数记录"""
        mock_settings.LANGFUSE_TRACING = True
        mock_settings.LANGFUSE_AUTO_EVAL = True

        manager = EvaluationManager()

        class NumericEvaluator(BaseEvaluator):
            @property
            def name(self) -> str:
                return "numeric_eval"

            def evaluate(self, output: str, context: dict) -> tuple[float, str]:
                return 0.7, "Numeric score"

        manager.register(NumericEvaluator())

        with patch("evaluation.manager.Langfuse") as mock_langfuse_class:
            mock_langfuse = Mock()
            mock_langfuse_class.return_value = mock_langfuse

            manager.evaluate_all("some output", {"trace_id": "test"})

            call_args = mock_langfuse.score.call_args
            assert call_args[1]["data_type"] == "NUMERIC"
