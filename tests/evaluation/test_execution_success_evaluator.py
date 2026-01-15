from evaluation import ExecutionSuccessEvaluator


class TestExecutionSuccessEvaluator:
    def test_name_property(self):
        evaluator = ExecutionSuccessEvaluator()
        assert evaluator.name == "execution_success"

    def test_sql_executed_successfully(self):
        evaluator = ExecutionSuccessEvaluator()
        score, comment = evaluator.evaluate("", {"sql_exec_error": ""})

        assert score == 1.0
        assert "successfully" in comment.lower()

    def test_sql_execution_failed(self):
        evaluator = ExecutionSuccessEvaluator()
        score, comment = evaluator.evaluate(
            "", {"sql_exec_error": "relation 'users' does not exist"}
        )

        assert score == 0.0
        assert "failed" in comment.lower()

    def test_sql_execution_failed_with_syntax_error(self):
        evaluator = ExecutionSuccessEvaluator()
        score, comment = evaluator.evaluate("", {"sql_exec_error": "syntax error near SELECT"})

        assert score == 0.0
        assert "syntax error" in comment.lower()

    def test_missing_sql_exec_error_in_context(self):
        evaluator = ExecutionSuccessEvaluator()
        score, comment = evaluator.evaluate("", {})

        assert score == 1.0
        assert "successfully" in comment.lower()

    def test_empty_sql_exec_error_string(self):
        evaluator = ExecutionSuccessEvaluator()
        score, comment = evaluator.evaluate("", {"sql_exec_error": ""})

        assert score == 1.0
        assert "successfully" in comment.lower()
