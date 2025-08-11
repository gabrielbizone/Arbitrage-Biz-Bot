def net_percent(gross_percent: float, swaps: int, fee_bps_per_swap: float) -> float:
    """Aproximação simples: líquido = bruto - (swaps * fee_bps/100).
    Ex.: fee_bps_per_swap=5 → 0,05% por swap.
    """
    fee_total = swaps * (fee_bps_per_swap / 100.0)
    return gross_percent - fee_total
