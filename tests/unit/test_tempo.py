from datetime import UTC, datetime

from votosbr.domain.tempo import TZ_BRASILIA, proxima_execucao


def test_proxima_execucao_no_mesmo_dia_antes_da_hora() -> None:
    agora = datetime(2026, 11, 2, 8, 0, tzinfo=UTC)  # 05h em Brasília
    assert proxima_execucao(agora, 6) == datetime(2026, 11, 2, 6, 0, tzinfo=TZ_BRASILIA)


def test_proxima_execucao_vai_para_o_dia_seguinte_apos_a_hora() -> None:
    agora = datetime(2026, 11, 2, 9, 0, tzinfo=UTC)  # 06h em ponto em Brasília
    assert proxima_execucao(agora, 6) == datetime(2026, 11, 3, 6, 0, tzinfo=TZ_BRASILIA)


def test_proxima_execucao_usa_a_data_de_brasilia() -> None:
    agora = datetime(2026, 11, 3, 1, 0, tzinfo=UTC)  # ainda dia 2, 22h em Brasília
    assert proxima_execucao(agora, 6) == datetime(2026, 11, 3, 6, 0, tzinfo=TZ_BRASILIA)
