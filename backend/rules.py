from datetime import date


def judge(doc: dict) -> tuple[str, str]:
    steps = doc.get("steps") or []
    fry = next((s for s in steps if s.get("name") == "清炒"), None)
    if fry is None:
        return "未放行", "缺少清炒工序"
    temp = float(fry.get("temp_c", 0))
    minutes = float(fry.get("minutes", 0))
    if not 80 <= temp <= 150:
        return "未放行", "清炒温度不在范围内"
    if not 5 <= minutes <= 30:
        return "未放行", "清炒时长不在范围内"
    return "放行", "清炒工序符合炮制要求"


def aux_batch_error(aux: dict | None, today: date) -> str | None:
    """册中点选的批号能否用于开炒。返回 None 表示可用，否则返回拒写原因。"""
    if aux is None:
        return "所选辅料批号不在册中，请重新点选"
    if aux["expires_on"] < today:
        return (
            f"辅料批号已过失效日：{aux['material']} · {aux['lot_no']} · "
            f"失效日 {aux['expires_on'].isoformat()}，不得用于开炒"
        )
    return None


def freeze_aux_batch(aux: dict) -> dict:
    """把册中批号快照进文书正文。冻结后改正册上失效日，不影响已写文书。"""
    return {
        "id": aux["id"],
        "material": aux["material"],
        "lot_no": aux["lot_no"],
        "expires_on": aux["expires_on"].isoformat(),
    }
