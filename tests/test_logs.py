import logging

import askGeminiPrompto as app


def test_domain_logs_reach_log_message(monkeypatch):
    """Une fois le pont branché, un log du domaine arrive dans logs_complets (et donc dans le rapport)."""
    logger = logging.getLogger("promptodys")
    # Configuration du logger rétablie après le test
    monkeypatch.setattr(logger, "handlers", [])
    monkeypatch.setattr(logger, "level", logger.level)
    monkeypatch.setattr(logger, "propagate", logger.propagate)
    monkeypatch.setattr(app, "logs_complets", [])

    app.configure_logger()
    logging.getLogger("promptodys.domain.note").info("message du domaine")

    assert app.logs_complets == ["message du domaine"]
