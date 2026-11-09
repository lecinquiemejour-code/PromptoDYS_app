import logging

from promptodys import app


def test_domain_logs_reach_log_message(monkeypatch):
    """Une fois le pont branché, un log du domaine arrive dans report_logs (et donc dans le rapport)."""
    logger = logging.getLogger("promptodys")
    # Configuration du logger rétablie après le test
    monkeypatch.setattr(logger, "handlers", [])
    monkeypatch.setattr(logger, "level", logger.level)
    monkeypatch.setattr(logger, "propagate", logger.propagate)
    monkeypatch.setattr(app, "report_logs", [])

    app.configure_logger()
    logging.getLogger("promptodys.domain.note").info("message du domaine")

    assert app.report_logs == ["message du domaine"]
